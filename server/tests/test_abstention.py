"""Item 2: OTHER_BUG + 'unknown' verdict, no mastery change / no canned lesson when unsure, /explain, artifacts."""
import json, os, pathlib, tempfile

os.environ["RELEARN_DB"] = os.path.join(tempfile.mkdtemp(), "abstain.db")

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import PROBLEMS, app
import app.main as main
from relearn_ml.labels import LABELS, MISCONCEPTIONS
from relearn_ml.execute import run_submission

ML = pathlib.Path(__file__).resolve().parents[2] / "ml"
OK_SUM = "def sum_list(nums):\n    t = 0\n    for x in nums:\n        t += x\n    return t\n"
M5_PRODUCT = "def product(nums):\n    p = 1\n    for x in nums:\n        p *= x\n        return p\n"
WRONG_FORMULA = "def sum_to_n(n):\n    return n * n\n"  # a real bug that is none of the 8 misconceptions
INDEX_ERROR = "def last_item(items):\n    return items[len(items)]\n"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def diag(c, pid, code, learner=None):
    return c.post("/diagnose", json={"problem_id": pid, "code": code, "learner_id": learner}).json()


def test_other_bug_is_the_last_label_and_never_a_mastery_skill():
    assert LABELS[-1] == "OTHER_BUG" and "OTHER_BUG" not in MISCONCEPTIONS and "OTHER_BUG" not in db.MISCONCEPTIONS
    assert len(MISCONCEPTIONS) == 8


def test_threshold_artifact_meets_the_coverage_target():
    t = json.loads((ML / "artifacts" / "threshold.json").read_text(encoding="utf-8"))
    assert 0 <= t["unknown_t"] < 1 and t["coverage_known_oof"] >= 0.90 and t["target_coverage"] == 0.90


def test_verdicts(c):
    r = diag(c, "sum_list", OK_SUM)
    assert r["verdict"] == "correct" and r["unknown"] is False and r["unknown_reason"] is None
    r = diag(c, "product", M5_PRODUCT)
    assert r["verdict"] == "misconception" and r["label"] == "M5_RETURN_IN_LOOP" and not r["unknown"]
    r = diag(c, "sum_to_n", WRONG_FORMULA)
    assert r["verdict"] == "unknown" and r["unknown"] is True and r["unknown_reason"]
    assert r["label"] == max(r["probabilities"], key=r["probabilities"].get), "label stays the top-1 class"
    assert r["closest_guess"]["label"] in MISCONCEPTIONS and 0 <= r["closest_guess"]["probability"] <= 1


def test_unknown_never_changes_mastery(c):
    diag(c, "sum_to_n", WRONG_FORMULA, "unsure-learner")
    m = c.get("/learner/unsure-learner").json()["mastery"]
    assert all(v["mastery"] == 0.5 for v in m.values())
    diag(c, "product", M5_PRODUCT, "unsure-learner")  # a confident misconception still counts
    assert c.get("/learner/unsure-learner").json()["mastery"]["M5_RETURN_IN_LOOP"]["mastery"] < 0.5


def test_intervene_for_an_unknown_bug_returns_the_explanation_not_a_lesson(c):
    r = c.post("/intervene", json={"label": "M1", "problem_id": "sum_to_n", "code": WRONG_FORMULA}).json()
    assert r["unknown"] is True and r["intervention"] is None and r["personalized"] is None
    e = r["explain"]
    assert "sum_to_n(5)" in e["where_it_went_wrong"]["words"] and e["best_solution"]["verified"]["passed"] == e["best_solution"]["verified"]["total"]


def test_explain_offers_a_fix_only_when_it_passes_every_test(c):
    e = c.post("/explain", json={"problem_id": "product", "code": M5_PRODUCT}).json()
    fix = e["proposed_fix"]
    assert fix and fix["verified"]["passed"] == fix["verified"]["total"] and fix["fixed_highlight_lines"]
    r = run_submission(fix["code"], PROBLEMS["product"])
    assert all(t["ok"] for t in r["tests"]), "independent re-check"
    e2 = c.post("/explain", json={"problem_id": "sum_to_n", "code": WRONG_FORMULA}).json()
    assert e2["proposed_fix"] is None and e2["best_solution"]["code"] and not e2["all_tests_pass"]


def test_explain_puts_errors_in_plain_words_with_the_line(c):
    w = c.post("/explain", json={"problem_id": "last_item", "code": INDEX_ERROR}).json()["where_it_went_wrong"]
    assert w["error"] == "IndexError" and "line 2" in w["words"] and "position" in w["words"]
    ok = c.post("/explain", json={"problem_id": "sum_list", "code": OK_SUM}).json()
    assert ok["all_tests_pass"] is True and ok["where_it_went_wrong"] is None and ok["proposed_fix"] is None


def test_strict_mode_needs_more_confidence():
    svc = main.SVC
    failing = [{"ok": False}]
    assert svc._verdict("M1_RANGE_OFF_BY_ONE", 0.5, failing, strict=False)[0] == "misconception"
    assert svc._verdict("M1_RANGE_OFF_BY_ONE", 0.5, failing, strict=True)[0] == "unknown"
    assert svc._verdict("OTHER_BUG", 0.99, failing, strict=False)[0] == "unknown"
    assert svc._verdict("M1_RANGE_OFF_BY_ONE", 0.01, [{"ok": True}], strict=False)[0] == "correct"


def test_metrics_carry_the_abstention_numbers(c):
    m = c.get("/metrics").json()
    assert m["abstention"]["coverage_known_oof"] >= 0.9 and "OTHER_BUG" in m["holdout"]["per_class"]
    u = m["unseen"]
    assert set(u["per_class"]) == set(MISCONCEPTIONS) and 0 <= u["mean_flagged_unknown"] <= 1
    o = m["realistic"]["other_bug"]
    assert o["n"] == 10 and o["flagged_unknown"] + o["confidently_mislabelled"] == 10


def test_why_features_explain_the_diagnosis_in_plain_english(c):
    r = diag(c, "product", M5_PRODUCT)
    w = r["why_features"]
    assert 1 <= len(w) <= 3 and all(set(x) == {"name", "value", "plain_english", "contribution"} for x in w)
    assert [x["contribution"] for x in w] == sorted((x["contribution"] for x in w), reverse=True) and w[0]["contribution"] > 0
    assert any("return" in x["plain_english"] for x in w) and not any("_" in x["plain_english"] for x in w)
    sq = diag(c, "square", "def square(n):\n    print(n * n)\n")["why_features"]
    assert any("never returns" in x["plain_english"] for x in sq)
    assert diag(c, "square", "def square(n)\n    return n\n")["why_features"] == []  # syntax error: nothing to explain


def test_metrics_carry_the_model_evaluation_files(c):
    m = c.get("/metrics").json()
    names = [x["model"] for x in m["model_comparison"]["models"]]
    assert names == ["Majority baseline", "Logistic regression", "LightGBM (production)"]
    for x in m["model_comparison"]["models"]:
        lo, hi = x["realistic"]["bootstrap"]["accuracy_ci95"]
        assert lo <= x["realistic"]["accuracy"] <= hi
    assert {r["features"] for r in m["ablation"]["results"]} >= {"AST only", "execution only", "task flags only"}
    for part in ("out_of_fold", "holdout"):
        cal = m["calibration"][part]
        assert len(cal["bins_before"]) == len(cal["bins_after"]) == 10 and 0 <= cal["ece_after"] <= 1
    cm = m["realistic"]["confusion"]
    assert sum(map(sum, cm["matrix"])) == m["realistic"]["n"] and m["realistic"]["bootstrap"]["n_resamples"] == 1000
