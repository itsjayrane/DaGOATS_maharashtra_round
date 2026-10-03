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
        CREATE TABLE IF NOT EXISTS concept_events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, learner_id TEXT, problem_id TEXT,
            misconception TEXT, source TEXT, reason TEXT, pool_idx INTEGER);
        CREATE TABLE IF NOT EXISTS concept_state(learner_id TEXT, misconception TEXT, last_idx INTEGER, PRIMARY KEY(learner_id, misconception));
        CREATE TABLE IF NOT EXISTS hint_events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, learner_id TEXT, problem_id TEXT, level INTEGER,
            source TEXT, reason TEXT, misconception TEXT, situation TEXT);
        CREATE INDEX IF NOT EXISTS ix_hint ON hint_events(learner_id, ts);
        CREATE TABLE IF NOT EXISTS custom_problems(id TEXT PRIMARY KEY, created REAL, problem TEXT);
        """)
    if os.environ.get("RELEARN_SEED_DEMO") == "1":
        seed_demo()


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


# ---- concept-check bookkeeping: every generated / cached / fallback question is logged so fallback frequency is visible
def log_concept(learner_id, problem_id, misconception, source, reason=None, pool_idx=None):
    with _lock, conn() as c:
        c.execute("INSERT INTO concept_events(ts, learner_id, problem_id, misconception, source, reason, pool_idx) VALUES(?,?,?,?,?,?,?)",
                  (time.time(), learner_id or "anon", problem_id, misconception, source, reason, pool_idx))


def concept_last(learner_id, misconception):
    with conn() as c:
        r = c.execute("SELECT last_idx FROM concept_state WHERE learner_id=? AND misconception=?", (learner_id, misconception)).fetchone()
        return r["last_idx"] if r else None


def concept_set_last(learner_id, misconception, idx):
    with _lock, conn() as c:
        c.execute("INSERT OR REPLACE INTO concept_state(learner_id, misconception, last_idx) VALUES(?,?,?)", (learner_id, misconception, idx))


def concept_stats(recent=20):
    with conn() as c:
        by_source = {r["source"]: r["n"] for r in c.execute("SELECT source, COUNT(*) n FROM concept_events GROUP BY source")}
        reasons = {(r["reason"] or "").split(":")[0]: r["n"] for r in c.execute("SELECT reason, COUNT(*) n FROM concept_events WHERE source='fallback_pool' GROUP BY reason")}
        rows = [dict(ts=r["ts"], learner_id=r["learner_id"], problem_id=r["problem_id"], misconception=r["misconception"], reason=r["reason"], pool_idx=r["pool_idx"])
                for r in c.execute("SELECT * FROM concept_events WHERE source='fallback_pool' ORDER BY id DESC LIMIT ?", (recent,))]
    total = sum(by_source.values())
    fb = by_source.get("fallback_pool", 0)
    return dict(total=total, by_source=by_source, fallback_count=fb, fallback_rate=(fb / total) if total else 0.0, fallback_reasons=reasons, recent_fallbacks=rows)


# ---- hint log: one row per hint request (so the Dashboard can show hint usage later)
def log_hint(learner_id, problem_id, level, source, reason=None, misconception=None, situation=None):
    with _lock, conn() as c:
        c.execute("INSERT INTO hint_events(ts, learner_id, problem_id, level, source, reason, misconception, situation) VALUES(?,?,?,?,?,?,?,?)",
                  (time.time(), learner_id or "anon", problem_id, level, source, reason, misconception, situation))


def learner_hints(learner_id, recent=20):
    lid = learner_id or "anon"
    with conn() as c:
        by_problem = {r["problem_id"]: dict(requests=r["n"], max_level=r["mx"]) for r in
                      c.execute("SELECT problem_id, COUNT(*) n, MAX(level) mx FROM hint_events WHERE learner_id=? AND source != 'none' GROUP BY problem_id", (lid,))}
        by_source = {r["source"]: r["n"] for r in c.execute("SELECT source, COUNT(*) n FROM hint_events WHERE learner_id=? GROUP BY source", (lid,))}
        rows = [dict(ts=r["ts"], problem_id=r["problem_id"], level=r["level"], source=r["source"], reason=r["reason"], misconception=r["misconception"])
                for r in c.execute("SELECT * FROM hint_events WHERE learner_id=? ORDER BY id DESC LIMIT ?", (lid, recent))]
    return dict(learner_id=lid, total=sum(by_source.values()), by_source=by_source, by_problem=by_problem, recent=rows)


# ---- RELEARN_SEED_DEMO=1: a clearly labelled SYNTHETIC learner so the Dashboard / Insights are not empty in a demo
DEMO_LEARNER = "demo-learner (synthetic)"
_DEMO = [  # (minutes ago, kind, problem, label, passed, resolved, misconception, mastery_after)
    (180, "diagnose", "sum_list", "M5_RETURN_IN_LOOP", 0, 0, "M5_RETURN_IN_LOOP", 0.25),
    (172, "reassess", "product", "M5_RETURN_IN_LOOP", 0, 0, "M5_RETURN_IN_LOOP", 0.21),
    (165, "reassess", "product", "CORRECT", 1, 1, "M5_RETURN_IN_LOOP", 0.80),
    (120, "diagnose", "sum_to_n", "M1_RANGE_OFF_BY_ONE", 0, 0, "M1_RANGE_OFF_BY_ONE", 0.25),
    (110, "diagnose", "one_to_n", "M1_RANGE_OFF_BY_ONE", 0, 0, "M1_RANGE_OFF_BY_ONE", 0.13),
    (60, "diagnose", "square", "M3_PRINT_NOT_RETURN", 0, 0, "M3_PRINT_NOT_RETURN", 0.25),
    (30, "diagnose", "average", "M6_FLOAT_DIVISION", 0, 0, "M6_FLOAT_DIVISION", 0.25),
    (10, "diagnose", "average", "CORRECT", 1, 0, None, None),
]


def seed_demo():
    """Idempotent: creates the synthetic learner only if it does not exist yet. Every row is marked synthetic."""
    with _lock, conn() as c:
        if c.execute("SELECT 1 FROM learners WHERE id=?", (DEMO_LEARNER,)).fetchone():
            return False
        ensure_learner(c, DEMO_LEARNER)
        now = time.time()
        for mins, kind, pid, label, passed, resolved, misc, after in _DEMO:
            c.execute("INSERT INTO attempts(learner_id, ts, kind, problem_id, misconception, label, confidence, passed, resolved, mastery_after, code, detail)"
                      " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (DEMO_LEARNER, now - mins * 60, kind, pid, misc, label, 0.95, passed, resolved, after, "", json.dumps({"synthetic": True})))
            if misc and after is not None:
                c.execute("UPDATE mastery SET value=?, resolved=? WHERE learner_id=? AND misconception=?", (after, int(bool(resolved)), DEMO_LEARNER, misc))
        return True
