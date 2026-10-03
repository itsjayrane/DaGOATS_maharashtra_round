"""Minimal, verified fixes of a learner's code for each misconception.

Candidate fixes are small *source-preserving* edits (character-offset replacements guided by the AST), so the learner's
formatting, comments and names survive. Every candidate is run against the problem's tests through `run`; the first
one that passes everything wins. If none does, the caller falls back to the problem's reference solution.
"""
import ast, difflib, hashlib, itertools, re, time
from collections import OrderedDict

MAX_ATTEMPTS = 24        # candidate programs actually executed
MAX_CANDIDATES = 40      # candidate edit-combinations considered at all
TIME_BUDGET_S = 3.0      # total wall time for one search
_FIX_CACHE = OrderedDict()  # (problem id, label, code hash) -> result
STR_METHODS = {"upper", "lower", "capitalize", "title", "strip", "lstrip", "rstrip", "replace", "swapcase", "zfill", "center"}
MUTATORS = {"append", "extend", "insert", "sort", "reverse", "pop", "remove"}
LOW_PREC = (ast.Add, ast.Sub)


def _is_name(n, name): return isinstance(n, ast.Name) and n.id == name
def _is_const(n, v): return isinstance(n, ast.Constant) and n.value == v and not isinstance(n.value, bool)
def _is_len(n): return isinstance(n, ast.Call) and _is_name(n.func, "len")
def _has_len(n): return any(_is_len(x) for x in ast.walk(n))
def _is_sub1(n): return isinstance(n, ast.BinOp) and isinstance(n.op, ast.Sub) and _is_const(n.right, 1)
def _is_add1(n): return isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add) and _is_const(n.right, 1)


class Ctx:
    def __init__(self, code, fn_name=None):
        self.code = code.replace("\r\n", "\n")
        self.lines = self.code.split("\n")
        self.starts, pos = [], 0
        for l in self.lines:
            self.starts.append(pos)
            pos += len(l) + 1
        self.tree = ast.parse(self.code)
        defs = [n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)]
        self.fn = next((d for d in defs if d.name == fn_name), defs[0] if defs else None)
        self.parent = {}
        self.params = set()
        if self.fn:
            self.params = {a.arg for a in self.fn.args.args}
            for p in ast.walk(self.fn):
                for c in ast.iter_child_nodes(p):
                    self.parent[c] = p

    # ---- offsets / edits
    def off(self, lineno, col):
        line = self.lines[lineno - 1]
        return self.starts[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8", errors="ignore"))

    def span(self, n): return self.off(n.lineno, n.col_offset), self.off(n.end_lineno, n.end_col_offset)
    def text(self, n): a, b = self.span(n); return self.code[a:b]
    def rep(self, n, s): a, b = self.span(n); return (a, b, s)
    def line_end(self, l): return min(self.starts[l - 1] + len(self.lines[l - 1]) + 1, len(self.code))
    def delete_lines(self, n): return (self.starts[n.lineno - 1], self.line_end(n.end_lineno), "")
    def delete_line_range(self, l1, l2): return (self.starts[l1 - 1], self.line_end(l2), "")
    def indent(self, lineno): return re.match(r"[ \t]*", self.lines[lineno - 1]).group()

    def insert_before(self, lineno, s):
        p = self.starts[lineno - 1]
        return (p, p, s + "\n")

    def insert_after(self, n, s):
        p = self.line_end(n.end_lineno)
        return (p, p, ("\n" + s) if (p == len(self.code) and not self.code.endswith("\n")) else s + "\n")

    def loops_above(self, n):
        out = []
        while n in self.parent:
            n = self.parent[n]
            if isinstance(n, (ast.For, ast.While)):
                out.append(n)
        return out

    def wrap(self, n, s):  # parenthesise s when n is a low-precedence binop
        return f"({s})" if isinstance(n, ast.BinOp) and isinstance(n.op, LOW_PREC) else s

    def plus1(self, n):
        return f"{self.wrap(n, self.text(n))} + 1"

    def body_indent(self):
        return self.indent(self.fn.body[0].lineno)

    def body_start_stmt(self):  # first real statement (after a docstring)
        b = self.fn.body
        if len(b) > 1 and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) and isinstance(b[0].value.value, str):
            return b[1]
        return b[0]


