"""Personalised intervention: the learner's own code, a verified minimal fix, highlights, fallbacks - all 8 misconceptions."""
import csv, json, os, pathlib, statistics, tempfile

os.environ["RELEARN_DB"] = os.path.join(tempfile.mkdtemp(), "pers.db")

import pytest
from fastapi.testclient import TestClient

from app.main import PROBLEMS, app
from relearn_ml import fixer, references
from relearn_ml.execute import run_submission

ML = pathlib.Path(__file__).resolve().parents[2] / "ml"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def passes(code, pid):
    r = run_submission(code, PROBLEMS[pid])
    return r["status"] == "ok" and all(t["ok"] for t in r["tests"])


# (label, problem, learner code, EXACT expected minimal fix, expected highlighted lines in the learner's code)
CASES = [
 ("M1_RANGE_OFF_BY_ONE", "sum_to_n",
  "def sum_to_n(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total\n",
  "def sum_to_n(n):\n    total = 0\n    for i in range(1, n + 1):\n        total += i\n    return total\n", [3]),
 ("M2_INDEX_FROM_ONE", "last_item",
  "def last_item(items):\n    return items[len(items)]\n",
  "def last_item(items):\n    return items[len(items) - 1]\n", [2]),
 ("M3_PRINT_NOT_RETURN", "square",
  "def square(n):\n    print(n * n)\n",
  "def square(n):\n    return n * n\n", [2]),
 ("M4_ACCUMULATOR_RESET", "sum_list",
  "def sum_list(nums):\n    for x in nums:\n        total = 0\n        total += x\n    return total\n",
  "def sum_list(nums):\n    total = 0\n    for x in nums:\n        total += x\n    return total\n", [3]),
 ("M5_RETURN_IN_LOOP", "product",
  "def product(nums):\n    p = 1\n    for x in nums:\n        p *= x\n        return p\n",
  "def product(nums):\n    p = 1\n    for x in nums:\n        p *= x\n    return p\n", [5]),
 ("M6_FLOAT_DIVISION", "average",
  "def average(nums):\n    return sum(nums) // len(nums)\n",
  "def average(nums):\n    return sum(nums) / len(nums)\n", [2]),
 ("M7_STRING_MUTABLE", "shout",
  "def shout(s):\n    s.upper()\n    return s + \"!\"\n",
  "def shout(s):\n    s = s.upper()\n    return s + \"!\"\n", [2]),
 ("M8_LIST_ALIASING", "append_copy",
  "def append_copy(lst, x):\n    res = lst\n    res.append(x)\n    return res\n",
  "def append_copy(lst, x):\n    res = lst[:]\n    res.append(x)\n    return res\n", [2]),
]


@pytest.mark.parametrize("label,pid,code,expected,hl", CASES, ids=[x[0][:2] for x in CASES])
def test_each_misconception_gets_their_code_and_a_minimal_verified_fix(c, label, pid, code, expected, hl):
    r = c.post("/intervene", json={"label": label, "problem_id": pid, "code": code})
    assert r.status_code == 200
    body = r.json()
    assert body["intervention"]["wrong_code"], "generic concept example is still returned"
    p = body["personalized"]
    assert p["your_code"] == code, "left panel must be the learner's ACTUAL code"
    assert p["source"] == "auto_fix" and p["fixed_code"] == expected, p["fixed_code"]
    assert p["verified"] == {"passed": len(PROBLEMS[pid]["tests"]), "total": len(PROBLEMS[pid]["tests"])}
    assert passes(p["fixed_code"], pid) and not passes(code, pid), "independent re-check of the verification claim"
    assert p["highlight_lines"] == hl
    assert p["fixed_highlight_lines"], "the changed line(s) are highlighted on the right too"
    assert p["fixed_code"].strip() != p["your_code"].strip() and not fixer.same_code(p["fixed_code"], p["your_code"])
    assert p["rule"]


def test_highlights_for_moved_accumulator_are_on_both_sides(c):
    _, pid, code, _, _ = CASES[3]
    p = c.post("/intervene", json={"label": "M4_ACCUMULATOR_RESET", "problem_id": pid, "code": code}).json()["personalized"]
    assert p["highlight_lines"] == [3] and p["fixed_highlight_lines"] == [2]  # reset line removed / init line added before the loop


