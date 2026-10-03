"""Wraps the trained model: probabilities + human-readable evidence (model feature contributions + observed behaviour)."""
import ast

import joblib
import numpy as np

from .paths import MODEL_PATH
from relearn_ml.features import featurize  # noqa: E402  (ml/ is put on sys.path by paths.py)
from relearn_ml.labels import LABELS, TWIN_OF  # noqa: E402

# feature key -> sentence; "{v}" is the raw value, "{pct}" the value as a percentage
DESC = {
    "ret_direct_in_loop": "A `return` sits directly in the loop body, so the function exits on the first pass.",
    "ret_in_loop": "There is a `return` inside a loop.",
    "ret_if_else_both": "An if/else inside the loop returns in both branches, so only the first item is ever examined.",
    "reset_in_loop": "A variable is set back to its starting value inside the loop, discarding earlier progress.",
    "init_before_loop": "The accumulator is initialised before the loop.",
    "ret_after_loop": "The result is returned after the loop finishes.",
    "range_len_minus1": "`range(... len(x) - 1)` stops one item early, skipping the last element.",
    "range_start1_len": "A loop over a list's indexes starts at 1, skipping the first element (indexes start at 0).",
    "range_start1_bare": "`range(1, n)` stops before n, so n itself is never included.",
    "range_onearg_bare": "`range(n)` ends at n - 1 and starts at 0.",
    "range_3arg_bare": "`range(start, stop, step)` stops before `stop`, so the upper limit is excluded.",
    "range_bare_any": "A range() stop value has no `+ 1`, so the end value is excluded.",
    "while_lt": "A while loop uses `<` where the end value should be included.",
    "sub_idx_len": "Indexing with `len(x)` is one past the last valid index (it raises IndexError).",
    "sub_idx_c1": "Index 1 is used as if it were the first element.",
    "sub_idx_bare_param": "A list is indexed directly by a count (`items[n]`) without subtracting 1.",
    "n_floordiv": "Floor division `//` is used, which drops the fractional part.",
    "floordiv_const": "A constant floor division such as `9 // 5` evaluates to 1, not 1.8.",
    "floordiv_nonconst": "A quotient is computed with `//`, discarding the decimal part.",
    "int_call": "`int(...)` truncates the quotient.",
    "sub_store_on_param": "Item assignment on a parameter (`s[i] = ...`) - strings cannot be changed in place.",
    "sub_store": "Item assignment is used (`x[i] = ...`).",
    "discarded_str_method": "A string method's return value is discarded (`s.upper()` alone does nothing to `s`).",
    "alias_of_param": "`new = old` only creates a second name for the SAME list, not a copy.",
    "mutate_alias": "The list is modified through an alias, which also changes the original.",
    "mutate_param": "The argument list itself is modified in place.",
    "list_mult_container": "`[row] * n` repeats a reference to the same inner list, not independent copies.",
    "append_outer_name": "The same row object, created outside the loop, is appended on every iteration.",
    "print_no_return": "The function prints a value but never returns one.",
    "print_and_return": "The function both prints and returns.",
    "exc_type": "TypeError was raised on {pct} of the tests.",
    "exc_index": "IndexError was raised on {pct} of the tests.",
    "none_frac": "The function returned None on {pct} of the tests.",
    "printed_frac": "The function printed output on {pct} of the tests.",
    "mutated_frac": "The function changed its input argument on {pct} of the tests.",
    "alias_frac": "Returned rows/cells share memory on {pct} of the tests.",
    "typemis_frac": "The result had the wrong type on {pct} of the tests (e.g. int instead of float).",
    "wrong_noexc_frac": "The code ran without errors but returned wrong values on {pct} of the tests.",
    "pass_frac": "{pct} of the tests pass.",
    "all_pass": "Every test passes.",
}


NO_ATTEMPT_MSG = "This is still the starter code - write your solution, then submit."


def is_no_attempt(code, fn_name):
    """True when the target function's body is empty: only `pass`, `...`, a docstring or a bare constant.

    The model has no 'no attempt' class, and a function that returns nothing looks exactly like print-without-return
    (M3), so an untouched starter would otherwise be diagnosed as M3 for every problem."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == fn_name), None)
    if fn is None:
        return False
    return all(isinstance(s, ast.Pass) or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)) for s in fn.body)


class DiagnoserService:
    def __init__(self):
        art = joblib.load(MODEL_PATH)
        self.model = art["model"]
        self.config = art.get("config")
        self.names = self.model.feature_names()

    def _contrib(self, feats, k, top=4):
        X = self.model._X([feats])
        F = X.shape[1]
        dense = X.toarray()[0]
        c = np.asarray(self.model.clf.booster_.predict(X.toarray(), pred_contrib=True))[0].reshape(len(LABELS), F + 1)[k][:F]
        out = []
        for i in np.argsort(-c):
            if c[i] <= 0.05 or len(out) >= top:
                break
            name = self.names[i]
            if name in DESC and dense[i] != 0:
                v = float(dense[i])
                out.append(dict(kind="model", feature=name, value=v, weight=round(float(c[i]), 3),
                                text=DESC[name].format(v=int(v) if v == int(v) else round(v, 2), pct=f"{round(v * 100)}%")))
        return out

    def diagnose(self, code, problem, exec_res):
        if exec_res["status"] != "ok":
            return dict(label=None, confidence=None, probabilities=None, ambiguous=False, runner_up=None,
                        evidence=[dict(kind="error", text=exec_res.get("error", exec_res["status"]))])
        if is_no_attempt(code, problem["fn"]):
            return dict(label=None, confidence=None, probabilities=None, ambiguous=False, runner_up=None, no_attempt=True,
                        error=NO_ATTEMPT_MSG, evidence=[dict(kind="error", text=NO_ATTEMPT_MSG)])
        feats = featurize(code, problem, exec_res)
        P = self.model.predict_proba([feats])[0]
        order = np.argsort(-P)
        k = int(order[0]); label = LABELS[k]
        runner = LABELS[int(order[1])]
        ambiguous = bool(P[order[0]] < 0.6 or (TWIN_OF.get(label) == runner and P[order[0]] - P[order[1]] < 0.25))
        tests = exec_res["tests"]
        ev = []
        if label == "CORRECT":
            ev.append(dict(kind="behavior", text=f"All {len(tests)} tests pass and no misconception signature was found."))
        else:
            ev += self._contrib(feats, k)
            bad = next((t for t in tests if not t["ok"]), None)
            if bad:
                what = f"raised {bad['exc']}" if bad["exc"] else ("returned None" if bad["none"] else f"returned {bad['got']!r}")
                ev.append(dict(kind="behavior", text=f"{problem['fn']}({', '.join(map(repr, bad['args']))}) {what}; expected {bad['expected']!r}."))
        return dict(label=label, confidence=round(float(P[k]), 4), probabilities={LABELS[i]: round(float(P[i]), 4) for i in range(len(LABELS))},
                    ambiguous=ambiguous, runner_up=dict(label=runner, probability=round(float(P[order[1]]), 4)), evidence=ev)
