"""Re:Learn API.  Run:  cd server && ../ml/.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000"""
import json
import os
from contextlib import asynccontextmanager
from typing import Optional, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import concept, db, explain, hint, ratelimit, sandbox
from .diagnoser import DiagnoserService
from relearn_ml import fixer, references
from .paths import CONTENT, DOCS, MODEL_PATH

PROBLEMS = {p["id"]: p for p in json.loads((CONTENT / "problems.json").read_text(encoding="utf-8"))}
MISC = json.loads((CONTENT / "misconceptions.json").read_text(encoding="utf-8"))
SVC: Optional[DiagnoserService] = None
MAX_CODE_CHARS = 20000  # longer submissions are rejected with 422
CLEAR_THRESHOLD = 0.25  # model must give the target misconception < 25% probability to count as "no longer detected"


@asynccontextmanager
async def lifespan(app):
    global SVC
    db.init()
    hint.log_startup()  # says right at startup whether AI hints are enabled (and where the key was found)
    if MODEL_PATH.exists():
        SVC = DiagnoserService()
    yield


app = FastAPI(title="Re:Learn API", version="0.1", lifespan=lifespan)
# CORS: local dev + any *.vercel.app (production and preview deploys). Add your custom domain via CORS_ORIGINS
# (comma-separated); CORS_ORIGIN_REGEX overrides the Vercel pattern; CORS_ORIGINS="*" opens the API to everyone.
DEV_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173"
ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", DEV_ORIGINS).split(",") if o.strip()]
ORIGIN_REGEX = os.environ.get("CORS_ORIGIN_REGEX", r"https://([a-z0-9-]+\.)*vercel\.app")
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_origin_regex=ORIGIN_REGEX, allow_methods=["*"], allow_headers=["*"])


def svc():
    if SVC is None:
        raise HTTPException(503, "Model not trained yet: run `cd ml && python train.py`")
    return SVC


def full_label(m: str) -> str:
    for k in MISC:
        if m.upper() == k or m.upper() == k.split("_")[0]:
            return k
    raise HTTPException(404, f"Unknown misconception '{m}'. Use one of {[k.split('_')[0] for k in MISC]}")


def get_problem(pid: str) -> dict:
    if pid not in PROBLEMS:
        raise HTTPException(404, f"Unknown problem '{pid}'")
    return PROBLEMS[pid]


def public_problem(p, with_example=True):
    t = p["tests"][0]
    out = dict(id=p["id"], title=p["title"], prompt=p["prompt"], function=p["fn"], params=p["params"], starter=p["starter"],
               misconceptions_possible=p["tags"], n_tests=len(p["tests"]))
    if with_example:
        out["example"] = dict(args=t["args"], expected=t["expected"])
    return out


def clean_tests(res):
    return [dict(args=t["args"], expected=t["expected"], got=t["got"], ok=t["ok"], error=t.get("exc"), message=t.get("msg"),
                 printed=t.get("printed", False), returned_none=t.get("none", False), modified_input=t.get("mutated", False))
            for t in res["tests"]]


# ---------------------------------------------------------------- endpoints
@app.get("/health")
def health():
    return dict(ok=True, model_loaded=SVC is not None, llm="none")


@app.get("/problems")
def problems():
    return [public_problem(p) for p in PROBLEMS.values()]


class DiagnoseIn(BaseModel):
    problem_id: str
    code: str = Field(max_length=MAX_CODE_CHARS)
    learner_id: Optional[str] = None  # if given, the attempt is stored and mastery updated


@app.post("/diagnose")
def diagnose(body: DiagnoseIn, request: Request):
    ratelimit.check(request, "diagnose", body.learner_id)
    p = get_problem(body.problem_id)
    res = sandbox.run(body.code, p)
    d = svc().diagnose(body.code, p, res)
    passed = res["status"] == "ok" and all(t["ok"] for t in res["tests"])
    out = dict(label=d["label"], confidence=d["confidence"], evidence=d["evidence"], test_results=clean_tests(res),
               passed=passed, status=res["status"], error=res.get("error") or d.get("error"), probabilities=d["probabilities"],
               ambiguous=d["ambiguous"], runner_up=d["runner_up"], verdict=d["verdict"], unknown=d["unknown"],
               unknown_reason=d["unknown_reason"], closest_guess=d["closest_guess"])
    if body.learner_id:
        lab = d["label"]
        upd = None
        if d["verdict"] == "misconception":  # unknown never changes mastery
            c = d["confidence"]
            upd = lambda v, r: (v * (1 - 0.5 * c), False)  # evidence of the misconception lowers mastery
        fail_sig = dict(failing=[i for i, t in enumerate(res["tests"]) if not t["ok"]], exc=sorted({t["exc"] for t in res["tests"] if t.get("exc")}),
                        status=res["status"])
        out["mastery_after"] = db.record(body.learner_id, "diagnose", p["id"], lab, d["confidence"], passed, body.code,
                                         dict(evidence=d["evidence"], verdict=d["verdict"], fail_sig=fail_sig),
                                         misconception=lab if upd else None, update=upd)
    return out