def apply_edits(code, edits):
    es = sorted(edits, key=lambda e: (e[0], e[1]))
    for a, b in zip(es, es[1:]):
        if a[1] > b[0]:
            return None  # overlapping edits
    for s, e, t in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        code = code[:s] + t + code[e:]
    return code


# ============================================================ candidate generators: label -> [(rule, [edits])]
def c_m1(c):
    out = []
    for n in ast.walk(c.fn):
        if isinstance(n, ast.Call) and _is_name(n.func, "range") and n.args:
            a = n.args
            stop = a[1] if len(a) >= 2 else a[0]
            if _is_sub1(stop):
                out.append(("range() stops one item early: removed the `- 1` from its stop value", [c.rep(stop, c.text(stop.left))]))
            elif not _is_add1(stop):
                out.append(("range(a, b) stops BEFORE b: stop value is now `" + c.plus1(stop) + "`", [c.rep(stop, c.plus1(stop))]))
                if len(a) == 1:
                    out.append((f"range(n) ends at n-1 and starts at 0: now `range(1, {c.plus1(stop)})`", [c.rep(n, f"range(1, {c.plus1(stop)})")]))
        if isinstance(n, ast.While) and isinstance(n.test, ast.Compare) and len(n.test.ops) == 1:
            t = n.test
            if isinstance(t.ops[0], ast.Lt):
                if _is_sub1(t.comparators[0]):
                    out.append(("while stops one item early: removed the `- 1` from its limit", [c.rep(t.comparators[0], c.text(t.comparators[0].left))]))
                else:
                    a_, b_ = c.span(t.left)[1], c.span(t.comparators[0])[0]
                    i = c.code[a_:b_].find("<")
                    if i >= 0:
                        out.append(("while stops before the last value: `<` is now `<=`", [(a_ + i, a_ + i + 1, "<=")]))
        if isinstance(n, ast.Assign) and _is_sub1(n.value) and _has_len(n.value.left):
            out.append(("bound is one too small: removed the `- 1`", [c.rep(n.value, c.text(n.value.left))]))
    covered = {id(x) for x in ast.walk(c.fn) if isinstance(x, ast.Call) and _is_name(x.func, "range")}
    for n in ast.walk(c.fn):  # last resort: a `- 1` that shortens a size/limit anywhere else (verified by the tests)
        if _is_sub1(n) and not any(id(p) in covered for p in [c.parent.get(n)]) and not isinstance(c.parent.get(n), (ast.Subscript, ast.Assign, ast.Compare)):
            out.append(("a size/limit is one too small: removed the `- 1`", [c.rep(n, c.text(n.left))]))
    return out


