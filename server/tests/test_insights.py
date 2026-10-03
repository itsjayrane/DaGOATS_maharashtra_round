"""Item 4: common-mistakes analytics, unknown clusters, hashed learners, CSV export, learner patterns."""
import csv, io, os, tempfile

os.environ["RELEARN_DB"] = os.path.join(tempfile.mkdtemp(), "insights.db")

import pytest
from fastapi.testclient import TestClient

from app import db, insights
from app.main import app

M1 = "def sum_to_n(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total\n"
M1_LONG = "def sum_to_n(n):\n    total = 0\n    for i in range(1, n):\n        total = total + i\n    return total\n"
M1_ONE = "def one_to_n(n):\n    return list(range(1, n))\n"
OK = "def sum_to_n(n):\n    return n * (n + 1) // 2\n"
WRONG = "def sum_to_n(n):\n    return n * n\n"


@pytest.fixture(scope="module")
def c():
    old = db.DB_PATH  # other test modules share the app: use a fresh database so the counts below are exact
    db.DB_PATH = os.path.join(tempfile.mkdtemp(), "insights-own.db")
    with TestClient(app) as client:
        db.init()
        for lid, pid, code in [("ana", "sum_to_n", M1), ("ben", "sum_to_n", M1_LONG), ("ana", "sum_to_n", OK),
                               ("ana", "one_to_n", M1_ONE), ("cy", "sum_to_n", WRONG), ("dee", "sum_to_n", WRONG)]:
            client.post("/diagnose", json={"problem_id": pid, "code": code, "learner_id": lid})
        yield client
    db.DB_PATH = old


def test_problem_common_mistakes_counts_shares_and_examples(c):
    r = c.get("/problems/sum_to_n/common-mistakes").json()
    assert r["total_wrong_attempts"] == 4, "the correct submission is excluded"
    m = next(x for x in r["mistakes"] if x["label"] == "M1_RANGE_OFF_BY_ONE")
    assert m["count"] == 2 and m["unique_learners"] == 2 and m["share"] == 0.5
    assert len(m["examples"]) == 2 and m["examples"][0]["code"] == M1, "shortest first"
    assert m["examples"][0]["highlight_lines"] == [3], "the line a verified fix changes"
    assert "sum_to_n(" in m["typical_failing_test"]["words"] and m["lesson_summary"] and m["name"]
    assert all(len(e["learner"]) == 12 and e["learner"] not in ("ana", "ben") for e in m["examples"])


def test_unknown_verdicts_are_clustered_by_failing_tests(c):
    r = c.get("/problems/sum_to_n/common-mistakes").json()
    assert not any(x["label"] == "OTHER_BUG" for x in r["mistakes"])
    cl = r["unknown_clusters"]
    assert len(cl) == 1 and cl[0]["count"] == 2 and cl[0]["unique_learners"] == 2
    assert cl[0]["signature"]["failing"] and "fails test(s)" in cl[0]["signature_words"]
    assert len(cl[0]["examples"]) == 1, "identical code is shown once"


def test_global_insights_and_synthetic_toggle(c):
    real = c.get("/insights/common-mistakes").json()
    assert real["total_wrong_attempts"] == 5 and real["unique_learners"] == 4
    m1 = next(x for x in real["mistakes"] if x["label"] == "M1_RANGE_OFF_BY_ONE")
    assert m1["problems"] == {"sum_to_n": 2, "one_to_n": 1} and m1["synthetic"] == 0
    db.seed_demo()
    assert c.get("/insights/common-mistakes").json()["total_wrong_attempts"] == 5, "synthetic rows hidden by default"
    both = c.get("/insights/common-mistakes?include_synthetic=true").json()
    assert both["total_wrong_attempts"] > 5 and any(x["synthetic"] for x in both["mistakes"])


def test_learner_hash_uses_the_salt(monkeypatch):
    a = insights.learner_hash("ana")
    monkeypatch.setenv("INSIGHTS_SALT", "another-salt")
    assert insights.learner_hash("ana") != a and len(a) == 12


def test_csv_export_hashes_ids_and_code_is_optional(c):
    text = c.get("/insights/export.csv").text
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows and "code" not in rows[0] and not any(r["learner_hash"] in ("ana", "ben", "cy", "dee") for r in rows)
    assert all(r["synthetic"] == "0" for r in rows)
    with_code = list(csv.DictReader(io.StringIO(c.get("/insights/export.csv?include_code=true").text)))
    assert any(r["code"] == M1 for r in with_code)
    assert "ana" not in text


def test_learner_patterns_need_two_problems(c):
    p = c.get("/learner/ana/patterns").json()
    assert [x["label"] for x in p["patterns"]] == ["M1_RANGE_OFF_BY_ONE"] and p["patterns"][0]["problems"] == ["one_to_n", "sum_to_n"]
    nxt = p["suggested_next"]
    assert nxt and nxt["problem_id"] not in ("sum_to_n", "one_to_n") and nxt["misconception"] == "M1_RANGE_OFF_BY_ONE"
    ben = c.get("/learner/ben/patterns").json()
    assert ben["patterns"] == [] and ben["suggested_next"] is None, "one problem is not a pattern"
    assert c.get("/learner/nobody/patterns").json()["patterns"] == []


def test_unknown_problem_is_404(c):
    assert c.get("/problems/nope/common-mistakes").status_code == 404
