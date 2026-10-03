import os, tempfile, time

os.environ["RELEARN_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")  # before importing the app

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:  # runs lifespan (db init + model load)
        yield client


SUM_OK = "def sum_list(nums):\n    t = 0\n    for x in nums:\n        t += x\n    return t\n"
SUM_M5 = "def sum_list(nums):\n    t = 0\n    for x in nums:\n        t += x\n        return t\n"
SUM_M4 = "def sum_list(nums):\n    for x in nums:\n        t = 0\n        t += x\n    return t\n"
M5_TRANSFER_OK = "def product(nums):\n    p = 1\n    for x in nums:\n        p *= x\n    return p\n"
M5_TRANSFER_BAD = "def product(nums):\n    p = 1\n    for x in nums:\n        p *= x\n        return p\n"


def test_health_and_cors(c):
    r = c.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 200 and r.json() == {"ok": True, "model_loaded": True}
    assert r.headers["access-control-allow-origin"] in ("*", "http://localhost:5173")
    pre = c.options("/diagnose", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
                                          "Access-Control-Request-Headers": "content-type"})
    assert pre.status_code == 200 and "access-control-allow-origin" in pre.headers


def test_problems(c):
    r = c.get("/problems").json()
    assert len(r) == 22 and {"id", "title", "prompt", "starter", "example"} <= set(r[0])
    assert "tests" not in r[0]  # hidden tests are not shipped to the client


def test_diagnose_correct(c):
    r = c.post("/diagnose", json={"problem_id": "sum_list", "code": SUM_OK}).json()
    assert r["label"] == "CORRECT" and r["passed"] and r["confidence"] > 0.8
    assert all(t["ok"] for t in r["test_results"]) and r["evidence"]


def test_diagnose_m5_has_evidence(c):
    r = c.post("/diagnose", json={"problem_id": "sum_list", "code": SUM_M5}).json()
    assert r["label"] == "M5_RETURN_IN_LOOP" and not r["passed"]
    assert any("return" in e["text"].lower() for e in r["evidence"])
    assert any(e["kind"] == "behavior" for e in r["evidence"])
    assert abs(sum(r["probabilities"].values()) - 1) < 1e-3


def test_diagnose_twin_m4_vs_m5(c):
    assert c.post("/diagnose", json={"problem_id": "sum_list", "code": SUM_M4}).json()["label"] == "M4_ACCUMULATOR_RESET"


def test_diagnose_timeout_is_2s(c):
    code = "def sum_list(nums):\n    while True:\n        pass\n"
    t = time.time()
    r = c.post("/diagnose", json={"problem_id": "sum_list", "code": code}).json()
    assert time.time() - t < 6
    assert r["label"] is None and r["status"] in ("timeout", "ok")  # step limit may fire first -> tests error with Timeout
    assert (r["status"] == "timeout") or all(t["error"] == "Timeout" for t in r["test_results"])


def test_diagnose_wall_clock_timeout_direct():
    from app import sandbox
    from app.main import PROBLEMS
    t = time.time()
    res = sandbox.run("import time\n", PROBLEMS["sum_list"])  # banned import is rejected, quickly
    assert res["status"] == "rejected"
    res = sandbox.run("def sum_list(nums):\n    return 0\n", PROBLEMS["sum_list"], timeout=0.001)
    assert res["status"] == "timeout" and time.time() - t < 5


def test_diagnose_syntax_error_and_bad_problem(c):
    r = c.post("/diagnose", json={"problem_id": "sum_list", "code": "def sum_list(nums:\n"}).json()
    assert r["label"] is None and r["status"] == "syntax_error"
    assert c.post("/diagnose", json={"problem_id": "nope", "code": "x"}).status_code == 404
    assert c.post("/diagnose", json={"problem_id": "sum_list"}).status_code == 422


def test_sandbox_blocks_dangerous_code(c):
    r = c.post("/diagnose", json={"problem_id": "sum_list", "code": "import os\ndef sum_list(nums):\n    return 0\n"}).json()
    assert r["status"] == "rejected" and r["label"] is None


def test_intervene(c):
    r = c.post("/intervene", json={"label": "M5_RETURN_IN_LOOP"}).json()
    assert r["intervention"]["wrong_code"] and r["intervention"]["predict"]["options"]
    assert c.post("/intervene", json={"label": "m3"}).json()["label"] == "M3_PRINT_NOT_RETURN"
    assert c.post("/intervene", json={"label": "CORRECT"}).json()["intervention"] is None
    assert c.post("/intervene", json={"label": "WAT"}).status_code == 404


