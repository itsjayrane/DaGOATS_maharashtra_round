"""'Practise your own question': the LLM only drafts; the sandbox decides. A fake `post` - no network, no real key."""
import json, os, socket, tempfile, time, urllib.error

os.environ.setdefault("RELEARN_DB", os.path.join(tempfile.mkdtemp(), "own.db"))  # never the dev database

import pytest
from fastapi.testclient import TestClient

from app import custom, db, draft, sandbox
from app.main import app

KEY = "sk-test-NEVER-SHOW-THIS-123"
REF = ("def second_largest(nums):\n    distinct = sorted(set(nums))\n    if len(distinct) < 2:\n        return None\n"
       "    return distinct[-2]\n")
WRONG = "def second_largest(nums):\n    return max(nums)\n"
MUTATING = ("def second_largest(nums):\n    nums.sort()\n    distinct = sorted(set(nums))\n    if len(distinct) < 2:\n"
            "        return None\n    return distinct[-2]\n")
TESTS = [{"input": [[3, 1, 2]], "expected": 999}, {"input": [[5, 5]]}, {"input": [[]]}, {"input": [[1, 2, 2, 3]]}, {"input": [[-1, -5]]}]
QUESTION = "Write a function that returns the second largest distinct number in a list, or None if there isn't one"


def draft_json(ref=REF, tests=TESTS, name="second_largest", assumptions="Duplicates count once."):
    return json.dumps({"function_name": name, "reference_solution": ref, "tests": tests, "assumptions": assumptions})


