"""Train the Re:Learn misconception diagnoser (LightGBM) with an unseen-problem holdout.

    cd ml && .venv/Scripts/python train.py

Split is BY problem_id: 4 whole problems are held out and never seen in training or model selection.
Feature set (text-free vs +TF-IDF) is chosen by 5-fold grouped CV on the 18 training problems only.
Outputs: ml/artifacts/diagnoser.joblib (all 22 problems, for serving), ml/artifacts/diagnoser_holdout.joblib,
         docs/metrics.md, docs/confusion_matrix.png
"""
import json, pathlib, warnings
import joblib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold

from relearn_ml.labels import LABELS, L2I, TWINS
from relearn_ml.model import Diagnoser, fit_temperature

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parent
DOCS = ROOT.parent / "docs"
ART = ROOT / "artifacts"

# One problem per misconception family where possible; sum_list carries all four twin labels (M1,M2,M4,M5).
HOLDOUT = ["sum_list", "average", "shout", "double_all"]
CONFIGS = {
    "AST + execution + task flags": dict(use_tfidf=False),
    "TF-IDF + AST + execution + task flags": dict(),
}
INK, MUTED, ACCENT = "#1f2937", "#6b7280", "#2b6cb0"


def load():
    return [json.loads(l) for l in open(ROOT / "data" / "dataset.jsonl", encoding="utf-8")]


def fit(rows, cfg):
    return Diagnoser(**cfg).fit(rows, [r["label"] for r in rows])