def c_m2(c):
    out = []
    for n in ast.walk(c.fn):
        if isinstance(n, ast.Subscript) and not isinstance(n.slice, ast.Slice):
            i = n.slice
            if _is_len(i):
                out.append(("the last valid index is len(x) - 1, not len(x)", [c.rep(i, c.text(i) + " - 1")]))
            elif isinstance(i, ast.Name):
                out.append((f"list indexes start at 0, so the item at position `{i.id}` is `[{i.id} - 1]`", [c.rep(i, f"{i.id} - 1")]))
            elif _is_const(i, 1):
                out.append(("the first item is at index 0, not 1", [c.rep(i, "0")]))
        if isinstance(n, ast.Assign) and _is_len(n.value):
            out.append(("the last valid index is len(x) - 1", [c.rep(n.value, c.text(n.value) + " - 1")]))
        if isinstance(n, ast.Call) and _is_name(n.func, "range") and len(n.args) >= 2 and _is_const(n.args[0], 1):
            out.append(("indexes start at 0: range now starts at 0", [c.rep(n.args[0], "0")]))
            ls = [x for x in ast.walk(n.args[1]) if _is_len(x)]
            if ls:
                out.append(("loop over every index: `range(len(x))`", [c.rep(n, f"range({c.text(ls[0])})")]))
        if isinstance(n, ast.Call) and _is_name(n.func, "enumerate") and (len(n.args) == 2 or n.keywords):
            out.append(("enumerate() already counts from 0 - removed the start value", [c.rep(n, f"enumerate({c.text(n.args[0])})")]))
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and _is_const(n.value, 1):
            out.append(("start the index at 0, not 1", [c.rep(n.value, "0")]))
        if isinstance(n, ast.While) and isinstance(n.test, ast.Compare) and len(n.test.ops) == 1 and isinstance(n.test.ops[0], ast.LtE) and _has_len(n.test.comparators[0]):
            t = n.test
            a_, b_ = c.span(t.left)[1], c.span(t.comparators[0])[0]
            i = c.code[a_:b_].find("<=")
            if i >= 0:
                out.append(("the last index is len(x) - 1: `<=` is now `<`", [(a_ + i, a_ + i + 2, "<")]))
    subs = [n for n in ast.walk(c.fn) if isinstance(n, ast.Subscript) and not isinstance(n.slice, ast.Slice)]
    ones = [n.slice for n in subs if _is_const(n.slice, 1)]
    if len(ones) > 1:
        out.append(("the first item is at index 0, not 1 (every occurrence)", [c.rep(i, "0") for i in ones]))
    lens = [n.slice for n in subs if _is_len(n.slice)]
    if len(lens) > 1:
        out.append(("the last valid index is len(x) - 1 (every occurrence)", [c.rep(i, c.text(i) + " - 1") for i in lens]))
    if ones and lens:
        out.append(("index 1 is really the second item and len(x) is past the end: first is 0, last is len(x) - 1",
                    [c.rep(i, "0") for i in ones] + [c.rep(i, c.text(i) + " - 1") for i in lens]))
    return out


def _print_stmts(c):
    return [n for n in ast.walk(c.fn) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and _is_name(n.value.func, "print") and n.value.args]


def _ret_text(c, v):
    if isinstance(v, ast.Constant) and isinstance(v.value, str) and v.value in ("True", "False", "None"):
        return v.value  # the learner printed the word; the function must return the value itself
    return c.text(v)


def _print_value(p):
    args = p.value.args
    non_str = [a for a in args if not (isinstance(a, ast.Constant) and isinstance(a.value, str))]
    return (non_str or args)[-1]


def c_m3(c):
    out, prints = [], _print_stmts(c)
    for p in prints:
        v = _print_value(p)
        edits = [c.rep(p, f"return {_ret_text(c, v)}")]
        sib = None
        body = getattr(c.parent.get(p), "body", [])
        if p in body and body.index(p) + 1 < len(body):
            nx = body[body.index(p) + 1]
            if isinstance(nx, ast.Return) and (nx.value is None or _is_const(nx.value, None) or (isinstance(nx.value, ast.Constant) and nx.value.value is None)):
                sib = nx
        if sib is not None:
            out.append(("print() only shows a value: `return` it (and dropped the `return None`)", edits + [c.delete_lines(sib)]))
        out.append(("print() only shows a value: the function must `return` it", edits))
    if len(prints) > 1:
        out.append(("every branch must `return` its value instead of printing it", [c.rep(p, f"return {_ret_text(c, _print_value(p))}") for p in prints]))
    has_return = any(isinstance(n, ast.Return) for n in ast.walk(c.fn))
    for p in prints:
        v = _print_value(p)
        if c.loops_above(p) and isinstance(v, ast.Name) and not has_return:
            ind = c.body_indent()
            out.append((f"print inside the loop only shows each step: removed it and `return {v.id}` after the loop",
                        [c.delete_lines(p), c.insert_after(c.fn.body[-1], f"{ind}return {v.id}")]))
    return out


