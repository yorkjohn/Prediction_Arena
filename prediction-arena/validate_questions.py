"""Validate the question bank before the event (plan sections 3.4 / 9 / 10).

Usage:
  python validate_questions.py
  python validate_questions.py path/to/other_bank.json

Hard errors -> exit 1. Warnings (unverified benchmarks, missing English) -> exit 0
but printed loudly, because the shipped demo bank is intentionally in that state.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT = ROOT / "seed" / "arena_seed_questions.json"
CATS = {"sports", "esports", "ai", "business", "world"}
REQUIRED = [
    "id", "mode", "category", "title_zh", "outcome",
    "benchmark_probability", "benchmark_verified", "source_note",
]


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if not path.exists():
        print(f"ERROR: bank not found: {path}")
        return 1
    bank = json.loads(path.read_text(encoding="utf-8"))
    qs = bank.get("questions", [])
    errors: list[str] = []
    warnings: list[str] = []

    if not qs:
        errors.append("question list is empty")

    seen = set()
    for i, q in enumerate(qs):
        label = q.get("id", f"#{i}")
        for key in REQUIRED:
            if key not in q:
                errors.append(f"{label}: missing field '{key}'")
        if q.get("id") in seen:
            errors.append(f"{label}: duplicate id")
        seen.add(q.get("id"))
        if q.get("mode") not in ("warmup", "real"):
            errors.append(f"{label}: mode must be warmup/real")
        if q.get("category") not in CATS:
            errors.append(f"{label}: unknown category '{q.get('category')}'")
        if q.get("outcome") not in (0, 1):
            errors.append(f"{label}: outcome must be 0 or 1")
        p = q.get("benchmark_probability")
        if q.get("mode") == "warmup":
            if p is not None and not (isinstance(p, (int, float)) and 0 <= float(p) <= 1):
                errors.append(f"{label}: warm-up benchmark must be null or within [0,1]")
        elif not isinstance(p, (int, float)) or not 0 <= float(p) <= 1:
            errors.append(f"{label}: benchmark_probability must be within [0,1]")
        if q.get("mode") == "real" and not q.get("benchmark_snapshot_time"):
            errors.append(f"{label}: real question missing benchmark_snapshot_time")
        if q.get("mode") == "real" and not q.get("benchmark_url"):
            errors.append(f"{label}: real question missing benchmark_url")
        if not q.get("title_zh"):
            errors.append(f"{label}: title_zh is empty")
        if not q.get("yes_zh"):
            warnings.append(f"{label}: YES definition (yes_zh) is empty")
        if q.get("mode") == "real" and not q.get("context_zh"):
            warnings.append(f"{label}: no background (context_zh)")
        if not q.get("title_en") or not q.get("context_en") or not q.get("yes_en"):
            warnings.append(f"{label}: English text incomplete (falls back to Chinese)")

    warmup = [q for q in qs if q.get("mode") == "warmup"]
    real = [q for q in qs if q.get("mode") == "real"]
    if len(warmup) != 3:
        errors.append(f"warm-up must have exactly 3 questions, got {len(warmup)}")

    per_cat = Counter(q.get("category") for q in real)
    for cat, n in sorted(per_cat.items()):
        if n < 5:
            errors.append(f"category '{cat}' has {n} questions; a 5-question round needs >= 5")
        if n < 20:
            warnings.append(f"category '{cat}' has {n}; plan section 3.2 asks for >= 20")

    unverified = [q.get("id") for q in qs
                  if q.get("mode") == "real" and not q.get("benchmark_verified")]
    placeholder = [q.get("id") for q in qs if q.get("source_note") == "DEMO_PLACEHOLDER"]
    needs_license = [q.get("id") for q in qs
                     if q.get("license_status") == "NEEDS_MANUAL_REVIEW"]
    sources = Counter(q.get("benchmark_source") for q in real)
    outcomes = Counter(q.get("outcome") for q in real)

    print("=" * 62)
    print(f"  Bank: {path.name}")
    print(f"  Total {len(qs)} | warm-up {len(warmup)} | real {len(real)}")
    print(f"  Real per category: {dict(sorted(per_cat.items()))}")
    print(f"  Outcome balance (real): YES={outcomes.get(1, 0)} NO={outcomes.get(0, 0)}")
    print(f"  Benchmark sources (real): {dict(sources)}")
    print("=" * 62)

    if unverified:
        print(f"  [!] {len(unverified)} real questions have UNVERIFIED benchmark probability")
        print(f"      e.g. {', '.join(str(x) for x in unverified[:8])}")
        print("      -> replace with pre-event market snapshots before the event")
    if placeholder:
        print(f"  [!] {len(placeholder)} questions still marked DEMO_PLACEHOLDER")
    if needs_license:
        print(f"  [!] {len(needs_license)} questions have UNVERIFIED display licensing")
        print("      -> confirm Polymarket / Manifold API & display terms (plan 10.3)")
    # Structural warnings are printed up front; the long list of per-question
    # translation warnings below must not bury them.
    if outcomes.get(1, 0) == 0 or outcomes.get(0, 0) == 0:
        print("  [!] all real questions resolve the same way; Brier loses discrimination")
    elif real:
        yes_ratio = outcomes.get(1, 0) / len(real)
        if yes_ratio >= 0.7 or yes_ratio <= 0.3:
            print(
                f"  [!] outcome skew: {outcomes.get(1, 0)} YES / {outcomes.get(0, 0)} NO "
                f"({yes_ratio:.0%} YES) — players can game it by always answering YES"
            )

    for w in warnings[:15]:
        print(f"  [warn] {w}")
    if len(warnings) > 15:
        print(f"  [warn] ... and {len(warnings) - 15} more")

    if errors:
        print(f"\n  {len(errors)} HARD ERROR(S):")
        for e in errors[:20]:
            print(f"    - {e}")
        print("  FIX THESE BEFORE THE EVENT.")
        return 1

    print(f"\n  Structure OK. {len(warnings)} warning(s), {len(unverified)} unverified benchmark(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
