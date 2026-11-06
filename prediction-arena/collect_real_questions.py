"""Collect REAL pre-event probability snapshots (v3, bounded request budget).

Sources
  - Polymarket : Gamma API (resolved outcomePrices) + CLOB prices-history
  - Manifold   : search-markets (resolved BINARY) + /v0/bets (probAfter rebuild)

Snapshot rule is identical for both: last traded YES probability at least ONE
HOUR before resolution / close time. Every row carries source URL, API URL,
asset/contract id and UTC snapshot timestamp for auditing. Nothing is invented.

A hard request budget keeps the run under a few minutes. Topic curation is
conservative: politics, wars, regulators, litigation, gossip and personal
micro-markets are excluded for an ICDM Youth audience.

Network: local proxy 127.0.0.1:10819 is required on this machine.
Usage:  python -u collect_real_questions.py
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
OUT = ROOT / "seed" / "real_markets_raw.json"
REVIEW = ROOT / "seed" / "real_markets_review.csv"
PROXY = "http://127.0.0.1:10819"
MAX_CALLS = 170
MIN_P, MAX_P = 0.10, 0.90
PER_TOPIC_TRIES = 18
MF_PER_TERM = 6

OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
)
OPENER.addheaders = [("User-Agent", "PredictionArenaResearch/3.0")]

GAMMA = "https://gamma-api.polymarket.com/markets"
CLOB = "https://clob.polymarket.com/prices-history"
MF_SEARCH = "https://api.manifold.markets/v0/search-markets"
MF_BETS = "https://api.manifold.markets/v0/bets"

CALLS = {"n": 0}


def fetch(url: str, timeout: int = 22):
    if CALLS["n"] >= MAX_CALLS:
        raise RuntimeError("request budget exhausted")
    CALLS["n"] += 1
    with OPENER.open(url, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    time.sleep(0.08)
    return data


def log(*a):
    print(*a, flush=True)


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def jlist(raw):
    try:
        v = json.loads(raw) if isinstance(raw, str) else raw
        return v if isinstance(v, list) else None
    except (TypeError, ValueError):
        return None


BLOCK = [
    "election", "president", "trump", "biden", "congress", "senate", "parliament",
    "prime minister", "government", "minister", "governor", "politic", "war ",
    "ukraine", "russia", "israel", "gaza", "iran", "china", "taiwan", "nato",
    "ceasefire", "hostage", "hamas", "tariff", "sanction", "pardon", "impeach",
    "lawsuit", "sec ", "fed ", "rate cut", "inflation", "recession", "shutdown",
    "nuclear", "military", "assassin", "death", "shoot", "arrest", "convict",
    "prison", "court", "supreme", "ban ", "legaliz", "resign", "cabinet",
    "ambassador", "border", "immigration", "protest", "coup", "pregnant",
    "breakup", "break up", "engaged", "divorce", "dating", "will i ",
    "will my ", "my next", "do i ", "am i ", "ipo", "settlement", "nyt",
    "coinbase", "kraken", "circle", "shein", "meissner", "vultures", "kanye",
    "swift", "kelce",
]

TOPICS: dict[str, list[str]] = {
    "sports": ["super bowl", "nba", "nfl", "mlb", "nhl", "ufc", "premier league",
               "champions league", "world cup", "wimbledon", "tennis", "formula 1",
               "grand prix", "olympic", "march madness", "ncaa", "lakers", "celtics",
               "arsenal", "manchester", "real madrid", "barcelona", "world series",
               "boxing", "soccer", "football", "basketball", "championship",
               "man city", "nfl mvp", "playoffs", "finals"],
    "esports": ["league of legends", "lol ", "dota", "the international", "cs2",
                "counter-strike", "valorant", "esports", "worlds 20", "overwatch",
                "rocket league", "world championship", "major champion"],
    "ai": ["openai", "chatgpt", "gpt-", "gpt ", "anthropic", "claude", "gemini",
           "spacex", "starship", "artificial intelligence", " ai ", "ai model",
           "nvidia", "robot", "self-driving", "waymo", "apple intelligence",
           "deepmind", "alphafold", "quantum", "moon landing", "mars ", " agi",
           "llm", "sora", "midjourney", "model release"],
    "business": ["box office", "oscar", "grammy", "iphone", "apple", "netflix",
                 "spotify", "disney", "movie", "album", "product launch", "release",
                 "tesla", "acquisition", "merger", "sales", "streaming", "video game",
                 "nintendo", "playstation", "xbox", "film", "gross"],
    "world": ["hottest year", "temperature", "climate", "nobel prize", "earthquake",
              "hurricane", "expo", "asteroid", "eclipse", "space station",
              "record high", "weather", "world record", "science"],
}

MF_QUERIES = {
    "sports": ["NBA Finals", "Super Bowl", "Champions League", "World Cup"],
    "esports": ["League of Legends Worlds", "Dota 2 The International",
                "CS2 Major", "Valorant Champions", "LoL World Championship"],
    "ai": ["GPT-5", "OpenAI", "Claude 4", "Gemini", "SpaceX Starship"],
    "business": ["iPhone", "Apple", "box office", "Oscar Best Picture"],
    "world": ["Nobel Prize", "hottest year on record", "climate record"],
}


def topic_of(question: str) -> str | None:
    q = " " + question.lower().strip() + " "
    if any(b in q for b in BLOCK):
        return None
    for topic, words in TOPICS.items():
        if any(w in q for w in words):
            return topic
    return None


def acceptable(p: float) -> bool:
    return MIN_P <= p <= MAX_P


# ---------------------------------------------------------------- Polymarket

def pm_snapshot(m: dict) -> dict | None:
    outcomes, prices, tokens = jlist(m.get("outcomes")), jlist(m.get("outcomePrices")), jlist(m.get("clobTokenIds"))
    if not outcomes or not prices or not tokens or len(tokens) != 2:
        return None
    try:
        a, b = float(prices[0]), float(prices[1])
    except (TypeError, ValueError):
        return None
    if not ((abs(a - 1) < 1e-6 and abs(b) < 1e-6) or
            (abs(a) < 1e-6 and abs(b - 1) < 1e-6)):
        return None
    yi = next((i for i, o in enumerate(outcomes) if str(o).lower() == "yes"), 0)
    end = datetime.fromisoformat(m["endDate"].replace("Z", "+00:00"))
    target = int(end.timestamp()) - 3600
    q = urllib.parse.urlencode({
        "market": tokens[yi], "startTs": target - 3 * 86400,
        "endTs": target, "interval": "1d", "fidelity": 60,
    })
    try:
        hist = fetch(f"{CLOB}?{q}").get("history", [])
    except Exception:
        return None
    if not hist:
        return None
    point = hist[-1]
    return {
        "probability": round(float(point["p"]), 4),
        "snapshot_unix": int(point["t"]), "snapshot_time": iso(int(point["t"])),
        "outcome": 1 if float(prices[yi]) > 0.5 else 0, "asset_id": tokens[yi],
    }


def collect_polymarket() -> list[dict]:
    raw: list[dict] = []
    for offset in range(0, 1200, 100):
        q = urllib.parse.urlencode({
            "closed": "true", "limit": 100, "offset": offset,
            "end_date_min": "2024-01-01T00:00:00Z",
            "end_date_max": "2026-11-01T00:00:00Z",
        })
        try:
            batch = fetch(f"{GAMMA}?{q}", timeout=35)
        except Exception as e:
            log(f"  [pm] stop at offset {offset}: {e}")
            break
        if not isinstance(batch, list) or not batch:
            break
        raw.extend(batch)
        if len(batch) < 100:
            break
    log(f"  [pm] scanned {len(raw)} closed markets (calls={CALLS['n']})")

    out, seen, tries = [], set(), Counter()
    for m in raw:
        if CALLS["n"] >= MAX_CALLS:
            break
        if not m.get("closed") or not m.get("endDate") or not m.get("question"):
            continue
        topic = topic_of(m["question"])
        if topic is None or tries[topic] >= PER_TOPIC_TRIES:
            continue
        slug = m.get("slug") or str(m.get("id"))
        if slug in seen:
            continue
        seen.add(slug)
        tries[topic] += 1
        s = pm_snapshot(m)
        if not s or not acceptable(s["probability"]):
            continue
        out.append({
            "source_platform": "Polymarket", "category": topic,
            "market_id": m.get("id"), "slug": slug,
            "question_en": m["question"], "end_date": m["endDate"],
            "market_url": f"https://polymarket.com/market/{slug}",
            "source_api": f"https://gamma-api.polymarket.com/markets/{m.get('id')}",
            "license_status": "NEEDS_MANUAL_REVIEW", **s,
        })
    return out


# ------------------------------------------------------------------ Manifold

def mf_snapshot(m: dict) -> dict | None:
    res, close_ms = m.get("resolution"), m.get("closeTime")
    if res not in ("YES", "NO") or not close_ms:
        return None
    target_ms = close_ms - 3600 * 1000
    try:
        bets = fetch(f"{MF_BETS}?{urllib.parse.urlencode({'contractId': m['id'], 'limit': 1000})}")
    except Exception:
        return None
    if not isinstance(bets, list):
        return None
    before = [b for b in bets if b.get("createdTime")
              and b["createdTime"] <= target_ms
              and isinstance(b.get("probAfter"), (int, float))]
    if not before:
        return None
    last = max(before, key=lambda b: b["createdTime"])
    return {
        "probability": round(float(last["probAfter"]), 4),
        "snapshot_unix": int(last["createdTime"] / 1000),
        "snapshot_time": iso(last["createdTime"] / 1000),
        "outcome": 1 if res == "YES" else 0, "asset_id": m["id"],
    }


def collect_manifold() -> list[dict]:
    out, seen = [], set()
    for topic, terms in MF_QUERIES.items():
        for term in terms:
            if CALLS["n"] >= MAX_CALLS:
                return out
            try:
                rows = fetch(f"{MF_SEARCH}?{urllib.parse.urlencode({'term': term, 'filter': 'resolved', 'limit': 30})}")
            except Exception as e:
                log(f"  [mf] {term}: {e}")
                continue
            if not isinstance(rows, list):
                continue
            taken = 0
            for m in rows:
                if taken >= MF_PER_TERM or CALLS["n"] >= MAX_CALLS:
                    break
                if m.get("outcomeType") != "BINARY" or not m.get("isResolved"):
                    continue
                if m.get("resolution") not in ("YES", "NO"):
                    continue
                question = m.get("question", "")
                if not question or m.get("id") in seen or topic_of(question) != topic:
                    continue
                seen.add(m.get("id"))
                taken += 1
                s = mf_snapshot(m)
                if not s or not acceptable(s["probability"]):
                    continue
                out.append({
                    "source_platform": "Manifold", "category": topic,
                    "market_id": m.get("id"), "slug": m.get("slug"),
                    "question_en": question, "end_date": iso(m["closeTime"] / 1000),
                    "market_url": m.get("url") or f"https://manifold.markets/market/{m.get('slug')}",
                    "source_api": f"https://api.manifold.markets/v0/market/{m.get('id')}",
                    "license_status": "NEEDS_MANUAL_REVIEW", **s,
                })
    return out


# ------------------------------------------------------------------- assemble

def balance(rows: list[dict]) -> list[dict]:
    picked = []
    for topic in TOPICS:
        group = [r for r in rows if r["category"] == topic]
        yes = [r for r in group if r["outcome"] == 1]
        no = [r for r in group if r["outcome"] == 0]
        merged = []
        for i in range(max(len(yes), len(no))):
            if i < len(yes):
                merged.append(yes[i])
            if i < len(no):
                merged.append(no[i])
        picked.extend(merged)
    return picked


def write_review(rows: list[dict]) -> None:
    with REVIEW.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["类别", "平台", "market_id", "原题(EN)", "事前概率",
                    "快照时间(UTC)", "结算结果", "市场链接", "来源API",
                    "许可状态", "人工结论"])
        for r in rows:
            w.writerow([r["category"], r["source_platform"], r["market_id"],
                        r["question_en"], r["probability"], r["snapshot_time"],
                        "YES" if r["outcome"] else "NO", r["market_url"],
                        r["source_api"], r["license_status"], "待人工筛选(§3.4)"])


def main() -> int:
    log("== real-snapshot collector v3 ==")
    pm = collect_polymarket()
    log(f"  [pm] acceptable rows: {len(pm)} (calls={CALLS['n']})")
    mf = collect_manifold()
    log(f"  [mf] acceptable rows: {len(mf)} (calls={CALLS['n']})")

    all_rows = balance(pm + mf)
    OUT.write_text(json.dumps({
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": ["Polymarket Gamma+CLOB", "Manifold search+bets"],
        "snapshot_rule": "last traded YES probability >= 1h before resolution",
        "probability_range": [MIN_P, MAX_P],
        "total_api_calls": CALLS["n"],
        "markets": all_rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    write_review(all_rows)

    log("=" * 68)
    log(f"  wrote {len(all_rows)} real markets -> {OUT.name}")
    log("  by category: " + str(dict(Counter(r["category"] for r in all_rows))))
    log("  by platform: " + str(dict(Counter(r["source_platform"] for r in all_rows))))
    log("  by outcome : " + str(dict(Counter(r["outcome"] for r in all_rows))))
    log("  license_status NOT verified — confirm API/display terms (plan 10.3)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
