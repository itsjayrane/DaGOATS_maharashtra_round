"""Model comparison, feature ablation and calibration - all on the SAME grouped split as train.py.

    cd ml && .venv/Scripts/python eval_models.py        (separate from train.py: keeps the Render build fast)

Split: every model is trained on the 18 training problems only (the 4 HOLDOUT problems are never seen) and scored on
  - the 4 held-out problems (template samples), and
  - the hand-written Realistic set (ml/data/realistic_test.csv) - evaluation only, never used to train, select or tune.
Top-1 predictions are scored (an OTHER_BUG prediction on a Realistic sample counts as an error).

Writes docs/model_comparison.json, docs/ablation.json, docs/calibration.json.
"""
import csv, json, pathlib, time

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from relearn_ml.execute import run_submission
from relearn_ml.features import dense_matrix, featurize
from relearn_ml.labels import L2I, LABELS, TWINS, short
from relearn_ml.model import Diagnoser
from relearn_ml.problems import load_problems
from realistic_eval import bootstrap
from train import HOLDOUT, calibrate

ROOT = pathlib.Path(__file__).resolve().parent
DOCS = ROOT.parent / "docs"


def scores(y, pred, boot=False):
    """y, pred: label-index arrays. Macro-F1 over the classes present in y."""
    y, pred = np.asarray(y), np.asarray(pred)
    present = sorted(set(y.tolist()))
    out = dict(n=int(len(y)), accuracy=float(accuracy_score(y, pred)),
               macro_f1=float(f1_score(y, pred, labels=present, average="macro", zero_division=0)),
               per_class_recall={LABELS[c]: float((pred[y == c] == c).mean()) for c in present})
    twins = {}
    for a, b in TWINS:
        m = np.isin(y, [L2I[a], L2I[b]])
        if m.any():
            twins[f"{short(a)}_{short(b)}"] = dict(n=int(m.sum()), exact=float((pred[m] == y[m]).mean()),
                                                   swapped=float((pred[m] == (L2I[a] + L2I[b] - y[m])).mean()))
    out["twin_pairs"] = twins
    if boot:
        out["bootstrap"] = bootstrap(y, pred, present)
    return out


class Majority:
    name = "Majority baseline"

    def fit(self, rows, labels):
        vals, counts = np.unique([L2I[l] for l in labels], return_counts=True)
        self.c = int(vals[counts.argmax()])
        return self

    def predict(self, rows):
        return np.full(len(rows), self.c)


class LogReg:
    """Logistic regression on exactly the production features (standardised), class-balanced."""
    name = "Logistic regression"

    def fit(self, rows, labels):
        X, self.keys = dense_matrix(rows)
        self.m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced"))
        self.m.fit(X, [L2I[l] for l in labels])
        return self

    def predict(self, rows):
        return self.m.predict(dense_matrix(rows)[0])


class LGBM:
    def __init__(self, name="LightGBM (production)", **cfg):
        self.name, self.cfg = name, dict(dict(use_tfidf=False), **cfg)

    def fit(self, rows, labels):
        self.m = Diagnoser(**self.cfg).fit(rows, labels)
        return self

    def predict(self, rows):
        return self.m.raw_proba(rows).argmax(1)  # temperature scaling does not change the top-1 class


def ece_and_bins(P, y, n_bins=10):
    conf, pred = P.max(1), P.argmax(1)
    correct = (pred == y).astype(float)
    edges = np.linspace(0, 1, n_bins + 1)
    bins, ece = [], 0.0
    for i in range(n_bins):
        m = (conf > edges[i]) & (conf <= edges[i + 1]) if i else (conf >= 0) & (conf <= edges[1])
        n = int(m.sum())
        b = dict(lo=float(edges[i]), hi=float(edges[i + 1]), n=n,
                 confidence=float(conf[m].mean()) if n else None, accuracy=float(correct[m].mean()) if n else None)
        if n:
            ece += n / len(y) * abs(b["accuracy"] - b["confidence"])
        bins.append(b)
    return float(ece), bins


