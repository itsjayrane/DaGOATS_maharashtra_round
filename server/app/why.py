"""'Why the model thinks so': the top features behind a diagnosis, from LightGBM's own per-feature contributions
(pred_contrib=True, i.e. TreeSHAP - no extra dependencies), described in plain English for learners and teachers."""
import numpy as np

from relearn_ml.labels import LABELS

TOP = 3
MISTAKE = {"M1": "an off-by-one range()", "M2": "counting positions from 1", "M3": "printing instead of returning",
           "M4": "resetting a total inside the loop", "M5": "returning inside the loop", "M6": "whole-number division",
           "M7": "changing a string in place", "M8": "two names for one list"}

# feature -> (sentence when the feature is present / non-zero, sentence when it is absent / zero)
PLAIN = {
    "has_return": ("your function has a return statement", "your function never returns a value"),
    "n_return": ("your function returns a value", "your function never returns a value"),
    "ret_in_loop": ("there is a return inside a loop", "there is no return inside a loop"),
    "ret_direct_in_loop": ("a return sits directly in the loop body, so the loop stops after the first item", "no return sits directly in a loop body"),
    "ret_if_else_both": ("both branches of an if/else inside the loop return, so only the first item is checked", None),
    "ret_after_loop": ("the result is returned after the loop finishes", "nothing is returned after the loop"),
    "reset_in_loop": ("a variable is set back to its start value inside the loop", "no variable is reset inside the loop"),
    "init_before_loop": ("the running total starts before the loop", "no running total is set up before the loop"),
    "range_len_minus1": ("range(len(x) - 1) stops one item early", None),
    "range_start1_len": ("the loop over positions starts at 1, skipping the first item", None),
    "range_start1_bare": ("range(1, n) stops before n", None),
    "range_onearg_bare": ("range(n) runs from 0 to n - 1", None),
    "range_3arg_bare": ("range(start, stop, step) stops before stop", None),
    "range_bare_any": ("a range() end value has no + 1, so the end is left out", "every range() end is adjusted with + 1"),
    "while_lt": ("a while loop uses < where the end might need to be included", None),
    "sub_idx_len": ("x[len(x)] asks for a position one past the end", None),
    "sub_idx_c1": ("x[1] is used as if it were the first item", None),
    "sub_idx_bare_param": ("a list is indexed directly by a count, like items[n]", None),
    "n_floordiv": ("// (whole-number division) is used", "no // division is used"),
    "floordiv_const": ("a constant like 9 // 5 becomes 1, not 1.8", None),
    "floordiv_nonconst": ("a result is divided with //, dropping the decimals", None),
    "int_call": ("int(...) cuts off the decimals", None),
    "n_truediv": ("/ (exact division) is used", None),
    "sub_store_on_param": ("the code tries to change a character with s[i] = ...", None),
    "sub_store": ("the code assigns to a position, x[i] = ...", None),
    "discarded_str_method": ("a string method's result is thrown away, e.g. s.upper() on its own", None),
    "alias_of_param": ("new = old makes a second name for the same list, not a copy", None),
    "alias_assign": ("one list name is assigned to another", None),
    "mutate_param": ("the list you were given is changed in place", "the input list is never changed"),
    "mutate_alias": ("the list is changed through a second name", None),
    "copy_idiom": ("the list is copied before it is changed", "the list is never copied"),
    "list_mult_container": ("[row] * n repeats the same inner list", None),
    "append_outer_name": ("the same row object is appended every time", None),
    "print_no_return": ("your function prints but never returns", None),
    "print_and_return": ("your function both prints and returns", None),
    "n_print": ("your function calls print", "your function does not print"),
    "pass_frac": ("{pct} of the tests pass", "none of the tests pass"),
    "all_pass": ("every test passes", "at least one test fails"),
    "any_pass": ("some tests pass", "no test passes"),
    "none_frac": ("your function gave back nothing (None) on {pct} of the tests", "your function always gives back a value"),
    "printed_frac": ("your function printed something on {pct} of the tests", None),
    "exc_type": ("a TypeError happened on {pct} of the tests", None),
    "exc_index": ("an IndexError happened on {pct} of the tests", None),
    "exc_other": ("an error happened on {pct} of the tests", None),
    "exc_timeout": ("the code ran too long on {pct} of the tests", None),
    "mutated_frac": ("your function changed its input on {pct} of the tests", "your function never changed its input"),
    "alias_frac": ("rows of the result share memory on {pct} of the tests", None),
    "typemis_frac": ("the answer had the wrong type on {pct} of the tests (e.g. a whole number instead of a decimal)", None),
    "wrong_noexc_frac": ("the code ran without errors but gave wrong answers on {pct} of the tests", "no test gave a wrong answer silently"),
    "n_nodes": ("the code's size ({v} syntax pieces)", None),
    "n_for": ("the code uses {v} for loop(s)", "the code has no for loop"),
    "n_while": ("the code uses a while loop", "the code has no while loop"),
    "status_bad": ("the code could not run normally", "the code ran normally"),
    "sig_any": ("{v} sign(s) of a common mistake were found", "no sign of any of the 8 common mistakes was found"),
    "p_ret_float": ("this problem expects a decimal answer", None),
    "p_str_param": ("this problem works on text", None),
    "p_list_param": ("this problem works on a list", None),
    "p_ret_list": ("this problem returns a list", None),
    "p_ret_bool": ("this problem returns True or False", None),
    "p_no_mutate": ("this problem must not change its input", None),
}
for _m, _what in MISTAKE.items():
    PLAIN[f"sig_{_m}"] = (f"{{v}} sign(s) of {_what} were found", f"no sign of {_what} was found")


def plain_english(name, v):
    on, off = PLAIN.get(name, (None, None))
    v = float(v)
    text = on if v != 0 else off
    if text is None:  # no wording for this direction: say it neutrally
        return f"the pattern '{name.replace('_', ' ')}' is {'present' if v else 'absent'}"
    if "{v} sign(s)" in text:
        text = text.replace("{v} sign(s)", "a sign" if v == 1 else "{v} signs").replace(" were found", " was found" if v == 1 else " were found")
    return text.format(v=int(v) if v == int(v) else round(v, 2), pct=f"{round(v * 100)}%")


def why_features(model, names, X, k, top=TOP):
    """Top positive contributions to class k: [{name, value, plain_english, contribution}] (contribution in log-odds)."""
    dense = X.toarray()
    c = np.asarray(model.clf.booster_.predict(dense, pred_contrib=True))[0].reshape(len(LABELS), X.shape[1] + 1)[k][:-1]
    out = []
    for i in np.argsort(-c)[:top]:
        if c[i] <= 0:
            break
        out.append(dict(name=names[i], value=round(float(dense[0, i]), 3), plain_english=plain_english(names[i], dense[0, i]),
                        contribution=round(float(c[i]), 3)))
    return out
