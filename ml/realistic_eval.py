"""Evaluate the serving model on the hand-written 'Realistic set' (ml/data/realistic_test.csv).

    cd ml && .venv/Scripts/python realistic_eval.py        (also called at the end of train.py)

The set was written independently of the generator templates and is never used for training or model selection.
Writes docs/realistic.json and a section in docs/metrics.md.
"""
import csv, json, math, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent
DOCS = ROOT.parent / "docs"
CSV = ROOT / "data" / "realistic_test.csv"
START, END = "<!-- realistic:start -->", "<!-- realistic:end -->"
sys.path.insert(0, str(ROOT))

# One-line reasons for the misclassifications, written by hand after reading the model's output for each
# failure (keys are sample ids from the CSV). Samples not listed here have no explanation attached.
WHY = {
    "R16": "A `while` loop that starts at index 1 silently skips the first item. No AST signal covers a while-loop start at 1 (only `range(1, ...)` "
           "is detected) and every while-based M2 example in training crashed with IndexError, so a quiet wrong sum was read as M1.",
    "R28": "The only structural signal that fired was a `return` directly in the `while` body, and the code still passes 3 of 5 tests because the first item "
           "often decides the answer; the model split 0.50 M1 vs 0.46 M5.",
    "R15": "`try/except` swallows the IndexError that normally gives M2 away, leaving only the weak `items[n]` signal; 0.28 (M2) vs 0.27 (M5) "
           "is a coin flip that happened to land right.",
    "R21": "An explicit `return None` defeats the structural 'prints but never returns' signal; only behavioural evidence (printed output, "
           "returned None) carried the M3 call.",
}
CLOSE = 0.6  # a correct prediction below this confidence is reported as a "close call"


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def run():
    import joblib
    import numpy as np
    from sklearn.metrics import accuracy_score, f1_score
    from relearn_ml.execute import run_submission
    from relearn_ml.features import featurize
    from relearn_ml.labels import LABELS, TWINS, short
    from relearn_ml.problems import load_problems

    problems = load_problems()
    rows = list(csv.DictReader(open(CSV, encoding="utf-8", newline="")))
    model = joblib.load(ROOT / "artifacts" / "diagnoser.joblib")["model"]  # the model the app serves (trained on all 22 problems)
    feats = [featurize(r["code"], problems[r["problem_id"]], run_submission(r["code"], problems[r["problem_id"]])) for r in rows]
    P = model.predict_proba(feats)
    pred = [LABELS[i] for i in P.argmax(1)]
    y = [r["label"] for r in rows]

    present = sorted(set(y))
    k = sum(a == b for a, b in zip(y, pred))
    lo, hi = wilson(k, len(y))
    twin = {}
    for a, b in TWINS:
        idx = [i for i, t in enumerate(y) if t in (a, b)]
        ok = sum(pred[i] == y[i] for i in idx)
        sw = sum(pred[i] == (b if y[i] == a else a) for i in idx)
        l2, h2 = wilson(ok, len(idx))
        twin[f"{short(a)}_{short(b)}"] = dict(n=len(idx), exact=ok / len(idx), correct=ok, swapped=sw / len(idx), ci95=[l2, h2])
    per_class = {l: dict(support=y.count(l), recall=sum(1 for i, t in enumerate(y) if t == l and pred[i] == l) / y.count(l),
                         f1=float(f1_score(y, pred, labels=[l], average="macro", zero_division=0))) for l in present}

    sig_keys = ["ret_in_loop", "ret_direct_in_loop", "reset_in_loop", "range_len_minus1", "range_start1_len", "range_bare_any",
                "sub_idx_len", "sub_idx_c1", "sub_idx_bare_param", "n_floordiv", "int_call", "sub_store_on_param", "discarded_str_method",
                "alias_of_param", "mutate_param", "mutate_alias", "list_mult_container", "append_outer_name", "print_no_return",
                "pass_frac", "exc_type", "exc_index", "none_frac", "mutated_frac", "alias_frac"]
    errors, close = [], []
    for i, r in enumerate(rows):
        conf = float(P[i].max())
        if pred[i] != y[i] or conf < CLOSE:
            order = np.argsort(-P[i])
            (errors if pred[i] != y[i] else close).append(dict(runner_up=LABELS[order[1]], id=r["id"], problem=r["problem_id"], true=y[i], predicted=pred[i], confidence=round(float(P[i][order[0]]), 3),
                               p_true=round(float(P[i][LABELS.index(y[i])]), 3), note=r["note"], code=r["code"],
                               signals={k2: (round(feats[i][k2], 2) if isinstance(feats[i][k2], float) else feats[i][k2]) for k2 in sig_keys if feats[i].get(k2)},
                               why=WHY.get(r["id"])))
    res = dict(n=len(y), accuracy=k / len(y), accuracy_ci95=[lo, hi], correct=k,
               macro_f1=float(f1_score(y, pred, labels=present, average="macro", zero_division=0)),
               twin_pairs=twin, per_class=per_class, errors=errors, close_calls=close,
               model="trained on all 22 problems",
               description="40 hand-written snippets: different structures, extra prints, comments, odd names; never used for training or selection")
    DOCS.mkdir(exist_ok=True)
    (DOCS / "realistic.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    sync_md()
    return res


def render_md(r):
    if not r:
        return "## Realistic set\n\nNot evaluated.\n"
    lo, hi = r["accuracy_ci95"]
    L = ["## Realistic set (headline)", "",
         f"{r['n']} hand-written snippets (`ml/data/realistic_test.csv`) with different structures, extra prints, comments, odd variable names "
         "and partial solutions, written independently of the generator templates and never used for training or model selection. "
         f"Evaluated once with the serving model ({r['model']}).", "",
         "| metric | value |", "|---|---|",
         f"| accuracy | **{r['accuracy']:.3f}** ({r['correct']}/{r['n']}; 95% CI {lo:.2f}-{hi:.2f}) |",
         f"| macro-F1 | **{r['macro_f1']:.3f}** |"]
    for k, t in r["twin_pairs"].items():
        L.append(f"| {k.replace('_', ' vs ')} twin-pair accuracy | **{t['exact']:.3f}** ({t['correct']}/{t['n']}; {t['swapped']:.2f} swapped with the twin) |")
    L += ["", "The template held-out score further down (1.000, held-out problems built from the same generator) is an **optimistic upper bound**, not the headline.", "",
          "With only 40 samples the intervals are wide; treat this as an honest sanity check on messier code, not a precise estimate.", ""]
    L += ["### Misclassifications", ""]
    if r["errors"]:
        L += ["| id | problem | true | predicted (conf.) | why |", "|---|---|---|---|---|"]
        for e in r["errors"]:
            L.append(f"| {e['id']} | `{e['problem']}` | {e['true'].split('_')[0]} | {e['predicted'].split('_')[0]} ({e['confidence']:.2f}) | {e.get('why') or e['note']} |")
    else:
        L.append("No misclassifications on this set.")
    if r.get("close_calls"):
        L += ["", f"### Close calls (correct, but confidence below {CLOSE:.1f})", "", "| id | problem | true | confidence | runner-up | why |", "|---|---|---|---|---|---|"]
        for e in r["close_calls"]:
            L.append(f"| {e['id']} | `{e['problem']}` | {e['true'].split('_')[0]} | {e['confidence']:.2f} | {e['runner_up'].split('_')[0]} | {e.get('why') or e['note']} |")
    return "\n".join(L) + "\n"


def sync_md():
    md = DOCS / "metrics.md"
    if not md.exists():
        return
    rj = DOCS / "realistic.json"
    r = json.loads(rj.read_text(encoding="utf-8")) if rj.exists() else None
    section = f"{START}\n{render_md(r)}{END}\n"
    s = md.read_text(encoding="utf-8")
    if START in s and END in s:
        s = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?", lambda _: section, s, flags=re.S)
    else:  # put it first: it is the headline
        s = re.sub(r"(# Diagnoser metrics\n)", lambda m: m.group(1) + "\n" + section + "\n", s, count=1) if "# Diagnoser metrics" in s else section + s
    md.write_text(s, encoding="utf-8")


if __name__ == "__main__":
    r = run()
    print(f"REALISTIC SET n={r['n']}  accuracy={r['accuracy']:.3f} (95% CI {r['accuracy_ci95'][0]:.2f}-{r['accuracy_ci95'][1]:.2f})  macro-F1={r['macro_f1']:.3f}")
    for k, t in r["twin_pairs"].items():
        print(f"  twin {k}: {t['correct']}/{t['n']} exact={t['exact']:.3f} swapped={t['swapped']:.3f}")
    print("  per-class recall:", {k.split('_')[0]: round(v['recall'], 2) for k, v in r["per_class"].items()})
    for e in r["errors"]:
        print(f"\n[{e['id']}] {e['problem']}: true={e['true'].split('_')[0]} pred={e['predicted'].split('_')[0]} conf={e['confidence']} p_true={e['p_true']}  ({e['note']})")
        print("   signals:", e["signals"])
        print("   " + e["code"].replace("\n", "\n   "))
