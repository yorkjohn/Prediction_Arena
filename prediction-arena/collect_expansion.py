"""Second-pass collection: widen the pool for the thin categories.

Same quality bar as the first pass, many more search terms. Manifold's public
resolved BINARY markets are searched per topic; pre-resolution probability is
rebuilt from /v0/bets (last probAfter at least 1h before close time).

No invented numbers. Politics, elections, wars, regulators, litigation,
gossip, personal micro-markets and polls are excluded.

Network: local proxy 127.0.0.1:10819.
Usage:  python -u collect_expansion.py
Output: seed/expansion_markets.json + seed/expansion_review.csv
"""
from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "seed" / "expansion_markets.json"
REVIEW = ROOT / "seed" / "expansion_review.csv"
BANK = ROOT / "seed" / "arena_seed_questions.json"

PROXY = "http://127.0.0.1:10819"
MF_SEARCH = "https://api.manifold.markets/v0/search-markets"
MF_BETS = "https://api.manifold.markets/v0/bets"
MAX_CALLS = 420
MIN_P, MAX_P = 0.12, 0.88
PER_TERM = 8

OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
)
OPENER.addheaders = [("User-Agent", "PredictionArenaResearch/6.0")]
CALLS = {"n": 0}

QUERIES = {
    "esports": [
        "T1 Worlds", "LoL Worlds 2023", "LoL Worlds 2024", "LoL Worlds 2025",
        "League of Legends World Championship", "Gen.G", "BLG", "JDG",
        "G2 Esports", "Fnatic", "DRX Worlds", "Dota 2 The International",
        "CS2 Major", "Valorant Champions", "worlds semifinal", "LoL final",
    ],
    "business": [
        "Oscar Best Picture", "Oscars 2025", "box office", "movie release",
        "iPhone 16", "Apple event", "Netflix", "Spotify", "Grammy",
        "album release", "Disney", "Tesla deliveries", "Cybertruck",
        "Nintendo Switch", "PlayStation", "video game release", "product launch",
    ],
    "world": [
        "Olympics 2024", "Paris Olympics medal", "Nobel Prize Physics",
        "Nobel Prize Medicine", "hottest year", "global temperature",
        "climate record", "World Cup 2026", "earthquake", "hurricane season",
        "space mission", "record high temperature",
    ],
    "ai": [
        "GPT-5", "OpenAI release", "Claude 4", "Gemini 2", "DeepSeek",
        "AGI", "AI model benchmark", "Sora release", "LLM benchmark",
        "AI agent", "model launch",
    ],
}

BLOCK = [
    "election", "president", "trump", "biden", "congress", "senate", "parliament",
    "prime minister", "government", "minister", "politic", "war ", "ukraine",
    "russia", "israel", "gaza", "iran", "china", "taiwan", "nato", "ceasefire",
    "hostage", "hamas", "tariff", "sanction", "pardon", "impeach", "lawsuit",
    "sec ", "fed ", "rate cut", "inflation", "recession", "shutdown", "nuclear",
    "military", "assassin", "death", "shoot", "arrest", "convict", "prison",
    "court", "supreme", "ban ", "resign", "cabinet", "immigration", "protest",
    "pregnant", "breakup", "break up", "engaged", "divorce", "dating",
    "will i ", "will my ", "my next", "do i ", "am i ", "i will ", "i get ",
    "zvi ", "[poll]", "porn", "nobel peace", "piss prize", "doomsday",
]


def fetch(url: str, timeout: int = 22):
    if CALLS["n"] >= MAX_CALLS:
        raise RuntimeError("request budget exhausted")
    CALLS["n"] += 1
    with OPENER.open(url, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    time.sleep(0.06)
    return data


def clean(q: str) -> bool:
    t = " " + q.lower().strip() + " "
    return not any(b in t for b in BLOCK)


def snapshot(m: dict) -> dict | None:
    res, close = m.get("resolution"), m.get("closeTime")
    if res not in ("YES", "NO") or not close:
        return None
    target = close - 3600 * 1000
    try:
        bets = fetch(f"{MF_BETS}?{urllib.parse.urlencode({'contractId': m['id'], 'limit': 1000})}")
    except Exception:
        return None
    if not isinstance(bets, list):
        return None
    before = [b for b in bets if b.get("createdTime") and b["createdTime"] <= target
              and isinstance(b.get("probAfter"), (int, float))]
    if not before:
        return None
    last = max(before, key=lambda b: b["createdTime"])
    return {
        "probability": round(float(last["probAfter"]), 4),
        "snapshot_unix": int(last["createdTime"] / 1000),
        "snapshot_time": datetime.fromtimestamp(
            last["createdTime"] / 1000, timezone.utc
        ).isoformat(timespec="seconds"),
        "outcome": 1 if res == "YES" else 0,
        "asset_id": m["id"],
    }


def used_ids() -> set[str]:
    if not BANK.exists():
        return set()
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    return {q.get("source_market_id") for q in bank["questions"] if q.get("source_market_id")}


def main() -> int:
    print("== second-pass expansion collector ==", flush=True)
    used = used_ids()
    out, seen = [], set(used)
    for topic, terms in QUERIES.items():
        for term in terms:
            if CALLS["n"] >= MAX_CALLS:
                break
            url = f"{MF_SEARCH}?" + urllib.parse.urlencode(
                {"term": term, "filter": "resolved", "limit": 30}
            )
            try:
                rows = fetch(url)
            except Exception as e:
                print(f"  [skip] {term}: {e}", flush=True)
                continue
            if not isinstance(rows, list):
                continue
            taken = kept = 0
            for m in rows:
                if taken >= PER_TERM or CALLS["n"] >= MAX_CALLS:
                    break
                if m.get("outcomeType") != "BINARY" or not m.get("isResolved"):
                    continue
                if m.get("resolution") not in ("YES", "NO"):
                    continue
                q = (m.get("question") or "").strip()
                if not q or len(q) < 18 or not clean(q) or m.get("id") in seen:
                    continue
                seen.add(m["id"])
                taken += 1
                s = snapshot(m)
                if not s or not MIN_P <= s["probability"] <= MAX_P:
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
                    "license_status": "NEEDS_MANUAL_REVIEW", **s,
                    "query_term": term,
                })
            print(f"  {topic:9s} {term:36s} -> {kept:2d} kept (calls {CALLS['n']})", flush=True)

    OUT.write_text(json.dumps({
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Manifold search-markets + /v0/bets",
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
    print("  total calls:", CALLS["n"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
