"""Leave-one-misconception-out: what does the app do with a misconception it has NEVER seen?

    cd ml && .venv/Scripts/python eval_unseen.py        (separate from train.py: keeps the Render build fast)

For each M in M1..M8: 3-fold cross-validation grouped by problem; the model is trained WITHOUT any M samples
(production feature set, production temperature and UNKNOWN_T from ml/artifacts/threshold.json), then scored on the
test-fold problems:
  - held-out-class rows: share flagged "unknown" (good) vs confidently labelled as something else (dangerous)
  - known rows (other classes): share wrongly flagged unknown (false-unknown rate)
Writes docs/unseen_eval.json.
"""
import json, pathlib, time
from collections import Counter

import numpy as np
from sklearn.model_selection import GroupKFold

from relearn_ml.labels import LABELS, L2I, MISCONCEPTIONS
from relearn_ml.model import Diagnoser

ROOT = pathlib.Path(__file__).resolve().parent
DOCS = ROOT.parent / "docs"


def calibrate(P, T):
    z = np.log(np.clip(P, 1e-9, 1)) / T
    z -= z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def main():
    t0 = time.time()
    thr = json.loads((ROOT / "artifacts" / "threshold.json").read_text(encoding="utf-8"))
    T, U = thr["temperature"], thr["unknown_t"]
    rows = [json.loads(l) for l in open(ROOT / "data" / "dataset.jsonl", encoding="utf-8")]
    y = np.array([L2I[r["label"]] for r in rows])
    g = np.array([r["problem"] for r in rows])
    O = L2I["OTHER_BUG"]
    per, fu_num, fu_den = {}, 0, 0
    for c in MISCONCEPTIONS:
        ci = L2I[c]
        held = dict(n=0, unknown=0, dangerous=0, as_=Counter())
        known_flagged = known_n = 0
        for a, b in GroupKFold(3).split(rows, y, g):
            train = [rows[i] for i in a if y[i] != ci]
            m = Diagnoser(use_tfidf=False).fit(train, [r["label"] for r in train])
            P = calibrate(m.raw_proba([rows[i] for i in b]), T)
            top, conf = P.argmax(1), P.max(1)
            unk = (top == O) | (conf < U)
            yb = y[b]
            hm = yb == ci
            held["n"] += int(hm.sum())
            held["unknown"] += int(unk[hm].sum())
            held["dangerous"] += int((~unk[hm]).sum())
            held["as_"].update(LABELS[t] for t in top[hm & ~unk])
            km = (yb != ci) & (yb != O)
            known_n += int(km.sum())
            known_flagged += int(unk[km].sum())
        per[c] = dict(n=held["n"], flagged_unknown=held["unknown"] / held["n"], confidently_mislabelled=held["dangerous"] / held["n"],
                      mislabelled_as=dict(held["as_"].most_common(3)), false_unknown_on_known=known_flagged / known_n)
        fu_num += known_flagged
        fu_den += known_n
        print(f"{c:22s} n={held['n']:4d}  flagged unknown={per[c]['flagged_unknown']:.2f}  dangerous={per[c]['confidently_mislabelled']:.2f}"
              f"  false-unknown on known={per[c]['false_unknown_on_known']:.2f}  as={dict(held['as_'].most_common(2))}")
    out = dict(
        description="Leave-one-misconception-out: the model never sees the held-out misconception; 3-fold CV grouped by problem; "
                    "production feature set, temperature and UNKNOWN_T. 'flagged_unknown' is the desired behaviour; "
                    "'confidently_mislabelled' means a confident, wrong diagnosis (dangerous).",
        unknown_t=U, temperature=T, per_class=per,
        mean_flagged_unknown=float(np.mean([v["flagged_unknown"] for v in per.values()])),
        mean_confidently_mislabelled=float(np.mean([v["confidently_mislabelled"] for v in per.values()])),
        false_unknown_rate_on_known=fu_num / fu_den, seconds=round(time.time() - t0))
    DOCS.mkdir(exist_ok=True)
    (DOCS / "unseen_eval.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"mean flagged unknown={out['mean_flagged_unknown']:.3f}  mean dangerous={out['mean_confidently_mislabelled']:.3f}  "
          f"false-unknown on known={out['false_unknown_rate_on_known']:.3f}  ({out['seconds']} s) -> docs/unseen_eval.json")


if __name__ == "__main__":
    main()
