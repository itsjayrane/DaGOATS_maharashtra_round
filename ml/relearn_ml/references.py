"""Verified reference solutions per problem, rendered from the CORRECT templates that pass every test."""
import random
import re
from functools import lru_cache

from .execute import run_submission
from .generate import POOLS, render
from .problems import load_problems
from .templates import TEMPLATES


def _default_render(tmpl):
    keys = sorted(set(re.findall(r"\$([a-z]+)", tmpl)), key=len, reverse=True)
    pick = {k: POOLS[k][0] for k in keys}
    if len(set(pick.values())) == len(pick):
        return re.sub(r"\$([a-z]+)", lambda m: pick[m.group(1)], tmpl)
    for seed in range(60):  # canonical names collide: fall back to a deterministic random draw
        out = render(tmpl, random.Random(seed))
        if out:
            return out
    return None


@lru_cache(maxsize=1)
def reference_variants():
    """problem_id -> every distinct verified correct solution (the first is the canonical reference)."""
    problems, out = load_problems(), {}
    for pid, p in problems.items():
        out[pid] = []
        for tmpl in TEMPLATES[pid]["CORRECT"]:
            code = _default_render(tmpl)
            if not code:
                continue
            code += "\n"
            res = run_submission(code, p)
            if res["status"] == "ok" and all(t["ok"] for t in res["tests"]) and code not in out[pid]:
                out[pid].append(code)
        if not out[pid]:
            raise RuntimeError(f"no passing reference solution for {pid}")
    return out


def reference_solutions():
    return {pid: v[0] for pid, v in reference_variants().items()}
