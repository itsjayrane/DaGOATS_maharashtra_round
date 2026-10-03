"""Item 1: input caps, rate limits, sandbox memory limits, fixer time budget + cache, synthetic demo seed."""
import json, os, sqlite3, sys, tempfile, time

os.environ["RELEARN_DB"] = os.path.join(tempfile.mkdtemp(), "robust.db")

import pytest
from fastapi.testclient import TestClient

from app import db, ratelimit, sandbox
from app.main import MAX_CODE_CHARS, PROBLEMS, app
from relearn_ml import fixer
from relearn_ml import sandbox as child

STARTER = "def sum_list(nums):\n    pass\n"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def limits_on(monkeypatch):
    monkeypatch.setenv("RELEARN_RATE_LIMIT", "on")
    ratelimit.reset()
    yield
    ratelimit.reset()


# ------------------------------------------------------------------ MAX_CODE_CHARS
def test_code_longer_than_the_cap_is_rejected_with_422(c):
    big = "def sum_list(nums):\n    return 0\n" + "#" * MAX_CODE_CHARS
    assert c.post("/diagnose", json={"problem_id": "sum_list", "code": big}).status_code == 422
    assert c.post("/hint", json={"problem_id": "sum_list", "code": big, "hint_level": 1}).status_code == 422
    assert c.post("/intervene", json={"label": "M5", "problem_id": "sum_list", "code": big}).status_code == 422
    assert c.post("/reassess", json={"learner_id": "x", "misconception": "M5", "problem_id": "product", "code": big, "concept_answer": 1}).status_code == 422
    ok = ("def sum_list(nums):\n    return 0\n" + "#" * MAX_CODE_CHARS)[:MAX_CODE_CHARS]
    assert c.post("/diagnose", json={"problem_id": "sum_list", "code": ok}).status_code == 200


# ------------------------------------------------------------------ rate limits
def hint_req(c, learner=None, xff=None):
    headers = {"X-Forwarded-For": xff} if xff else {}
    return c.post("/hint", json={"problem_id": "sum_list", "code": STARTER, "hint_level": 1, "learner_id": learner}, headers=headers)


def test_hint_is_limited_to_10_per_minute_per_ip_with_retry_after(c, limits_on):
    codes = [hint_req(c, xff="10.0.0.1").status_code for _ in range(10)]
    assert codes == [200] * 10
    r = hint_req(c, xff="10.0.0.1")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1 and "wait" in r.json()["detail"]
    assert hint_req(c, xff="10.0.0.2").status_code == 200, "another client is not affected"


def test_first_x_forwarded_for_entry_is_the_client(c, limits_on):
    for _ in range(10):
        assert hint_req(c, xff="10.1.1.1, 172.16.0.9").status_code == 200
    assert hint_req(c, xff="10.1.1.1").status_code == 429  # same client behind a different proxy chain


def test_limit_also_applies_per_learner_across_ips(c, limits_on):
    for i in range(10):
        assert hint_req(c, learner="same-learner", xff=f"10.2.0.{i}").status_code == 200
    assert hint_req(c, learner="same-learner", xff="10.2.0.99").status_code == 429


def test_diagnose_allows_30_per_minute(c, limits_on, monkeypatch):
    monkeypatch.setattr(ratelimit, "_now", lambda: 1000.0)  # frozen clock: no refill during the ~5 s of real sandbox runs
    body = {"problem_id": "sum_list", "code": "def sum_list(nums):\n    return 0\n"}
    codes = [c.post("/diagnose", json=body, headers={"X-Forwarded-For": "10.3.0.1"}).status_code for _ in range(31)]
    assert codes[:30] == [200] * 30 and codes[30] == 429


def test_rate_limit_can_be_switched_off(c, monkeypatch):
    monkeypatch.setenv("RELEARN_RATE_LIMIT", "off")
    assert all(hint_req(c, xff="10.4.0.1").status_code == 200 for _ in range(15))


# ------------------------------------------------------------------ sandbox memory limits
def test_memory_error_becomes_memory_limit_with_a_friendly_message(c):
    code = "def sum_list(nums):\n    big = [0] * (10 ** 10)\n    return 0\n"  # ~80 GB: MemoryError on any OS
    r = c.post("/diagnose", json={"problem_id": "sum_list", "code": code}).json()
    assert r["status"] == "memory_limit" and r["label"] is None and "too much memory" in r["error"]


@pytest.mark.skipif(os.name != "posix", reason="resource.setrlimit is POSIX-only (Linux in production)")
def test_posix_child_has_an_address_space_limit():
    code = "def sum_list(nums):\n    block = bytearray(700 * 1024 * 1024)\n    return len(block)\n"  # 700 MB > 512 MB limit
    res = sandbox.run(code, PROBLEMS["sum_list"])
    assert res["status"] == "memory_limit"


def test_limits_are_only_applied_on_posix():
    if os.name == "posix":
        pytest.skip("covered by the POSIX test above")
    assert child.apply_limits() is False  # Windows dev: guarded, no crash


# ------------------------------------------------------------------ fixer budget + cache
def test_fixer_respects_its_time_budget_and_caches(monkeypatch):
    calls = []

    def slow_run(code, problem):
        calls.append(code)
        time.sleep(0.4)
        return {"status": "ok", "tests": [{"ok": False}]}  # nothing ever passes -> worst case search
    code = "def sum_list(nums):\n    total = 0\n    for i in range(1, len(nums)):\n        total += nums[i]\n    return total  # budget-test\n"
    t = time.time()
    assert fixer.find_fix(code, PROBLEMS["sum_list"], "M2_INDEX_FROM_ONE", slow_run, time_budget=1.0) is None
    assert time.time() - t < 2.0 and len(calls) <= 4
    n = len(calls)
    t = time.time()
    fixer.find_fix(code, PROBLEMS["sum_list"], "M2_INDEX_FROM_ONE", slow_run, time_budget=1.0)
    assert len(calls) == n and time.time() - t < 0.1, "second call is served from the cache"


def test_fixer_caps_the_number_of_candidates():
    assert fixer.MAX_CANDIDATES == 40 and fixer.MAX_ATTEMPTS <= fixer.MAX_CANDIDATES and fixer.TIME_BUDGET_S == 3.0


# ------------------------------------------------------------------ RELEARN_SEED_DEMO
def test_demo_seed_creates_a_labelled_synthetic_learner_once(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "seed.db"))
    monkeypatch.setenv("RELEARN_SEED_DEMO", "1")
    db.init()
    db.init()  # idempotent
    con = sqlite3.connect(db.DB_PATH)
    rows = con.execute("SELECT detail FROM attempts WHERE learner_id=?", (db.DEMO_LEARNER,)).fetchall()
    assert db.DEMO_LEARNER == "demo-learner (synthetic)" and len(rows) == len(db._DEMO)
    assert all(json.loads(d)["synthetic"] is True for (d,) in rows)
    learner = db.learner(db.DEMO_LEARNER)
    assert learner["mastery"]["M5_RETURN_IN_LOOP"]["resolved"] is True and len(learner["history"]) == len(db._DEMO)


def test_no_seed_without_the_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "noseed.db"))
    monkeypatch.delenv("RELEARN_SEED_DEMO", raising=False)
    db.init()
    assert db.learner(db.DEMO_LEARNER) is None
