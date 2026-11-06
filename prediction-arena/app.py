"""Prediction Arena - ICDM Youth on-site demo.

Local-first implementation (plan section 8): Flask + SQLite, no cloud, no domain,
no ICP filing. The notebook runs this server; phones on the same Wi-Fi open the LAN URL.

Answers (outcome) and benchmark probabilities stay on the server. The client only
ever receives redacted questions. See plan section 8.5.

Run:  python app.py
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import random
import socket
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, g, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent
# ARENA_DB lets the self-check run against a throwaway database.
DB_PATH = Path(os.environ.get("ARENA_DB", str(ROOT / "arena.db")))
SEED_PATH = ROOT / "seed" / "arena_seed_questions.json"
STATIC = ROOT / "static"

CATEGORIES = ["sports", "esports", "ai", "business", "world"]
REAL_COUNT = 5
WARMUP_COUNT = 3

app = Flask(__name__, static_folder=None)
try:
    app.json.ensure_ascii = False
except AttributeError:  # Flask < 2.2
    app.config["JSON_AS_ASCII"] = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id     TEXT NOT NULL UNIQUE,
  nickname      TEXT NOT NULL,
  avatar_color  TEXT NOT NULL,
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
  id                    TEXT PRIMARY KEY,
  mode                  TEXT NOT NULL,
  category              TEXT NOT NULL,
  title_zh              TEXT NOT NULL,
  title_en              TEXT NOT NULL DEFAULT '',
  context_zh            TEXT NOT NULL DEFAULT '',
  context_en            TEXT NOT NULL DEFAULT '',
  yes_zh                TEXT NOT NULL DEFAULT '',
  yes_en                TEXT NOT NULL DEFAULT '',
  outcome               INTEGER NOT NULL,
  benchmark_probability REAL,
  benchmark_verified    INTEGER NOT NULL DEFAULT 0,
  benchmark_source      TEXT,
  benchmark_snapshot_time TEXT,
  benchmark_url         TEXT,
  source_api            TEXT,
  license_status        TEXT,
  explain_zh            TEXT NOT NULL DEFAULT '',
  explain_en            TEXT NOT NULL DEFAULT '',
  source_note           TEXT NOT NULL DEFAULT '',
  source_market_id      TEXT,
  active                INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sessions (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id           INTEGER NOT NULL,
  client_id         TEXT NOT NULL,
  selected_category TEXT NOT NULL,
  actual_category   TEXT NOT NULL,
  question_ids_json TEXT NOT NULL,
  started_at        TEXT NOT NULL,
  completed_at      TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS predictions (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      INTEGER NOT NULL,
  client_id    TEXT NOT NULL,
  session_id   INTEGER NOT NULL,
  question_id  TEXT NOT NULL,
  p_yes        REAL NOT NULL,
  brier_score  REAL,
  submitted_at TEXT NOT NULL,
  UNIQUE (session_id, question_id),
  FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_pred_session ON predictions(session_id);
CREATE INDEX IF NOT EXISTS idx_pred_question ON predictions(question_id);
CREATE INDEX IF NOT EXISTS idx_session_client ON sessions(client_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if count == 0:
            seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
            for q in seed["questions"]:
                conn.execute(
                    """INSERT INTO questions
                       (id, mode, category, title_zh, title_en, context_zh, context_en,
                        yes_zh, yes_en, outcome, benchmark_probability,
                        benchmark_verified, benchmark_source, benchmark_snapshot_time,
                        benchmark_url, source_api, license_status,
                        explain_zh, explain_en, source_note, source_market_id, active)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                    (
                        q["id"], q["mode"], q["category"],
                        q.get("title_zh", ""), q.get("title_en", ""),
                        q.get("context_zh", ""), q.get("context_en", ""),
                        q.get("yes_zh", ""), q.get("yes_en", ""),
                        int(q["outcome"]),
                        None if q.get("benchmark_probability") is None
                        else float(q["benchmark_probability"]),
                        int(bool(q.get("benchmark_verified", False))),
                        q.get("benchmark_source"), q.get("benchmark_snapshot_time"),
                        q.get("benchmark_url"), q.get("source_api"),
                        q.get("license_status"),
                        q.get("explain_zh", ""), q.get("explain_en", ""),
                        q.get("source_note", ""), q.get("source_market_id"),
                    ),
                )
            conn.commit()
            print(f"[arena] seeded {len(seed['questions'])} questions from {SEED_PATH.name}")
        else:
            print(f"[arena] keeping existing question bank ({count} rows)")
    finally:
        conn.close()