class IntervenIn(BaseModel):
    label: str
    problem_id: Optional[str] = None  # with `code`, the response includes `personalized`: the learner's own code + a verified minimal fix
    code: Optional[str] = Field(default=None, max_length=MAX_CODE_CHARS)
    learner_id: Optional[str] = None  # used to rotate fallback concept questions (never the same one twice in a row)


@app.post("/intervene")
def intervene(body: IntervenIn, request: Request):
    ratelimit.check(request, "intervene", body.learner_id)
    if body.problem_id and body.code is not None and SVC is not None:
        p = get_problem(body.problem_id)
        res = sandbox.run(body.code, p)
        d = SVC.diagnose(body.code, p, res)
        if res["status"] == "ok" and d["unknown"]:  # never a canned lesson for an unknown bug: explain what happened instead
            guess = (d.get("closest_guess") or {}).get("label")
            return dict(label=d["label"], unknown=True, unknown_reason=d["unknown_reason"], closest_guess=d["closest_guess"],
                        intervention=None, personalized=None,
                        explain=explain.explain(p, body.code, sandbox.run, [guess] if guess else None, references.reference_variants()[p["id"]][0]))
    if body.label.upper() == "CORRECT":
        return dict(label="CORRECT", intervention=None, message="No misconception detected - nothing to remediate.")
    m = full_label(body.label)
    c = MISC[m]
    out = dict(label=m, name=c["name"], summary=c["summary"], intervention=c["intervention"], personalized=None)
    if body.problem_id and body.code is not None:
        p = get_problem(body.problem_id)
        # minimal fix of THEIR code, verified in the sandbox against the problem's tests; falls back to the reference solution
        out["personalized"] = fixer.personalize(body.code, p, m, sandbox.run, references.reference_variants()[p["id"]])
        # problem-specific concept check built from the problem, the learner's code and the misconception (pool fallback, logged)
        q, src = concept.for_learner(p, body.code, m, sandbox.run, body.learner_id)
        out["intervention"] = {**c["intervention"], "predict": q}
        out["concept_source"] = src
    return out


@app.get("/transfer/{misconception}")
def transfer(misconception: str, learner_id: Optional[str] = None, exclude: Optional[str] = None):
    m = full_label(misconception)
    skip = {exclude, db.last_diagnosed_problem(learner_id, m) if learner_id else None} - {None}
    probs = [public_problem(p) for p in PROBLEMS.values() if m.split("_")[0] in p["tags"] and p["id"] not in skip]
    qs = [dict(id=q["id"], q=q["q"], options=q["options"]) for q in MISC[m]["concept_questions"]]
    return dict(misconception=m, name=MISC[m]["name"], excluded_problems=sorted(skip), problems=probs, concept_questions=qs)


class ReassessIn(BaseModel):
    learner_id: str
    misconception: str
    problem_id: str
    code: str = Field(max_length=MAX_CODE_CHARS)
    concept_answer: Union[int, str]
    concept_id: Optional[str] = None  # defaults to the first concept question


def parse_answer(q, ans) -> Optional[int]:
    if isinstance(ans, int):
        return ans
    s = str(ans).strip()
    if s.isdigit():
        return int(s)
    if len(s) == 1 and s.lower() in "abcd":
        return "abcd".index(s.lower())
    return next((i for i, o in enumerate(q["options"]) if o.strip().lower() == s.lower()), None)


@app.post("/reassess")
def reassess(body: ReassessIn):
    m = full_label(body.misconception)
    short = m.split("_")[0]
    p = get_problem(body.problem_id)
    if short not in p["tags"]:
        raise HTTPException(422, f"Problem '{p['id']}' cannot reveal {short}; fetch candidates from GET /transfer/{short}")
    qs = MISC[m]["concept_questions"]
    q = next((x for x in qs if x["id"] == body.concept_id), None) if body.concept_id else qs[0]
    if q is None:
        raise HTTPException(422, f"Unknown concept_id; valid: {[x['id'] for x in qs]}")

    prior = db.last_diagnosed_problem(body.learner_id, m)
    res = sandbox.run(body.code, p)
    d = svc().diagnose(body.code, p, res)
    passed = res["status"] == "ok" and all(t["ok"] for t in res["tests"])
    p_m = d["probabilities"][m] if d["probabilities"] else None
    clear = d["label"] is not None and d["label"] != m and p_m < CLEAR_THRESHOLD
    chosen = parse_answer(q, body.concept_answer)
    concept_ok = chosen == q["answer"]

    reasons = [
        dict(check="new_task", passed=prior != p["id"],
             detail="Different task from the one where the misconception was found." if prior != p["id"]
             else "Same task as the original diagnosis - a correct answer here could be memorised; pick a transfer problem."),
        dict(check="tests_pass", passed=passed,
             detail=f"{sum(t['ok'] for t in res['tests'])}/{len(res['tests'])} tests pass." if res["status"] == "ok" else res.get("error", res["status"])),
        dict(check="misconception_not_detected", passed=bool(clear),
             detail=(f"Model: {d['label']} (P({short})={p_m:.2f}, needs < {CLEAR_THRESHOLD})." if d["label"] else (d.get("error") or "Code did not run, so it cannot be assessed."))),
        dict(check="concept_answer", passed=concept_ok,
             detail="Concept question answered correctly." if concept_ok else "Concept question answered incorrectly."),
    ]
    resolved = all(r["passed"] for r in reasons)

    def upd(v, was):
        return (max(v + (1 - v) * 0.6, 0.8), True) if resolved else (v * 0.85, False)  # a verified resolution always lands in the "good" band
    after = db.record(body.learner_id, "reassess", p["id"], d["label"], d["confidence"], passed, body.code,
                      dict(reasons=reasons, concept_id=q["id"], concept_answer=body.concept_answer),
                      misconception=m, resolved=resolved, update=upd)
    failed = [r["check"] for r in reasons if not r["passed"]]
    return dict(resolved=resolved, misconception=m, reasons=reasons, failed_checks=failed,
                message="Misconception resolved." if resolved else "Not resolved yet: " + ", ".join(failed) + ".",
                diagnosis=dict(label=d["label"], confidence=d["confidence"], evidence=d["evidence"]), test_results=clean_tests(res),
                concept_explanation=None if concept_ok else f"Correct answer: {q['options'][q['answer']]}", mastery_after=after)


