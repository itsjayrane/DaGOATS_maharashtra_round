"""Problem-specific hints: AI hints with guardrails, deterministic fallback, reacting to the learner's code. No network."""
import json, os, re, tempfile

os.environ.setdefault("RELEARN_DB", os.path.join(tempfile.mkdtemp(), "own.db"))  # never the dev database

import pytest
from fastapi.testclient import TestClient

from app import custom, draft, hint, hintgen, sandbox
from app.main import PROBLEMS, app
from relearn_ml import references

KEY = "sk-test-NEVER-SHOW-THIS-789"
Q = "Write a function that returns the second largest distinct number in a list, or None if there isn't one"
REF = ("def second_largest(nums):\n    distinct = sorted(set(nums))\n    if len(distinct) < 2:\n        return None\n"
       "    return distinct[-2]\n")
DRAFT = json.dumps({"function_name": "second_largest", "reference_solution": REF, "assumptions": "none",
                    "tests": [{"input": [[3, 1, 2]]}, {"input": [[5, 5]]}, {"input": [[]]}, {"input": [[2, 9, 7, 9]]}, {"input": [[-1, -5]]}]})
GOOD = ["For [2, 9, 7, 9] the answer is 7: the biggest number that is not the maximum.",
        "Remove duplicates first, then find the largest value that is smaller than the maximum.",
        "Start with: unique = set(nums)"]
OWN = dict(id="custom-own", fn="second_largest", prompt=Q, params=["nums"],
           tests=[dict(args=[[3, 1, 2]], expected=2), dict(args=[[5, 5]], expected=None), dict(args=[[]], expected=None),
                  dict(args=[[2, 9, 7, 9]], expected=7)])


