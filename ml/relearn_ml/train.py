"""Train + evaluate. python -m relearn_ml.train  (after relearn_ml.generate)

Evaluation is GROUPED BY PROBLEM: the model is always scored on problems it never saw during training."""
import json, pathlib, time
import joblib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold, StratifiedKFold

from .execute import run_submission
from .features import featurize
from .labels import LABELS, L2I, TWINS
from .model import Diagnoser, fit_temperature
from .problems import load_problems
from .wild import WILD

ROOT = pathlib.Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
INK, MUTED, ACCENT = "#1f2937", "#6b7280", "#2b6cb0"

CONFIGS = {
    "TF-IDF only (logistic regression)": dict(kind="lr", use_ast=False, use_exec=False, use_prob=False),
    "TF-IDF only (LightGBM)": dict(use_ast=False, use_exec=False, use_prob=False),
    "AST + execution + task flags (no text)": dict(use_tfidf=False),
    "TF-IDF + AST (no execution)": dict(use_exec=False, use_prob=False),
    "FULL: TF-IDF + AST + execution + task flags": dict(),
}
FULL = "FULL: TF-IDF + AST + execution + task flags"


def load():
    return [json.loads(l) for l in open(ROOT / "data" / "dataset.jsonl", encoding="utf-8")]


def cv_oof(rows, y, cfg, splitter, groups=None):
    P = np.zeros((len(rows), len(LABELS)))
    for tr, te in splitter.split(rows, y, groups):
        m = Diagnoser(**cfg).fit([rows[i] for i in tr], [LABELS[y[i]] for i in tr])
        P[te] = m.raw_proba([rows[i] for i in te])
    return P


def twin_confusion(y, pred):
    out = {}
    for a, b in TWINS:
        ia, ib = L2I[a], L2I[b]
        ma, mb = y == ia, y == ib
        out[f"{a[:2]}->{b[:2]}"] = float((pred[ma] == ib).sum() / max(ma.sum(), 1))
        out[f"{b[:2]}->{a[:2]}"] = float((pred[mb] == ia).sum() / max(mb.sum(), 1))
    return out


