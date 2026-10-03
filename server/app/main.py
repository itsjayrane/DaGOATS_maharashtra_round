"""Re:Learn API.  Run:  cd server && ../ml/.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000"""
import json
import os
from contextlib import asynccontextmanager
from typing import Optional, Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import db, sandbox
from .diagnoser import DiagnoserService
from .paths import CONTENT, DOCS, MODEL_PATH

PROBLEMS = {p["id"]: p for p in json.loads((CONTENT / "problems.json").read_text(encoding="utf-8"))}
MISC = json.loads((CONTENT / "misconceptions.json").read_text(encoding="utf-8"))
SVC: Optional[DiagnoserService] = None
CLEAR_THRESHOLD = 0.25  # model must give the target misconception < 25% probability to count as "no longer detected"


@asynccontextmanager
async def lifespan(app):
    global SVC
    db.init()
    if MODEL_PATH.exists():
        SVC = DiagnoserService()
    yield


app = FastAPI(title="Re:Learn API", version="0.1", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])


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
    return dict(ok=True, model_loaded=SVC is not None)


@app.get("/problems")
def problems():
    return [public_problem(p) for p in PROBLEMS.values()]


class DiagnoseIn(BaseModel):
    problem_id: str
    code: str
    learner_id: Optional[str] = None  # if given, the attempt is stored and mastery updated


@app.post("/diagnose")
def diagnose(body: DiagnoseIn):
    p = get_problem(body.problem_id)
    res = sandbox.run(body.code, p)
    d = svc().diagnose(body.code, p, res)
    passed = res["status"] == "ok" and all(t["ok"] for t in res["tests"])
    out = dict(label=d["label"], confidence=d["confidence"], evidence=d["evidence"], test_results=clean_tests(res),
               passed=passed, status=res["status"], error=res.get("error"), probabilities=d["probabilities"],
               ambiguous=d["ambiguous"], runner_up=d["runner_up"])
    if body.learner_id:
        lab = d["label"]
        upd = None
        if lab and lab != "CORRECT":
            c = d["confidence"]
            upd = lambda v, r: (v * (1 - 0.5 * c), False)  # evidence of the misconception lowers mastery
        out["mastery_after"] = db.record(body.learner_id, "diagnose", p["id"], lab, d["confidence"], passed, body.code,
                                         dict(evidence=d["evidence"]), misconception=lab if upd else None, update=upd)
    return out


class IntervenIn(BaseModel):
    label: str


@app.post("/intervene")
def intervene(body: IntervenIn):
    if body.label.upper() == "CORRECT":
        return dict(label="CORRECT", intervention=None, message="No misconception detected - nothing to remediate.")
    m = full_label(body.label)
    c = MISC[m]
    return dict(label=m, name=c["name"], summary=c["summary"], intervention=c["intervention"])


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
    code: str
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
             detail=(f"Model: {d['label']} (P({short})={p_m:.2f}, needs < {CLEAR_THRESHOLD})." if d["label"] else "Code did not run, so it cannot be assessed.")),
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
    return json.loads(f.read_text(encoding="utf-8"))


@app.get("/metrics/confusion-matrix")
def confusion_matrix_png():
    f = DOCS / "confusion_matrix.png"
    if not f.exists():
        raise HTTPException(404, "confusion_matrix.png missing: run `cd ml && python train.py`")
    return FileResponse(f, media_type="image/png")
