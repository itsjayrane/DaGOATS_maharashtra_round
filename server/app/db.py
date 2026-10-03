"""SQLite persistence: learners' mastery (0..1 per misconception) and attempt history."""
import json, os, sqlite3, threading, time
from .paths import ROOT

DB_PATH = os.environ.get("RELEARN_DB", str(ROOT / "server" / "relearn.db"))
_lock = threading.Lock()
MISCONCEPTIONS = ["M1_RANGE_OFF_BY_ONE", "M2_INDEX_FROM_ONE", "M3_PRINT_NOT_RETURN", "M4_ACCUMULATOR_RESET",
                  "M5_RETURN_IN_LOOP", "M6_FLOAT_DIVISION", "M7_STRING_MUTABLE", "M8_LIST_ALIASING"]
PRIOR = 0.5  # unknown


def conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS learners(id TEXT PRIMARY KEY, created REAL);
        CREATE TABLE IF NOT EXISTS mastery(learner_id TEXT, misconception TEXT, value REAL, resolved INTEGER DEFAULT 0,
            PRIMARY KEY(learner_id, misconception));
        CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY AUTOINCREMENT, learner_id TEXT, ts REAL, kind TEXT,
            problem_id TEXT, misconception TEXT, label TEXT, confidence REAL, passed INTEGER, resolved INTEGER,
            mastery_after REAL, code TEXT, detail TEXT);
        CREATE INDEX IF NOT EXISTS ix_att ON attempts(learner_id, ts);
        """)


def ensure_learner(c, lid):
    c.execute("INSERT OR IGNORE INTO learners VALUES(?,?)", (lid, time.time()))
    for m in MISCONCEPTIONS:
        c.execute("INSERT OR IGNORE INTO mastery(learner_id, misconception, value) VALUES(?,?,?)", (lid, m, PRIOR))


def get_mastery(c, lid, m):
    r = c.execute("SELECT value, resolved FROM mastery WHERE learner_id=? AND misconception=?", (lid, m)).fetchone()
    return (r["value"], bool(r["resolved"])) if r else (PRIOR, False)


def record(lid, kind, problem_id, label, confidence, passed, code, detail, misconception=None, resolved=False, update=None):
    """update: fn(value, resolved) -> (value, resolved) applied to `misconception`; returns mastery after."""
    with _lock, conn() as c:
        ensure_learner(c, lid)
        after = None
        if misconception and update:
            v, res = get_mastery(c, lid, misconception)
            v2, res2 = update(v, res)
            c.execute("UPDATE mastery SET value=?, resolved=? WHERE learner_id=? AND misconception=?", (v2, int(res2), lid, misconception))
            after = v2
        c.execute("INSERT INTO attempts(learner_id, ts, kind, problem_id, misconception, label, confidence, passed, resolved, mastery_after, code, detail)"
                  " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  (lid, time.time(), kind, problem_id, misconception, label, confidence, int(passed), int(resolved), after, code, json.dumps(detail, default=str)))
        return after


def last_diagnosed_problem(lid, misconception):
    with conn() as c:
        r = c.execute("SELECT problem_id FROM attempts WHERE learner_id=? AND kind='diagnose' AND label=? ORDER BY id DESC LIMIT 1",
                      (lid, misconception)).fetchone()
        return r["problem_id"] if r else None


def learner(lid):
    with conn() as c:
        if not c.execute("SELECT 1 FROM learners WHERE id=?", (lid,)).fetchone():
            return None
        mastery = {r["misconception"]: dict(mastery=round(r["value"], 3), resolved=bool(r["resolved"]))
                   for r in c.execute("SELECT * FROM mastery WHERE learner_id=?", (lid,))}
        hist = [dict(id=r["id"], ts=r["ts"], kind=r["kind"], problem_id=r["problem_id"], misconception=r["misconception"], label=r["label"],
                     confidence=r["confidence"], passed=bool(r["passed"]), resolved=bool(r["resolved"]), mastery_after=r["mastery_after"])
                for r in c.execute("SELECT * FROM attempts WHERE learner_id=? ORDER BY id", (lid,))]
        return dict(learner_id=lid, mastery=mastery, history=hist)
