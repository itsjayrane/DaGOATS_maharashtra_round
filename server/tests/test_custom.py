"""Item 3: teacher-written custom problems (accept / reject paths), listing, diagnosis out of distribution, /explain."""
import os, tempfile

os.environ["RELEARN_DB"] = os.path.join(tempfile.mkdtemp(), "custom.db")

import pytest
from fastapi.testclient import TestClient

from app import ratelimit
from app.main import app

REF = "def count_vowels(word):\n    n = 0\n    for ch in word:\n        if ch in 'aeiou':\n            n += 1\n    return n\n"
TESTS = [{"input": ["banana"]}, {"input": ["sky"], "expected": 0}, {"input": ["education"]}, {"input": ["a"], "expected": 1}]
BODY = dict(statement="Count how many lowercase vowels (a, e, i, o, u) are in the word.", function_name="count_vowels",
            reference_solution=REF, tests=TESTS)


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def made(c):
    r = c.post("/custom/problems", json=BODY)
    assert r.status_code == 200, r.text
    return r.json()


def test_accepts_a_valid_problem_and_derives_missing_expected_values(made):
    assert made["id"].startswith("custom-") and made["custom"] is True and made["badge"] == "custom — teacher-written"
    assert [t["expected"] for t in made["tests"]] == [3, 0, 5, 1], "derived from the reference where not given"
    assert made["params"] == ["word"] and made["param_types"] == ["str"] and made["return_type"] == "int"
    assert made["starter"].startswith("def count_vowels(word):")


def test_listed_with_the_badge_in_problems(c, made):
    p = next(p for p in c.get("/problems").json() if p["id"] == made["id"])
    assert p["badge"] == "custom — teacher-written" and p["n_tests"] == 4 and "tests" not in p


@pytest.mark.parametrize("change,needle", [
    (dict(tests=TESTS[:3]), "at least 4 tests"),
    (dict(tests=None), "at least 4 tests"),
    (dict(reference_solution="def count_vowels(word):\n    return len(word\n"), "does not parse"),
    (dict(reference_solution="def other(word):\n    return 0\n"), "must define a function named"),
    (dict(reference_solution="def count_vowels(word):\n    return 1 / 0\n"), "fails on test 1"),
    (dict(tests=TESTS[:3] + [{"input": ["a"], "expected": 7}]), "the test expects 7"),
    (dict(function_name="count vowels"), "valid Python name"),
    (dict(tests=TESTS[:3] + [{"input": ["a", "b"]}]), "takes 1"),
    (dict(statement="short"), "statement"),
    (dict(reference_solution="def count_vowels(word):\n    while True:\n        pass\n"), "does not run"),
])
def test_rejects_bad_problems_with_422(c, change, needle):
    r = c.post("/custom/problems", json={**BODY, **change})
    assert r.status_code == 422 and needle in r.text, r.text


def test_mutating_reference_is_rejected(c):
    ref = "def add_one(xs):\n    xs.append(1)\n    return xs\n"
    r = c.post("/custom/problems", json=dict(statement="Return the list with 1 added at the end.", function_name="add_one",
                                             reference_solution=ref, tests=[{"input": [[1]]}, {"input": [[]]}, {"input": [[2, 3]]}, {"input": [[0]]}]))
    assert r.status_code == 422 and "changes its input" in r.text


def test_diagnosis_on_a_custom_problem_is_out_of_distribution(c, made):
    ok = c.post("/diagnose", json={"problem_id": made["id"], "code": REF}).json()
    assert ok["in_distribution"] is False and ok["verdict"] == "correct"
    wrong = "def count_vowels(word):\n    n = 0\n    for ch in word:\n        if ch in 'aeiou':\n            n += 1\n        return n\n"
    w = c.post("/diagnose", json={"problem_id": made["id"], "code": wrong}).json()
    assert w["in_distribution"] is False and w["verdict"] in ("misconception", "unknown") and not w["passed"]
    if w["verdict"] == "misconception":
        assert w["confidence"] >= 0.6, "stricter abstention on custom problems"
    built_in = c.post("/diagnose", json={"problem_id": "sum_list", "code": "def sum_list(nums):\n    return 0\n"}).json()
    assert built_in["in_distribution"] is True


def test_explain_on_a_custom_problem_uses_the_teacher_reference(c, made):
    wrong = "def count_vowels(word):\n    return len(word)\n"
    e = c.post("/explain", json={"problem_id": made["id"], "code": wrong}).json()
    assert "count_vowels('banana')" in e["where_it_went_wrong"]["words"]
    assert e["best_solution"]["code"] == REF and e["best_solution"]["verified"]["passed"] == 4
    h = c.post("/hint", json={"problem_id": made["id"], "code": wrong, "hint_level": 1}).json()
    assert h["source"] == "curated" and h["hint"]


def test_custom_endpoints_are_rate_limited_to_5_per_minute(c, monkeypatch):
    monkeypatch.setenv("RELEARN_RATE_LIMIT", "on")
    ratelimit.reset()
    codes = [c.post("/custom/problems", json={**BODY, "tests": TESTS[:2]}, headers={"X-Forwarded-For": "10.9.9.9"}).status_code for _ in range(6)]
    assert codes[:5] == [422] * 5 and codes[5] == 429
    ratelimit.reset()


def test_unknown_custom_id_is_404(c):
    assert c.post("/diagnose", json={"problem_id": "custom-doesnotexist", "code": "x"}).status_code == 404
