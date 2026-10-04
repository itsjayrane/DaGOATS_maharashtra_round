"""'Show solution' for every problem: verified code + explanation (AI only if configured and valid). Fake LLM, no network."""
import json, os, tempfile, urllib.error

os.environ.setdefault("RELEARN_DB", os.path.join(tempfile.mkdtemp(), "own.db"))  # never the dev database

import pytest
from fastapi.testclient import TestClient

from app import db, draft, solution
from app.main import app
from relearn_ml import references

KEY = "sk-test-NEVER-SHOW-THIS-456"
SUM_REF = references.reference_variants()["sum_list"][0]
M5_PRODUCT = "def product(nums):\n    p = 1\n    for x in nums:\n        p *= x\n        return p\n"
OWN_REF = ("def second_largest(nums):\n    distinct = sorted(set(nums))\n    if len(distinct) < 2:\n        return None\n"
           "    return distinct[-2]\n")
GOOD_AI = {"summary": "It keeps a running total and adds every number to it.",
           "steps": ["Start with `total = 0`.", "Go through each number in the list.", "Add it to the total.", "Finally `return total`."],
           "key_idea": "Set the running total once, before the loop.",
           "common_mistake": "Resetting the total inside the loop, so only the last number counts."}


def reply(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


class FakeLLM:
    def __init__(self, *items):
        self.items, self.calls = list(items), []

    def __call__(self, url, payload, headers, timeout):
        self.calls.append(dict(url=url, payload=payload, headers=headers, timeout=timeout))
        item = self.items.pop(0) if self.items else "nothing"
        if isinstance(item, BaseException):
            raise item
        return item if isinstance(item, dict) else reply(item)


@pytest.fixture
def no_llm(monkeypatch):
    for k in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def llm(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("LLM_API_KEY", KEY)

    def install(*items):
        fake = FakeLLM(*items)
        monkeypatch.setattr(draft, "http_post", fake)
        return fake
    return install


@pytest.fixture(autouse=True)
def empty_cache():
    db.init()
    with db._lock, db.conn() as c:
        c.execute("DELETE FROM solution_explanations")


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def check_shape(e):
    assert set(e) == {"summary", "steps", "key_idea", "common_mistake"}
    assert 3 <= len(e["steps"]) <= 6 and all(isinstance(s, str) and s for s in e["steps"])
    assert e["summary"] and e["key_idea"] and e["common_mistake"]


# ---------------------------------------------------------------- built-in problems
def test_builtin_problem_without_llm_gets_the_reference_and_a_builtin_explanation(c, no_llm):
    r = c.get("/problems/sum_list/solution").json()
    assert r["solution"] == SUM_REF and r["source"] == "builtin" and r["verified"] == {"passed": 5, "total": 5}
    e = r["explanation"]
    check_shape(e)
    assert e["steps"][0] == "Start `total` at `0`." and e["steps"][-1] == "Return `total`."
    assert "outside the loop" in e["key_idea"].lower() and "your_fix" not in r
    assert not e["common_mistake"].startswith("You may"), "plain words"


def test_builtin_problem_with_llm_gets_an_ai_explanation_of_the_same_verified_code(c, llm):
    fake = llm(json.dumps(GOOD_AI))
    r = c.get("/problems/sum_list/solution").json()
    assert r["solution"] == SUM_REF and r["source"] == "ai" and r["explanation"] == GOOD_AI
    sent = fake.calls[0]
    assert sent["headers"]["User-Agent"] == "relearn/1.0" and sent["payload"]["max_tokens"] == 2000 and sent["timeout"] <= 15
    sysmsg, user = sent["payload"]["messages"][0]["content"], sent["payload"]["messages"][1]["content"]
    assert "<problem>" in sysmsg and "<code>" in sysmsg and "DATA" in sysmsg
    assert user.startswith("<problem>\n") and f"<code>\n{SUM_REF}\n</code>" in user


def test_gpt_oss_explanations_use_low_reasoning_and_2000_tokens(c, llm, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-120b")
    fake = llm(json.dumps(GOOD_AI))
    c.get("/problems/sum_list/solution")
    assert fake.calls[0]["payload"]["reasoning_effort"] == "low" and fake.calls[0]["payload"]["max_tokens"] == 2000


# ---------------------------------------------------------------- own-question / custom problems
def own_problem(c):
    body = dict(statement="Return the second largest distinct number in a list, or None.", function_name="second_largest",
                reference_solution=OWN_REF, tests=[{"input": [[3, 1, 2]]}, {"input": [[5, 5]]}, {"input": [[]]}, {"input": [[1, 2, 2, 3]]}],
                source="ai_draft")
    return c.post("/custom/problems", json=body).json()["id"]


def test_own_question_solution_is_the_sandbox_checked_reference(c, no_llm):
    pid = own_problem(c)
    r = c.get(f"/problems/{pid}/solution").json()
    assert r["solution"] == OWN_REF and r["source"] == "builtin" and r["verified"] == {"passed": 4, "total": 4}
    check_shape(r["explanation"])
    old = c.get(f"/custom/problems/{pid}/solution").json()  # alias keeps the older fields
    assert old["reference_solution"] == OWN_REF and "passes all 4 tests" in old["note"] and old["explanation"] == r["explanation"]


def test_own_question_with_llm(c, llm):
    pid = own_problem(c)
    ai = dict(GOOD_AI, steps=["Remove repeats with `set(nums)` and sort them.", "If fewer than two values remain, give back None.",
                             "Otherwise `return distinct[-2]`."], summary="It sorts the distinct values and takes the second largest.")
    llm(json.dumps(ai))
    r = c.get(f"/problems/{pid}/solution").json()
    assert r["solution"] == OWN_REF and r["source"] == "ai" and r["explanation"]["steps"][2] == "Otherwise `return distinct[-2]`."


# ---------------------------------------------------------------- fallbacks
@pytest.mark.parametrize("bad", [
    urllib.error.HTTPError("https://llm.example.test/v1/chat/completions", 500, f"boom {KEY}", {}, None),
    "Sure! here is my explanation: {not json",
    json.dumps(dict(GOOD_AI, steps=["Use `sum(nums)` instead.", "It is shorter.", "Return it."])),           # code not in the reference
    json.dumps(dict(GOOD_AI, summary="Better: ```def sum_list(n): return sum(n)```")),                        # a code block
    json.dumps(dict(GOOD_AI, key_idea="You could write def helper(x): first.")),                             # writes a function
    json.dumps(dict(GOOD_AI, steps=["word " * 40, "word " * 40, "word " * 40])),                              # too long
    json.dumps(dict(GOOD_AI, steps=["only one step"])),                                                      # 3-6 steps
    json.dumps({"summary": "no other fields"}),
    reply(""),
])
def test_any_bad_ai_reply_falls_back_to_the_builtin_explanation(c, llm, bad):
    llm(bad)
    r = c.get("/problems/sum_list/solution")
    assert r.status_code == 200 and KEY not in r.text and "boom" not in r.text
    j = r.json()
    assert j["source"] == "builtin" and j["solution"] == SUM_REF
    check_shape(j["explanation"])


def test_validate_accepts_quotes_of_the_reference_only():
    assert solution.validate(GOOD_AI, SUM_REF) == GOOD_AI
    with pytest.raises(ValueError):
        solution.validate(dict(GOOD_AI, summary="Uses `total += x * 2` here."), SUM_REF)


# ---------------------------------------------------------------- cache, your_fix, logging, mastery
def test_explanations_are_cached_so_the_llm_is_called_at_most_once(c, llm):
    fake = llm(json.dumps(GOOD_AI), json.dumps(GOOD_AI))
    a = c.get("/problems/sum_list/solution").json()
    b = c.get("/problems/sum_list/solution").json()
    assert a["explanation"] == b["explanation"] and b["source"] == "ai" and len(fake.calls) == 1
    fake2 = llm("garbage")
    first = c.get("/problems/product/solution").json()
    again = c.get("/problems/product/solution").json()
    assert first["source"] == again["source"] == "builtin" and len(fake2.calls) == 1, "a failed call is not retried either"


def test_your_fix_after_a_wrong_attempt_only(c, no_llm):
    lid = "sol-fix-1"
    assert "your_fix" not in c.get("/problems/product/solution", params={"learner_id": lid}).json(), "no attempt yet"
    c.post("/diagnose", json={"problem_id": "product", "code": M5_PRODUCT, "learner_id": lid})
    r = c.get("/problems/product/solution", params={"learner_id": lid}).json()
    f = r["your_fix"]
    assert f["your_code"] == M5_PRODUCT and f["code"] != M5_PRODUCT and f["changed_lines"]
    assert f["verified"]["passed"] == f["verified"]["total"]
    assert "your_fix" not in c.get("/problems/product/solution").json(), "no learner -> no fix"
    good = references.reference_variants()["product"][0]
    c.post("/diagnose", json={"problem_id": "product", "code": good, "learner_id": lid})
    assert "your_fix" not in c.get("/problems/product/solution", params={"learner_id": lid}).json(), "latest attempt passed"


def test_reveal_is_logged_and_never_changes_mastery(c, no_llm):
    lid = "sol-log-1"
    c.post("/diagnose", json={"problem_id": "product", "code": M5_PRODUCT, "learner_id": lid})
    before = c.get(f"/learner/{lid}").json()
    n0 = len(db.solution_events("square"))
    c.get("/problems/square/solution", params={"learner_id": lid})
    ev = db.solution_events("square")
    assert len(ev) == n0 + 1 and ev[-1]["event"] == "solution_revealed" and ev[-1]["learner_id"] == lid
    after = c.get(f"/learner/{lid}").json()
    assert after["mastery"] == before["mastery"] and after["history"] == before["history"]


def test_problem_list_never_contains_reference_solutions(c, no_llm):
    own_problem(c)
    text = c.get("/problems").text
    assert "reference" not in text and SUM_REF not in text and "distinct[-2]" not in text
    assert c.get("/problems/nope/solution").status_code == 404


def test_an_outer_json_fence_is_fine(c, llm):
    nl = chr(10)
    llm("```json" + nl + json.dumps(GOOD_AI) + nl + "```")
    r = c.get("/problems/sum_list/solution").json()
    assert r["source"] == "ai" and r["explanation"] == GOOD_AI
