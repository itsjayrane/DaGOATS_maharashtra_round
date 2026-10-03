"""Run learner code against a problem's tests (restricted builtins + step limit). Demo-grade sandbox."""
import ast, builtins, contextlib, copy, io, math, sys

SAFE = ["print","len","range","sum","min","max","abs","int","float","str","list","dict","set","tuple","sorted",
        "enumerate","zip","round","bool","reversed","any","all","map","filter","isinstance","divmod","pow","chr","ord",
        "True","False","None","Exception","ValueError","TypeError","IndexError","KeyError","ZeroDivisionError","StopIteration"]
BANNED_NAMES = {"open","exec","eval","compile","input","__import__","globals","locals","vars","getattr","setattr","delattr",
                "breakpoint","exit","quit","help","memoryview","type","object","super","classmethod","staticmethod"}
STEP_LIMIT = 400_000

class StepLimit(Exception): pass

def static_check(tree):
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)): return "imports are not allowed"
        if isinstance(n, ast.Name) and n.id in BANNED_NAMES: return f"`{n.id}` is not allowed"
        if isinstance(n, ast.Attribute) and n.attr.startswith("__"): return "dunder access is not allowed"
    return None

def _eq(a, b):
    if isinstance(b, bool) or isinstance(a, bool): return type(a) is type(b) and a == b
    if isinstance(b, float) or isinstance(a, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-9)
    if isinstance(b, list): return isinstance(a, list) and len(a) == len(b) and all(_eq(x, y) for x, y in zip(a, b))
    return a == b

def _call(fn, args):
    steps = [0]
    def tracer(frame, event, arg):
        if event == "line":
            steps[0] += 1
            if steps[0] > STEP_LIMIT: raise StepLimit()
        return tracer
    old = sys.gettrace(); sys.settrace(tracer)
    try: return fn(*args)
    finally: sys.settrace(old)

def run_submission(code, problem):
    """Returns dict: status ('ok'|'syntax_error'|'rejected'|'no_function'), tests: [...]"""
    try: tree = ast.parse(code)
    except SyntaxError as e:
        return dict(status="syntax_error", error=f"{e.msg} (line {e.lineno})", tests=[])
    bad = static_check(tree)
    if bad: return dict(status="rejected", error=bad, tests=[])
    safe = {k: getattr(builtins, k) for k in SAFE if hasattr(builtins, k)}
    env = {"__builtins__": safe}
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            sys.settrace(None)
            exec(compile(tree, "<learner>", "exec"), env)
    except BaseException as e:
        return dict(status="syntax_error", error=f"{type(e).__name__}: {e}", tests=[])
    fn = env.get(problem["fn"])
    if not callable(fn): return dict(status="no_function", error=f"define a function named `{problem['fn']}`", tests=[])
    out = []
    for t in problem["tests"]:
        args = copy.deepcopy(t["args"]); before = copy.deepcopy(args)
        buf = io.StringIO(); rec = dict(args=t["args"], expected=t["expected"], got=None, ok=False, exc=None,
                                        printed=False, mutated=False, alias=False, none=False, type_mismatch=False)
        try:
            with contextlib.redirect_stdout(buf):
                res = _call(fn, args)
        except StepLimit:
            rec["exc"] = "Timeout"; out.append(rec); continue
        except BaseException as e:
            rec["exc"] = type(e).__name__; rec["msg"] = str(e)[:120]; rec["printed"] = bool(buf.getvalue().strip())
            rec["mutated"] = args != before; out.append(rec); continue
        rec["printed"] = bool(buf.getvalue().strip()); rec["stdout"] = buf.getvalue()[:200]
        rec["mutated"] = args != before
        rec["none"] = res is None
        try: rec["got"] = copy.deepcopy(res)
        except Exception: rec["got"] = repr(res)
        ok = _eq(res, t["expected"])
        rec["type_mismatch"] = (not ok) and type(res) is not type(t["expected"]) and res is not None
        if ok and problem["checks"].get("no_mutate") and rec["mutated"]: ok = False
        if ok and problem["checks"].get("independent_rows") and isinstance(res, list) and len(res) > 1:
            probe = copy.deepcopy(res)
            if all(isinstance(r, list) and r for r in probe):
                probe[0][0] = 99
                if any(r[0] == 99 for r in probe[1:]): ok = False; rec["alias"] = True
        rec["ok"] = ok
        out.append(rec)
    return dict(status="ok", tests=out)
