"""Collect REAL pre-event prices from Kalshi's public read-only API.

Endpoint: https://api.elections.kalshi.com/trade-api/v2/markets
  - status=settled + series_ticker -> resolved binary markets
  - result = yes/no -> audited settlement
  - previous_price_dollars -> official previous-day closing price (the pre-event
    snapshot used here; sports markets stay open until after the game, so their
    "1h before close" candle is NOT a genuine pre-match price)
  - rules_primary -> full settlement rule, used to write clear Chinese wording

Only sports / weather / non-policy markets are kept. Politics, elections,
regulators and wars are excluded (same rule as the other collectors).

Network: local proxy 127.0.0.1:10819.
Usage:  python -u collect_kalshi.py
Output: seed/kalshi_markets.json + seed/kalshi_review.csv
"""
from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "seed" / "kalshi_markets.json"
REVIEW = ROOT / "seed" / "kalshi_review.csv"
PROXY = "http://127.0.0.1:10819"
BASE = "https://api.elections.kalshi.com/trade-api/v2"

OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
)
OPENER.addheaders = [("User-Agent", "PredictionArenaResearch/5.0")]

SERIES: dict[str, list[str]] = {
    "sports": [
        "KXNBAGAME", "KXNHLGAME", "KXMLBGAME", "KXNFLGAME", "KXEPLGAME",
        "KXNCAABGAME", "KXUCLGAME", "KXLALIGAGAME", "KXSERIEAGAME",
    ],
    "world": [
        "KXHIGHNY", "KXHIGHLAX", "KXHIGHCHI", "KXLOWNY", "KXHIGHATL",
        "KXHIGHDEN", "KXSNOWNY",
    ],
    "business": [
        "KXBTCD", "KXETHD", "KXSP500D", "KXNASDAQD",
    ],
}

BLOCK = [
    "election", "president", "trump", "biden", "congress", "senate", "parliament",
    "prime minister", "government", "minister", "politic", "war ", "ukraine",
    "russia", "israel", "gaza", "iran", "china", "taiwan", "nato", "tariff",
    "sanction", "fed ", "rate cut", "inflation", "recession", "shutdown",
    "immigration", "lawsuit", "indict", "convict", "assassin", "death",
]

MIN_P, MAX_P = 0.10, 0.90
MAX_CALLS = 90
CALLS = {"n": 0}


def fetch(url: str, timeout: int = 25):
    if CALLS["n"] >= MAX_CALLS:
        raise RuntimeError("budget exhausted")
    CALLS["n"] += 1
    with OPENER.open(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def category_for(m: dict) -> str | None:
    text = " " + " ".join(str(m.get(k) or "") for k in
                          ("title", "rules_primary", "event_ticker")).lower() + " "
    if any(b in text for b in BLOCK):
        return None
    return None  # replaced by the explicit series map below


def main() -> int:
    print("== Kalshi real-price collector ==", flush=True)
    rows, seen = [], set()
    for topic, series_list in SERIES.items():
        for series in series_list:
            url = f"{BASE}/markets?" + urllib.parse.urlencode({
                "status": "settled", "series_ticker": series, "limit": 100,
            })
            try:
                data = fetch(url)
            except Exception as e:
                print(f"  [skip] {series}: {e}", flush=True)
                continue
            markets = data.get("markets", []) if isinstance(data, dict) else []
            kept = 0
            for m in markets:
                if m.get("result") not in ("yes", "no"):
                    continue
                rules = (m.get("rules_primary") or "").strip()
                if not rules or m.get("ticker") in seen:
                    continue
                if any(b in (" " + rules.lower() + " ") for b in BLOCK):
                    continue
                try:
                    p = float(m.get("previous_price_dollars") or 0)
                except (TypeError, ValueError):
                    continue
                if not MIN_P <= p <= MAX_P:
                    continue
                seen.add(m["ticker"])
                kept += 1
                rows.append({
                    "source_platform": "Kalshi",
                    "category": topic,
                    "market_id": m["ticker"],
                    "slug": m.get("event_ticker"),
                    "question_en": (m.get("title") or "").strip(),
                    "rules_primary": rules,
                    "end_date": m.get("close_time"),
                    "market_url": f"https://kalshi.com/markets/{series.lower()}",
                    "source_api": f"{BASE}/markets/{m['ticker']}",
                    "license_status": "NEEDS_MANUAL_REVIEW",
                    "probability": round(p, 4),
                    "snapshot_unix": None,
                    "snapshot_time": m.get("close_time"),
                    "snapshot_method": "previous_day_close",
                    "outcome": 1 if m["result"] == "yes" else 0,
                    "asset_id": m["ticker"],
                    "series_ticker": series,
                })
            print(f"  {topic:9s} {series:16s} {len(markets):3d} markets -> {kept:2d} kept",
                  flush=True)

    OUT.write_text(json.dumps({
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Kalshi public trade-api v2",
        "snapshot_rule": "official previous_price_dollars (previous-day close); "
                         "close_time is recorded as the reference time, not the exact snapshot",
        "markets": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    with REVIEW.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["类别", "系列", "ticker", "原题", "结算规则", "赛前一日概率",
                    "快照口径", "结算结果", "市场链接", "来源API", "许可状态", "人工结论"])
        for r in rows:
            w.writerow([r["category"], r["series_ticker"], r["market_id"],
                        r["question_en"], r["rules_primary"], r["probability"],
                        r["snapshot_method"], "YES" if r["outcome"] else "NO",
                        r["market_url"], r["source_api"], r["license_status"],
                        "待人工筛选(§3.4)"])

    print("=" * 68, flush=True)
    print(f"  wrote {len(rows)} -> {OUT.name}", flush=True)
    print("  by category:", dict(Counter(r["category"] for r in rows)), flush=True)
    print("  by outcome :", dict(Counter(r["outcome"] for r in rows)), flush=True)
    print("  calls:", CALLS["n"], flush=True)
    print("  NOTE: probability = previous_price_dollars (no exact timestamp).", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