def c_m4(c):
    out = []
    for lp in (n for n in ast.walk(c.fn) if isinstance(n, (ast.For, ast.While))):
        updated = set()
        for x in ast.walk(lp):
            if isinstance(x, ast.AugAssign) and isinstance(x.target, ast.Name):
                updated.add(x.target.id)
            if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == "append" and isinstance(x.func.value, ast.Name):
                updated.add(x.func.value.id)
            if isinstance(x, ast.Assign) and len(x.targets) == 1 and isinstance(x.targets[0], ast.Name) and any(isinstance(y, ast.Name) and y.id == x.targets[0].id for y in ast.walk(x.value)):
                updated.add(x.targets[0].id)
        for s in lp.body:
            if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name) and isinstance(s.value, (ast.Constant, ast.List)) and s.targets[0].id in updated:
                nm = s.targets[0].id
                init_before = any(isinstance(b, ast.Assign) and len(b.targets) == 1 and isinstance(b.targets[0], ast.Name) and b.targets[0].id == nm and b.lineno < lp.lineno for b in c.fn.body)
                if init_before:
                    out.append((f"`{nm}` was reset on every pass: removed the reset inside the loop", [c.delete_lines(s)]))
                else:
                    out.append((f"moved `{c.text(s)}` out of the loop so it runs once, before the loop",
                                [c.delete_lines(s), c.insert_before(lp.lineno, c.indent(lp.lineno) + c.text(s))]))
    return out


def c_m5(c):
    out = []
    returns = [n for n in ast.walk(c.fn) if isinstance(n, ast.Return) and c.loops_above(n)]
    for r in returns:
        outer = c.loops_above(r)[-1]
        sibs = [n for n in c.parent.get(outer, c.fn).body if isinstance(n, ast.Return) and n.lineno > outer.lineno] if hasattr(c.parent.get(outer, c.fn), "body") else []
        if sibs:
            out.append(("`return` inside the loop ends the function on the first pass: removed it (the result is returned after the loop)", [c.delete_lines(r)]))
        val = c.text(r.value) if r.value is not None else ""
        move = [c.delete_lines(r), c.insert_after(outer, f"{c.indent(outer.lineno)}return {val}".rstrip())]
        out.append(("`return` ends the whole function: moved it after the loop so every item is processed", move))
        if sibs:
            out.append(("`return` ends the whole function: moved it after the loop", move + [c.delete_lines(sibs[0])]))
        par = c.parent.get(r)
        if isinstance(par, ast.If) and par.orelse == [r]:
            else_line = next((l for l in range(r.lineno - 1, par.lineno, -1) if re.match(r"\s*else\s*:", c.lines[l - 1])), None)
            if else_line:
                out.append(("the `else: return ...` ended the loop after one item: moved that return after the loop",
                            [c.delete_line_range(else_line, r.end_lineno), c.insert_after(outer, f"{c.indent(outer.lineno)}return {val}")]))
    return out


def c_m6(c):
    out, fds = [], [n for n in ast.walk(c.fn) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.FloorDiv)]

    def op_edit(n):
        a, b = c.span(n.left)[1], c.span(n.right)[0]
        i = c.code[a:b].find("//")
        return (a + i, a + i + 2, "/") if i >= 0 else None
    es = [(n, op_edit(n)) for n in fds]
    for n, e in es:
        if e:
            out.append(("`//` throws away the decimals: use `/` for the exact quotient", [e]))
    if len(es) > 1 and all(e for _, e in es):
        out.append(("`//` throws away the decimals: every division now uses `/`", [e for _, e in es]))
    for n in ast.walk(c.fn):
        if isinstance(n, ast.Call) and _is_name(n.func, "int") and len(n.args) == 1:
            inner = c.text(n.args[0])
            par = c.parent.get(n)
            if isinstance(par, (ast.BinOp, ast.UnaryOp)):
                inner = f"({inner})"
            out.append(("`int()` cuts off the decimals: removed it", [c.rep(n, inner)]))
    return out