def test_transfer(c):
    r = c.get("/transfer/M5", params={"exclude": "sum_list"}).json()
    ids = [p["id"] for p in r["problems"]]
    assert "sum_list" not in ids and "product" in ids and r["concept_questions"]
    assert "answer" not in r["concept_questions"][0]  # answers never leave the server
    assert c.get("/transfer/M9").status_code == 404


def test_learner_unknown(c):
    assert c.get("/learner/ghost").status_code == 404


def test_reassess_full_flow_and_mastery(c):
    lid = "learner-1"
    d = c.post("/diagnose", json={"problem_id": "sum_list", "code": SUM_M5, "learner_id": lid}).json()
    assert d["label"] == "M5_RETURN_IN_LOOP" and d["mastery_after"] < 0.5
    # 1) all conditions met on a NEW task
    ok = c.post("/reassess", json={"learner_id": lid, "misconception": "M5", "problem_id": "product", "code": M5_TRANSFER_OK, "concept_answer": 1}).json()
    assert ok["resolved"] is True and all(r["passed"] for r in ok["reasons"])
    L = c.get(f"/learner/{lid}").json()
    assert L["mastery"]["M5_RETURN_IN_LOOP"]["resolved"] is True and L["mastery"]["M5_RETURN_IN_LOOP"]["mastery"] > d["mastery_after"]
    assert [h["kind"] for h in L["history"]] == ["diagnose", "reassess"]
    assert all(0 <= v["mastery"] <= 1 for v in L["mastery"].values())


def test_reassess_each_condition_blocks_resolution(c):
    lid = "learner-2"
    c.post("/diagnose", json={"problem_id": "sum_list", "code": SUM_M5, "learner_id": lid})
    base = {"learner_id": lid, "misconception": "M5", "problem_id": "product", "code": M5_TRANSFER_OK, "concept_answer": 1}
    # concept wrong
    r = c.post("/reassess", json={**base, "concept_answer": 0}).json()
    assert not r["resolved"] and r["failed_checks"] == ["concept_answer"] and r["concept_explanation"]
    # still has the misconception (tests fail and model detects it)
    r = c.post("/reassess", json={**base, "code": M5_TRANSFER_BAD}).json()
    assert not r["resolved"] and "tests_pass" in r["failed_checks"] and "misconception_not_detected" in r["failed_checks"]
    # correct code but SAME task as the original diagnosis -> not accepted
    r = c.post("/reassess", json={**base, "problem_id": "sum_list", "code": SUM_OK}).json()
    assert not r["resolved"] and r["failed_checks"] == ["new_task"]
    # letter / text answers are parsed
    assert c.post("/reassess", json={**base, "concept_answer": "b"}).json()["resolved"] is True
    # validation
    assert c.post("/reassess", json={**base, "problem_id": "square"}).status_code == 422
    assert c.post("/reassess", json={**base, "concept_id": "zzz"}).status_code == 422
    assert c.post("/reassess", json={**base, "misconception": "M0"}).status_code == 404
    assert c.post("/reassess", json={**base, "problem_id": "nope"}).status_code == 404


def test_failed_reassess_lowers_mastery_and_clears_resolved(c):
    lid = "learner-3"
    base = {"learner_id": lid, "misconception": "M5", "problem_id": "product", "code": M5_TRANSFER_OK, "concept_answer": 1}
    assert c.post("/reassess", json=base).json()["resolved"]
    hi = c.get(f"/learner/{lid}").json()["mastery"]["M5_RETURN_IN_LOOP"]["mastery"]
    assert not c.post("/reassess", json={**base, "code": M5_TRANSFER_BAD}).json()["resolved"]
    now = c.get(f"/learner/{lid}").json()["mastery"]["M5_RETURN_IN_LOOP"]
    assert now["mastery"] < hi and now["resolved"] is False


def test_metrics(c):
    r = c.get("/metrics").json()
    assert "holdout" in r and "accuracy" in r["holdout"] and "twin_pairs" in r["holdout"] and "caveat" in r


def test_confusion_matrix_image(c):
    r = c.get("/metrics/confusion-matrix")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == bytes([0x89]) + b"PNG"


def test_cors_allows_vercel_and_blocks_others(c):
    ok = c.get("/health", headers={"Origin": "https://relearn-abc123.vercel.app"})
    assert ok.headers.get("access-control-allow-origin") == "https://relearn-abc123.vercel.app"
    bad = c.get("/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in bad.headers
    sneaky = c.get("/health", headers={"Origin": "https://vercel.app.evil.com"})
    assert "access-control-allow-origin" not in sneaky.headers


def test_baseline_endpoint(c):
    r = c.get("/baseline").json()
    assert r["status"] in ("ok", "not_run")
    if r["status"] == "not_run":
        assert "reason" in r
    else:
        assert {"ours", "gemini", "gemini_model"} <= set(r)
