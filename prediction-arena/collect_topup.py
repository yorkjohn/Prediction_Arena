"""Targeted top-up collection for the two thin categories (esports, world).

Reuses the snapshot logic from collect_real_questions.py so the one-hour-before-
resolution rule stays identical. Output: seed/topup_markets.json

Usage:  python -u collect_topup.py
"""
from __future__ import annotations

import json
import urllib.parse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from collect_real_questions import (
    MF_SEARCH, acceptable, fetch, iso, mf_snapshot,
)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "seed" / "topup_markets.json"

QUERIES = {
    "esports": [
        "LoL Worlds 2024", "T1 win Worlds", "League of Legends World Championship",
        "BLG Worlds", "Fnatic LOL World Championships", "G2 Esports worlds",
        "The International Dota winner", "Valorant Champions winner",
    ],
    "world": [
        "hottest year on record", "global temperature record",
        "Olympics 2024 medal count", "2024 Summer Olympics",
        "warmest year on record", "average global temperature",
    ],
}

# Extra exclusions on top of the shared BLOCK list: politics-adjacent Nobel
# questions and doomsday/oddity markets are not suitable for a youth demo.
EXTRA_BLOCK = [
    "trump", "nobel peace", "piss prize", "doomsday", "war ", "ukraine",
    "president", "election", "ice ", "catastrophe", "nuclear",
]


def clean(question: str) -> bool:
    q = " " + question.lower() + " "
    return not any(b in q for b in EXTRA_BLOCK)


def main() -> int:
    print("== targeted top-up: esports + world ==", flush=True)
    out, seen = [], set()
    for topic, terms in QUERIES.items():
        for term in terms:
            url = f"{MF_SEARCH}?{urllib.parse.urlencode({'term': term, 'filter': 'resolved', 'limit': 25})}"
            try:
                rows = fetch(url)
            except Exception as e:
                print(f"  [skip] {term}: {e}", flush=True)
                continue
            if not isinstance(rows, list):
                continue
            for m in rows:
                if m.get("outcomeType") != "BINARY" or not m.get("isResolved"):
                    continue
                if m.get("resolution") not in ("YES", "NO"):
                    continue
                q = m.get("question", "")
                if not q or not clean(q) or m.get("id") in seen:
                    continue
                seen.add(m["id"])
                s = mf_snapshot(m)
                if not s or not acceptable(s["probability"]):
                    continue
                out.append({
                    "source_platform": "Manifold", "category": topic,
                    "market_id": m["id"], "slug": m.get("slug"),
                    "question_en": q, "end_date": iso(m["closeTime"] / 1000),
                    "market_url": m.get("url") or f"https://manifold.markets/market/{m.get('slug')}",
                    "source_api": f"https://api.manifold.markets/v0/market/{m['id']}",
                    "license_status": "NEEDS_MANUAL_REVIEW", **s,
                })
                print(f"  [ok] {topic:8s} p={s['probability']:.3f} y={s['outcome']} | {q[:70]}",
                      flush=True)

    OUT.write_text(json.dumps({
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "categories": list(QUERIES), "markets": out,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 62, flush=True)
    print(f"  wrote {len(out)} -> {OUT.name}", flush=True)
    print("  by category:", dict(Counter(r["category"] for r in out)), flush=True)
    print("  by outcome :", dict(Counter(r["outcome"] for r in out)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
