"""Curated content checks (no server needed): hints, concept pool, references, and no LLM SDKs anywhere (the only LLM
call is the optional, stdlib-only problem drafting in server/app/draft.py)."""
import contextlib, io, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content"


def load(name):
    return {k: v for k, v in json.loads((CONTENT / name).read_text(encoding="utf-8")).items() if not k.startswith("_")}


def test_hints_three_distinct_levels_for_every_problem():
    problems = {p["id"] for p in json.loads((CONTENT / "problems.json").read_text(encoding="utf-8"))}
    h = load("hints.json")
    assert set(h["problems"]) == problems
    for pid, levels in h["problems"].items():
        assert len({levels["1"], levels["2"], levels["3"]}) == 3, pid
    assert len(h["misconceptions"]) == 8 and all(len(set(v.values())) == 3 for v in h["misconceptions"].values())


def test_concept_pool_answers_are_verified_by_running_the_snippet():
    for label, items in load("concept_pool.json").items():
        assert len(items) >= 2, label
        for it in items:
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    exec(it["code"], {})
                lines = [l.strip() for l in buf.getvalue().strip().splitlines()]
                got = lines[-1] if lines else ""
            except Exception as e:
                got = type(e).__name__
            assert got == it["options"][it["answer"]], (label, it["code"], got)


def test_no_external_llm_code_in_the_repo():
    pattern = re.compile(r"generativelanguage|google\.generativeai|GEMINI_API_KEY|import openai|anthropic\.", re.I)
    offenders = []
    for folder in ("ml/relearn_ml", "server/app", "client/src"):
        for f in (ROOT / folder).rglob("*"):
            if f.suffix in (".py", ".js", ".jsx") and pattern.search(f.read_text(encoding="utf-8", errors="ignore")):
                offenders.append(str(f.relative_to(ROOT)))
    assert offenders == []


def test_every_problem_has_difficulty_and_framing_and_glossary_is_plain():
    meta = json.loads((CONTENT / "problem_meta.json").read_text(encoding="utf-8"))
    probs = json.loads((CONTENT / "problems.json").read_text(encoding="utf-8"))
    for p in probs:
        assert meta[p["id"]]["difficulty"] in ("easy", "medium", "harder") and 20 < len(meta[p["id"]]["framing"]) < 140, p["id"]
    terms = json.loads((CONTENT / "glossary.json").read_text(encoding="utf-8"))["terms"]
    assert len(terms) >= 15 and all(len(v) <= 140 for v in terms.values())


def test_twin_probes_verify_by_execution():
    import runpy
    mod = runpy.run_path(str(CONTENT / "verify_probes.py"))
    probes = json.loads((CONTENT / "probes.json").read_text(encoding="utf-8"))["probes"]
    assert mod["problems"](probes) == []
    pairs = {tuple(sorted(p["pair"])) for p in probes}
    assert pairs == {("M1_RANGE_OFF_BY_ONE", "M2_INDEX_FROM_ONE"), ("M4_ACCUMULATOR_RESET", "M5_RETURN_IN_LOOP")}
