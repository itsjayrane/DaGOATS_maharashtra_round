"""Common-mistakes analytics for teachers (no AI): what wrong answers learners actually submit.

Source: /diagnose attempts that did not pass. Named mistakes are grouped by misconception; 'unknown' verdicts are
clustered by their failing-test signature (which tests fail + which exceptions). Learners are counted by a salted
SHA-256 hash (env INSIGHTS_SALT) - raw ids never leave this module.
"""
import csv
import hashlib
import io
import json
import os
import time
from collections import Counter, defaultdict

from . import paths  # noqa: F401  (puts ml/ on sys.path)
from relearn_ml import fixer
from . import db
from .concept import call_text, fmt

DEV_SALT = "relearn-dev-salt"  # override in production with env INSIGHTS_SALT
EXAMPLES = 2
HIGHLIGHT_BUDGET_S = 4.0
_HL_CACHE = {}
_SIG_CACHE = {}


def learner_hash(lid):
    salt = os.environ.get("INSIGHTS_SALT") or DEV_SALT
    return hashlib.sha256(f"{salt}:{lid}".encode()).hexdigest()[:12]


def _rows(problem_id=None, include_synthetic=False, learner_id=None):
    q = ("SELECT learner_id, ts, problem_id, label, confidence, passed, code, detail FROM attempts"
         " WHERE kind='diagnose' AND label IS NOT NULL AND label != 'CORRECT' AND passed=0")
    args = []
    if problem_id:
        q += " AND problem_id=?"; args.append(problem_id)
    if learner_id:
        q += " AND learner_id=?"; args.append(learner_id)
    with db.conn() as c:
        rows = [dict(r) for r in c.execute(q + " ORDER BY id", args)]
    out = []
    for r in rows:
        d = json.loads(r["detail"] or "{}")
        r["synthetic"] = bool(d.get("synthetic"))
        if r["synthetic"] and not include_synthetic:
            continue
        r["verdict"] = d.get("verdict") or ("misconception" if r["label"].startswith("M") else "unknown")
        if r["verdict"] == "correct":
            continue
        r["fail_sig"] = d.get("fail_sig")
        out.append(r)
    return out


def _fail_sig(r, problem, run):
    """Failing tests + exceptions: stored at diagnose time; recomputed (cached) for older rows."""
    if r.get("fail_sig"):
        return r["fail_sig"]
    key = (problem["id"], hashlib.sha1((r["code"] or "").encode()).hexdigest())
    if key not in _SIG_CACHE:
        res = run(r["code"] or "", problem)
        tests = res.get("tests") or []
        _SIG_CACHE[key] = dict(failing=[i for i, t in enumerate(tests) if not t["ok"]], status=res["status"],
                               exc=sorted({t["exc"] for t in tests if t.get("exc")}))
    return _SIG_CACHE[key]


def _highlight(code, problem, label, run, deadline):
    """Lines a verified minimal fix changes (empty if none is found in the time budget)."""
    key = (problem["id"], label, hashlib.sha1(code.encode()).hexdigest())
    if key not in _HL_CACHE:
        left = deadline - time.monotonic()
        if left <= 0 or not label.startswith("M"):
            return []
        found = fixer.find_fix(code, problem, label, run, time_budget=min(2.0, left))
        _HL_CACHE[key] = fixer.diff_lines(code, found["code"])[0] if found else []
    return _HL_CACHE[key]


def _examples(rows, get_problem, run, deadline):
    seen, out = set(), []
    for r in sorted((r for r in rows if (r["code"] or "").strip()), key=lambda r: len(r["code"])):
        norm = "\n".join(l.rstrip() for l in r["code"].strip().splitlines())
        if norm in seen:
            continue
        seen.add(norm)
        p = get_problem(r["problem_id"])
        out.append(dict(problem_id=r["problem_id"], code=r["code"], learner=learner_hash(r["learner_id"]), synthetic=r["synthetic"],
                        highlight_lines=_highlight(r["code"], p, r["label"], run, deadline)))
        if len(out) == EXAMPLES:
            break
    return out


def _typical_test(rows, get_problem, run):
    c, excs = Counter(), Counter()
    for r in rows:
        sig = _fail_sig(r, get_problem(r["problem_id"]), run)
        if sig.get("failing"):
            c[(r["problem_id"], sig["failing"][0])] += 1
        excs.update(sig.get("exc") or [])
    if not c:
        return None
    (pid, i), n = c.most_common(1)[0]
    p = get_problem(pid)
    t = p["tests"][i]
    call = call_text(p["fn"], t["args"])
    words = f"{n} of {len(rows)} attempt(s) first fail the check {call}, which should give {fmt(t['expected'])}."
    if excs:
        e, k = excs.most_common(1)[0]
        words += f" {k} stop(s) with {e}."
    return dict(problem_id=pid, test_index=i, call=call, expected=fmt(t["expected"]), words=words)