def test_unfixable_code_falls_back_to_reference_solution(c):
    # inverted logic: no minimal edit repairs it -> reference solution, itself verified
    code = "def contains_negative(nums):\n    for n in nums:\n        if n >= 0:\n            return False\n    return True\n"
    p = c.post("/intervene", json={"label": "M5_RETURN_IN_LOOP", "problem_id": "contains_negative", "code": code}).json()["personalized"]
    assert p["source"] == "reference_solution" and p["fixed_code"] == p["reference_solution"]
    assert passes(p["fixed_code"], "contains_negative") and p["verified"]["passed"] == p["verified"]["total"]
    assert not fixer.same_code(p["fixed_code"], p["your_code"]) and p["highlight_lines"]  # still points at the cause (the return in the loop)
    # a "fix" that doesn't pass the tests is never shown: round() keeps average wrong even after // -> /
    code = "def average(nums):\n    return round(sum(nums) // len(nums), 2)\n"
    p = c.post("/intervene", json={"label": "M6_FLOAT_DIVISION", "problem_id": "average", "code": code}).json()["personalized"]
    assert p["source"] == "reference_solution" and passes(p["fixed_code"], "average")


def test_panels_are_never_identical_even_if_learner_code_is_the_reference(c):
    for pid in ("sum_list", "square", "make_grid", "replace_at"):
        ref = references.reference_variants()[pid][0]
        p = c.post("/intervene", json={"label": "M5_RETURN_IN_LOOP", "problem_id": pid, "code": ref}).json()["personalized"]
        assert not fixer.same_code(p["fixed_code"], p["your_code"]) or p["identical"], pid
        if len(references.reference_variants()[pid]) > 1:
            assert not p["identical"] and not fixer.same_code(p["fixed_code"], p["your_code"]) and passes(p["fixed_code"], pid), pid


def test_without_code_the_response_is_the_generic_lesson_only(c):
    r = c.post("/intervene", json={"label": "M5"}).json()
    assert r["personalized"] is None and r["intervention"]["trace"]
    assert c.post("/intervene", json={"label": "CORRECT", "problem_id": "sum_list", "code": "x"}).json()["intervention"] is None
    assert c.post("/intervene", json={"label": "M5", "problem_id": "nope", "code": "x"}).status_code == 404


def test_reference_solutions_exist_and_pass_for_every_problem():
    v = references.reference_variants()
    assert set(v) == set(PROBLEMS)
    assert all(passes(code, pid) for pid, codes in v.items() for code in codes)


def _corpora():
    real = [dict(problem=r["problem_id"], label=r["label"], code=r["code"]) for r in csv.DictReader(open(ML / "data" / "realistic_test.csv", encoding="utf-8", newline=""))]
    seen, tmpl = set(), []
    for line in open(ML / "data" / "dataset.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["label"] != "CORRECT" and (r["problem"], r["norm"]) not in seen:
            seen.add((r["problem"], r["norm"]))
            tmpl.append(dict(problem=r["problem"], label=r["label"], code=r["code"]))
    return [x for x in real if x["label"] != "CORRECT"], tmpl


def test_invariants_over_every_wrong_sample_in_both_corpora(capsys):
    """Left/right never identical, right panel always passes every test, minimal diffs, high auto-fix coverage."""
    run = lambda code, p: run_submission(code, p)
    refs = references.reference_variants()
    stats = {}
    for name, rows in zip(("realistic set", "training templates"), _corpora()):
        auto, changed = 0, []
        for r in rows:
            p = PROBLEMS[r["problem"]]
            out = fixer.personalize(r["code"], p, r["label"], run, refs[r["problem"]])
            assert passes(out["fixed_code"], r["problem"]), (name, r["problem"], r["label"])
            assert not fixer.same_code(out["fixed_code"], out["your_code"]), (name, r["problem"], r["label"])
            assert out["highlight_lines"], (name, r["problem"], r["label"], "no highlighted culprit line")
            assert max(out["highlight_lines"]) <= len(out["your_code"].split("\n"))
            if out["source"] == "auto_fix":
                auto += 1
                changed.append(len(out["highlight_lines"]))
                assert out["fixed_highlight_lines"] or out["highlight_lines"]
        cov = auto / len(rows)
        stats[name] = (auto, len(rows), cov, statistics.median(changed), max(changed))
        assert cov >= 0.93, f"auto-fix coverage regressed on {name}: {cov:.2f}"
        assert statistics.median(changed) <= 2 and max(changed) <= 6, "fixes must stay minimal"
    with capsys.disabled():
        for k, (a, n, cov, med, mx) in stats.items():
            print(f"\n  auto-fix on {k}: {a}/{n} = {cov:.0%}; lines changed in learner's code: median {med}, max {mx}")
