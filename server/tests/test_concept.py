"""Problem-specific concept checks: built from problem + learner's code + misconception, verified, cached, with a logged fallback."""
import json, logging, os, pathlib, tempfile

os.environ["RELEARN_DB"] = os.path.join(tempfile.mkdtemp(), "concept.db")

import pytest
from fastapi.testclient import TestClient

from app import concept
from app.main import PROBLEMS, app

CONTENT = pathlib.Path(__file__).resolve().parents[2] / "content"

CASES = [  # (label, problem, learner code)
 ("M1_RANGE_OFF_BY_ONE", "sum_to_n", "def sum_to_n(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total\n"),
 ("M2_INDEX_FROM_ONE", "last_item", "def last_item(items):\n    return items[len(items)]\n"),
 ("M3_PRINT_NOT_RETURN", "square", "def square(n):\n    print(n * n)\n"),
 ("M4_ACCUMULATOR_RESET", "sum_list", "def sum_list(nums):\n    for x in nums:\n        total = 0\n        total += x\n    return total\n"),
 ("M5_RETURN_IN_LOOP", "product", "def product(nums):\n    p = 1\n    for x in nums:\n        p *= x\n        return p\n"),
 ("M6_FLOAT_DIVISION", "average", "def average(nums):\n    return sum(nums) // len(nums)\n"),
 ("M7_STRING_MUTABLE", "shout", "def shout(s):\n    s.upper()\n    return s + \"!\"\n"),
 ("M8_LIST_ALIASING", "append_copy", "def append_copy(lst, x):\n    res = lst\n    res.append(x)\n    return res\n"),
]
CORRECT_SUM = "def sum_list(nums):\n    total = 0\n    for x in nums:\n        total += x\n    return total\n"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def ask(c, label, pid, code, learner="L"):
    return c.post("/intervene", json={"label": label, "problem_id": pid, "code": code, "learner_id": learner}).json()


def true_behaviour(code, call):
    """Independent ground truth: run the learner's code on the quoted call in this process (test code is trusted)."""
    env = {}
    exec(code, env)
    try:
        return concept.fmt(eval(call, env))
    except Exception as e:
        return f"raises {type(e).__name__}"


@pytest.mark.parametrize("label,pid,code", CASES, ids=[x[0][:2] for x in CASES])
def test_each_misconception_gets_a_question_about_the_learners_own_code(c, label, pid, code):
    r = ask(c, label, pid, code)
    q = r["intervention"]["predict"]
    assert r["concept_source"] in ("generated", "cache") and q["source"] in ("generated", "cache")
    # the existing JSON shape is kept (UI keys) and the requested fields exist
    assert {"question", "options", "answer", "explanation"} <= set(q) and q["answer"] == q["answerIndex"] and q["code"] in q["question"]
    concept.validate(q)
    assert code.strip("\n") in q["question"], "the snippet is the learner's own code (same names, same structure)"
    assert PROBLEMS[pid]["fn"] in q["question"] and PROBLEMS[pid]["title"] in q["question"]
    assert len(q["options"]) == 4 and len(set(q["options"])) == 4 and 0 <= q["answer"] < 4
    assert q["explanation"]
    # the keyed answer is the code's ACTUAL behaviour, checked independently of the generator
    if label == "M8_LIST_ALIASING":
        assert q["options"][q["answer"]] == "[1, 2, 3]" and "[1, 2]" in q["options"]  # lst really was changed; the unchanged list is a distractor
    else:
        call = q["based_on"]["call"]
        truth = "None" if label == "M3_PRINT_NOT_RETURN" else true_behaviour(code, call)
        assert q["options"][q["answer"]] == truth, (q["options"], truth)


def test_the_question_is_different_for_different_problems(c):
    """Same misconception (M5), three problems -> three different questions, each about its own function and values."""
    codes = {
        "product": "def product(nums):\n    p = 1\n    for x in nums:\n        p *= x\n        return p\n",
        "sum_list": "def sum_list(nums):\n    total = 0\n    for x in nums:\n        total += x\n        return total\n",
        "count_evens": "def count_evens(nums):\n    count = 0\n    for n in nums:\n        if n % 2 == 0:\n            count += 1\n        return count\n",
    }
    qs = {pid: ask(c, "M5_RETURN_IN_LOOP", pid, code)["intervention"]["predict"] for pid, code in codes.items()}
    assert len({q["question"] for q in qs.values()}) == 3
    assert len({q["based_on"]["call"] for q in qs.values()}) == 3
    for pid, q in qs.items():
        assert PROBLEMS[pid]["fn"] in q["question"]
    static = json.loads((CONTENT / "misconceptions.json").read_text(encoding="utf-8"))["M5_RETURN_IN_LOOP"]["intervention"]["predict"]["question"]
    assert all(q["question"] != static for q in qs.values()), "no longer the generic def f(): ... example"


