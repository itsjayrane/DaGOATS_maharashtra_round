"""OTHER_BUG samples: wrong programs that are NOT one of the 8 known misconceptions.

Made by mutating CORRECT templates with one generic edit - swap an arithmetic operator, change a constant, invert a
comparison, drop a statement, or return the wrong variable. A mutant is kept only if it parses, runs, FAILS at least one
test, and fires none of the M1-M8 signature features below (so it never looks like a known misconception by construction).
"""
import ast
import math
import random
import re
from collections import Counter, defaultdict

from .execute import run_submission
from .features import SIGNATURE_KEYS, ast_features, featurize, normalize

ALL_SIGNATURES = [k for keys in SIGNATURE_KEYS.values() for k in keys]

ARITH = [(" + ", " - "), (" - ", " + "), (" * ", " + "), (" / ", " * "), ("+= ", "-= "), ("*= ", "+= ")]
COMPARE = [(" <= ", " > "), (" >= ", " < "), (" == ", " != "), (" != ", " == "), (" < ", " >= "), (" > ", " <= ")]
BLOCK = re.compile(r"^\s*(def|for|while|if|elif|else|return|try|except)\b|:\s*$")


def fires_signature(code):
    f = ast_features(code)
    return any(f.get(k, 0) for k in ALL_SIGNATURES)


def _variants(code):
    """(operator, mutant) pairs - each mutant differs from `code` by exactly one edit."""
    lines = code.split("\n")
    body = [i for i, l in enumerate(lines) if i > 0 and l.strip()]
    for i in body:
        line = lines[i]
        for a, b in ARITH:
            if a in line:
                yield "swap_operator", "\n".join(lines[:i] + [line.replace(a, b, 1)] + lines[i + 1:])
        for a, b in COMPARE:
            if a in line:
                yield "invert_comparison", "\n".join(lines[:i] + [line.replace(a, b, 1)] + lines[i + 1:])
        for m in re.finditer(r"(?<![\w.])(\d+)(?![\w.])", line):
            new = str(int(m.group(1)) + 1)
            yield "change_constant", "\n".join(lines[:i] + [line[:m.start()] + new + line[m.end():]] + lines[i + 1:])
        if not BLOCK.search(line):
            yield "drop_statement", "\n".join(lines[:i] + lines[i + 1:])
        r = re.match(r"^(\s*)return (\w+)\s*$", line)
        if r:
            names = set(re.findall(r"^\s*(\w+)\s*=", code, re.M)) | set(re.findall(r"def \w+\(([^)]*)\)", code)[0].replace(" ", "").split(","))
            for n in sorted(names - {r.group(2), ""}):
                yield "return_wrong_variable", "\n".join(lines[:i] + [f"{r.group(1)}return {n}"] + lines[i + 1:])


def mutants_for(code, problem):
    """Valid OTHER_BUG mutants of one correct program: (operator, code, exec result)."""
    if fires_signature(code):
        return []
    out, seen = [], {normalize(code)}
    for op, m in _variants(code):
        try:
            ast.parse(m)
        except SyntaxError:
            continue
        n = normalize(m)
        if n in seen or fires_signature(m):
            continue
        seen.add(n)
        res = run_submission(m, problem)
        if res["status"] != "ok" or not res["tests"] or all(t["ok"] for t in res["tests"]):
            continue  # must run and must fail at least one test
        out.append((op, m, res))
    return out


def other_bug_rows(rng: random.Random, problems, templates, render, target, renders_per_template=4):
    """Balanced OTHER_BUG rows: about `target` in total, spread evenly over problems."""
    by_problem = defaultdict(list)
    for pid, by_label in templates.items():
        for tmpl in by_label.get("CORRECT", []):
            for _ in range(renders_per_template):
                code = render(tmpl, rng)
                if code:
                    for op, m, res in mutants_for(code + "\n", problems[pid]):
                        by_problem[pid].append((op, m, res))
    rows, ops = [], Counter()
    pids = [p for p in by_problem if by_problem[p]]
    cap = math.ceil(target / max(1, len(pids)))
    for pid in pids:
        pool = by_problem[pid]
        rng.shuffle(pool)
        seen = set()
        for op, m, res in pool:
            n = normalize(m)
            if n in seen:
                continue
            seen.add(n)
            rows.append(dict(problem=pid, label="OTHER_BUG", code=m, mutation=op, **featurize(m, problems[pid], res)))
            ops[op] += 1
            if len(seen) >= cap:
                break
    rng.shuffle(rows)
    return rows[:target], ops