def main():
    DOCS.mkdir(exist_ok=True); ART.mkdir(exist_ok=True)
    rows = load()
    tr = [r for r in rows if r["problem"] not in HOLDOUT]
    te = [r for r in rows if r["problem"] in HOLDOUT]
    ytr = np.array([L2I[r["label"]] for r in tr]); yte = np.array([L2I[r["label"]] for r in te])
    gtr = np.array([r["problem"] for r in tr])
    print(f"train: {len(tr)} samples / {len(set(gtr))} problems   held-out: {len(te)} samples / {len(HOLDOUT)} problems")

    # --- model selection on TRAIN problems only (grouped CV) ---
    cv = {}; oof_by = {}
    for name, cfg in CONFIGS.items():
        P = np.zeros((len(tr), len(LABELS)))
        for a, b in GroupKFold(5).split(tr, ytr, gtr):
            P[b] = fit([tr[i] for i in a], cfg).raw_proba([tr[i] for i in b])
        cv[name] = f1_score(ytr, P.argmax(1), average="macro"); oof_by[name] = P
        print(f"  CV (train problems) {name:40s} macro-F1={cv[name]:.3f}")
    best = max(cv, key=cv.get)
    T = fit_temperature(oof_by[best], ytr)
    print(f"selected: {best}   temperature T={T:.2f}")

    # --- train on train split, score on unseen problems ---
    model = fit(tr, CONFIGS[best]); model.T = T
    P = model.predict_proba(te); pred = P.argmax(1)
    acc = accuracy_score(yte, pred); mf1 = f1_score(yte, pred, average="macro", labels=sorted(set(yte)))
    present = sorted(set(yte) | set(pred))
    rep = classification_report(yte, pred, labels=list(range(len(LABELS))), target_names=LABELS, output_dict=True, zero_division=0)

    twin = {}
    for a, b in TWINS:
        ia, ib = L2I[a], L2I[b]
        m = np.isin(yte, [ia, ib])
        twin[(a, b)] = dict(n=int(m.sum()), n_a=int((yte == ia).sum()), n_b=int((yte == ib).sum()),
                            exact=float((pred[m] == yte[m]).mean()) if m.any() else float("nan"),
                            in_pair=float(np.isin(pred[m], [ia, ib]).mean()) if m.any() else float("nan"),
                            swapped=float(((pred[m] == (ia + ib - yte[m]))).mean()) if m.any() else float("nan"))
    per_prob = {p: float(accuracy_score(yte[[r["problem"] == p for r in te]], pred[[r["problem"] == p for r in te]])) for p in HOLDOUT}

    print(f"\nHELD-OUT (unseen problems {HOLDOUT})\n  accuracy={acc:.3f}  macro-F1={mf1:.3f}")
    for (a, b), t in twin.items():
        print(f"  twin {a[:2]}/{b[:2]}: exact acc={t['exact']:.3f} (n={t['n']}: {t['n_a']} vs {t['n_b']})  swapped-with-twin={t['swapped']:.3f}")
    for k, v in per_prob.items(): print(f"  {k}: acc={v:.3f}")

    # --- confusion matrix ---
    names = ["OK" if l == "CORRECT" else l.split("_")[0] for l in LABELS]
    cm = confusion_matrix(yte, pred, labels=range(len(LABELS)))
    cmn = cm / np.maximum(cm.sum(1, keepdims=True), 1)
    plt.rcParams.update({"font.family": "sans-serif", "text.color": INK, "axes.labelcolor": INK})
    fig, ax = plt.subplots(figsize=(6.6, 5.6))
    ax.imshow(cmn, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(names)), names, color=MUTED); ax.set_yticks(range(len(names)), names, color=MUTED)
    for i in range(len(names)):
        for j in range(len(names)):
            if cm[i, j]:
                ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=9, color="white" if cmn[i, j] > .55 else INK)
    for a, b in TWINS:
        k = min(L2I[a], L2I[b])
        ax.add_patch(plt.Rectangle((k - .5, k - .5), 2, 2, fill=False, ec=ACCENT, lw=1.4, ls="--"))
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"Unseen problems ({', '.join(HOLDOUT)}) - counts; shade = row share; dashed = twin pairs", fontsize=8.5, loc="left")
    for s in ax.spines.values(): s.set_visible(False)
    fig.tight_layout(); fig.savefig(DOCS / "confusion_matrix.png", dpi=160); plt.close(fig)

    # --- docs/metrics.md ---
    L = ["# Diagnoser metrics", "",
         "Model: LightGBM multiclass (9 labels), temperature-calibrated. Generated by `ml/train.py`.", "",
         "## Protocol", "",
         f"- Split **by problem_id**. Held-out (never seen in training or selection): `{', '.join(HOLDOUT)}` ({len(te)} samples).",
         f"- Training: {len(set(gtr))} other problems ({len(tr)} samples).",
         f"- Feature set chosen by 5-fold grouped CV on the training problems only: **{best}** "
         f"(CV macro-F1 {cv[best]:.3f}; " + "; ".join(f"{k}: {v:.3f}" for k, v in cv.items() if k != best) + ").",
         "- Data are **synthetic** (templates in `ml/relearn_ml/templates.py`, labels verified by execution). No real learner data.", "",
         "## Headline (unseen problems)", "",
         f"| metric | value |", "|---|---|", f"| accuracy | {acc:.3f} |", f"| macro-F1 | {mf1:.3f} |", "",
         "Per held-out problem accuracy: " + ", ".join(f"`{k}` {v:.2f}" for k, v in per_prob.items()), "",
         "## Twin pairs", "",
         "Twins give the same wrong output on many inputs, so the model must use code structure. "
         "*Exact* = predicted the right label of the two; *swapped* = predicted the other twin.", "",
         "| pair | n (true a / true b) | exact accuracy | predicted in pair | swapped with twin |", "|---|---|---|---|---|"]
    for (a, b), t in twin.items():
        L.append(f"| {a.split('_')[0]} vs {b.split('_')[0]} | {t['n']} ({t['n_a']} / {t['n_b']}) | {t['exact']:.3f} | {t['in_pair']:.3f} | {t['swapped']:.3f} |")
    L += ["", "## Per-class report (unseen problems)", "", "| class | precision | recall | F1 | support |", "|---|---|---|---|---|"]
    for l in LABELS:
        r = rep[l]; L.append(f"| {l} | {r['precision']:.2f} | {r['recall']:.2f} | {r['f1-score']:.2f} | {int(r['support'])} |")
    L += ["", "Classes with support 0 had no sample among the held-out problems (macro-F1 above averages only classes present).", "",
          "## Confusion matrix", "", "![confusion matrix](confusion_matrix.png)", "",
          "## Caveats", "",
          "- **Do not read a perfect score as 'solved'.** Samples are renamed/reformatted variants of a few dozen templates, so the "
          "effective held-out sample size is far smaller than the row counts above, and each held-out problem has close structural "
          "siblings in training (e.g. `count_evens`/`product` for `sum_list`). The 5-fold grouped CV over all 22 problems "
          "(`python -m relearn_ml.train`) is the more realistic estimate: macro-F1 about 0.94, with the weakest problems being the ones with unique structure.",
          "- 4 held-out problems is a small, single split: treat the numbers as indicative, not tight estimates.",
          "- Held-out problems are written in the same generator style as training ones; real learner code will be messier.",
          "- Reproduce: `cd ml && .venv/Scripts/python -m relearn_ml.generate && .venv/Scripts/python train.py`."]
    (DOCS / "metrics.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    (DOCS / "metrics.json").write_text(json.dumps(dict(
        model="LightGBM multiclass, temperature-calibrated", feature_set=best, temperature=float(T),
        data="synthetic (template-generated, execution-verified labels)", holdout_problems=HOLDOUT,
        n_train=len(tr), n_holdout=len(te), cv_macro_f1_train_problems=cv,
        holdout=dict(accuracy=float(acc), macro_f1=float(mf1), per_problem_accuracy=per_prob,
                     per_class={l: dict(precision=rep[l]["precision"], recall=rep[l]["recall"], f1=rep[l]["f1-score"], support=int(rep[l]["support"])) for l in LABELS},
                     twin_pairs={f"{a.split('_')[0]}_{b.split('_')[0]}": t for (a, b), t in twin.items()}),
        caveat="Held-out score is optimistic: samples are variants of a few dozen templates. See docs/metrics.md."), indent=1), encoding="utf-8")

    # --- save models ---
    joblib.dump(dict(model=model, labels=LABELS, holdout=HOLDOUT, config=best), ART / "diagnoser_holdout.joblib")
    final = fit(rows, CONFIGS[best]); final.T = T
    joblib.dump(dict(model=final, labels=LABELS, config=best, temperature=T), ART / "diagnoser.joblib")
    print("saved models + docs/metrics.md + docs/confusion_matrix.png")


if __name__ == "__main__":
    main()
