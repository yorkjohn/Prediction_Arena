"""Third-pass curation: 50 ADDITIONAL questions (10 per category).

Only the Chinese wording lives here. Every probability / outcome / timestamp /
URL still comes from the audited candidate pools (v3 + third-pass collection).

Selection bar (unchanged): familiar to a Chinese youth audience, outcome not
common knowledge, unambiguous YES definition, probability with discrimination,
no politics / elections / wars / gossip / personal micro-markets / polls.

Usage:  python -B expand_bank_more.py
Writes: seed/candidates_all_v4.json  (merged pool)
        seed/more_picks.json         (market_id -> curated wording)
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V3 = ROOT / "seed" / "candidates_all_v3.json"
MORE = ROOT / "seed" / "more_markets.json"
BANK = ROOT / "seed" / "arena_seed_questions.json"
V4 = ROOT / "seed" / "candidates_all_v4.json"
PICKS = ROOT / "seed" / "more_picks.json"

# market_id -> (category, Chinese question). Only the wording is hand-written.
SELECTION: dict[str, tuple[str, str]] = {
    # ---- business (10) -----------------------------------------------------
    "XPKxLBgQV3uzMGePBcWw": ("business", "2024 年金球奖，《奥本海默》获奖数是否多于《芭比》？"),
    "8b6rdp4x6d": ("business", "2025 金球奖最佳影片得主，是否同时拿下奥斯卡最佳影片？"),
    "dKwBVNmz3hFrRVVbH3kE": ("business", "《怪物猎人：荒野》是否跨平台发售？"),
    "2X6zwNH07zCoSZxm4t8V": ("business", "《星空》发售时 Metacritic 评分是否达到 85 分？"),
    "zlnA9LO85t": ("business", "2026 年 1 月 Xbox 开发者直面会是否公布《上古卷轴 6》？"),
    "jYJM6vOGa3RXMcMFVvoS": ("business", "2024 年 iPhone 销量是否超过 2023 年？"),
    "vN5h8xyuFnBQG3ppEtMw": ("business", "2023 年 iPhone 销量是否超过 2022 年？"),
    "88gAL9tyhs": ("business", "《美人鱼》的中国续集是否在 2025 年上映？"),
    "5fcajtwhf7": ("business", "鲍勃·艾格是否在 2025 年底前卸任迪士尼 CEO？"),
    "h2QQqCQIgZ": ("business", "奥利维亚·罗德里戈是否在 2026 年拿到 Billboard 冠军单曲？"),
    # ---- world (10) --------------------------------------------------------
    "blonK9LG9gO1i0ByBdv0": ("world", "2024 巴黎奥运会，中国是否获得最多金牌？"),
    "52zyUhLhA2": ("world", "2026 年诺贝尔文学奖是否颁给主要用英语写作的作家？"),
    "BoFtzRIFqOqVKkTrdb4Y": ("world", "2024 年诺贝尔文学奖是否颁给用英语写作的作家？"),
    "1tC1H07RZUAJ10jea5Ep": ("world", "萤火虫航天「蓝色幽灵」M1 是否成功软着陆月球？"),
    "Jtv6pGOIRIuC7wJ7tc4H": ("world", "直觉机器 IM-2 任务是否成功软着陆月球？"),
    "g573r5Wyhyf9oTOakSeH": ("world", "「月球-25」探测器是否在 2023 年 7 月底前成功登月？"),
    "QnfvRxxE2umLrPn3IBOq": ("world", "肖恩·怀特是否夺得 2022 冬奥会男子单板滑雪 U 型池金牌？"),
    "dzuCO2pcpu": ("world", "2026 年男子网球大满贯是否由阿尔卡拉斯、辛纳之外的球员夺冠？"),
    "0whMTwd4PBAZ2NVQIWjw": ("world", "温网半决赛，阿尔卡拉斯是否击败梅德韦杰夫？"),
    "PLQuPs66Et": ("world", "新格伦火箭第二次飞行，一级是否成功回收着陆？"),
    # ---- ai (10) -----------------------------------------------------------
    "KmEdGIGKGfNtzBKVGrfd": ("ai", "GPT-4.5 / GPT-5 发布时，GPT-4 是否在 ChatGPT 免费开放？"),
    "IircPSRTj0SF8HiJDjjQ": ("ai", "特斯拉在 11 月 30 日交付日是否交付超过 10 辆 Cybertruck？"),
    "JI1Fr2ionbJ6mnu0jXdD": ("ai", "iPhone 16 各版本是否全部通过 JerryRigEverything 耐久测试？"),
    "su7iy54gs5": ("ai", "2025 年一季度末前，是否有开源模型击败 OpenAI o1？"),
    "5RI2cIg5LC": ("ai", "阿里是否在 2025 年 4 月底前发布 Qwen 3？"),
    "bdyuelwg31": ("ai", "Claude 3.5 Haiku 是否优于 Claude 3 Opus？"),
    "Rl8pq5NgLg": ("ai", "2026 年前是否出现由文字描述生成逼真视频的 AI？"),
    "zSqgAZgE0C": ("ai", "2026 年前 AI 是否生成逼真的动物运动视频？"),
    "NbkTM8IxncCTMqQUE5vr": ("ai", "中国公司是否在 2024 年底前复现 Sora？"),
    "0uCORyyLzc": ("ai", "OpenAI 与谷歌是否都在 2025 年 12 月前发布新一代前沿图像模型？"),
    # ---- esports (10) ------------------------------------------------------
    "37HERhhUvqsLT6c8TpSA": ("esports", "2024 MSI，T1 是否战胜 Team Liquid？"),
    "Xk8vGcjlY0xJmys0NoYr": ("esports", "2024 MSI，T1 是否战胜 G2？"),
    "n7eplgI72ksmnJlxeFQi": ("esports", "Gen.G 是否 3:0 横扫 Cloud9？"),
    "llPRgSYTrQchEH1gTMvU": ("esports", "JDG 是否 3:0 横扫 Golden Guardians？"),
    "YNOksZ9mD7WFdT6lNOqn": ("esports", "DRX 是否在全球总决赛决赛中赢下至少 2 局？"),
    "paq5ty4WvK3OAUuTcT00": ("esports", "T1 对阵 JDG 是否打满 5 局？"),
    "rbKKeQumHtZEJir0rzDN": ("esports", "5 月 10 日，G2 是否战胜 T1？"),
    "M2QsfDDkk0qiPAXi5DCh": ("esports", "5 月 11 日，Fnatic 是否战胜 Team Liquid？"),
    "afHUiFdJWGy092NNCsUf": ("esports", "Cloud9 是否战胜 Fnatic？"),
    "ZyCLrKVxkRNL8vKoXNiP": ("esports", "Cloud9 是否战胜 Bilibili Gaming？"),
    # ---- sports (10) -------------------------------------------------------
    "usLp528Qn9": ("sports", "第 60 届超级碗冠军是否来自国联西区？"),
    "fPt3q0Oo0N335pFRP5rH": ("sports", "2023 超级碗冠军是否也打进 2024 超级碗？"),
    "253577": ("sports", "密歇根大学是否赢得 2024 大学橄榄球全国冠军？"),
    "KXNBAGAME-26NOV04LALSAC-LAL": ("sports", "11/4 NBA，湖人是否战胜国王？"),
    "KXNBAGAME-26NOV04CLEOKC-OKC": ("sports", "11/4 NBA，雷霆是否战胜骑士？"),
    "RzgZnOn220": ("sports", "第 60 届超级碗是否刷新美国电视收视纪录？"),
    "NcP9AdAPcA": ("sports", "梅西是否第二次捧起世界杯冠军？"),
    "i5UrJ7f6sY0HyJzUShc8": ("sports", "当季 NBA 常规赛 MVP 与总决赛 MVP 是否为同一人？"),
    "OIu0nnzPhl": ("sports", "亚历山大是否在 NBA 总决赛第 5 场得分 35 分以上？"),
    "KXNBAGAME-26NOV04MIALAC-LAC": ("sports", "11/4 NBA，快船是否战胜热火？"),
}


def clean_en(text: str) -> str:
    """Drop collection-only prefixes such as [SHORT FUSE] / [M200 subsidy]."""
    return re.sub(r"^\[[^\]]*\]\s*", "", (text or "").strip()).strip()


def main() -> int:
    old = json.loads(V3.read_text(encoding="utf-8"))["markets"]
    new = json.loads(MORE.read_text(encoding="utf-8"))["markets"]
    merged: dict[str, dict] = {m["market_id"]: m for m in old}
    for m in new:
        merged.setdefault(m["market_id"], m)
    V4.write_text(json.dumps(
        {"count": len(merged), "markets": list(merged.values())},
        ensure_ascii=False, indent=2,
    ), encoding="utf-8")

    used = {
        q.get("source_market_id")
        for q in json.loads(BANK.read_text(encoding="utf-8"))["questions"]
        if q.get("source_market_id")
    }
    overlap = [mid for mid in SELECTION if mid in used]
    if overlap:
        raise RuntimeError(f"picks duplicate existing bank questions: {overlap}")

    picks = {}
    for mid, (cat, zh) in SELECTION.items():
        m = merged.get(mid)
        if m is None:
            raise RuntimeError(f"selected market missing from merged pool: {mid}")
        picks[mid] = {
            "cat": cat,
            "title_zh": zh,
            "title_en": clean_en(m["question_en"]),
        }
    PICKS.write_text(json.dumps(picks, ensure_ascii=False, indent=2), encoding="utf-8")

    cats = Counter(v["cat"] for v in picks.values())
    outcomes = Counter(merged[mid]["outcome"] for mid in picks)
    probs = [merged[mid]["probability"] for mid in picks]
    print("=" * 66)
    print(f"  merged pool  : {len(old)} + {len(new)} -> {len(merged)} unique  ({V4.name})")
    print(f"  new picks    : {len(picks)}  {dict(sorted(cats.items()))}")
    print(f"  outcome      : YES {outcomes.get(1,0)} / NO {outcomes.get(0,0)}")
    print(f"  probability  : {min(probs):.3f} .. {max(probs):.3f}")
    print(f"  wording file : {PICKS.name}")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