def c_m7(c):
    out = []
    for n in ast.walk(c.fn):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Subscript) and isinstance(n.targets[0].value, ast.Name) and not isinstance(n.targets[0].slice, ast.Slice):
            nm, i, v = n.targets[0].value.id, n.targets[0].slice, c.text(n.value)
            v = c.wrap(n.value, v)
            if _is_const(i, 0):
                new = f"{nm} = {v} + {nm}[1:]"
            else:
                it = c.text(i) if isinstance(i, (ast.Name, ast.Constant)) else f"({c.text(i)})"
                new = f"{nm} = {nm}[:{it}] + {v} + {nm}[{it} + 1:]"
            out.append(("strings can't be changed in place: build a NEW string with slicing and assign it back", [c.rep(n, new)]))
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) and n.value.func.attr in STR_METHODS and isinstance(n.value.func.value, ast.Name):
            nm = n.value.func.value.id
            out.append((f"`{nm}.{n.value.func.attr}()` returns a NEW string: its result must be assigned back to `{nm}`", [c.rep(n, f"{nm} = {c.text(n.value)}")]))
        if (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) and n.value.func.attr in STR_METHODS
                and isinstance(n.value.func.value, ast.Subscript) and isinstance(n.value.func.value.value, ast.Name) and _is_const(n.value.func.value.slice, 0)):
            nm = n.value.func.value.value.id
            out.append((f"`{nm}[0].{n.value.func.attr}()` makes a NEW string that is thrown away: build the result and assign it back",
                        [c.rep(n, f"{nm} = {c.text(n.value)} + {nm}[1:]")]))
    return out


def _mutated_params(c):
    out = []
    for n in ast.walk(c.fn):
        tgt = None
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in MUTATORS and isinstance(n.func.value, ast.Name):
            tgt = n.func.value.id
        elif isinstance(n, (ast.Assign, ast.AugAssign)):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                    tgt = t.value.id
        if tgt in c.params and tgt not in out:
            out.append(tgt)
    return out


def _list_of_lists_names(c):
    """names assigned a list whose elements are themselves lists/expressions (a grid row template like [[0] * c])."""
    return {t.id: True for a in ast.walk(c.fn) if isinstance(a, ast.Assign) and isinstance(a.value, ast.List) and a.value.elts
            and not all(isinstance(e, ast.Constant) for e in a.value.elts) for t in a.targets if isinstance(t, ast.Name)}


def c_m8(c):
    out = []
    for n in ast.walk(c.fn):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Name):
            out.append((f"`{n.targets[0].id} = {n.value.id}` only gives the SAME list a second name: copy it with `{n.value.id}[:]`", [c.rep(n.value, f"{n.value.id}[:]")]))
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult):
            for lst, cnt in ((n.left, n.right), (n.right, n.left)):
                if isinstance(lst, ast.List) and len(lst.elts) == 1 and not isinstance(lst.elts[0], ast.Constant):
                    e = lst.elts[0]
                    el = f"{c.text(e)}[:]" if isinstance(e, ast.Name) else c.text(e)
                    out.append(("`[row] * n` repeats ONE row n times: build a separate row for each position", [c.rep(n, f"[{el} for _ in range({c.text(cnt)})]")]))
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult):
            for nm_node, cnt in ((n.left, n.right), (n.right, n.left)):
                if isinstance(nm_node, ast.Name) and _list_of_lists_names(c).get(nm_node.id):
                    out.append((f"`{nm_node.id} * n` repeats the SAME inner lists: copy each row", [c.rep(n, f"[_row[:] for _row in {c.text(n)}]")]))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "append" and n.args and isinstance(n.args[0], ast.Name) and c.loops_above(n):
            nm = n.args[0].id
            if any(isinstance(a, ast.Assign) and any(isinstance(t, ast.Name) and t.id == nm for t in a.targets) and not c.loops_above(a) for a in ast.walk(c.fn)):
                out.append((f"the same `{nm}` list is appended every time: append a copy `{nm}[:]` instead", [c.rep(n.args[0], f"{nm}[:]")]))
    first = c.body_start_stmt()
    for p in _mutated_params(c):
        out.append((f"the function changes its argument `{p}` in place: work on a copy (`{p} = {p}[:]`)", [c.insert_before(first.lineno, f"{c.indent(first.lineno)}{p} = {p}[:]")]))
    return out


