"""Item 5: the 4-section student explanation card (what went wrong -> why -> your code fixed -> best solution)."""
import os, tempfile

os.environ.setdefault("RELEARN_DB", os.path.join(tempfile.mkdtemp(), "own.db"))  # never the dev database

import re

import pytest
from fastapi.testclient import TestClient

from app import explain
from app.main import PROBLEMS, app
from relearn_ml.labels import MISCONCEPTIONS

M5 = "def product(nums):\n    p = 1\n    for x in nums:\n        p *= x\n        return p\n"
M3 = "def square(n):\n    print(n * n)\n"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def test_every_misconception_has_a_short_why():
    assert set(explain.WHY) == set(MISCONCEPTIONS)
    for m, t in explain.WHY.items():
        n = len(re.findall(r"[.!?](?:\s|$)", t.format(fn="f")))
        assert 1 <= n <= 2, (m, n)


def test_card_has_all_four_sections(c):
    e = c.post("/explain", json={"problem_id": "product", "code": M5, "label": "M5"}).json()
    assert e["where_it_went_wrong"]["words"] and e["why"]["label"] == "M5_RETURN_IN_LOOP" and "return" in e["why"]["text"]
    assert e["proposed_fix"]["verified"]["passed"] == e["proposed_fix"]["verified"]["total"] and e["best_solution"]["code"]


def test_why_without_a_label_comes_from_the_diagnosis(c):
    e = c.post("/explain", json={"problem_id": "square", "code": M3}).json()
    assert e["why"]["label"] == "M3_PRINT_NOT_RETURN" and "square returns None" in e["why"]["text"]
    u = c.post("/explain", json={"problem_id": "sum_to_n", "code": "def sum_to_n(n):\n    return n * n\n"}).json()
    assert u["why"]["label"] is None and u["why"]["text"] == explain.WHY_UNKNOWN
    ok = c.post("/explain", json={"problem_id": "square", "code": "def square(n):\n    return n * n\n"}).json()
    assert ok["why"] is None and ok["all_tests_pass"]
