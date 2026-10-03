"""POST /explain - deterministic explanation of a wrong submission (no AI).

1. where_it_went_wrong: the first failing test in plain words (or the error, explained simply).
2. proposed_fix: a minimal fix of THEIR code - shown only if it passes every test (fixer verifies it in the sandbox).
3. best_solution: a verified reference solution for the problem, with a one-line reason.
"""
import time

from relearn_ml import fixer
from relearn_ml.labels import MISCONCEPTIONS
from .concept import call_text, fmt

EXCEPTIONS = {  # plain-English meaning of common Python errors (12th-grade level)
    "NameError": "it uses a name Python does not know - maybe a typo, or a variable that was never created",
    "TypeError": "it combines values that do not work together - for example adding text to a number, or changing a string in place",
    "IndexError": "it asks for a position that the list or string does not have - positions start at 0 and end at length - 1",
    "ZeroDivisionError": "it divides by zero",
    "KeyError": "it looks up a key that is not in the dictionary",
    "AttributeError": "it uses a method or property that this kind of value does not have",
    "ValueError": "it got a value of the right type but with content it cannot use",
    "UnboundLocalError": "it uses a variable before giving it a value",
    "RecursionError": "the function keeps calling itself and never stops",
    "Timeout": "it never finished - probably a loop that does not stop",
    "IndentationError": "the spaces at the start of a line do not line up the way Python expects",
    "SyntaxError": "Python could not read the code - check brackets, colons and quotes",
}
STATUS_WORDS = {
    "syntax_error": "Python could not read your code",
    "timeout": "your code never finished (probably a loop that does not stop)",
    "memory_limit": "your code used too much memory (for example a list that keeps growing)",
    "no_function": "the function with the expected name is missing",
    "rejected": "your code uses something that is not allowed here",
    "crash": "your code stopped unexpectedly",
}
TOTAL_FIX_BUDGET_S = 4.0
WHY = {  # one template per misconception, at most 2 sentences, 12th-grade wording
    "M1_RANGE_OFF_BY_ONE": "range(a, b) stops just before b, so your loop never reaches the last number. To include b, write range(a, b + 1).",
    "M2_INDEX_FROM_ONE": "Python counts positions from 0, so the first item is x[0] and the last is x[len(x) - 1]. Using len(x), or starting at 1, goes one step too far.",
    "M3_PRINT_NOT_RETURN": "print only shows a value on the screen; it does not give it back, so {fn} returns None. Use return to hand the answer back.",
    "M4_ACCUMULATOR_RESET": "Your running total is set back to its starting value inside the loop, so it forgets everything except the last item. Set it once, before the loop.",
    "M5_RETURN_IN_LOOP": "return ends the whole function at once, so your loop stops after the first item. Put the return after the loop has finished.",
    "M6_FLOAT_DIVISION": "// throws away everything after the decimal point (7 // 2 is 3, not 3.5). Use / when you need the exact answer.",
    "M7_STRING_MUTABLE": "A string can never be changed in place, so s.upper() makes a NEW string and s[i] = 'x' is not allowed. Keep the new string by writing s = s.upper().",
    "M8_LIST_ALIASING": "b = a does not copy a list - both names point to the SAME list, so changing one changes the other. Make a real copy with a[:] or list(a).",
}
WHY_UNKNOWN = "This does not look like one of the 8 common mistakes we know, so the best guide is the failing check above: compare what your code gave with what it should give."


def plain_exception(name):
    return EXCEPTIONS.get(name, "it stopped with an error")


def where_it_went_wrong(problem, res):
    if res["status"] != "ok":
        return dict(kind="error", status=res["status"], words=f"Before any test could finish, {STATUS_WORDS.get(res['status'], 'something went wrong')}.",
                    technical=res.get("error"))
    bad = [(i, t) for i, t in enumerate(res["tests"]) if not t["ok"]]
    if not bad:
        return None
    i, t = bad[0]
    call = call_text(problem["fn"], t["args"])
    if t.get("exc"):
        line = f" (line {t['line']})" if t.get("line") else ""
        words = f"For {call}, your function stopped with {t['exc']}{line}: {plain_exception(t['exc'])}."
    elif t.get("none"):
        words = f"For {call}, your function gave back nothing (None), but it should give back {fmt(t['expected'])}."
    elif t.get("mutated") and problem["checks"].get("no_mutate"):
        words = f"For {call}, your function changed the list it was given. It must leave the original unchanged."
    elif t.get("alias"):
        words = f"For {call}, the rows of your grid are all the same list: changing one cell changes every row."
    else:
        words = f"For {call}, your function gave back {fmt(t['got'])}, but it should give back {fmt(t['expected'])}."
    return dict(kind="test", test_index=i, call=call, expected=fmt(t["expected"]), got=None if t.get("exc") else fmt(t["got"]),
                error=t.get("exc"), technical=t.get("msg"), words=words, failing_tests=len(bad), total_tests=len(res["tests"]))


def why(label, problem, names=None):
    """Section 2 of the explanation card. `label` None -> the bug is unknown."""
    if label in WHY:
        return dict(label=label, name=(names or {}).get(label), text=WHY[label].format(fn=problem["fn"]))
    return dict(label=None, name=None, text=WHY_UNKNOWN)


def explain(problem, code, run, label_order=None, reference=None):
    """Everything an explanation card needs. `label_order`: misconception labels to try first when looking for a fix."""
    code = code.replace("\r\n", "\n")
    res = run(code, problem)
    where = where_it_went_wrong(problem, res)
    fix = None
    if where is not None and res["status"] == "ok":
        deadline = time.monotonic() + TOTAL_FIX_BUDGET_S
        order = [l for l in (label_order or []) if l in MISCONCEPTIONS] + [l for l in MISCONCEPTIONS if l not in (label_order or [])]
        for label in order:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            found = fixer.find_fix(code, problem, label, run, time_budget=min(3.0, left))
            if found and not fixer.same_code(found["code"], code):  # only a fix that passes every test is ever shown
                la, lb = fixer.diff_lines(code, found["code"])
                fix = dict(code=found["code"], highlight_lines=la, fixed_highlight_lines=lb, rule=found["rule"], label=label,
                           verified=dict(passed=found["passed"], total=found["total"]))
                break
    best = None
    if reference:
        rr = run(reference, problem)
        n = len(rr.get("tests", []))
        ok = rr["status"] == "ok" and n and all(t["ok"] for t in rr["tests"])
        best = dict(code=reference, verified=dict(passed=sum(t["ok"] for t in rr.get("tests", [])), total=n),
                    reason=f"A clear, correct solution - it passes all {n} tests." if ok else "Reference solution.")
    return dict(problem_id=problem["id"], all_tests_pass=where is None, where_it_went_wrong=where, proposed_fix=fix, best_solution=best)