CANDS = {"M1_RANGE_OFF_BY_ONE": c_m1, "M2_INDEX_FROM_ONE": c_m2, "M3_PRINT_NOT_RETURN": c_m3, "M4_ACCUMULATOR_RESET": c_m4,
         "M5_RETURN_IN_LOOP": c_m5, "M6_FLOAT_DIVISION": c_m6, "M7_STRING_MUTABLE": c_m7, "M8_LIST_ALIASING": c_m8}


# ============================================================ search + helpers
def find_fix(code, problem, label, run, max_attempts=MAX_ATTEMPTS, time_budget=TIME_BUDGET_S):
    """Returns dict(code, rule, passed, total, attempts) for the first candidate that passes every test, else None.
    Capped at MAX_CANDIDATES combinations, max_attempts executions and `time_budget` seconds; cached per (problem, label, code)."""
    key = (problem.get("id"), label, hashlib.sha1(code.replace("\r\n", "\n").encode()).hexdigest())
    if key in _FIX_CACHE:
        _FIX_CACHE.move_to_end(key)
        return _FIX_CACHE[key]
    result = _search(code, problem, label, run, max_attempts, time.monotonic() + time_budget)
    _FIX_CACHE[key] = result
    while len(_FIX_CACHE) > 256:
        _FIX_CACHE.popitem(last=False)
    return result


def _search(code, problem, label, run, max_attempts, deadline):
    try:
        c = Ctx(code, problem["fn"])
    except SyntaxError:
        return None
    if c.fn is None or label not in CANDS:
        return None
    cands = CANDS[label](c)
    combos = ([[x] for x in cands] + [list(p) for p in itertools.combinations(cands, 2)])[:MAX_CANDIDATES]
    seen, tried = {c.code}, 0
    for combo in combos:
        if time.monotonic() > deadline:
            break
        new = apply_edits(c.code, [e for _, es in combo for e in es])
        if new is None or new in seen:
            continue
        seen.add(new)
        try:
            ast.parse(new)
        except SyntaxError:
            continue
        if tried >= max_attempts:
            break
        tried += 1
        res = run(new, problem)
        if res["status"] == "ok" and res["tests"] and all(t["ok"] for t in res["tests"]):
            return dict(code=new, rule="; ".join(dict.fromkeys(d for d, _ in combo)), passed=len(res["tests"]), total=len(res["tests"]), attempts=tried)
    return None


def diff_lines(a, b):
    """1-based line numbers changed in a (replaced/deleted) and in b (replaced/inserted); blank lines ignored."""
    al, bl = a.split("\n"), b.split("\n")
    la, lb = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, al, bl, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            la += [i + 1 for i in range(i1, i2) if al[i].strip()]
        if tag in ("replace", "insert"):
            lb += [j + 1 for j in range(j1, j2) if bl[j].strip()]
    return la, lb


def same_code(a, b):
    try:
        return ast.dump(ast.parse(a)) == ast.dump(ast.parse(b))
    except SyntaxError:
        return a.strip() == b.strip()