def _group(rows, total, get_problem, run, deadline, extra):
    return dict(**extra, count=len(rows), share=round(len(rows) / total, 4) if total else 0.0,
                unique_learners=len({r["learner_id"] for r in rows}), synthetic=sum(r["synthetic"] for r in rows),
                problems=dict(Counter(r["problem_id"] for r in rows).most_common()),
                examples=_examples(rows, get_problem, run, deadline), typical_failing_test=_typical_test(rows, get_problem, run))


def common_mistakes(get_problem, misc, run, problem_id=None, include_synthetic=False):
    deadline = time.monotonic() + HIGHLIGHT_BUDGET_S
    rows = _rows(problem_id, include_synthetic)
    total = len(rows)
    named, unknown = defaultdict(list), defaultdict(list)
    for r in rows:
        if r["verdict"] == "misconception" and r["label"] in misc:
            named[r["label"]].append(r)
        else:
            sig = _fail_sig(r, get_problem(r["problem_id"]), run)
            unknown[(r["problem_id"], tuple(sig.get("failing") or []), tuple(sig.get("exc") or []), sig.get("status"))].append(r)
    mistakes = [_group(rs, total, get_problem, run, deadline,
                       dict(label=m, name=misc[m]["name"], lesson_summary=misc[m]["summary"]))
                for m, rs in sorted(named.items(), key=lambda kv: -len(kv[1]))]
    clusters = []
    for (pid, failing, exc, status), rs in sorted(unknown.items(), key=lambda kv: -len(kv[1])):
        n = len(get_problem(pid)["tests"])
        if status and status != "ok":
            sig_words = f"code does not run ({status})"
        else:
            sig_words = f"fails test(s) {', '.join(str(i + 1) for i in failing)} of {n}" + (f", raising {', '.join(exc)}" if exc else "")
        clusters.append(_group(rs, total, get_problem, run, deadline,
                               dict(signature=dict(problem_id=pid, failing=list(failing), exc=list(exc)), signature_words=sig_words)))
    return dict(problem_id=problem_id, total_wrong_attempts=total, unique_learners=len({r["learner_id"] for r in rows}),
                include_synthetic=include_synthetic, mistakes=mistakes, unknown_clusters=clusters)


def export_csv(include_code=False, include_synthetic=False):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["learner_hash", "time_utc", "problem_id", "label", "verdict", "confidence", "synthetic"] + (["code"] if include_code else []))
    for r in _rows(None, include_synthetic):
        w.writerow([learner_hash(r["learner_id"]), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r["ts"])), r["problem_id"], r["label"],
                    r["verdict"], r["confidence"], int(r["synthetic"])] + ([r["code"]] if include_code else []))
    return buf.getvalue()


def learner_patterns(learner_id, problems, misc, min_attempts=2, min_problems=2, top=3):
    """Misconceptions a learner keeps making: >= 2 attempts across >= 2 different problems (top 3), + a next problem."""
    rows = [r for r in _rows(learner_id=learner_id, include_synthetic=True) if r["verdict"] == "misconception" and r["label"] in misc]
    by = defaultdict(list)
    for r in rows:
        by[r["label"]].append(r)
    pats = []
    for m, rs in by.items():
        probs = sorted({r["problem_id"] for r in rs})
        if len(rs) >= min_attempts and len(probs) >= min_problems:
            pats.append(dict(label=m, name=misc[m]["name"], attempts=len(rs), problems=probs, lesson_summary=misc[m]["summary"],
                             last_ts=max(r["ts"] for r in rs)))
    pats.sort(key=lambda p: (-p["attempts"], -p["last_ts"]))
    pats = pats[:top]
    nxt = None
    if pats:
        with db.conn() as c:
            tried = {r["problem_id"] for r in c.execute("SELECT DISTINCT problem_id FROM attempts WHERE learner_id=?", (learner_id,))}
        code = pats[0]["label"].split("_")[0]
        cand = [p for p in problems if code in p.get("tags", []) and p["id"] not in tried]
        if cand:
            p = cand[0]
            nxt = dict(problem_id=p["id"], title=p["title"], misconception=pats[0]["label"],
                       reason=f"You have hit \"{pats[0]['name']}\" on {len(pats[0]['problems'])} problems - this one practises the same idea.")
    return dict(learner_id=learner_id, patterns=pats, suggested_next=nxt)