def reply(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


class FakeLLM:
    """Separate reply queues for drafting and for hints (told apart by the system prompt)."""

    def __init__(self, drafts=(), hints=()):
        self.drafts, self.hints, self.calls = list(drafts), list(hints), []

    def __call__(self, url, payload, headers, timeout):
        kind = "hints" if "progressive hints" in payload["messages"][0]["content"] else "draft"
        self.calls.append(dict(kind=kind, payload=payload, timeout=timeout))
        q = self.hints if kind == "hints" else self.drafts
        return reply(q.pop(0) if q else "nothing left")


@pytest.fixture
def llm(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("LLM_API_KEY", KEY)

    def install(**kw):
        fake = FakeLLM(**kw)
        monkeypatch.setattr(draft, "http_post", fake)
        return fake
    return install


@pytest.fixture
def no_llm(monkeypatch):
    for k in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def ask(c, pid, code, level, lid=None):
    return c.post("/hint", json={"problem_id": pid, "code": code, "hint_level": level, "learner_id": lid}).json()


def norm(s):
    return re.sub(r"\s+", "", s)


# ---------------------------------------------------------------- AI hints + guardrails
def test_ai_hints_are_accepted_when_valid_and_served(c, llm):
    fake = llm(drafts=[DRAFT], hints=[json.dumps({"hints": GOOD})])
    p = c.post("/custom/practice", json={"statement": Q}).json()
    assert "hints" not in p, "hints are served one at a time by /hint, not with the problem"
    stored = custom.get(p["id"])["hints"]
    assert stored["source"] == "ai" and [stored[k] for k in "123"] == GOOD
    h = ask(c, p["id"], p["starter"], 1)
    assert h["hint"] == GOOD[0] and h["prefix"] is None and h["kind"] == "problem"
    hint_call = next(x for x in fake.calls if x["kind"] == "hints")
    user = hint_call["payload"]["messages"][1]["content"]
    assert "<code>" in user and REF in user and "second_largest([2, 9, 7, 9]) returns 7" in user, "verified code + sandbox example"
    assert hint_call["timeout"] <= hintgen.MAX_WORDS and hint_call["payload"]["max_tokens"] == 1000


@pytest.mark.parametrize("bad,why", [
    ([GOOD[0], GOOD[1], "Start with:\n" + REF], "solution"),
    ([GOOD[0], GOOD[1], "Start with: distinct = sorted(set(nums))\nif len(distinct) < 2:"], "solution"),
    ([GOOD[0], GOOD[1], "Use these lines:\nunique = set(nums)\nordered = sorted(unique)"], "more than one line"),
    ([GOOD[0], "Write `unique = set(nums)` and then sort it.", GOOD[2]], "hint 2 contains code"),
    (["For [2, 9, 7, 9] the answer is 7 " + "because " * 30, GOOD[1], GOOD[2]], "longer than"),
    ([GOOD[0], GOOD[0], GOOD[2]], "repeat"),
    (hintgen.GENERIC, "generic"),
    (["Find the second biggest value in the list, ignoring repeats.", GOOD[1], GOOD[2]], "real example"),
    ([GOOD[0], GOOD[1]], "exactly 3"),
])
def test_guardrails_reject_bad_hints(bad, why):
    with pytest.raises(ValueError, match=why):
        hintgen.validate(bad, OWN, REF)
    assert hintgen.validate(GOOD, OWN, REF) == GOOD


def test_rejected_twice_falls_back_to_deterministic(c, llm):
    bad = json.dumps({"hints": hintgen.GENERIC})
    fake = llm(drafts=[DRAFT], hints=[bad, json.dumps({"hints": [GOOD[0], GOOD[0], GOOD[2]]})])
    p = c.post("/custom/practice", json={"statement": Q}).json()
    hints = custom.get(p["id"])["hints"]
    assert hints["source"] == "builtin" and len([x for x in fake.calls if x["kind"] == "hints"]) == 2, "one regeneration only"
    regen = [x for x in fake.calls if x["kind"] == "hints"][1]["payload"]["messages"][-1]["content"]
    assert regen.startswith("Rejected:") and "generic" in regen


def test_rejected_once_then_regenerated(c, llm):
    llm(drafts=[DRAFT], hints=["not json", json.dumps({"hints": GOOD})])
    p = c.post("/custom/practice", json={"statement": Q}).json()
    assert custom.get(p["id"])["hints"]["source"] == "ai"


def test_draft_endpoint_returns_hints_for_teacher_review(c, llm):
    llm(drafts=[DRAFT], hints=[json.dumps({"hints": GOOD})])
    d = c.post("/custom/draft", json={"statement": Q}).json()
    assert d["hints"] == GOOD and d["hints_source"] == "ai"


# ---------------------------------------------------------------- deterministic hints
def test_deterministic_second_largest_mentions_the_example_and_the_concept():
    h = hintgen.deterministic(OWN, REF)
    assert h["1"] == "For [2, 9, 7, 9], the answer is 7." and "set()" in h["2"] and "sort" in h["2"]
    assert h["3"] == "Start with: distinct = sorted(set(nums))" and h["source"] == "builtin"
    assert hintgen.validate([h["1"], h["2"], h["3"]], OWN, REF)


def test_deterministic_sum_list():
    p, ref = PROBLEMS["sum_list"], references.reference_variants()["sum_list"][0]
    h = hintgen.deterministic(p, ref)
    t = hintgen.example(p)
    assert hintgen.fmt(t["args"][0]) in h["1"] and str(t["expected"]) in h["1"]
    assert "loop over every item in nums" in h["2"] and "running total" in h["2"] and h["3"] == "Start with: total = 0"


def test_teacher_problem_gets_specific_hints_and_validated_custom_hints(c, no_llm):
    body = dict(statement="Return the second largest distinct number, or None.", function_name="second_largest",
                reference_solution=REF, tests=[{"input": [[3, 1, 2]]}, {"input": [[5, 5]]}, {"input": [[]]}, {"input": [[2, 9, 7, 9]]}])
    plain = c.post("/custom/problems", json=body).json()
    assert custom.get(plain["id"])["hints"]["1"] == "Return the second largest distinct number, or None. For example, for [2, 9, 7, 9] the answer is 7."
    with_ai = c.post("/custom/problems", json={**body, "source": "ai_draft", "hints": GOOD}).json()
    assert custom.get(with_ai["id"])["hints"]["source"] == "ai"
    bad = c.post("/custom/problems", json={**body, "hints": hintgen.GENERIC}).json()
    assert custom.get(bad["id"])["hints"]["source"] == "builtin", "invalid hints are replaced, not stored"


def test_backfill_for_custom_problems_without_hints(c, no_llm):
    p = custom.build(Q, "second_largest", REF, [{"input": t["args"]} for t in OWN["tests"]], sandbox.run, source="ai_draft")
    custom.save(p)  # an older problem: no hints stored
    assert "hints" not in custom.get(p["id"])
    h = ask(c, p["id"], p["starter"], 2)
    assert "set()" in h["hint"] and custom.get(p["id"])["hints"]["2"] == h["hint"]


# ---------------------------------------------------------------- reacting to the learner's code
def test_wrong_code_gets_the_failing_test_as_a_prefix(c, no_llm):
    h = ask(c, "sum_list", "def sum_list(nums):\n    return 0\n", 2, "hint-pre-1")
    assert h["prefix"].startswith("Right now sum_list(") and "gives 0 but should give" in h["prefix"]
    assert h["hint"] == hint.HINTS["problems"]["sum_list"]["2"] or h["kind"] == "misconception"
    s = ask(c, "sum_list", PROBLEMS["sum_list"]["starter"], 1)
    assert s["prefix"] is None and s["hint"] == hint.HINTS["problems"]["sum_list"]["1"], "starter code: level 1 as is"
    e = ask(c, "sum_list", "def sum_list(nums)\n    return 0\n", 1)
    assert e["prefix"] == "Right now Python could not read your code."
    x = ask(c, "last_item", "def last_item(items):\n    return items[len(items)]\n", 1)
    assert "stops with IndexError" in x["prefix"]


def test_diagnosed_misconception_uses_the_misconception_variant(c, no_llm):
    code = "def product(nums):\n    p = 1\n    for x in nums:\n        p *= x\n        return p\n"
    hs = [ask(c, "product", code, lvl, "hint-m5") for lvl in (1, 2, 3)]
    assert all(h["kind"] == "misconception" for h in hs)
    assert [h["hint"] for h in hs] == [hint.HINTS["misconceptions"]["M5_RETURN_IN_LOOP"][str(l)] for l in (1, 2, 3)]
    assert all(h["prefix"].startswith("Right now product(") for h in hs)


# ---------------------------------------------------------------- never generic, never the solution
def test_no_problem_hint_equals_a_generic_template_or_contains_the_solution(c, no_llm):
    generic = {norm(g) for g in hintgen.GENERIC}
    for pid, p in PROBLEMS.items():
        ref = references.reference_variants()[pid][0]
        for source in (hint.problem_hints(p), hintgen.deterministic(p, ref)):
            for lvl in "123":
                assert norm(source[lvl]) not in generic, (pid, lvl)
                assert norm(ref) not in norm(source[lvl]), (pid, lvl, "full solution in a hint")
    own = hintgen.deterministic(OWN, REF)
    assert all(norm(own[l]) not in generic and norm(REF) not in norm(own[l]) for l in "123")
