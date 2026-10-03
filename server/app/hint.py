"""Progressive hints (POST /hint): curated, offline and deterministic - no AI.

content/hints.json holds, for every problem, three hand-written levels (1 = what the output should be, 2 = which
concept/operation to use, 3 = a one-line code nudge, never the full solution), plus a three-level variant per
misconception (M1..M8) that is used when the diagnoser confidently recognises the learner's bug.
Every request is logged (hint_events) for the Dashboard.
"""
import json
import logging
import time
from datetime import datetime, timezone

from .paths import CONTENT
from . import db
from .diagnoser import is_no_attempt

log = logging.getLogger("relearn.hint")
HINTS = {k: v for k, v in json.loads((CONTENT / "hints.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
NO_HINT_MSG = "All tests pass, no hint needed."
STARTED = time.time()


def pick(problem, level, label=None):
    """(text, kind): the misconception variant when a bug was recognised, otherwise the problem's own hint."""
    if label in HINTS["misconceptions"]:
        return HINTS["misconceptions"][label][str(level)], "misconception"
    return (HINTS["problems"].get(problem["id"]) or HINTS["generic"])[str(level)], "problem"


def _confident_misconception(d):
    if not d or not d.get("label") or d["label"] == "CORRECT" or d.get("unknown"):
        return None
    return d["label"] if (d.get("confidence") or 0) >= 0.5 and d["label"] in HINTS["misconceptions"] else None


def get_hint(problem, code, level, learner_id, run, diagnose=None):
    """Returns dict(level, hint, source, kind); source is 'curated', or 'none' when every test already passes."""
    code = code.replace("\r\n", "\n")
    situation, label = "wrong", None
    if is_no_attempt(code, problem["fn"]):
        situation = "start"
    else:
        res = run(code, problem)  # the server re-runs the tests itself: client-sent results are never trusted
        if res["status"] != "ok":
            situation = "error"
        elif res["tests"] and all(t["ok"] for t in res["tests"]):
            db.log_hint(learner_id, problem["id"], level, "none", "all_tests_pass", None, "passing")
            return dict(level=level, hint=NO_HINT_MSG, source="none", kind="none")
        elif diagnose:
            try:
                label = _confident_misconception(diagnose(code, problem, res))
            except Exception:  # a hint must never fail because the diagnosis did
                label = None
    text, kind = pick(problem, level, label)
    db.log_hint(learner_id, problem["id"], level, "curated", None, label, situation)
    return dict(level=level, hint=text, source="curated", kind=kind)


def status():
    return dict(llm="none", hints="curated", problems_with_hints=len(HINTS["problems"]),
                misconception_variants=len(HINTS["misconceptions"]),
                backend_started_at=datetime.fromtimestamp(STARTED, timezone.utc).isoformat())


def log_startup():
    log.info("hints: curated and offline (%d problems, %d misconception variants)", len(HINTS["problems"]), len(HINTS["misconceptions"]))
