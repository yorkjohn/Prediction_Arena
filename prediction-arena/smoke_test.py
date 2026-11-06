"""On-site self-check. Runs against a throwaway DB via Flask's test client.

Usage:  python smoke_test.py
It never touches arena.db (the live database).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TMP_DB = ROOT / "arena_smoke.db"
if TMP_DB.exists():
    TMP_DB.unlink()
os.environ["ARENA_DB"] = str(TMP_DB)
sys.path.insert(0, str(ROOT))

import app as arena  # noqa: E402

arena.init_db()
c = arena.app.test_client()
checks = 0


def ok(label, cond, extra=""):
    global checks
    assert cond, f"FAIL: {label} {extra}"
    checks += 1
    print(f"  PASS  {label}")


def get(path):
    return c.get(path)


def post(path, body):
    return c.post(path, json=body)


print("== Prediction Arena self-check ==")

h = get("/api/health").get_json()
ok("health + seeded bank", h["ok"] and h["real_questions"] >= 25, str(h))

for cid, nick in [("smoke_A", "预测者甲"), ("smoke_B", "预测者乙")]:
    r = post("/api/join", {"client_id": cid, "nickname": nick}).get_json()
    ok(f"join {cid}", r["ok"] and r["user"]["avatar_color"].startswith("#"))

w = get("/api/questions/warmup")
wj = w.get_json()
ok("3 warm-up questions", len(wj["questions"]) == 3)
raw_warmup = json.dumps(wj, ensure_ascii=False)
ok("warm-up payload redacted", "outcome" not in raw_warmup and "benchmark_probability" not in raw_warmup)
wa = post("/api/warmup/answer", {"question_id": "W01", "p_yes": 30, "lang": "zh"}).get_json()
ok("warm-up reveals outcome + brier", wa["ok"] and wa["outcome"] == 1 and abs(wa["brier"] - 0.49) < 1e-6, str(wa))

sa = post("/api/session/start", {"client_id": "smoke_A", "category": "ai"}).get_json()
sb = post("/api/session/start", {"client_id": "smoke_B", "category": "random"}).get_json()
ok("session A draws 5 unique questions", len(sa["questions"]) == 5 and len({q["id"] for q in sa["questions"]}) == 5)
ok("session A is the requested category", sa["actual_category"] == "ai")
ok("session B random category valid", sb["actual_category"] in arena.CATEGORIES)
raw_start = json.dumps(sa, ensure_ascii=False)
ok("challenge payload redacted", "outcome" not in raw_start and "benchmark_probability" not in raw_start)

p_values = [80, 30, 50, 70, 10]
first_q = sa["questions"][0]["id"]
for i, q in enumerate(sa["questions"]):
    r = post("/api/predictions", {
        "client_id": "smoke_A", "session_id": sa["session_id"],
        "question_id": q["id"], "p_yes": p_values[i]
    })
    ok(f"A submit {i + 1}/5", r.status_code == 200 and r.get_json()["submitted"] == i + 1, r.get_data(as_text=True))

dup = post("/api/predictions", {
    "client_id": "smoke_A", "session_id": sa["session_id"],
    "question_id": first_q, "p_yes": 99
})
ok("duplicate submission locked (409)", dup.status_code == 409, str(dup.status_code))

for q in sb["questions"]:
    post("/api/predictions", {
        "client_id": "smoke_B", "session_id": sb["session_id"],
        "question_id": q["id"], "p_yes": 60
    })

ra = get(f"/api/session/{sa['session_id']}/result?client_id=smoke_A").get_json()
ok("result has 5 details", len(ra["details"]) == 5)
ok("result exposes outcome after completion", all("outcome" in d for d in ra["details"]))
ok("real-market benchmark flagged verified", all(d["benchmark_verified"] is True for d in ra["details"]))
ok("every result carries a market source", all(d.get("benchmark_source") for d in ra["details"]))
ok("rank assigned", isinstance(ra["rank"], int) and ra["rank"] >= 1)
manual = sum(((p / 100.0) - d["outcome"]) ** 2 for p, d in zip(p_values, ra["details"])) / 5
ok("Brier Score matches manual calculation", abs(ra["avg_brier"] - round(manual, 4)) < 1e-3,
   f"{ra['avg_brier']} vs {manual:.4f}")
ok("50% counted as neutral", ra["neutral_count"] == 1, str(ra["neutral_count"]))

lb = get("/api/leaderboard").get_json()["leaderboard"]
ok("leaderboard has both finishers", len(lb) == 2)
ok("leaderboard sorted by Brier", lb[0]["brier"] <= lb[1]["brier"])

d = get("/api/dashboard").get_json()
ok("dashboard counts 2 participants", d["total_participants"] == 2, str(d["total_participants"]))
ok("dashboard aggregated per question", len(d["per_question"]) > 0)
# NB: real questions in the "world" category are WO01..., not warm-ups.
ok("warm-up answers excluded from stats",
   all(q["question_id"] not in ("W01", "W02", "W03") for q in d["per_question"]))

# Plan section 11 / stage 6: many participants at once.
import concurrent.futures  # noqa: E402


def one_player(n: int) -> bool:
    cid = f"load_{n}"
    cli = arena.app.test_client()
    if cli.post("/api/join", json={"client_id": cid, "nickname": f"压测{n}"}).status_code != 200:
        return False
    s = cli.post("/api/session/start", json={"client_id": cid, "category": "random"}).get_json()
    if not s.get("ok"):
        return False
    for q in s["questions"]:
        r = cli.post("/api/predictions", json={
            "client_id": cid, "session_id": s["session_id"],
            "question_id": q["id"], "p_yes": 40 + n % 40,
        })
        if r.status_code != 200:
            return False
    return cli.get(
        f"/api/session/{s['session_id']}/result?client_id={cid}"
    ).status_code == 200


with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    results = list(pool.map(one_player, range(20)))
ok("20 simultaneous players all complete", len(results) == 20 and all(results),
   f"{sum(1 for x in results if x)}/20 succeeded")

d2 = get("/api/dashboard").get_json()
ok("dashboard reflects concurrent load", d2["total_participants"] >= 22,
   str(d2["total_participants"]))

# Refresh / WeChat background-kill recovery path.
post("/api/join", {"client_id": "smoke_C", "nickname": "刷新测试"})
sc = post("/api/session/start", {"client_id": "smoke_C", "category": "sports"}).get_json()
for q in sc["questions"][:2]:
    post("/api/predictions", {
        "client_id": "smoke_C", "session_id": sc["session_id"],
        "question_id": q["id"], "p_yes": 55,
    })
resumed = get(f"/api/session/{sc['session_id']}/questions?client_id=smoke_C").get_json()
ok("refresh resumes mid-session with 2 answers",
   len(resumed["questions"]) == 5 and len(resumed["answered"]) == 2
   and resumed["completed"] is False, str(resumed.get("answered")))
ok("resumed payload still redacted",
   "outcome" not in json.dumps(resumed, ensure_ascii=False)
   and "benchmark_probability" not in json.dumps(resumed, ensure_ascii=False))

exp = get("/api/export.csv")
ok("CSV export is notebook-only and non-empty", exp.status_code == 200 and len(exp.data) > 200)

print(f"== {checks} checks passed ==")
try:
    TMP_DB.unlink()
except OSError:
    pass
