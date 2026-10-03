"""Teacher-written custom problems (no AI). POST /custom/problems builds a full problem from a statement, a function
name, a reference solution and >= 4 tests: the reference is run in the sandbox, missing expected values are taken from
its output, and the request is rejected (422) if the reference fails to parse/run or disagrees with a given expected value.
Fields the diagnoser needs (param/return types, checks) are derived from the reference's behaviour."""
import ast
import hashlib
import json
import re
import time

from fastapi import HTTPException

from . import paths  # noqa: F401  (puts ml/ on sys.path)
from relearn_ml.execute import _eq
from . import db

BADGE = "custom — teacher-written"
MIN_TESTS = 4


def _type_name(v):
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "list"
    return "any"


def _reject(msg):
    raise HTTPException(422, msg)


def build(statement, function_name, reference_solution, tests, run):
    """Validated problem dict (not yet stored). `run(code, problem)` executes in the sandbox."""
    statement = (statement or "").strip()
    if len(statement) < 10:
        _reject("Write a problem statement (at least 10 characters).")
    if not re.fullmatch(r"[A-Za-z_]\w{0,40}", function_name or ""):
        _reject("The function name must be a valid Python name (letters, digits, underscores).")
    try:
        tree = ast.parse(reference_solution)
    except SyntaxError as e:
        _reject(f"The reference solution does not parse: {e.msg} (line {e.lineno}).")
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function_name), None)
    if fn is None:
        _reject(f"The reference solution must define a function named `{function_name}`.")
    params = [a.arg for a in fn.args.args]
    tests = tests or []
    if len(tests) < MIN_TESTS:
        _reject(f"Give at least {MIN_TESTS} tests (you gave {len(tests)}).")
    norm = []
    for i, t in enumerate(tests):
        args = t.get("input")
        args = args if isinstance(args, list) else [args]
        if len(args) != len(params):
            _reject(f"Test {i + 1} has {len(args)} input value(s) but `{function_name}` takes {len(params)}.")
        norm.append(dict(args=args, expected=t.get("expected"), given="expected" in t and t["expected"] is not None))
    probe = dict(id="custom-probe", fn=function_name, params=params, checks={},
                 tests=[dict(args=t["args"], expected=t["expected"]) for t in norm])
    res = run(reference_solution, probe)
    if res["status"] != "ok":
        _reject(f"The reference solution does not run: {res.get('error') or res['status']}.")
    for i, (t, r) in enumerate(zip(norm, res["tests"])):
        if r.get("exc"):
            _reject(f"The reference solution fails on test {i + 1}: {r['exc']} {r.get('msg') or ''}".strip() + ".")
        if t["given"] and not _eq(r["got"], t["expected"]):
            _reject(f"Test {i + 1}: the reference solution returns {r['got']!r}, but the test expects {t['expected']!r}.")
        t["expected"] = r["got"]
        if r.get("mutated"):
            _reject(f"The reference solution changes its input on test {i + 1}; custom problems need a non-mutating reference.")
    outs = [t["expected"] for t in norm]
    ptypes = [_type_name(a) for a in norm[0]["args"]]
    rtypes = {_type_name(o) for o in outs}
    rtype = rtypes.pop() if len(rtypes) == 1 else "any"
    checks = {}
    if "list" in ptypes:
        checks["no_mutate"] = True  # the reference never mutates (checked above), so learners must not either
    if outs and all(isinstance(o, list) and o and all(isinstance(r, list) for r in o) for o in outs):
        checks["independent_rows"] = True
    pid = "custom-" + hashlib.sha1(f"{function_name}|{statement}|{time.time()}".encode()).hexdigest()[:10]
    title = statement.split(".")[0][:48] or function_name
    return dict(id=pid, fn=function_name, title=title, prompt=statement, params=params,
                starter=f"def {function_name}({', '.join(params)}):\n    # your code here\n    pass\n",
                tests=[dict(args=t["args"], expected=t["expected"]) for t in norm], tags=[], param_types=ptypes,
                return_type=rtype, checks=checks, custom=True, reference=reference_solution.rstrip() + "\n")


def save(problem):
    with db._lock, db.conn() as c:
        c.execute("INSERT INTO custom_problems(id, created, problem) VALUES(?,?,?)", (problem["id"], time.time(), json.dumps(problem)))


def get(pid):
    with db.conn() as c:
        r = c.execute("SELECT problem FROM custom_problems WHERE id=?", (pid,)).fetchone()
    return json.loads(r["problem"]) if r else None


def all_problems():
    with db.conn() as c:
        return [json.loads(r["problem"]) for r in c.execute("SELECT problem FROM custom_problems ORDER BY created")]