def main():
    ART.mkdir(exist_ok=True)
    t0 = time.time()
    rows = load()
    y = np.array([L2I[r["label"]] for r in rows])
    groups = np.array([r["problem"] for r in rows])
    print(f"{len(rows)} samples, {len(set(groups))} problems")

    gkf = GroupKFold(n_splits=5)
    results, oof = {}, {}
    for name, cfg in CONFIGS.items():
        P = cv_oof(rows, y, cfg, gkf, groups)
        pred = P.argmax(1)
        results[name] = dict(macro_f1=f1_score(y, pred, average="macro"), accuracy=accuracy_score(y, pred),
                             twin_confusion=twin_confusion(y, pred))
        print(f"{name:48s} macroF1={results[name]['macro_f1']:.3f} acc={results[name]['accuracy']:.3f}")
        oof[name] = P
    # reference: random (template-leaky) split -- shows why grouped evaluation matters
    Pr = cv_oof(rows, y, CONFIGS[FULL], StratifiedKFold(5, shuffle=True, random_state=0))
    results["_random_split_full_macro_f1"] = f1_score(y, Pr.argmax(1), average="macro")
    print("random-split (leaky) macroF1:", round(results["_random_split_full_macro_f1"], 3))

    BEST = max(CONFIGS, key=lambda k: results[k]["macro_f1"])  # model selection by held-out-problem macro-F1
    print("selected for production:", BEST)
    oof_full = oof[BEST]
    T = fit_temperature(oof_full, y)
    z = np.log(np.clip(oof_full, 1e-9, 1)) / T
    Pc = np.exp(z - z.max(1, keepdims=True))
    Pc /= Pc.sum(1, keepdims=True)
    conf, correct = Pc.max(1), Pc.argmax(1) == y
    ece = sum(abs(correct[(conf > lo) & (conf <= lo + .1)].mean() - conf[(conf > lo) & (conf <= lo + .1)].mean())
              * ((conf > lo) & (conf <= lo + .1)).mean() for lo in np.arange(0, 1, .1) if ((conf > lo) & (conf <= lo + .1)).any())
    print(f"temperature T={T:.2f}  ECE={ece:.3f}")
    report = classification_report(y, Pc.argmax(1), labels=list(range(len(LABELS))), target_names=LABELS, output_dict=True, zero_division=0)

    per_problem = {g: float(accuracy_score(y[groups == g], Pc.argmax(1)[groups == g])) for g in sorted(set(groups))}

    # final model on all data
    final = Diagnoser(**CONFIGS[BEST]).fit(rows, [r["label"] for r in rows])
    final.T = T
    # out-of-template sanity check
    problems = load_problems()
    wr, wy = [], []
    for pid, lab, code in WILD:
        res = run_submission(code, problems[pid])
        passed = res["status"] == "ok" and all(t["ok"] for t in res["tests"])
        assert (lab == "CORRECT") == passed, f"wild label/behaviour mismatch: {pid} {lab}"
        wr.append(featurize(code, problems[pid], res))
        wy.append(L2I[lab])
    wy = np.array(wy)
    wp = final.predict_proba(wr).argmax(1)
    wild = dict(n=len(wy), accuracy=float(accuracy_score(wy, wp)), macro_f1=float(f1_score(wy, wp, average="macro")),
                errors=[dict(problem=WILD[i][0], true=LABELS[wy[i]], pred=LABELS[wp[i]]) for i in range(len(wy)) if wy[i] != wp[i]])
    print("wild set:", {k: v for k, v in wild.items() if k != "errors"}, wild["errors"])

    joblib.dump(dict(model=final, labels=LABELS), ART / "diagnoser.joblib")
    json.dump(dict(selected=BEST, grouped_cv=results, temperature=T, ece=float(ece), per_class=report, per_problem_accuracy=per_problem,
                   wild=wild, n_samples=len(rows), n_problems=len(set(groups))), open(ART / "metrics.json", "w"), indent=1)

    plots(y, Pc.argmax(1), results, final, BEST)
    print(f"done in {time.time() - t0:.0f}s")


def plots(y, pred, results, final, best):
    plt.rcParams.update({"font.family": "sans-serif", "text.color": INK, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED})
    names = [l.split("_")[0] if l != "CORRECT" else "OK" for l in LABELS]
    cm = confusion_matrix(y, pred, labels=range(len(LABELS)), normalize="true")
    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    ax.imshow(cm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(names)), names)
    ax.set_yticks(range(len(names)), names)
    for i in range(len(names)):
        for j in range(len(names)):
            if cm[i, j] >= 0.01:
                ax.text(j, i, f"{cm[i, j]:.2f}", ha="center", va="center", fontsize=8, color="white" if cm[i, j] > .55 else INK)
    for a, b in TWINS:  # outline twin blocks
        ia, ib = L2I[a], L2I[b]
        ax.add_patch(plt.Rectangle((min(ia, ib) - .5, min(ia, ib) - .5), 2, 2, fill=False, ec=ACCENT, lw=1.4, ls="--"))
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title("Diagnosis on unseen problems (row-normalised; dashed = twin pairs)", fontsize=10, loc="left")
    for s in ax.spines.values(): s.set_visible(False)
    fig.tight_layout(); fig.savefig(ART / "confusion_matrix.png", dpi=160); plt.close(fig)

    labs = [k for k in results if not k.startswith("_")]
    vals = [results[k]["macro_f1"] for k in labs]
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    ys = range(len(labs))[::-1]
    ax.barh(list(ys), vals, color=[ACCENT if k == best else "#a9bfd9" for k in labs], height=.6)
    ax.set_yticks(list(ys), labs, fontsize=8)
    for y_, v in zip(ys, vals): ax.text(v + .01, y_, f"{v:.2f}", va="center", fontsize=8, color=INK)
    ax.set_xlim(0, 1.08); ax.set_xlabel("macro-F1 on held-out problems (5-fold grouped CV)")
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(ART / "ablation.png", dpi=160); plt.close(fig)


if __name__ == "__main__":
    main()