@app.get("/learner/{learner_id}")
def learner(learner_id: str):
    r = db.learner(learner_id)
    if r is None:
        raise HTTPException(404, "Unknown learner (they are created on first diagnose/reassess).")
    return r


@app.get("/metrics")
def metrics():
    f = DOCS / "metrics.json"
    if not f.exists():
        raise HTTPException(404, "metrics.json missing: run `cd ml && python train.py`")
    out = json.loads(f.read_text(encoding="utf-8"))
    r = DOCS / "realistic.json"  # hand-written realistic set: the headline number
    out["realistic"] = json.loads(r.read_text(encoding="utf-8")) if r.exists() else None
    u = DOCS / "unseen_eval.json"  # leave-one-misconception-out (ml/eval_unseen.py)
    out["unseen"] = json.loads(u.read_text(encoding="utf-8")) if u.exists() else None
    return out


@app.get("/metrics/confusion-matrix")
def confusion_matrix_png():
    f = DOCS / "confusion_matrix.png"
    if not f.exists():
        raise HTTPException(404, "confusion_matrix.png missing: run `cd ml && python train.py`")
    return FileResponse(f, media_type="image/png")


@app.get("/baseline")
def baseline():
    """Kept for compatibility. The LLM baseline was removed: the app runs fully offline with no external AI."""
    return dict(status="removed", reason="No LLM is used anywhere; the app runs fully offline.")


@app.get("/concept-stats")
def concept_stats():
    """How often concept checks are generated, served from cache, or fall back to the pool (and why)."""
    return db.concept_stats()


class HintIn(BaseModel):
    problem_id: str
    code: str = Field(max_length=MAX_CODE_CHARS)
    hint_level: int = Field(ge=1, le=3)  # 1 = where, 2 = what/why, 3 = small code nudge
    learner_id: Optional[str] = None
    problem_statement: Optional[str] = None  # accepted for convenience; the server uses its own statement
    test_results: Optional[list] = None  # accepted but never trusted: the server re-runs the tests on `code`


@app.post("/hint")
def hint_endpoint(body: HintIn, request: Request):
    """Progressive curated hint: {"level": int, "hint": str, "source": "curated"|"none", "kind": "problem"|"misconception"|"none"}."""
    ratelimit.check(request, "hint", body.learner_id)
    p = get_problem(body.problem_id)
    return hint.get_hint(p, body.code, body.hint_level, body.learner_id, sandbox.run,
                         diagnose=(lambda code, prob, res: SVC.diagnose(code, prob, res)) if SVC else None)


@app.get("/learner/{learner_id}/hints")
def learner_hints(learner_id: str):
    """Hint usage log for the Dashboard: totals, per-problem counts and the most recent requests."""
    return db.learner_hints(learner_id)


@app.get("/hint-status")
def hint_status():
    """Hint configuration: curated and offline (llm: "none")."""
    return hint.status()


class ExplainIn(BaseModel):
    problem_id: str
    code: str = Field(max_length=MAX_CODE_CHARS)


@app.post("/explain")
def explain_endpoint(body: ExplainIn, request: Request):
    """Deterministic explanation: where it went wrong, a fix of THEIR code (only if it passes every test), the best solution."""
    ratelimit.check(request, "diagnose")
    p = get_problem(body.problem_id)
    order = None
    if SVC is not None:
        d = SVC.diagnose(body.code, p, sandbox.run(body.code, p))
        order = [x for x in (d.get("label"), (d.get("closest_guess") or {}).get("label")) if x]
    return explain.explain(p, body.code, sandbox.run, order, references.reference_variants()[p["id"]][0])
