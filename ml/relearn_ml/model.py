"""Diagnoser: TF-IDF(normalized code) + AST + execution features -> LightGBM multiclass, temperature-calibrated."""
import numpy as np
import scipy.sparse as sp
from lightgbm import LGBMClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from .features import dense_matrix, tokens
from .labels import LABELS, L2I

LGBM_PARAMS = dict(n_estimators=250, learning_rate=0.06, num_leaves=15, min_child_samples=5, subsample=0.8,
                   subsample_freq=1, colsample_bytree=0.5, class_weight="balanced", verbose=-1, random_state=0, n_jobs=4)


class Diagnoser:
    def __init__(self, kind="lgbm", use_tfidf=True, use_ast=True, use_exec=True, use_prob=True, other_weight=1.0):
        self.other_weight = other_weight  # extra factor on the balanced weight of OTHER_BUG (tuned on out-of-fold data)
        self.kind, self.use_tfidf, self.use_ast, self.use_exec, self.use_prob = kind, use_tfidf, use_ast, use_exec, use_prob
        self.T = 1.0

    def _X(self, rows, fit=False):
        parts = []
        if self.use_tfidf:
            if fit:
                self.vec = TfidfVectorizer(tokenizer=tokens, token_pattern=None, lowercase=False, ngram_range=(1, 3),
                                           min_df=3, max_features=1500, sublinear_tf=True)
                parts.append(self.vec.fit_transform([r["norm"] for r in rows]))
            else:
                parts.append(self.vec.transform([r["norm"] for r in rows]))
        if self.use_ast or self.use_exec or self.use_prob:
            D, self.dense_keys = dense_matrix(rows, self.use_ast, self.use_exec, self.use_prob)
            parts.append(sp.csr_matrix(D))
        return sp.hstack(parts).tocsr().astype(np.float32)

    def _weights(self, y):
        return _balanced(y, getattr(self, 'other_weight', 1.0))

    def fit(self, rows, labels):
        y = np.array([L2I[l] for l in labels])
        X = self._X(rows, fit=True)
        self.clf = (LogisticRegression(C=5, max_iter=3000, class_weight="balanced") if self.kind == "lr"
                    else LGBMClassifier(**dict(LGBM_PARAMS, class_weight=self._weights(y))))
        self.clf.fit(X, y)
        self.classes_ = list(self.clf.classes_)
        return self

    def raw_proba(self, rows):
        P = self.clf.predict_proba(self._X(rows))
        full = np.zeros((len(rows), len(LABELS)))
        full[:, self.classes_] = P
        return full

    def predict_proba(self, rows):
        P = np.clip(self.raw_proba(rows), 1e-9, 1)
        z = np.log(P) / self.T
        z -= z.max(1, keepdims=True)
        e = np.exp(z)
        return e / e.sum(1, keepdims=True)

    def feature_names(self):
        names = list(self.vec.get_feature_names_out()) if self.use_tfidf else []
        return names + list(self.dense_keys)


def _balanced(y, other_weight):
    counts = np.bincount(y, minlength=len(LABELS))
    present = [i for i in range(len(LABELS)) if counts[i]]
    w = {i: len(y) / (len(present) * counts[i]) for i in present}
    if L2I.get("OTHER_BUG") in w:
        w[L2I["OTHER_BUG"]] *= other_weight
    return w


def fit_temperature(P, y):
    """Grid-search the scalar T minimising NLL of softmax(log P / T) on out-of-fold predictions."""
    logP = np.log(np.clip(P, 1e-9, 1))
    best, bt = 1e9, 1.0
    for T in np.linspace(0.4, 10.0, 193):  # wide grid: with OTHER_BUG the best T can be > 3
        z = logP / T
        z -= z.max(1, keepdims=True)
        p = np.exp(z)
        p /= p.sum(1, keepdims=True)
        nll = -np.log(p[np.arange(len(y)), y] + 1e-12).mean()
        if nll < best:
            best, bt = nll, T
    return bt