def test_cache_is_keyed_by_problem_misconception_and_code(c):
    label, pid, code = CASES[4]
    a = ask(c, label, pid, code, "cache-1")
    b = ask(c, label, pid, code, "cache-2")
    assert b["concept_source"] == "cache" and a["intervention"]["predict"]["question"] == b["intervention"]["predict"]["question"]
    other = code.replace("p = 1", "p = 1  # start")
    d = ask(c, label, pid, other)  # same problem + misconception, DIFFERENT code -> must not show someone else's code
    assert d["concept_source"] == "generated" and "# start" in d["intervention"]["predict"]["question"] and "# start" not in a["intervention"]["predict"]["question"]


def test_generation_failure_falls_back_to_the_pool_and_is_logged(c, caplog):
    before = c.get("/concept-stats").json()
    with caplog.at_level(logging.WARNING, logger="relearn.concept"):
        # correct code but forced label M5: nothing fails, so no problem-specific question exists
        r = ask(c, "M5_RETURN_IN_LOOP", "sum_list", CORRECT_SUM, "fb-1")
    q = r["intervention"]["predict"]
    assert r["concept_source"] == "fallback_pool" and q["source"] == "fallback_pool" and 0 <= q["pool_index"] < 4
    assert q["question"] in [x["question"] for x in concept.POOL["M5_RETURN_IN_LOOP"]]
    assert any("FALLBACK" in m and "no_failing_test" in m and "sum_list" in m for m in caplog.messages)
    after = c.get("/concept-stats").json()
    assert after["fallback_count"] == before["fallback_count"] + 1 and after["fallback_reasons"]["no_failing_test"] >= 1
    assert after["recent_fallbacks"][0]["problem_id"] == "sum_list" and 0 < after["fallback_rate"] <= 1


def test_pool_never_repeats_the_same_question_twice_in_a_row(c):
    seq = [ask(c, "M4_ACCUMULATOR_RESET", "sum_list", CORRECT_SUM, "rot")["intervention"]["predict"]["pool_index"] for _ in range(9)]
    assert all(a != b for a, b in zip(seq, seq[1:])), seq
    assert len(set(seq[:4])) == 4, "all four pool questions get used before any repeats"
    other = ask(c, "M4_ACCUMULATOR_RESET", "sum_list", CORRECT_SUM, "rot-other-learner")["intervention"]["predict"]["pool_index"]
    assert 0 <= other < 4  # independent rotation per learner


def test_invalid_or_crashing_generation_falls_back(c, monkeypatch, caplog):
    label, pid, code = CASES[5]
    bad = dict(question="x", options=["a", "a", "b", "c"], answer=9, explanation="e")
    monkeypatch.setattr(concept, "generate", lambda *a, **k: bad)
    with caplog.at_level(logging.WARNING, logger="relearn.concept"):
        r = ask(c, label, pid, code.replace("nums", "values").replace("average", "average"), "inv")  # different code => cache miss
    assert r["concept_source"] == "fallback_pool"
    assert any("invalid_question" in m for m in caplog.messages)

    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(concept, "generate", boom)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="relearn.concept"):
        r = ask(c, label, pid, code + "# again\n", "inv2")
    assert r["concept_source"] == "fallback_pool" and any("exception: RuntimeError" in m for m in caplog.messages)
    reasons = c.get("/concept-stats").json()["fallback_reasons"]
    assert reasons.get("invalid_question", 0) >= 1 and reasons.get("exception", 0) >= 1


def test_pool_content_is_valid_and_separate_from_the_reassessment_questions():
    misc = json.loads((CONTENT / "misconceptions.json").read_text(encoding="utf-8"))
    assert set(concept.POOL) == set(misc)
    for label, items in concept.POOL.items():
        assert len(items) == 4
        for q in items:
            concept.validate(dict(q, answerIndex=q["answer"]))
        assert len({q["question"] for q in items}) == 4
        reassess = {x["q"] for x in misc[label]["concept_questions"]} | {misc[label]["intervention"]["predict"]["question"]}
        assert not reassess & {q["question"] for q in items}, f"{label}: pool must not reuse reassessment / static questions"


def test_reassessment_concept_questions_are_untouched(c):
    r = c.get("/transfer/M5").json()
    assert [q["id"] for q in r["concept_questions"]] == ["M5-c1", "M5-c2"] and "answer" not in r["concept_questions"][0]
    misc = json.loads((CONTENT / "misconceptions.json").read_text(encoding="utf-8"))
    assert [q["answer"] for q in misc["M5_RETURN_IN_LOOP"]["concept_questions"]] == [1, 1]


