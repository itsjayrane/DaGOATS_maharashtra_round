"""Progressive hints (POST /hint): problem-specific, 3 levels (1 WHAT with a real example, 2 HOW, 3 a first-line NUDGE,
never the full solution).

Where they come from:
- built-in problems: curated content/hints.json;
- custom / AI-drafted problems: hints stored with the problem (hintgen: AI-written if configured and valid, else built
  from the verified solution); older custom problems get deterministic hints on their first /hint call (backfill);
- a confidently diagnosed misconception (not "unknown") switches to that misconception's curated variant.
The hint reacts to the learner's current code: unless it is still the starter, the server re-runs the tests and adds
the first failing test in words as a `prefix` ("Right now f([3, 1]) gives None but should give 1.").
Every request is logged (hint_events) for the Dashboard.
"""
import json
import logging
import time
from datetime import datetime, timezone

from .paths import CONTENT
from . import custom, db, hintgen
from .concept import call_text, fmt
from .diagnoser import is_no_attempt
from .explain import STATUS_WORDS

log = logging.getLogger("relearn.hint")
HINTS = {k: v for k, v in json.loads((CONTENT / "hints.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
NO_HINT_MSG = "All tests pass, no hint needed."
STARTED = time.time()


def problem_hints(problem, reference=None):
    """The problem's own 3 hints: curated (built-in), stored (custom), or generated now from the verified solution and
    stored (backfill for custom problems created before hints existed). Never the generic templates."""
    curated = HINTS["problems"].get(problem["id"])
    if curated:
        return curated
    if problem.get("hints"):
        return problem["hints"]
    ref = reference or problem.get("reference")
    hints = hintgen.deterministic(problem, ref) if ref else None
    if hints and problem.get("custom"):
        problem["hints"] = hints
        custom.update(problem)
    return hints or {"1": f"Read the problem again and work out the answer for the example by hand.", "2": "Write your plan as steps in plain words.",
                     "3": "Start with the first step of your plan as one line of code."}


def pick(problem, level, label=None):
    """(text, kind): the misconception variant when a bug was recognised, otherwise the problem's own hint."""
    if label in HINTS["misconceptions"]:
        return HINTS["misconceptions"][label][str(level)], "misconception"
    return problem_hints(problem)[str(level)], "problem"


def failing_prefix(problem, res):
    """The first failing test in words, or what stops the code from running."""
    if res["status"] != "ok":
        return f"Right now {STATUS_WORDS.get(res['status'], 'your code does not run')}."
    for t in res["tests"]:
        if t["ok"]:
            continue
        call = call_text(problem["fn"], t["args"])
        if t.get("exc"):
            return f"Right now {call} stops with {t['exc']} but should give {fmt(t['expected'])}."
        got = "None" if t.get("none") else fmt(t["got"])
        return f"Right now {call} gives {got} but should give {fmt(t['expected'])}."
    return None


def _confident_misconception(d):
    if not d or not d.get("label") or d["label"] == "CORRECT" or d.get("unknown"):
        return None
    return d["label"] if (d.get("confidence") or 0) >= 0.5 and d["label"] in HINTS["misconceptions"] else None


def get_hint(problem, code, level, learner_id, run, diagnose=None):
    """Returns dict(level, hint, source, kind); source is 'curated', or 'none' when every test already passes."""
    code = code.replace("\r\n", "\n")
    situation, label, prefix = "wrong", None, None
    if is_no_attempt(code, problem["fn"]):
        situation = "start"
    else:
        res = run(code, problem)  # the server re-runs the tests itself: client-sent results are never trusted
        prefix = failing_prefix(problem, res)
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
    return dict(level=level, hint=text, source="curated", kind=kind, prefix=prefix)


def status():
    return dict(llm="none", hints="curated", problems_with_hints=len(HINTS["problems"]),
                misconception_variants=len(HINTS["misconceptions"]),
                backend_started_at=datetime.fromtimestamp(STARTED, timezone.utc).isoformat())


def log_startup():
    log.info("hints: curated and offline (%d problems, %d misconception variants)", len(HINTS["problems"]), len(HINTS["misconceptions"]))
