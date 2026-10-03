"""Item 6: resolution v2 - BKT-style P(misconception) + >= 2 different cleared transfer problems."""
import pytest
from fastapi.testclient import TestClient

from app import bkt
from app.main import app
from relearn_ml import references

SUM_M5 = "def sum_list(nums):\n    total = 0\n    for x in nums:\n        total += x\n        return total\n"
PRODUCT_OK = references.reference_variants()["product"][0]
EVENS_OK = references.reference_variants()["count_evens"][0]
PRODUCT_BAD = "def product(nums):\n    p = 1\n    for x in nums:\n        p *= x\n        return p\n"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def reassess(c, lid, pid, code):
    return c.post("/reassess", json={"learner_id": lid, "misconception": "M5", "problem_id": pid, "code": code, "concept_answer": 1}).json()


def test_two_clean_passes_bring_p_below_the_threshold():
    for start in (0.5, 0.7375, bkt.P_MAX):  # prior, after one confident diagnosis, worst case
        p = bkt.update(bkt.update(start, True), True)
        assert p < bkt.P_RESOLVED, (start, p)
    assert not bkt.is_resolved(0.01, {"a"}) and bkt.is_resolved(0.1, {"a", "b"}) and not bkt.is_resolved(0.2, {"a", "b"})


def test_a_pass_then_a_fail_raises_p():
    p1 = bkt.update(0.7, True)
    assert p1 < 0.7 and bkt.update(p1, False) > p1


def test_one_clean_transfer_is_not_enough(c):
    c.post("/diagnose", json={"problem_id": "sum_list", "code": SUM_M5, "learner_id": "r1"})
    r = reassess(c, "r1", "product", PRODUCT_OK)
    assert r["resolved"] is False and r["cleared_problems"] == ["product"] and r["needed"] == 2
    assert r["failed_checks"] == ["enough_evidence"] and "1 / 2" in r["message"]
    assert [x["check"] for x in r["reasons"]][-1] == "enough_evidence" and len(r["reasons"]) == 5


def test_the_same_problem_twice_never_counts_twice(c):
    c.post("/diagnose", json={"problem_id": "sum_list", "code": SUM_M5, "learner_id": "r2"})
    a = reassess(c, "r2", "product", PRODUCT_OK)
    b = reassess(c, "r2", "product", PRODUCT_OK)
    assert b["resolved"] is False and b["cleared_problems"] == ["product"] and b["evidence_counted"] is False
    assert b["p_misconception"] == a["p_misconception"]
    r = reassess(c, "r2", "count_evens", EVENS_OK)
    assert r["resolved"] is True and r["cleared_problems"] == ["count_evens", "product"] and r["p_misconception"] < 0.15
    m = c.get("/learner/r2").json()["mastery"]["M5_RETURN_IN_LOOP"]
    assert m["resolved"] and abs(m["mastery"] - (1 - r["p_misconception"])) < 1e-3, "mastery = 1 - P"


def test_a_fail_after_a_pass_raises_p_via_the_api(c):
    c.post("/diagnose", json={"problem_id": "sum_list", "code": SUM_M5, "learner_id": "r3"})
    a = reassess(c, "r3", "product", PRODUCT_OK)
    b = reassess(c, "r3", "count_evens", "def count_evens(nums):\n    n = 0\n    for x in nums:\n        if x % 2 == 0:\n            n += 1\n        return n\n")
    assert b["p_misconception"] > a["p_misconception"] and not b["resolved"] and b["cleared_problems"] == ["product"]


def test_a_new_diagnosis_starts_the_evidence_over(c):
    c.post("/diagnose", json={"problem_id": "sum_list", "code": SUM_M5, "learner_id": "r4"})
    reassess(c, "r4", "product", PRODUCT_OK)
    c.post("/diagnose", json={"problem_id": "product", "code": PRODUCT_BAD, "learner_id": "r4"})
    r = reassess(c, "r4", "count_evens", EVENS_OK)
    assert r["cleared_problems"] == ["count_evens"] and not r["resolved"]
