"""Problem-specific concept check: "predict what YOUR code does".

Built from three inputs - (1) the problem, (2) the learner's submitted code, (3) the diagnosed misconception - so the
snippet uses the learner's own function name, variables and structure. The correct option is the code's ACTUAL behaviour
on a small input, obtained by running the learner's code in the sandbox, so the answer is right by construction.

If a question cannot be built (or fails validation) a question from a pool of 4 per misconception is used instead
(never the same one twice in a row for a learner), and every fallback is logged and counted (GET /concept-stats).
"""
import hashlib
import json
import logging
import random
from collections import OrderedDict

from .paths import CONTENT  # imported first: puts ml/ on sys.path
from relearn_ml import fixer  # noqa: E402
from . import db  # noqa: E402

log = logging.getLogger("relearn.concept")
POOL = {k: v for k, v in json.loads((CONTENT / "concept_pool.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
CACHE_MAX = 500
_CACHE = OrderedDict()  # (problem_id, misconception, code hash) -> question


class Unavailable(Exception):
    """A problem-specific question can't be built for this submission (reason is logged)."""
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class InvalidQuestion(Exception):
    pass


def _seed(*parts):
    return int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def fmt(v):
    if isinstance(v, float):
        v = round(v, 4)
    return repr(v)


def call_text(fn, args):
    return f"{fn}({', '.join(repr(a) for a in args)})"


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _candidates(actual, expected, args, exc=None):
    """Plausible wrong answers (as display strings) for a question whose true answer is `actual` (or an exception)."""
    out = [fmt(expected)]
    if exc:
        other = "TypeError" if exc != "TypeError" else "IndexError"
        return out + ["None", f"raises {other}", "raises ValueError"] + [fmt(a) for a in args[:1]]
    if _is_num(actual):
        near = [actual + 1, actual - 1] + ([expected + 1, expected - 1] if _is_num(expected) else [])
        if _is_num(expected) and actual >= 0 and expected >= 0:
            near = [v for v in near if v >= 0]  # no negative distractors for a non-negative quantity
        out += [fmt(v) for v in near] + [fmt(actual * 2), "0"]
    elif isinstance(actual, bool):
        out += [fmt(not actual), "None"]
    elif isinstance(actual, list):
        if len(actual) > 1:
            out += [fmt(actual[:-1]), fmt(actual[1:]), fmt(actual[::-1])]
        out += ["[]", fmt(actual + actual[-1:])] if actual else []
    elif isinstance(actual, str):
        out += [fmt(a) for a in args if isinstance(a, str) and a != actual]
        out += [fmt(actual.upper()), fmt(actual.lower()), fmt(actual + "!")]
    out += ["None", "raises TypeError", "raises ValueError", "0"]
    return out


def _options(actual_s, actual, expected, args, rng, extra_first=(), exc=None):
    opts, seen = [actual_s], {actual_s}
    for c in list(extra_first) + _candidates(actual, expected, args, exc):
        if c not in seen:
            seen.add(c)
            opts.append(c)
        if len(opts) == 4:
            break
    if len(opts) < 4:
        raise Unavailable("cannot_build_4_distinct_options")
    rng.shuffle(opts)
    return opts, opts.index(actual_s)


def _culprit(code, label, fn):
    lines = fixer.locate(code, label, fn)
    src = code.replace("\r\n", "\n").split("\n")
    txt = src[lines[0] - 1].strip() if lines and lines[0] <= len(src) else ""
    return (txt[:60] + "...") if len(txt) > 60 else txt


def _explanation(label, ctx):
    c = f"`{ctx['culprit']}`" if ctx["culprit"] else "your code"
    a, e, call = ctx["actual_s"], ctx["expected_s"], ctx["call"]
    if label == "M1_RANGE_OFF_BY_ONE":
        return f"`{call}` gives {a}, not {e}: {c} stops before its end value, so the last value is never used."
    if label == "M2_INDEX_FROM_ONE":
        if ctx["exc"] == "IndexError":
            return f"Python counts from 0, so that position does not exist: {c} runs past the end and raises IndexError."
        return f"Indexes start at 0, so {c} picks the wrong position: {a} instead of {e}."
    if label == "M3_PRINT_NOT_RETURN":
        return f"`{ctx['fn']}` only prints; it has no `return`, so the call gives back None and y is None. What appears on screen is output, not a value."
    if label == "M4_ACCUMULATOR_RESET":
        return f"{c} runs on every pass of the loop, so the total restarts each time and only the last item counts: {a} instead of {e}."
    if label == "M5_RETURN_IN_LOOP":
        return f"{c} is inside the loop, so the function ends on the first pass: {a} instead of {e}."
    if label == "M6_FLOAT_DIVISION":
        return f"{c} drops the decimals (`//` floors, `int()` truncates): {a} instead of {e}."
    if label == "M7_STRING_MUTABLE":
        if ctx["exc"] == "TypeError":
            return f"Strings cannot be changed in place: {c} raises TypeError."
        return f"A string method returns a NEW string and {c} throws it away, so the result stays {a} instead of {e}."
    if label == "M8_LIST_ALIASING":
        return f"{c} gives the same list a second name instead of a copy, so changing it also changes the original: {a}."
    return f"Your function gives {a}, not {e}."


CRASH_IS_THE_POINT = ("M2_INDEX_FROM_ONE", "M7_STRING_MUTABLE")  # IndexError / TypeError are how these show up


def _trivial(a):
    return (_is_num(a) and abs(a) < 2) or (isinstance(a, (list, str)) and len(a) < 2)


def _rank(t, label):
    """Lower is better: avoid crashes unless they are the point, avoid degenerate inputs, then prefer small inputs."""
    crash = 1 if (t.get("exc") and label not in CRASH_IS_THE_POINT) else 0
    return (crash, sum(_trivial(a) for a in t["args"]), len(json.dumps(t["args"])))


def generate(problem, code, label, run):
    """Builds the question or raises Unavailable(reason)."""
    res = run(code, problem)
    if res["status"] != "ok":
        raise Unavailable(f"student_code_{res['status']}")
    bad = [t for t in res["tests"] if not t["ok"]]
    if not bad:
        raise Unavailable("no_failing_test")
    if label == "M8_LIST_ALIASING":
        bad = [t for t in bad if t.get("mutated") or t.get("alias")] or bad
    t = min(bad, key=lambda x: _rank(x, label))
    fn, title, args, params = problem["fn"], problem["title"], t["args"], problem["params"]
    rng = random.Random(_seed(problem["id"], label, code))
    code_block = code.strip("\n")
    head = f'Here is your function for "{title}":\n\n{code_block}\n\n'
    call = call_text(fn, args)
    exc = t.get("exc")
    expected = t["expected"]
    ctx = dict(fn=fn, call=call, culprit=_culprit(code, label, fn), exc=exc, expected_s=fmt(expected))

    if label == "M8_LIST_ALIASING" and problem["checks"].get("independent_rows") and isinstance(t["got"], list) and t["got"] and all(isinstance(r, list) and r for r in t["got"]):
        got = t["got"]
        shared = bool(t.get("alias"))
        after = [[9] + r[1:] for r in got] if shared else [[9] + got[0][1:]] + [list(r) for r in got[1:]]
        right = [[9] + got[0][1:]] + [list(r) for r in got[1:]]
        actual, actual_s = after, fmt(after)
        text = head + f"Now run:\n\ng = {call}\ng[0][0] = 9\nprint(g)\n\nWhat does it print?"
        extra = [fmt(right), fmt(got), fmt(got[:-1] + [[9] + got[-1][1:]])]
        ctx.update(actual_s=actual_s)
    elif label == "M8_LIST_ALIASING" and t.get("mutated") and t.get("args_after") is not None:
        i = next(k for k, a in enumerate(args) if isinstance(a, list))
        var = params[i]
        after = t["args_after"][i]
        decl = f"{var} = {args[i]!r}\n"
        call_v = f"{fn}({', '.join(params[k] if k == i else repr(a) for k, a in enumerate(args))})"
        actual, actual_s = after, fmt(after)
        text = head + f"Now run:\n\n{decl}result = {call_v}\n\nWhat is `{var}` afterwards?"
        extra = [fmt(args[i])]
        expected = args[i]
        ctx.update(actual_s=actual_s, expected_s=fmt(args[i]))
    elif label == "M3_PRINT_NOT_RETURN" and t.get("none"):
        actual, actual_s = None, "None"
        text = head + f"After `y = {call}`, what is y?"
        extra = [fmt(expected), "an error", "0"]
        ctx.update(actual_s="None")
    else:
        if exc:
            actual, actual_s = f"raises {exc}", f"raises {exc}"
            text = head + f"What happens when you call `{call}`?"
        else:
            actual, actual_s = t["got"], fmt(t["got"])
            text = head + f"What does `{call}` return?"
        extra = []
        ctx.update(actual_s=actual_s)
    opts, ans = _options(actual_s, actual, expected, args, rng, extra, exc)
    return dict(question=text, question_text=text.split("\n\n")[-1], code=code_block, options=opts, answer=ans, answerIndex=ans,
                explanation=_explanation(label, ctx), source="generated", based_on=dict(problem=problem["id"], call=call))


def validate(q):
    """Schema check shared by generated and pool questions; raises InvalidQuestion."""
    if not isinstance(q, dict):
        raise InvalidQuestion("not an object")
    if not isinstance(q.get("question"), str) or not q["question"].strip():
        raise InvalidQuestion("empty question")
    o = q.get("options")
    if not (isinstance(o, list) and len(o) == 4 and all(isinstance(x, str) and x.strip() for x in o) and len(set(o)) == 4):
        raise InvalidQuestion("options must be 4 distinct non-empty strings")
    if not (isinstance(q.get("answer"), int) and not isinstance(q["answer"], bool) and 0 <= q["answer"] < 4):
        raise InvalidQuestion("answer index out of range")
    if q.get("answerIndex", q["answer"]) != q["answer"]:
        raise InvalidQuestion("answerIndex != answer")
    if not isinstance(q.get("explanation"), str) or not q["explanation"].strip():
        raise InvalidQuestion("empty explanation")
    return q


def pick_pool(label, learner_id, problem_id):
    pool = POOL[label]
    n = len(pool)
    key = learner_id or "anon"
    last = db.concept_last(key, label)
    idx = _seed(problem_id, label) % n if last is None else (last + 1) % n  # rotation: never the same one twice in a row
    db.concept_set_last(key, label, idx)
    q = dict(pool[idx], answerIndex=pool[idx]["answer"], source="fallback_pool", pool_index=idx)
    return validate(q), idx


def for_learner(problem, code, label, run, learner_id=None):
    """Returns (question, source) with source in {'generated', 'cache', 'fallback_pool'}.

    Cache key = (problem_id, misconception, hash of the code). The code hash is part of the key because the question
    embeds the learner's own code: keying on problem + misconception alone would show one learner another's code."""
    key = (problem["id"], label, hashlib.sha1(code.replace("\r\n", "\n").strip().encode()).hexdigest())
    if key in _CACHE:
        _CACHE.move_to_end(key)
        db.log_concept(learner_id, problem["id"], label, "cache")
        return dict(_CACHE[key], source="cache"), "cache"
    try:
        q = validate(generate(problem, code, label, run))
        _CACHE[key] = q
        while len(_CACHE) > CACHE_MAX:
            _CACHE.popitem(last=False)
        db.log_concept(learner_id, problem["id"], label, "generated")
        return dict(q), "generated"
    except Unavailable as e:
        reason = e.reason
    except InvalidQuestion as e:
        reason = f"invalid_question: {e}"
    except Exception as e:  # never let question generation break the intervention panel
        reason = f"exception: {type(e).__name__}: {e}"
    q, idx = pick_pool(label, learner_id, problem["id"])
    log.warning("concept check FALLBACK problem=%s misconception=%s reason=%s pool_index=%d learner=%s",
                problem["id"], label, reason, idx, learner_id or "anon")
    db.log_concept(learner_id, problem["id"], label, "fallback_pool", reason, idx)
    return q, "fallback_pool"
