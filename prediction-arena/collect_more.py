"""Third-pass collection: find MORE questions beyond the 100-question bank.

Reuses collect_expansion.py's proxy/fetch/snapshot/clean machinery, but with
fresh search terms, a larger per-term allowance and its own output files so
earlier collection artefacts are never overwritten.

Already-used markets (final bank AND every prior candidate pool) are skipped.
No invented numbers. Politics, elections, wars, gossip and personal markets
are excluded by collect_expansion.BLOCK.

Network: local proxy 127.0.0.1:10819.
Usage:  python -u collect_more.py
Output: seed/more_markets.json + seed/more_review.csv
"""
from __future__ import annotations

import csv
import json
import urllib.parse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import collect_expansion as ce

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "seed" / "more_markets.json"
REVIEW = ROOT / "seed" / "more_review.csv"
POOLS = [ROOT / "seed" / f"candidates_all{v}.json" for v in ("", "_v2", "_v3")]

ce.MAX_CALLS = 620
ce.PER_TERM = 10
SEARCH_LIMIT = 50
MIN_P, MAX_P = 0.12, 0.88

QUERIES = {
    "esports": [
        "MSI 2024", "LCK final", "LPL playoffs", "Worlds final game",
        "Dota The International winner", "CS2 Major champion",
        "Valorant Masters", "Valorant Champions winner", "ESL One",
        "esports world cup", "LoL Worlds MVP", "T1 vs Gen.G",
        "Bilibili Gaming", "KT Rolster", "G2 vs T1",
    ],
    "business": [
        "box office opening weekend", "highest grossing movie", "Grammy award",
        "Emmy award", "Golden Globe", "Nintendo Switch 2", "PlayStation 6",
        "Xbox", "Steam concurrent players", "iPhone sales", "Tesla delivery",
        "SpaceX Starship", "Falcon 9 launch", "Apple Vision Pro app",
        "Netflix subscriber", "Spotify Wrapped", "video game sales",
        "product launch date", "Disney票房", "movie sequel",
    ],
    "world": [
        "Olympics 2026", "Winter Olympics medal", "World Cup 2022 winner",
        "Nobel Prize Chemistry", "Nobel Prize Literature", "record temperature",
        "hurricane landfall", "solar eclipse", "asteroid mission", "Moon landing",
        "Mars mission", "Tour de France winner", "Formula 1 champion",
        "Wimbledon winner", "US Open tennis", "Super Bowl halftime",
        "FIFA ranking", "global temperature 2025", "El Nino", "volcano eruption",
    ],
    "ai": [
        "Gemini release", "Claude 3.5", "Llama 3", "Mistral model", "o3 release",
        "AI video model", "Sora public", "Anthropic valuation", "AI agent launch",
        "GPT-4 Turbo", "robotics demo", "humanoid robot", "AI benchmark score",
        "DeepSeek V3", "Qwen model", "image generation model", "AI coding",
    ],
    "sports": [
        "NBA Finals MVP", "Champions League final", "Super Bowl winner",
        "World Series", "Premier League top four", "F1 race winner",
        "Tennis Grand Slam", "UFC fight", "MLB home run", "NHL Stanley Cup",
    ],
}


def already_seen() -> set[str]:
    seen = ce.used_ids()
    for p in POOLS:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            seen |= {m["market_id"] for m in data.get("markets", [])}
    return seen


def main() -> int:
    print("== third-pass collector (more questions) ==", flush=True)
    seen = already_seen()
    print(f"  skipping {len(seen)} already-known markets", flush=True)
    out = []
    for topic, terms in QUERIES.items():
        for term in terms:
            if ce.CALLS["n"] >= ce.MAX_CALLS:
                print("  request budget reached", flush=True)
                break
            url = f"{ce.MF_SEARCH}?" + urllib.parse.urlencode(
                {"term": term, "filter": "resolved", "limit": SEARCH_LIMIT}
            )
            try:
                rows = ce.fetch(url)
            except Exception as exc:
                print(f"  [skip] {term}: {exc}", flush=True)
                continue
            if not isinstance(rows, list):
                continue
            taken = kept = 0
            for m in rows:
                if taken >= ce.PER_TERM or ce.CALLS["n"] >= ce.MAX_CALLS:
                    break
                if m.get("outcomeType") != "BINARY" or not m.get("isResolved"):
                    continue
                if m.get("resolution") not in ("YES", "NO"):
                    continue
                q = (m.get("question") or "").strip()
                if not q or len(q) < 18 or not ce.clean(q) or m.get("id") in seen:
                    continue
                seen.add(m["id"])
                taken += 1
                snap = ce.snapshot(m)
                if not snap or not MIN_P <= snap["probability"] <= MAX_P:
                    continue
                kept += 1
                out.append({
                    "source_platform": "Manifold", "category": topic,
                    "market_id": m["id"], "slug": m.get("slug"),
                    "question_en": q,
                    "end_date": datetime.fromtimestamp(
                        m["closeTime"] / 1000, timezone.utc
                    ).isoformat(timespec="seconds"),
                    "market_url": m.get("url") or f"https://manifold.markets/market/{m.get('slug')}",
                    "source_api": f"https://api.manifold.markets/v0/market/{m['id']}",
                    "license_status": "NEEDS_MANUAL_REVIEW", **snap,
                    "query_term": term,
                })
            print(f"  {topic:9s} {term[:32]:32s} -> {kept:2d} kept (calls {ce.CALLS['n']})", flush=True)
        else:
            continue
        break

    OUT.write_text(json.dumps({
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Manifold search-markets + /v0/bets (third pass)",
        "snapshot_rule": "last probAfter >= 1h before close time",
        "markets": out,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    with REVIEW.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["类别", "搜索词", "market_id", "原题(EN)", "事前概率", "快照时间",
                    "结算结果", "市场链接", "人工结论"])
        for m in out:
            w.writerow([m["category"], m["query_term"], m["market_id"],
                        m["question_en"], m["probability"], m["snapshot_time"],
                        "YES" if m["outcome"] else "NO", m["market_url"], "待筛选"])

    print("=" * 70, flush=True)
    print(f"  wrote {len(out)} new candidates -> {OUT.name}", flush=True)
    print("  by category:", dict(Counter(m["category"] for m in out)), flush=True)
    print("  by outcome :", dict(Counter(m["outcome"] for m in out)), flush=True)
    print("  total calls:", ce.CALLS["n"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