# ------------------------------------------------------------------ LLM-written concept checks (shared Gemini client, mocked)
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class GMock(BaseHTTPRequestHandler):
    prompts = []
    reply = staticmethod(lambda prompt: (200, {}))

    def log_message(self, *a): pass

    def _send(self, status, obj):
        b = json.dumps(obj).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        prompt = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["contents"][0]["parts"][0]["text"]
        GMock.prompts.append(prompt)
        status, obj = GMock.reply(prompt)
        if status != 200:
            return self._send(status, {"error": {"code": status, "message": "mock error"}})
        self._send(200, {"candidates": [{"content": {"parts": [{"text": json.dumps(obj)}]}, "finishReason": "STOP"}], "modelVersion": "mock-flash"})


@pytest.fixture()
def gem(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), GMock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    GMock.prompts = []
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_BASE", f"http://127.0.0.1:{srv.server_port}")
    yield GMock
    srv.shutdown()


PRODUCT = CASES[4][2]  # M5: return inside the loop -> product([2, 3, 4]) really returns 2 (intended 24)
GOOD = {"question": "With your product function, what does product([2, 3, 4]) give back?",
        "options": ["24", "2", "9", "None"], "answerIndex": 1,
        "explanation": "Your return sits inside the loop, so the function stops after multiplying in the first number and gives back 2."}


def test_llm_writes_the_question_around_the_verified_answer(c, gem):
    gem.reply = staticmethod(lambda p: (200, GOOD))
    code = PRODUCT + "# llm-ok\n"
    r = ask(c, "M5_RETURN_IN_LOOP", "product", code, "llm-ok")
    q = r["intervention"]["predict"]
    assert r["concept_source"] == "llm" and q["source"] == "llm"
    concept.validate(q)
    assert q["options"][q["answer"]] == "2" and q["answer"] == q["answerIndex"] == 1, "verified answer at the stated index"
    assert q["question"].startswith('Here is your function for "Product of a list"') and code.strip() in q["question"]
    assert q["question"].endswith(GOOD["question"]) and q["explanation"] == GOOD["explanation"]
    p = gem.prompts[0]
    assert "gives: 2" in p and "intended result is 24" in p and "Exactly one must be exactly: 2" in p and "p *= x" in p
    again = ask(c, "M5_RETURN_IN_LOOP", "product", code, "llm-ok-2")
    assert again["concept_source"] == "cache" and len(gem.prompts) == 1, "LLM questions are cached per (problem, misconception, code)"


BAD_LLM = [
    ("verified answer", {**GOOD, "options": ["24", "3", "9", "None"], "answerIndex": 0}),
    ("answerIndex", {**GOOD, "answerIndex": 0}),
    ("not distinct", {**GOOD, "options": ["2", "2 ", "9", "None"], "answerIndex": 0}),
    ("does not refer", {**GOOD, "question": "What happens when it runs?"}),
    ("explanation", {**GOOD, "explanation": "word " * 80}),
    ("full function", {**GOOD, "explanation": "Write def product(nums): with the return after the loop."}),
    ("4 non-empty", {**GOOD, "options": ["24", "2", "9"], "answerIndex": 1}),
]


@pytest.mark.parametrize("why,reply", BAD_LLM, ids=[b[0].replace(" ", "_") for b in BAD_LLM])
def test_bad_llm_questions_fall_back_to_the_verified_one(c, gem, caplog, why, reply):
    gem.reply = staticmethod(lambda p: (200, reply))
    with caplog.at_level(logging.WARNING, logger="relearn.concept"):
        r = ask(c, "M5_RETURN_IN_LOOP", "product", PRODUCT + f"# bad-{why}\n", "bad")
    q = r["intervention"]["predict"]
    assert r["concept_source"] == "generated" and q["options"][q["answer"]] == "2", "the learner still gets the verified question"
    assert any("LLM not used" in m and "guardrail_rejected" in m and why in m for m in caplog.messages), caplog.messages


def test_api_trouble_keeps_the_verified_question_and_is_retried_next_time(c, gem, caplog):
    code = PRODUCT + "# busy\n"
    gem.reply = staticmethod(lambda p: (503, None))
    with caplog.at_level(logging.WARNING, logger="relearn.concept"):
        r = ask(c, "M5_RETURN_IN_LOOP", "product", code, "busy")
    assert r["concept_source"] == "generated" and any("reason=overloaded" in m for m in caplog.messages)
    gem.reply = staticmethod(lambda p: (200, GOOD))
    r2 = ask(c, "M5_RETURN_IN_LOOP", "product", code, "busy")
    assert r2["concept_source"] == "llm" and len(gem.prompts) == 2, "a transient failure is not cached"
    st = c.get("/concept-stats").json()["by_source"]
    assert st.get("llm", 0) >= 1 and st.get("generated", 0) >= 1