def reply(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


class FakeLLM:
    """Stands in for http_post: returns queued replies (or raises queued exceptions) and records every call."""

    def __init__(self, *items, delay=0.0):
        self.items, self.calls, self.delay = list(items), [], delay

    def __call__(self, url, payload, headers, timeout):
        self.calls.append(dict(url=url, payload=payload, headers=headers, timeout=timeout))
        if self.delay:
            time.sleep(self.delay)
        item = self.items.pop(0) if self.items else "no more replies"
        if isinstance(item, BaseException):
            raise item
        return item if isinstance(item, dict) else reply(item)


@pytest.fixture
def llm(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("LLM_API_KEY", KEY)

    def install(*items, delay=0.0):
        fake = FakeLLM(*items, delay=delay)
        monkeypatch.setattr(draft, "http_post", fake)
        return fake
    return install


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def no_secrets(r):
    text = r.text
    assert KEY not in text and "llm.example.test" not in text and "Traceback" not in text
    return r


# ---------------------------------------------------------------- configuration
def test_status_configured_and_not(c, monkeypatch):
    for k in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert c.get("/custom/draft/status").json() == {"available": False, "model": None}
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    assert c.get("/custom/draft/status").json()["available"] is False, "a remote provider needs a key"
    monkeypatch.setenv("LLM_API_KEY", KEY)
    r = no_secrets(c.get("/custom/draft/status"))
    assert r.json() == {"available": True, "model": "fake-model"}
    monkeypatch.delenv("LLM_API_KEY")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    assert c.get("/custom/draft/status").json()["available"] is True, "a local server (Ollama) needs no key"


def test_not_configured_is_503_and_health_is_unchanged(c, monkeypatch):
    for k in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    r = c.post("/custom/practice", json={"statement": QUESTION})
    assert r.status_code == 503 and "not switched on" in r.json()["detail"]
    assert c.get("/health").json() == {"ok": True, "model_loaded": True, "llm": "none"}


# ---------------------------------------------------------------- practice flow
def test_practice_saves_a_public_problem_with_sandbox_expected_values(c, llm):
    fake = llm(draft_json())
    r = no_secrets(c.post("/custom/practice", json={"statement": QUESTION, "learner_id": "own-1"}))
    assert r.status_code == 200, r.text
    p = r.json()
    assert "reference_solution" not in r.text and "reference" not in p and "distinct[-2]" not in r.text
    assert p["source"] == "ai_draft" and p["badge"] == custom.BADGE_AI and p["custom"] is True
    assert p["example"] == {"args": [[3, 1, 2]], "expected": 2}, "expected comes from running the reference, not the LLM's 999"
    assert p["assumptions"] == "Duplicates count once." and p["attempts"] == 1 and p["starter"].startswith("def second_largest(nums):")
    saved = custom.get(p["id"])
    assert [t["expected"] for t in saved["tests"]] == [2, None, None, 2, -5] and saved["source"] == "ai_draft"
    sent = fake.calls[0]
    assert sent["url"] == "https://llm.example.test/v1/chat/completions" and sent["headers"]["Authorization"] == f"Bearer {KEY}"
    assert sent["payload"]["temperature"] == 0.2 and sent["payload"]["max_tokens"] == 2000
    assert "response_format" not in sent["payload"] and "tools" not in sent["payload"]
    msgs = sent["payload"]["messages"]
    assert msgs[0]["role"] == "system" and "<question>" in msgs[0]["content"] and "DATA" in msgs[0]["content"]
    assert msgs[1]["content"] == f"<question>\n{QUESTION}\n</question>"
    assert 0 < sent["timeout"] <= draft.BUDGET_S


def test_problems_list_never_contains_reference_solutions(c, llm):
    llm(draft_json())
    pid = c.post("/custom/practice", json={"statement": QUESTION}).json()["id"]
    r = c.get("/problems")
    mine = next(x for x in r.json() if x["id"] == pid)
    assert mine["badge"] == custom.BADGE_AI and "reference" not in mine and "reference_solution" not in r.text
    assert "distinct[-2]" not in c.get("/custom/problems").text


def test_diagnose_correct_and_wrong_solutions(c, llm):
    llm(draft_json())
    pid = c.post("/custom/practice", json={"statement": QUESTION}).json()["id"]
    ok = c.post("/diagnose", json={"problem_id": pid, "code": REF}).json()
    assert ok["verdict"] == "correct" and ok["in_distribution"] is False and ok["passed"]
    bad = c.post("/diagnose", json={"problem_id": pid, "code": WRONG}).json()
    assert not bad["passed"] and bad["verdict"] in ("misconception", "unknown")
    assert any(not t["ok"] for t in bad["test_results"])
    e = c.post("/explain", json={"problem_id": pid, "code": WRONG}).json()
    assert e["best_solution"] is None and e["solution_hidden"] is True, "the solution stays hidden until asked for"
    assert e["where_it_went_wrong"]["words"] and "distinct[-2]" not in json.dumps(e)


def test_solution_endpoint_reveals_and_logs(c, llm):
    llm(draft_json())
    pid = c.post("/custom/practice", json={"statement": QUESTION}).json()["id"]
    assert db.solution_events(pid) == []
    s = c.get(f"/custom/problems/{pid}/solution", params={"learner_id": "own-2"}).json()
    assert s["reference_solution"] == REF and s["verified"] == {"passed": 5, "total": 5} and "passes all 5 tests" in s["note"]
    ev = db.solution_events(pid)
    assert len(ev) == 1 and ev[0]["event"] == "solution_revealed" and ev[0]["learner_id"] == "own-2"
    assert c.get("/custom/problems/sum_list/solution").status_code == 404
    assert c.get("/custom/problems/custom-nope/solution").status_code == 404


# ---------------------------------------------------------------- parsing + repair loop
def test_fenced_and_chatty_json_is_parsed():
    chatty = "Sure! Here is the exercise:\n```json\n" + draft_json() + "\n```\nHope this helps {not json}"
    d = draft.parse(chatty)
    assert d["function_name"] == "second_largest" and d["reference_solution"] == REF
    assert all(set(t) == {"input"} for t in d["tests"]), "expected values from the model are dropped"
    assert draft.first_json_object('text {"a": "} { tricky \\" quote", "b": {"c": 1}} tail') == '{"a": "} { tricky \\" quote", "b": {"c": 1}}'
    assert draft.first_json_object("no object here") is None


def test_bad_json_then_good_takes_two_attempts(c, llm):
    fake = llm('{"function_name": "second_largest", "reference_solution": "def f(:", ', draft_json())
    r = c.post("/custom/draft", json={"statement": QUESTION})
    assert r.status_code == 200 and r.json()["attempts"] == 2 and len(fake.calls) == 2
    repair = fake.calls[1]["payload"]["messages"][-1]["content"]
    assert repair.startswith("The grader rejected this draft:") and repair.endswith("reply with only the corrected JSON object.")
    body = r.json()
    assert body["reference_solution"] == REF and [t["expected"] for t in body["tests"]] == [2, None, None, 2, -5]


def test_mutating_reference_is_repaired_with_the_sandbox_error(c, llm):
    fake = llm(draft_json(ref=MUTATING), draft_json())
    r = c.post("/custom/draft", json={"statement": QUESTION})
    assert r.status_code == 200 and r.json()["attempts"] == 2
    assert "changes its input" in fake.calls[1]["payload"]["messages"][-1]["content"]


def test_three_bad_drafts_give_a_friendly_422(c, llm):
    fake = llm("nope", draft_json(ref="def other(nums):\n    return 1\n"), '{"tests": []}')
    r = no_secrets(c.post("/custom/practice", json={"statement": QUESTION}))
    assert r.status_code == 422 and "rewording" in r.json()["detail"] and len(fake.calls) == 3


def test_not_a_programming_question_is_a_friendly_422(c, llm):
    llm('{"error": "not a programming exercise"}')
    r = c.post("/custom/practice", json={"statement": "What is the capital of France, please?"})
    assert r.status_code == 422 and "does not look like a small Python exercise" in r.json()["detail"]


def test_time_budget_is_respected_without_hanging(llm):
    fake = llm("garbage", "garbage", "garbage", delay=1.2)
    t0 = time.monotonic()
    with pytest.raises(draft.HTTPException) as e:
        draft.generate(QUESTION, sandbox.run, budget_s=4.0)
    assert e.value.status_code == 422 and time.monotonic() - t0 < 4.0, "never runs past the budget"
    assert len(fake.calls) == 2, "the third call is not started with < MIN_CALL_S left"
    assert fake.calls[1]["timeout"] < fake.calls[0]["timeout"] <= 4.0, "per-call timeout = remaining budget"


def test_provider_timeout_is_a_friendly_502(c, llm):
    llm(socket.timeout("timed out"))
    r = no_secrets(c.post("/custom/practice", json={"statement": QUESTION}))
    assert r.status_code == 502 and r.json()["detail"] == draft.MSG_DOWN


def test_short_statement_is_422(c, llm):
    llm(draft_json())
    r = c.post("/custom/practice", json={"statement": "  sort   "})
    assert r.status_code == 422 and "at least 10 characters" in r.json()["detail"]


@pytest.mark.parametrize("error,message", [
    (urllib.error.HTTPError("https://llm.example.test/v1/chat/completions", 429, f"rate limited for key {KEY}", {}, None), draft.MSG_RATE),
    (urllib.error.HTTPError("https://llm.example.test/v1/chat/completions", 500, f"internal error {KEY}", {}, None), draft.MSG_DOWN),
    (urllib.error.URLError(f"cannot resolve llm.example.test with {KEY}"), draft.MSG_DOWN),
    (ValueError(f"bad json from upstream {KEY}"), draft.MSG_DOWN),
    ({"error": {"message": f"invalid key {KEY}"}}, draft.MSG_DOWN),  # 200 OK but no choices
])
def test_provider_failures_are_502_without_raw_text_or_key(c, llm, error, message):
    llm(error)
    r = no_secrets(c.post("/custom/practice", json={"statement": QUESTION}))
    assert r.status_code == 502 and r.json()["detail"] == message


# ---------------------------------------------------------------- teacher path
def test_teacher_path_keeps_the_teacher_badge_and_validates_source(c):
    body = dict(statement="Return the second largest distinct number, or None.", function_name="second_largest",
                reference_solution=REF, tests=[{"input": t["input"]} for t in TESTS])
    t = c.post("/custom/problems", json=body).json()
    assert t["badge"] == custom.BADGE and t["source"] == "teacher"
    a = c.post("/custom/problems", json={**body, "source": "ai_draft"}).json()
    assert a["badge"] == custom.BADGE_AI and a["source"] == "ai_draft"
    assert c.post("/custom/problems", json={**body, "source": "robot"}).status_code == 422