def main():
    t0 = time.time()
    rows = [json.loads(l) for l in open(ROOT / "data" / "dataset.jsonl", encoding="utf-8")]
    tr = [r for r in rows if r["problem"] not in HOLDOUT]
    te = [r for r in rows if r["problem"] in HOLDOUT]
    ytr, yte = np.array([L2I[r["label"]] for r in tr]), np.array([L2I[r["label"]] for r in te])
    problems = load_problems()
    real = list(csv.DictReader(open(ROOT / "data" / "realistic_test.csv", encoding="utf-8", newline="")))
    rf = [featurize(r["code"], problems[r["problem_id"]], run_submission(r["code"], problems[r["problem_id"]])) for r in real]
    yr = np.array([L2I[r["label"]] for r in real])
    labels_tr = [r["label"] for r in tr]
    split = dict(train=f"{len(tr)} samples from {len(set(r['problem'] for r in tr))} training problems",
                 holdout=f"{len(te)} samples from held-out problems {HOLDOUT}", realistic=f"{len(real)} hand-written snippets")

    # ---- 1) model comparison ------------------------------------------------------------------------------------
    comp = []
    for m in (Majority(), LogReg(), LGBM()):
        m.fit(tr, labels_tr)
        comp.append(dict(model=m.name, realistic=scores(yr, m.predict(rf), boot=True), holdout=scores(yte, m.predict(te))))
        r = comp[-1]["realistic"]
        print(f"{m.name:24s} realistic acc={r['accuracy']:.3f} macro-F1={r['macro_f1']:.3f}   holdout acc={comp[-1]['holdout']['accuracy']:.3f}")
    (DOCS / "model_comparison.json").write_text(json.dumps(dict(
        description="Same grouped split for every model: trained on the training problems only, scored on the held-out "
                    "problems and on the hand-written Realistic set (top-1, no abstention; never used for training or "
                    "selection). Bootstrap: 1000 resamples of the Realistic set. The headline Realistic numbers elsewhere "
                    "use the serving model, which is trained on all 22 problems.",
        split=split, models=comp), indent=1), encoding="utf-8")

    # ---- 2) feature-group ablation ------------------------------------------------------------------------------
    groups = {
        "all (AST + execution + task flags)": dict(),
        "AST only": dict(use_exec=False, use_prob=False),
        "execution only": dict(use_ast=False, use_prob=False),
        "task flags only": dict(use_ast=False, use_exec=False),
        "without AST": dict(use_ast=False),
        "without execution": dict(use_exec=False),
        "without task flags": dict(use_prob=False),
    }
    abl = []
    for name, cfg in groups.items():
        m = LGBM(name, **cfg).fit(tr, labels_tr)
        r, h = scores(yr, m.predict(rf)), scores(yte, m.predict(te))
        abl.append(dict(features=name, realistic_macro_f1=r["macro_f1"], realistic_accuracy=r["accuracy"],
                        holdout_macro_f1=h["macro_f1"], holdout_accuracy=h["accuracy"]))
        print(f"  ablation {name:36s} realistic macro-F1={r['macro_f1']:.3f}  holdout macro-F1={h['macro_f1']:.3f}")
    (DOCS / "ablation.json").write_text(json.dumps(dict(
        description="LightGBM retrained on the training problems with feature groups removed; scored on the Realistic set "
                    "(and the held-out problems). Report only - the production feature set was chosen by grouped CV on the "
                    "training problems, not by these numbers.", split=split, results=abl), indent=1), encoding="utf-8")

    # ---- 3) calibration -----------------------------------------------------------------------------------------
    T = json.loads((ROOT / "artifacts" / "threshold.json").read_text(encoding="utf-8"))["temperature"]
    gtr = np.array([r["problem"] for r in tr])
    oof = np.zeros((len(tr), len(LABELS)))
    for a, b in GroupKFold(5).split(tr, ytr, gtr):
        oof[b] = Diagnoser(use_tfidf=False).fit([tr[i] for i in a], [labels_tr[i] for i in a]).raw_proba([tr[i] for i in b])
    hold_raw = LGBM().fit(tr, labels_tr).m.raw_proba(te)
    cal = {}
    for key, P, y, note in (("out_of_fold", oof, ytr, "grouped 5-fold CV over the training problems - the data T was fitted on"),
                            ("holdout", hold_raw, yte, "the 4 held-out problems - never used to fit T (independent check)")):
        eb, bb = ece_and_bins(P, y)
        ea, ba = ece_and_bins(calibrate(P, T), y)
        cal[key] = dict(note=note, n=int(len(y)), ece_before=eb, ece_after=ea, bins_before=bb, bins_after=ba)
        print(f"  calibration {key:12s} ECE before={eb:.3f} after={ea:.3f}")
    (DOCS / "calibration.json").write_text(json.dumps(dict(
        description="Reliability of the top-class probability (10 equal-width bins) before and after temperature scaling "
                    "(T from ml/artifacts/threshold.json). ECE = sample-weighted mean |accuracy - confidence| over bins.",
        temperature=T, **cal), indent=1), encoding="utf-8")
    print(f"done in {time.time() - t0:.0f} s -> docs/model_comparison.json, docs/ablation.json, docs/calibration.json")


if __name__ == "__main__":
    main()
