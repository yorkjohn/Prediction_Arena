"""Build questions from football-data.co.uk's FREE Premier League CSV.

Source: https://www.football-data.co.uk/mmz4281/2425/E0.csv  (2024/25, 380 matches)
  - BFEH / BFED / BFEA = Betfair EXCHANGE home/draw/away decimal odds
    (BFH/BFD/BFA are the regular Betfair bookmaker — intentionally NOT used)
  - FTR = H / D / A = audited full-time result
  - Odds are PRE-CLOSING, collected Friday afternoon for weekend fixtures and
    Tuesday afternoon for midweek fixtures (source notes.txt) -> genuinely pre-match

Conversion follows plan section 5.3:
  q_i = 1 / O_i ;  p_home = q_home / (q_home + q_draw + q_away)
  YES = home wins (FTR == 'H'); draw or away win both count as NO.

No invented numbers: every probability and outcome is computed from the CSV.
Only markets with a familiar team, a discriminating price and a balanced
YES/NO mix are flagged `selected` for the game bank.

Usage:  python collect_football_data.py
Output: seed/football_markets.json + seed/football_review.csv
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "seed" / "E0_2425.csv"
OUT = ROOT / "seed" / "football_markets.json"
REVIEW = ROOT / "seed" / "football_review.csv"
SOURCE_URL = "https://www.football-data.co.uk/mmz4281/2425/E0.csv"

TEAM_ZH = {
    "Man United": "曼联", "Man City": "曼城", "Arsenal": "阿森纳",
    "Liverpool": "利物浦", "Chelsea": "切尔西", "Tottenham": "热刺",
    "Newcastle": "纽卡斯尔", "Aston Villa": "阿斯顿维拉",
    "West Ham": "西汉姆联", "Brighton": "布莱顿", "Everton": "埃弗顿",
    "Wolves": "狼队", "Crystal Palace": "水晶宫", "Fulham": "富勒姆",
    "Brentford": "布伦特福德", "Bournemouth": "伯恩茅斯",
    "Nott'm Forest": "诺丁汉森林", "Nottingham Forest": "诺丁汉森林",
    "Leicester": "莱斯特城", "Southampton": "南安普顿",
    "Ipswich": "伊普斯维奇", "Leeds": "利兹联",
}
FAMILIAR = {
    "Man United", "Man City", "Arsenal", "Liverpool", "Chelsea", "Tottenham",
    "Newcastle", "Aston Villa", "West Ham", "Everton", "Brighton", "Wolves",
}
MIN_P, MAX_P = 0.15, 0.85
PICK_PER_OUTCOME = 5


def zh(team: str) -> str:
    return TEAM_ZH.get(team, team)


def main() -> int:
    if not CSV_PATH.exists():
        print(f"ERROR: CSV missing -> {CSV_PATH}")
        return 1
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8-sig", errors="replace")))
    print(f"== football-data.co.uk collector: {len(rows)} matches ==", flush=True)

    markets = []
    for i, r in enumerate(rows, start=2):  # CSV line number (header = line 1)
        try:
            oh, od, oa = float(r["BFEH"]), float(r["BFED"]), float(r["BFEA"])
            ftr = r["FTR"].strip().upper()
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if min(oh, od, oa) <= 1.0 or ftr not in ("H", "D", "A"):
            continue
        qh, qd, qa = 1 / oh, 1 / od, 1 / oa
        total = qh + qd + qa
        p_home = qh / total
        if not MIN_P <= p_home <= MAX_P:
            continue

        home, away = r["HomeTeam"].strip(), r["AwayTeam"].strip()
        outcome = 1 if ftr == "H" else 0
        date = r["Date"].strip()
        familiar = home in FAMILIAR or away in FAMILIAR
        hz, az = zh(home), zh(away)
        markets.append({
            "source_platform": "football-data.co.uk (Betfair Exchange)",
            "category": "sports",
            "market_id": f"E0-2425-L{i}",
            "csv_line": i,
            "match_date": date,
            "home_team": home, "away_team": away,
            "home_zh": hz, "away_zh": az,
            "title_zh": f"2024/25 英超，{hz}主场对阵{az}，{hz}是否获胜？",
            "title_en": f"Will {home} beat {away} at home? (Premier League 2024/25)",
            "context_zh": "赛前 Betfair Exchange 主胜 / 平局 / 客胜赔率换算的市场概率。注意平局或客队获胜都算 NO。",
            "context_en": "Pre-match Betfair Exchange 1X2 odds converted to a home-win probability. A draw or an away win both count as NO.",
            "yes_zh": f"{hz}赢下该场比赛", "yes_en": f"{home} win the match",
            "probability": round(p_home, 4),
            "outcome": outcome,
            "raw_odds": {"home": oh, "draw": od, "away": oa},
            "implied_unnormalised": round(qh, 4),
            "overround": round(total, 4),
            "full_time_result": ftr,
            "score": f"{r.get('FTHG', '')}-{r.get('FTAG', '')}",
            "snapshot_method": "pre-closing Betfair Exchange 1X2 odds (Fri afternoon / Tue afternoon), normalised",
            "source_url": SOURCE_URL,
            "license_status": "NEEDS_MANUAL_REVIEW",
            "familiar": familiar,
            "selected": False,
        })

    print(f"  candidates with usable Betfair Exchange odds: {len(markets)}", flush=True)

    # Spread the chosen prices across the whole range. A bank where every
    # benchmark is ~0.50 teaches nothing about calibration or Brier scoring.
    TARGETS = [0.22, 0.38, 0.52, 0.68, 0.82]
    used_dates: set[str] = set()
    for y in (1, 0):
        chosen = []
        for target in TARGETS:
            pool = [m for m in markets
                    if m["outcome"] == y and m["familiar"]
                    and not m["selected"]
                    and m["match_date"] not in used_dates]
            if not pool:
                continue
            pick = min(pool, key=lambda m: (abs(m["probability"] - target), m["csv_line"]))
            pick["selected"] = True
            used_dates.add(pick["match_date"])
            chosen.append(pick)
        print(f"  selected outcome={y}: {len(chosen)} "
              f"(prices {[round(m['probability'], 2) for m in chosen]})", flush=True)

    OUT.write_text(json.dumps({
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE_URL,
        "licence_note": "Site states 'My data is free'; no formal redistribution/ attribution clause found. Recommend crediting the source publicly.",
        "conversion": "q=1/O; p_home=q_home/(q_home+q_draw+q_away); YES iff FTR=='H'",
        "matches_in_csv": len(rows),
        "markets": markets,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    with REVIEW.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["CSV行", "比赛日期", "主队", "客队", "赛前主胜概率", "原始赔率H/D/A",
                    "归一化前qH", "超额率", "全场结果", "比分", "YES?", "入选", "快照口径", "来源"])
        for m in markets:
            w.writerow([m["csv_line"], m["match_date"], m["home_team"], m["away_team"],
                        m["probability"], "/".join(str(m["raw_odds"][k]) for k in ("home", "draw", "away")),
                        m["implied_unnormalised"], m["overround"], m["full_time_result"],
                        m["score"], m["outcome"], "YES" if m["selected"] else "",
                        m["snapshot_method"], SOURCE_URL])

    sel = [m for m in markets if m["selected"]]
    print("=" * 68, flush=True)
    print(f"  wrote {len(markets)} markets -> {OUT.name}", flush=True)
    print(f"  selected {len(sel)} (outcome {dict(Counter(m['outcome'] for m in sel))})", flush=True)
    print(f"  review: {REVIEW.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
