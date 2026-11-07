"""Export the question bank as a human-review table (plan section 3.5).

Output (in the game/ project root, easy to hand to a reviewer):
  题目审核表.csv    UTF-8 BOM, opens cleanly in Excel
  题目审核表.xlsx   frozen header, auto-filter, wrapped text, blank review columns

Every value comes from the generated question bank. Nothing is translated by
guesswork here — the Chinese wording is the wording that ships in the game.

Usage:  python export_review_table.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BANK = ROOT / "seed" / "arena_seed_questions.json"
OUT_CSV = ROOT.parent / "题目审核表.csv"
OUT_XLSX = ROOT.parent / "题目审核表_150题.xlsx"

CAT_ZH = {
    "sports": "体育", "esports": "电竞", "ai": "AI 与科技",
    "business": "商业与生活", "world": "国际与社会",
}

SOURCE_ZH = {
    "Polymarket": "Polymarket",
    "Manifold": "Manifold",
    "Kalshi": "Kalshi",
    "football-data.co.uk (Betfair Exchange)": "Betfair 交易所（football-data.co.uk 免费 CSV）",
}

HEADERS = [
    "编号", "类型", "类别", "中文题目", "YES 定义", "中文背景",
    "真实结果", "参考概率", "概率来源", "快照口径 / 时间", "来源链接", "许可状态",
    "观众熟悉度(待填)", "结果已知风险(待填)", "人工结论(通过/备用/淘汰)", "淘汰原因 / 备注",
]


def snapshot(q: dict) -> str:
    method = q.get("benchmark_snapshot_method")
    t = q.get("benchmark_snapshot_time")
    if method:
        return f"{method}；参考时间 {t}"
    if q.get("benchmark_source") == "Kalshi":
        return f"前一交易日收盘价；市场关闭 {t}"
    if q.get("benchmark_source") == "football-data.co.uk (Betfair Exchange)":
        return f"赛前 pre-closing 赔率；比赛日 {t}"
    return f"结算前 ≥1 小时最后成交价；{t}"


def build_rows() -> list[list]:
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    rows = []
    for q in bank["questions"]:
        warmup = q["mode"] == "warmup"
        p = q.get("benchmark_probability")
        rows.append([
            q["id"],
            "练手（不计分）" if warmup else "正式",
            "—（练手）" if warmup else CAT_ZH.get(q["category"], q["category"]),
            q["title_zh"],
            q["yes_zh"],
            q["context_zh"],
            "是（YES）" if q["outcome"] == 1 else "否（NO）",
            "—" if p is None else f"{round(float(p) * 100, 1)}%",
            "教学示例" if warmup else SOURCE_ZH.get(q.get("benchmark_source"), q.get("benchmark_source") or ""),
            "—" if warmup else snapshot(q),
            q.get("benchmark_url") or "—",
            q.get("license_status") or "—",
            "", "", "", "",
        ])
    return rows


def write_csv(rows: list[list]) -> None:
    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        w.writerows(rows)


def write_xlsx(rows: list[list]) -> bool:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        return False

    wb = Workbook()
    ws = wb.active
    ws.title = "题目审核"
    ws.append(HEADERS)
    for r in rows:
        ws.append(r)

    head_fill = PatternFill("solid", fgColor="2F5597")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = head_fill
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 32

    widths = [8, 14, 14, 46, 30, 46, 11, 11, 26, 40, 46, 22, 16, 16, 22, 30]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    fill_review = PatternFill("solid", fgColor="FFF2CC")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)
        for idx in (13, 14, 15, 16):  # blank columns for the reviewer
            row[idx - 1].fill = fill_review

    ws.freeze_panes = "D2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(OUT_XLSX)
    return True


def main() -> int:
    rows = build_rows()
    write_csv(rows)
    has_xlsx = write_xlsx(rows)
    print(f"  {len(rows)} questions -> {OUT_CSV.name}")
    if has_xlsx:
        print(f"  {len(rows)} questions -> {OUT_XLSX.name}")
    else:
        print("  openpyxl unavailable; CSV only")
    print("  blank columns: 观众熟悉度 / 结果已知风险 / 人工结论 / 淘汰原因")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
