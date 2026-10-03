"""Run learner code in a separate Python process with a hard wall-clock timeout (2 s).

Inside the child, relearn_ml.execute adds restricted builtins, a banned-name AST check and a line-step limit.
This is demo-grade isolation (no memory/CPU/FS/network limits at the OS level) - see docs/ for the threat model.
"""
import json, subprocess, sys
from .paths import ML_DIR

TIMEOUT_S = 2.0


def run(code: str, problem: dict, timeout: float = TIMEOUT_S) -> dict:
    payload = json.dumps({"code": code, "problem": problem})
    try:
        p = subprocess.run([sys.executable, "-X", "utf8", "-m", "relearn_ml.sandbox"], input=payload, capture_output=True,
                           text=True, timeout=timeout, cwd=str(ML_DIR), encoding="utf-8")
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": f"Your code ran longer than {timeout:g}s (infinite loop?).", "tests": []}
    if p.returncode != 0 or not p.stdout.strip():
        return {"status": "crash", "error": (p.stderr or "sandbox crashed")[-300:], "tests": []}
    res = json.loads(p.stdout)
    if res.get("status") == "ok" and any(t.get("exc") == "Timeout" for t in res["tests"]):
        # in-process step limit fired (runaway loop): report as a timeout rather than letting the model guess
        return {"status": "timeout", "error": "Your code never finished on at least one test (infinite loop?).", "tests": []}
    return res
