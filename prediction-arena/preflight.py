"""Prediction Arena - on-site pre-flight check.

Run BEFORE the event, and AGAIN after changing Wi-Fi / starting a hotspot:

    python preflight.py
    start_arena.bat check        (same report, from the launcher)

Strictly read-only: it never starts the server, never writes the database and
never changes firewall rules. It prints what is wrong plus the exact command
that fixes it. A non-zero exit code means something will block the event.
"""
from __future__ import annotations

import hashlib
import json
import re
import socket
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent
SEED = ROOT / "seed" / "arena_seed_questions.json"
STATIC = ROOT / "static"
DB = ROOT / "arena.db"
PORT = 5000
HOTSPOT_IP = "192.168.137.1"
CATEGORIES = ["sports", "esports", "ai", "business", "world"]
REAL_PER_ROUND = 5

REPORT: list[tuple[str, str, str]] = []
NEXT: list[str] = []
MARK = {"ok": "[OK]", "warn": "[!] ", "fail": "[XX]", "info": "[--]"}


def add(level: str, label: str, detail: str = "") -> None:
    REPORT.append((level, label, detail))
    print(MARK[level] + " " + label)
    if detail:
        for line in detail.splitlines():
            print("      " + line)


def opener():
    """Ignore any injected HTTP proxy - this is a purely local check."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


# -------------------------------------------------------------------------- deps

def check_deps() -> None:
    missing = []
    for mod, pkg in [("flask", "Flask"), ("segno", "segno"),
                     ("PIL", "Pillow"), ("openpyxl", "openpyxl")]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        add("fail", "Python 依赖",
            "缺少 " + ", ".join(missing) + "  →  pip install -r requirements.txt")
        NEXT.append("安装依赖：pip install -r requirements.txt")
    else:
        add("ok", "Python 依赖", "Flask / segno / Pillow / openpyxl 齐备")


# -------------------------------------------------------------------------- bank

def check_bank():
    if not SEED.exists():
        add("fail", "题库种子", f"找不到 {SEED}")
        NEXT.append("恢复题库种子：python build_question_bank.py")
        return None
    try:
        seed = json.loads(SEED.read_text(encoding="utf-8"))
        qs = seed.get("questions", [])
    except (OSError, ValueError) as exc:
        add("fail", "题库种子", f"JSON 无法解析：{exc}")
        return None

    real = [q for q in qs if q.get("mode") == "real"]
    warm = [q for q in qs if q.get("mode") == "warmup"]
    cats = Counter(q.get("category") for q in real)
    problems = []
    if len(warm) != 3:
        problems.append(f"练手题 {len(warm)} 道（应为 3）")
    for cat in CATEGORIES:
        if cats.get(cat, 0) < REAL_PER_ROUND:
            problems.append(f"{cat} 仅 {cats.get(cat, 0)} 道，选该类别会报错")
    if any(q.get("outcome") not in (0, 1) for q in qs):
        problems.append("存在非 0/1 的 outcome")
    if any(q.get("benchmark_probability") is None for q in real):
        problems.append("有正式题缺参考概率")
    for field in ("title_zh", "title_en", "yes_zh"):
        if any(not q.get(field) for q in real):
            problems.append(f"字段 {field} 存在空值")

    digest = hashlib.sha256(SEED.read_bytes()).hexdigest()[:12]
    ids = {q["id"] for q in qs}
    balance = Counter(q.get("outcome") for q in real)
    summary = (f"{len(real)} 正式 + {len(warm)} 练手 | "
               + " / ".join(f"{c}:{cats.get(c, 0)}" for c in CATEGORIES)
               + f" | YES {balance.get(1, 0)} / NO {balance.get(0, 0)}"
               + f" | 指纹 {digest}")
    if problems:
        add("fail", "题库种子", summary + "\n问题：" + "；".join(problems))
        NEXT.append("修题库：python validate_questions.py 查看明细")
    else:
        add("ok", "题库种子", summary)
    return ids


# -------------------------------------------------------------------------- db

def check_db(seed_ids) -> None:
    if not DB.exists():
        add("info", "运行数据库", "arena.db 尚未生成；首次启动服务会自动导入题库")
        return
    try:
        conn = sqlite3.connect(str(DB), timeout=5)
        ids = {r[0] for r in conn.execute("SELECT id FROM questions")}
        preds = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        conn.close()
    except sqlite3.Error as exc:
        add("fail", "运行数据库", f"无法读取：{exc}")
        return

    if seed_ids and ids != seed_ids:
        add("warn", "运行数据库与题库不一致",
            f"库内 {len(ids)} 题 / 种子 {len(seed_ids)} 题。"
            "换题库后必须停服务 → 删 arena.db → 重启，否则仍用旧题。")
        NEXT.append("同步题库：停服务 → 删 arena.db → 重启服务")
    else:
        add("ok", "运行数据库", f"已导入 {len(ids)} 题，与种子一致")
    if preds:
        add("info", "已有成绩", f"{preds} 条提交记录；要清空现场成绩，停服务后删除 arena.db")


# -------------------------------------------------------------------------- network

def local_ips():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    primary = "127.0.0.1"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("223.5.5.5", 80))
        primary = s.getsockname()[0]
        ips.add(primary)
    except OSError:
        pass
    finally:
        s.close()
    usable = {ip for ip in ips
              if not ip.startswith("127.") and not ip.startswith("169.254.")}
    return usable, primary


def check_network(ips, primary) -> bool:
    hotspot_on = HOTSPOT_IP in ips
    add("ok", "本机局域网地址",
        f"主地址 {primary} | 全部可用 {', '.join(sorted(ips)) or '无'}")
    add("info" if not hotspot_on else "ok", "笔记本移动热点",
        "已开启（192.168.137.1 可用）" if hotspot_on
        else "当前未开启 → 现场若要使用热点版二维码，请先开热点并再跑一次本体检")
    add("info", "手机入口",
        f"http://{primary}:{PORT}/   看板 http://127.0.0.1:{PORT}/dashboard")
    return hotspot_on


# -------------------------------------------------------------------------- service

def check_service() -> bool:
    op = opener()
    try:
        with op.open(f"http://127.0.0.1:{PORT}/api/health", timeout=2) as r:
            data = json.loads(r.read().decode("utf-8"))
        add("ok", "服务状态", f"运行中 · real_questions={data.get('real_questions')}")
        try:
            op.open(f"http://127.0.0.1:{PORT}/seed/arena_seed_questions.json", timeout=2)
            add("fail", "答案文件隔离", "含结果的题库文件竟可经 HTTP 访问！")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                add("ok", "答案文件隔离", "题库文件不可经 HTTP 访问（404）")
            else:
                add("warn", "答案文件隔离", f"返回 {exc.code}，请人工确认")
        except Exception:
            add("warn", "答案文件隔离", "无法确认，服务异常")
        return True
    except Exception:
        add("info", "服务状态", "未运行（体检不依赖它）→ 现场双击 start_arena.bat 启动")
        NEXT.append("启动服务：双击 start_arena.bat，别关那个窗口")
        return False


# -------------------------------------------------------------------------- qr codes

def check_qrcodes(ips, hotspot_on) -> None:
    try:
        import numpy as np
        import zxingcpp
        from PIL import Image
    except ImportError:
        add("warn", "二维码核对", "未装 zxing-cpp，跳过解码核对 → pip install zxing-cpp")
        return

    files = sorted(ROOT.glob("qrcode*.png"))
    if not files:
        add("warn", "二维码核对", "没有 qrcode*.png → python make_qrcode.py --print")
        NEXT.append("生成二维码：python make_qrcode.py --print")
        return

    matched, hotspot, stale = [], [], []
    for p in files:
        try:
            im = Image.open(p).convert("RGB")
            hits = zxingcpp.read_barcodes(np.asarray(im))
        except Exception as exc:
            add("warn", f"二维码 {p.name}", f"无法解码：{exc}")
            continue
        if not hits:
            add("warn", f"二维码 {p.name}", "未识别到二维码")
            continue
        url = hits[0].text
        host = urlparse(url).hostname
        if host in ips:
            matched.append((p.name, url))
        elif host == HOTSPOT_IP:
            hotspot.append((p.name, url))
        else:
            stale.append((p.name, url))

    for name, url in matched:
        add("ok", f"二维码 {name}", f"→ {url}   【现在可扫】")
    for name, url in hotspot:
        add("info", f"二维码 {name}", f"→ {url}   【需先开热点，现在扫不通】")
    for name, url in stale:
        add("warn", f"二维码 {name}", f"→ {url}   【已过期，换网络后作废】")

    if not matched:
        if hotspot:
            add("warn", "二维码就绪度",
                "当前网络没有可扫的码；只有热点版。开热点 → 再跑本体检可确认。")
        else:
            add("warn", "二维码就绪度", "没有任何与当前 IP 匹配的二维码")
        NEXT.append("连好现场网络后重跑：python make_qrcode.py --print")
    else:
        add("ok", "二维码就绪度", f"{len(matched)} 张与当前网络匹配，可直接扫")


# -------------------------------------------------------------------------- firewall

PS_FIREWALL = r'''
$ErrorActionPreference = "SilentlyContinue"
$rules = Get-NetFirewallRule -Direction Inbound -Action Allow -Enabled True |
         Where-Object { $_.DisplayName -match 'python|Python|5000|Arena' }
$out = foreach ($r in $rules) {
  $a = $r | Get-NetFirewallApplicationFilter
  $p = $r | Get-NetFirewallPortFilter
  [PSCustomObject]@{
    Name = [string]$r.DisplayName
    Program = [string]$a.Program
    Protocol = [string]$p.Protocol
    LocalPort = [string]($p.LocalPort -join ',')
    Profile = [string]$r.Profile
  }
}
if ($out) { $out | ConvertTo-Json -Compress -Depth 3 } else { "[]" }
'''


def check_firewall() -> None:
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_FIREWALL],
            capture_output=True, text=True, timeout=40,
            encoding="utf-8", errors="replace",
        )
        raw = (proc.stdout or "").strip()
        start_candidates = [i for i in (raw.find("["), raw.find("{")) if i >= 0]
        data = json.loads(raw[min(start_candidates):]) if start_candidates else []
        if isinstance(data, dict):
            data = [data]
    except Exception as exc:
        add("warn", "防火墙", f"自动查询失败（{exc}）；请用手机实测能否访问 5000 端口")
        return

    exe = str(sys.executable).lower()
    port_ok = any("5000" in (r.get("LocalPort") or "")
                  and (r.get("Protocol") or "").upper() == "TCP" for r in data)
    prog_ok = any((r.get("Program") or "").lower() == exe for r in data)

    if port_ok:
        add("ok", "防火墙", "存在 TCP 5000 入站放行规则（按端口，最稳）")
    elif prog_ok:
        add("ok", "防火墙", "当前 python.exe 已在入站放行名单")
    else:
        add("warn", "防火墙",
            "当前 Python 不在放行名单，外部手机很可能连不上！\n"
            f"当前解释器：{sys.executable}\n"
            "一次性修复：右键 allow_firewall.bat → 以管理员身份运行\n"
            '或管理员命令行：netsh advfirewall firewall add rule '
            'name="Prediction Arena TCP 5000" dir=in action=allow '
            'protocol=TCP localport=5000 profile=any')
        NEXT.append("放行防火墙：以管理员身份运行 allow_firewall.bat（只需一次）")


# -------------------------------------------------------------------------- static

def check_static() -> None:
    external = []
    for f in STATIC.iterdir():
        if f.is_file() and f.suffix in (".html", ".js", ".css"):
            text = f.read_text(encoding="utf-8", errors="replace")
            for url in re.findall(r'https?://[^\s"\'<>)]+', text):
                if "127.0.0.1" not in url and "localhost" not in url:
                    external.append(f"{f.name}: {url}")
    if external:
        add("fail", "静态页外部依赖",
            "发现外链，断网会白屏：" + "；".join(external[:3]))
    else:
        add("ok", "静态页外部依赖", "无 CDN / 外部 API，纯本地资源，断网也能玩")

    if (STATIC / "arena_seed_questions.json").exists():
        add("fail", "答案文件位置", "含结果的题库文件出现在 static/ 目录！")
    else:
        add("ok", "答案文件位置", "题库种子在 seed/，不在静态目录下")


# -------------------------------------------------------------------------- main

def main() -> int:
    print("=" * 70)
    print("  Prediction Arena · 现场体检   " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("  只读检查：不启动服务、不改数据库、不改防火墙")
    print("=" * 70)

    check_deps()
    seed_ids = check_bank()
    check_db(seed_ids)
    ips, primary = local_ips()
    hotspot_on = check_network(ips, primary)
    check_service()
    check_qrcodes(ips, hotspot_on)
    check_firewall()
    check_static()

    fails = sum(1 for lv, _, _ in REPORT if lv == "fail")
    warns = sum(1 for lv, _, _ in REPORT if lv == "warn")
    print("-" * 70)
    print(f"  结论：{fails} 项阻断（FAIL），{warns} 项需留意（WARN）")
    if NEXT:
        print("  建议按序处理：")
        for i, item in enumerate(dict.fromkeys(NEXT), 1):
            print(f"    {i}. {item}")
    print("=" * 70)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
