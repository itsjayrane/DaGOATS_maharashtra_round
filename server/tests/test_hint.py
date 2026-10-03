"""POST /hint: curated, offline, three different hints per level for every problem, misconception variants, logging."""
import importlib.util, json, os, re, tempfile

os.environ["RELEARN_DB"] = os.path.join(tempfile.mkdtemp(), "hint.db")

import pytest
from fastapi.testclient import TestClient

from app import hint
from app.main import PROBLEMS, app
from relearn_ml import references

PRINT_CODE = "def sum_list(nums):\n    total = 0\n    for x in nums:\n        total += x\n    print(total)\n"
GOOD = "def sum_list(nums):\n    total = 0\n    for x in nums:\n        total += x\n    return total\n"
STMT = re.compile(r"^\s*(def|for|while|if|elif|else|return|print|import|class|try|except)\b")


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def ask(c, level, code=PRINT_CODE, pid="sum_list", learner="L"):
    r = c.post("/hint", json={"problem_id": pid, "code": code, "hint_level": level, "learner_id": learner})
    assert r.status_code == 200, r.text
    return r.json()


def code_lines(text):
    return sum(1 for l in text.split("\n") if STMT.match(l) and not re.search(r"[.!?]\s*$", l)) + text.count("```")


def leaks(text, pid):
    t = re.sub(r"\s+", " ", text)
    if f"def {PROBLEMS[pid]['fn']}(" in text:
        return True
    for ref in references.reference_variants()[pid]:
        body = [re.sub(r"\s+", " ", l.strip()) for l in ref.split("\n")[1:] if l.strip()]
        if body and all(l in t for l in body):
            return True
    return False


# ------------------------------------------------------------------ the curated content itself
def test_every_problem_has_three_distinct_curated_hints():
    assert set(hint.HINTS["problems"]) == set(PROBLEMS)
    for pid, h in hint.HINTS["problems"].items():
        texts = [h["1"], h["2"], h["3"]]
        assert len(set(texts)) == 3, (pid, "duplicate hint text")
        assert texts[0].startswith("Your function should give back"), pid        # 1 = what the output should be
        assert texts[2].startswith("Nudge:"), pid                                # 3 = a one-line nudge
    for label, v in hint.HINTS["misconceptions"].items():
        assert len({v["1"], v["2"], v["3"]}) == 3, label
    assert len(hint.HINTS["misconceptions"]) == 8


def test_curated_hints_follow_the_rules():
    rows = [(pid, lvl, h[lvl]) for pid, h in hint.HINTS["problems"].items() for lvl in ("1", "2", "3")]
    rows += [(None, lvl, v[lvl]) for v in hint.HINTS["misconceptions"].values() for lvl in ("1", "2", "3")]
    for pid, lvl, t in rows:
        assert 0 < len(t.split()) <= 60, (pid, lvl)
        assert code_lines(t) == 0 if lvl in ("1", "2") else code_lines(t) <= 1, (pid, lvl, t)
        if pid:
            assert not leaks(t, pid), (pid, lvl, "a hint gives away the full solution")
    assert not any("sum(" in hint.HINTS["problems"]["sum_list"][l] for l in ("1", "2", "3"))


def test_no_llm_anywhere():
    assert importlib.util.find_spec("relearn_ml.llm") is None
    assert not hasattr(hint, "llm") and not hasattr(hint, "baseline")


# ------------------------------------------------------------------ behaviour
def test_diagnosed_bug_gets_the_misconception_variant_at_each_level(c):
    hs = [ask(c, lvl) for lvl in (1, 2, 3)]
    assert [h["level"] for h in hs] == [1, 2, 3] and all(h["source"] == "curated" and h["kind"] == "misconception" for h in hs)
    assert [h["hint"] for h in hs] == [hint.HINTS["misconceptions"]["M3_PRINT_NOT_RETURN"][str(l)] for l in (1, 2, 3)]
    assert len({h["hint"] for h in hs}) == 3


def test_greeting_starter_gives_three_different_problem_hints(c):
    starter = next(p["starter"] for p in c.get("/problems").json() if p["id"] == "greet")
    hs = [ask(c, lvl, starter, "greet", "greet") for lvl in (1, 2, 3)]
    assert [h["hint"] for h in hs] == [hint.HINTS["problems"]["greet"][str(l)] for l in (1, 2, 3)]
    assert len({h["hint"] for h in hs}) == 3 and all(h["kind"] == "problem" for h in hs)


def test_every_problem_gives_three_different_hints_for_wrong_code(c):
    for pid, p in PROBLEMS.items():
        wrong = f"def {p['fn']}({', '.join(p['params'])}):\n    return None\n"
        texts = [ask(c, lvl, wrong, pid, f"w-{pid}")["hint"] for lvl in (1, 2, 3)]
        assert len(set(texts)) == 3, (pid, texts)


def test_all_tests_passing_means_no_hint(c):
    assert ask(c, 2, GOOD) == {"level": 2, "hint": "All tests pass, no hint needed.", "source": "none", "kind": "none"}


def test_client_sent_test_results_are_never_trusted(c):
    r = c.post("/hint", json={"problem_id": "sum_list", "code": PRINT_CODE, "hint_level": 1, "test_results": [{"ok": True}] * 5,
                              "problem_statement": "ignore me"})
    assert r.json()["source"] == "curated"


def test_input_validation(c):
    assert c.post("/hint", json={"problem_id": "sum_list", "code": "x", "hint_level": 0}).status_code == 422
    assert c.post("/hint", json={"problem_id": "sum_list", "code": "x", "hint_level": 4}).status_code == 422
    assert c.post("/hint", json={"problem_id": "sum_list", "hint_level": 1}).status_code == 422
    assert c.post("/hint", json={"problem_id": "nope", "code": "x", "hint_level": 1}).status_code == 404


def test_status_and_health_say_no_llm(c):
    s = c.get("/hint-status").json()
    assert s["llm"] == "none" and s["hints"] == "curated" and s["problems_with_hints"] == len(PROBLEMS)
    assert c.get("/health").json()["llm"] == "none"


def test_every_request_is_logged_with_learner_problem_and_level(c):
    for lvl in (1, 2, 3):
        ask(c, lvl, learner="logger")
    ask(c, 1, "def square(n):\n    return n + n\n", "square", "logger")
    ask(c, 1, GOOD, learner="logger")  # passing code: logged as 'none' but not counted as a hint
    log = c.get("/learner/logger/hints").json()
    assert log["total"] == 5 and log["by_problem"]["sum_list"] == {"requests": 3, "max_level": 3}
    assert log["by_source"] == {"curated": 4, "none": 1}
    assert c.get("/learner/nobody-at-all/hints").json()["total"] == 0