def locate(code, label, fn_name=None):
    """Lines (1-based) where the misconception's signature appears - used to highlight when no line-level fix exists."""
    try:
        c = Ctx(code, fn_name)
    except SyntaxError:
        return []
    if c.fn is None:
        return []
    L = set()
    for n in ast.walk(c.fn):
        ln = getattr(n, "lineno", None)
        if ln is None:
            continue
        if label == "M1_RANGE_OFF_BY_ONE":
            if isinstance(n, ast.Call) and _is_name(n.func, "range") and n.args:
                stop = n.args[1] if len(n.args) >= 2 else n.args[0]
                if _is_sub1(stop) or not _is_add1(stop):
                    L.add(ln)
            if isinstance(n, ast.While) and isinstance(n.test, ast.Compare) and any(isinstance(o, ast.Lt) for o in n.test.ops):
                L.add(n.test.lineno)
            if isinstance(n, ast.Assign) and _is_sub1(n.value):
                L.add(ln)
        elif label == "M2_INDEX_FROM_ONE":
            if isinstance(n, ast.Subscript) and not isinstance(n.slice, ast.Slice) and (_is_len(n.slice) or isinstance(n.slice, ast.Name) or _is_const(n.slice, 1)):
                L.add(ln)
            if isinstance(n, ast.Call) and (_is_name(n.func, "range") and len(n.args) >= 2 and _is_const(n.args[0], 1) or _is_name(n.func, "enumerate") and len(n.args) == 2):
                L.add(ln)
            if isinstance(n, ast.Assign) and (_is_const(n.value, 1) or _is_len(n.value)):
                L.add(ln)
        elif label == "M3_PRINT_NOT_RETURN":
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and _is_name(n.value.func, "print"):
                L.add(ln)
        elif label == "M4_ACCUMULATOR_RESET":
            if isinstance(n, ast.Assign) and isinstance(n.value, (ast.Constant, ast.List)) and c.loops_above(n) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                L.add(ln)
        elif label == "M5_RETURN_IN_LOOP":
            if isinstance(n, ast.Return) and c.loops_above(n):
                L.add(ln)
        elif label == "M6_FLOAT_DIVISION":
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.FloorDiv) or isinstance(n, ast.Call) and _is_name(n.func, "int"):
                L.add(ln)
        elif label == "M7_STRING_MUTABLE":
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Subscript) for t in n.targets):
                L.add(ln)
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) and n.value.func.attr in STR_METHODS:
                L.add(ln)
        elif label == "M8_LIST_ALIASING":
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Name) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                L.add(ln)
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult) and (any(isinstance(x, ast.List) and len(x.elts) == 1 and not isinstance(x.elts[0], ast.Constant) for x in (n.left, n.right))
                                                                              or any(isinstance(x, ast.Name) and _list_of_lists_names(c).get(x.id) for x in (n.left, n.right))):
                L.add(ln)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in MUTATORS and isinstance(n.func.value, ast.Name) and n.func.value.id in c.params | {t.id for a in ast.walk(c.fn) if isinstance(a, ast.Assign) and isinstance(a.value, ast.Name) for t in a.targets if isinstance(t, ast.Name)}:
                L.add(ln)
            if isinstance(n, (ast.Assign, ast.AugAssign)):
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                        L.add(ln)
    return sorted(L)


def pick_reference(code, refs):
    """A verified correct solution that is NOT the learner's own code (panels must never show identical code)."""
    refs = [refs] if isinstance(refs, str) else list(refs)
    return next((r for r in refs if not same_code(r, code)), refs[0])


def personalize(code, problem, label, run, references):
    """Everything the intervention panel needs for THIS learner's code. `run(code, problem)` executes tests;
    `references` is one reference solution or a list of verified alternatives."""
    code = code.replace("\r\n", "\n")
    reference = pick_reference(code, references)
    fix = find_fix(code, problem, label, run)
    if fix and not same_code(fix["code"], code):
        la, lb = diff_lines(code, fix["code"])
        return dict(problem_id=problem["id"], label=label, your_code=code, highlight_lines=la or locate(code, label, problem["fn"]),
                    fixed_code=fix["code"], fixed_highlight_lines=lb, source="auto_fix", rule=fix["rule"],
                    verified=dict(passed=fix["passed"], total=fix["total"]), reference_solution=reference, identical=False)
    res = run(reference, problem)
    n = len(res["tests"])
    return dict(problem_id=problem["id"], label=label, your_code=code, highlight_lines=locate(code, label, problem["fn"]),
                fixed_code=reference, fixed_highlight_lines=[], source="reference_solution",
                rule="We couldn't make a safe one-line fix of your code, so here is a correct solution for this problem instead.",
                verified=dict(passed=sum(t["ok"] for t in res["tests"]), total=n), reference_solution=reference,
                identical=same_code(reference, code))