def redact(row: sqlite3.Row) -> dict:
    """Client-facing question. Never expose outcome, benchmark or explanation."""
    return {
        "id": row["id"],
        "category": row["category"],
        "title_zh": row["title_zh"],
        "title_en": row["title_en"] or row["title_zh"],
        "context_zh": row["context_zh"],
        "context_en": row["context_en"] or row["context_zh"],
        "yes_zh": row["yes_zh"],
        "yes_en": row["yes_en"] or row["yes_zh"],
    }


def err(message: str, code: int = 400):
    return jsonify({"ok": False, "error": message}), code


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("223.5.5.5", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


# --------------------------------------------------------------------------- pages

@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/dashboard")
def dashboard():
    return send_from_directory(STATIC, "dashboard.html")


@app.get("/static/<path:name>")
def static_files(name):
    return send_from_directory(STATIC, name)


@app.get("/api/health")
def health():
    db = get_db()
    n = db.execute("SELECT COUNT(*) FROM questions WHERE mode='real' AND active=1").fetchone()[0]
    return jsonify({"ok": True, "real_questions": n, "server_time": now()})


# --------------------------------------------------------------------------- identity

@app.post("/api/join")
def join():
    body = request.get_json(silent=True) or {}
    client_id = str(body.get("client_id", "")).strip()[:64]
    if not client_id:
        return err("missing client_id")
    nickname = str(body.get("nickname", "")).strip()[:20] or "匿名预测者"
    color = "#" + hashlib.md5(client_id.encode("utf-8")).hexdigest()[:6]
    db = get_db()
    db.execute(
        """INSERT INTO users (client_id, nickname, avatar_color, created_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(client_id) DO UPDATE SET nickname = excluded.nickname""",
        (client_id, nickname, color, now()),
    )
    db.commit()
    user = db.execute(
        "SELECT id, client_id, nickname, avatar_color FROM users WHERE client_id = ?",
        (client_id,),
    ).fetchone()
    return jsonify({"ok": True, "user": dict(user)})


# --------------------------------------------------------------------------- warm-up

@app.get("/api/questions/warmup")
def warmup():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM questions WHERE mode='warmup' AND active=1 ORDER BY id LIMIT ?",
        (WARMUP_COUNT,),
    ).fetchall()
    return jsonify({"ok": True, "questions": [redact(r) for r in rows]})


@app.post("/api/warmup/answer")
def warmup_answer():
    body = request.get_json(silent=True) or {}
    qid = str(body.get("question_id", ""))
    try:
        p = float(body.get("p_yes", 0)) / 100.0
    except (TypeError, ValueError):
        return err("invalid p_yes")
    if not 0.0 <= p <= 1.0:
        return err("p_yes out of range")
    db = get_db()
    q = db.execute("SELECT * FROM questions WHERE id = ? AND mode='warmup'", (qid,)).fetchone()
    if q is None:
        return err("question not found", 404)
    lang = "en" if body.get("lang") == "en" else "zh"
    y = int(q["outcome"])
    return jsonify({
        "ok": True,
        "outcome": y,
        "brier": round((p - y) ** 2, 4),
        "explain": (q["explain_en"] or q["explain_zh"]) if lang == "en" else q["explain_zh"],
    })


# --------------------------------------------------------------------------- challenge

@app.post("/api/session/start")
def session_start():
    body = request.get_json(silent=True) or {}
    client_id = str(body.get("client_id", "")).strip()[:64]
    if not client_id:
        return err("missing client_id")
    selected = str(body.get("category", "random"))
    if selected not in CATEGORIES + ["random"]:
        return err("invalid category")
    actual = random.choice(CATEGORIES) if selected == "random" else selected

    db = get_db()
    user = db.execute("SELECT id FROM users WHERE client_id = ?", (client_id,)).fetchone()
    if user is None:
        return err("join first", 403)

    rows = db.execute(
        """SELECT * FROM questions
           WHERE mode='real' AND active=1 AND category = ?
           ORDER BY RANDOM() LIMIT ?""",
        (actual, REAL_COUNT),
    ).fetchall()
    if len(rows) < REAL_COUNT:
        return err(f"category {actual} has fewer than {REAL_COUNT} active questions", 409)

    ids = [r["id"] for r in rows]
    cur = db.execute(
        """INSERT INTO sessions
           (user_id, client_id, selected_category, actual_category, question_ids_json, started_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user["id"], client_id, selected, actual, json.dumps(ids), now()),
    )
    db.commit()
    return jsonify({
        "ok": True,
        "session_id": cur.lastrowid,
        "selected_category": selected,
        "actual_category": actual,
        "questions": [redact(r) for r in rows],
    })


@app.get("/api/session/<int:sid>/questions")
def session_questions(sid: int):
    client_id = request.args.get("client_id", "").strip()[:64]
    db = get_db()
    s = db.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    if s is None or s["client_id"] != client_id:
        return err("session not found", 404)
    ids = json.loads(s["question_ids_json"])
    rows = [db.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone() for qid in ids]
    done = {
        r["question_id"]
        for r in db.execute("SELECT question_id FROM predictions WHERE session_id = ?", (sid,))
    }
    return jsonify({
        "ok": True,
        "session_id": sid,
        "actual_category": s["actual_category"],
        "completed": s["completed_at"] is not None,
        "questions": [redact(r) for r in rows if r is not None],
        "answered": sorted(done),
    })


@app.post("/api/predictions")
def submit_prediction():
    body = request.get_json(silent=True) or {}
    client_id = str(body.get("client_id", "")).strip()[:64]
    qid = str(body.get("question_id", ""))
    try:
        sid = int(body.get("session_id", 0))
        p = float(body.get("p_yes", 0)) / 100.0
    except (TypeError, ValueError):
        return err("invalid payload")
    if not 0.0 <= p <= 1.0:
        return err("p_yes out of range")

    db = get_db()
    s = db.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    if s is None or s["client_id"] != client_id:
        return err("session not found", 404)
    if s["completed_at"] is not None:
        return err("session already completed", 409)
    if qid not in json.loads(s["question_ids_json"]):
        return err("question is not in this session", 400)

    cur = db.execute(
        """INSERT OR IGNORE INTO predictions
           (user_id, client_id, session_id, question_id, p_yes, submitted_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (s["user_id"], client_id, sid, qid, p, now()),
    )
    db.commit()
    if cur.rowcount == 0:
        return err("already submitted, answer locked", 409)
    count = db.execute(
        "SELECT COUNT(*) FROM predictions WHERE session_id = ?", (sid,)
    ).fetchone()[0]
    # A session counts as finished the moment the fifth answer is locked in,
    # even if the player never opens the result page (plan section 4.3).
    if count >= REAL_COUNT and s["completed_at"] is None:
        db.execute("UPDATE sessions SET completed_at = ? WHERE id = ?", (now(), sid))
        db.commit()
    return jsonify({"ok": True, "submitted": count, "total": REAL_COUNT})


def leaderboard_rows(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        """SELECT s.id AS session_id, u.client_id, u.nickname, u.avatar_color,
                  AVG((pr.p_yes - q.outcome) * (pr.p_yes - q.outcome)) AS avg_brier,
                  SUM(CASE WHEN pr.p_yes <> 0.5 AND
                                ((pr.p_yes > 0.5 AND q.outcome = 1) OR
                                 (pr.p_yes < 0.5 AND q.outcome = 0))
                           THEN 1 ELSE 0 END) AS hits,
                  SUM(CASE WHEN pr.p_yes <> 0.5 THEN 1 ELSE 0 END) AS decisive
           FROM sessions s
           JOIN predictions pr ON pr.session_id = s.id
           JOIN questions q ON q.id = pr.question_id
           JOIN users u ON u.id = s.user_id
           WHERE s.completed_at IS NOT NULL
           GROUP BY s.id
           HAVING COUNT(pr.id) = ?""",
        (REAL_COUNT,),
    ).fetchall()
    out = []
    for r in rows:
        decisive = r["decisive"] or 0
        out.append({
            "nickname": r["nickname"],
            "avatar_color": r["avatar_color"],
            "brier": round(float(r["avg_brier"]), 4),
            "hit_rate": round(float(r["hits"]) / decisive, 3) if decisive else None,
            "session_id": r["session_id"],
        })
    out.sort(key=lambda x: (x["brier"], -(x["hit_rate"] or 0)))
    for i, item in enumerate(out):
        item["rank"] = i + 1
    return out


@app.get("/api/session/<int:sid>/result")
def session_result(sid: int):
    client_id = request.args.get("client_id", "").strip()[:64]
    db = get_db()
    s = db.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    if s is None or s["client_id"] != client_id:
        return err("session not found", 404)
    preds = db.execute(
        "SELECT * FROM predictions WHERE session_id = ? ORDER BY id", (sid,)
    ).fetchall()
    if len(preds) < REAL_COUNT:
        return err("finish all five questions first", 409)

    details = []
    total = 0.0
    hits = 0
    decisive = 0
    for pr in preds:
        q = db.execute("SELECT * FROM questions WHERE id = ?", (pr["question_id"],)).fetchone()
        y = int(q["outcome"])
        bs = (float(pr["p_yes"]) - y) ** 2
        total += bs
        if float(pr["p_yes"]) != 0.5:
            decisive += 1
            if (float(pr["p_yes"]) > 0.5 and y == 1) or (float(pr["p_yes"]) < 0.5 and y == 0):
                hits += 1
        db.execute("UPDATE predictions SET brier_score = ? WHERE id = ?", (bs, pr["id"]))
        details.append({
            "question_id": q["id"],
            "title_zh": q["title_zh"],
            "title_en": q["title_en"] or q["title_zh"],
            "p_yes": float(pr["p_yes"]),
            "outcome": y,
            "benchmark_probability": float(q["benchmark_probability"]),
            "benchmark_verified": bool(q["benchmark_verified"]),
            "benchmark_source": q["benchmark_source"],
            "benchmark_snapshot_time": q["benchmark_snapshot_time"],
            "benchmark_url": q["benchmark_url"],
            "brier": round(bs, 4),
        })

    if s["completed_at"] is None:
        db.execute("UPDATE sessions SET completed_at = ? WHERE id = ?", (now(), sid))
    db.commit()

    board = leaderboard_rows(db)
    my = next((b for b in board if b["session_id"] == sid), None)
    return jsonify({
        "ok": True,
        "details": details,
        "avg_brier": round(total / REAL_COUNT, 4),
        "hit_rate": round(hits / decisive, 3) if decisive else None,
        "neutral_count": REAL_COUNT - decisive,
        "rank": my["rank"] if my else None,
        "leaderboard": board[:50],
    })


@app.get("/api/leaderboard")
def leaderboard():
    return jsonify({"ok": True, "leaderboard": leaderboard_rows(get_db())[:50]})


@app.get("/api/dashboard")
def dashboard_data():
    db = get_db()
    total = db.execute(
        "SELECT COUNT(DISTINCT client_id) FROM predictions"
    ).fetchone()[0]
    by_cat = {
        r["actual_category"]: r["n"]
        for r in db.execute(
            "SELECT actual_category, COUNT(*) AS n FROM sessions GROUP BY actual_category"
        )
    }
    completed = db.execute(
        "SELECT COUNT(*) FROM sessions WHERE completed_at IS NOT NULL"
    ).fetchone()[0]
    per_q = [
        {
            "question_id": r["question_id"],
            "title": r["title_zh"],
            "count": r["n"],
            "avg_p": round(float(r["avg_p"]), 4),
        }
        for r in db.execute(
            """SELECT pr.question_id, q.title_zh, COUNT(*) AS n, AVG(pr.p_yes) AS avg_p
               FROM predictions pr JOIN questions q ON q.id = pr.question_id
               WHERE q.mode = 'real'
               GROUP BY pr.question_id ORDER BY pr.question_id"""
        )
    ]
    return jsonify({
        "ok": True,
        "server_time": now(),
        "total_participants": total,
        "completed_sessions": completed,
        "started_sessions": sum(by_cat.values()),
        "by_category": by_cat,
        "per_question": per_q,
    })


@app.get("/api/export.csv")
def export_csv():
    """Organizer-only archive. Deliberately restricted to the notebook itself."""
    if request.remote_addr not in ("127.0.0.1", "::1"):
        return err("organizer notebook only — open this link via 127.0.0.1", 403)
    db = get_db()
    rows = db.execute(
        """SELECT s.id AS session_id, u.nickname, s.actual_category,
                  pr.question_id, q.title_zh, pr.p_yes, q.outcome, pr.submitted_at
           FROM predictions pr
           JOIN sessions s ON s.id = pr.session_id
           JOIN questions q ON q.id = pr.question_id
           JOIN users u ON u.id = pr.user_id
           ORDER BY s.id, pr.id"""
    ).fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "session_id", "nickname", "category", "question_id", "question",
        "p_yes", "outcome", "brier", "submitted_at",
    ])
    for r in rows:
        p = float(r["p_yes"])
        y = int(r["outcome"])
        w.writerow([
            r["session_id"], r["nickname"], r["actual_category"],
            r["question_id"], r["title_zh"], round(p, 4), y,
            round((p - y) ** 2, 6), r["submitted_at"],
        ])
    # BOM so Excel on Windows opens Chinese text correctly.
    payload = "\ufeff" + buf.getvalue()
    return Response(
        payload,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=arena_export.csv"},
    )


if __name__ == "__main__":
    init_db()
    ip = lan_ip()
    print("=" * 62)
    print("  Prediction Arena  |  ICDM Youth on-site demo")
    print(f"  Phone URL : http://{ip}:5000/")
    print(f"  Dashboard : http://{ip}:5000/dashboard")
    print(f"  Database  : {DB_PATH}")
    print("  Phones must be on the SAME Wi-Fi / hotspot as this notebook.")
    print("=" * 62)
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)
