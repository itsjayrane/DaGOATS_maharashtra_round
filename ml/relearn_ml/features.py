"""Feature extraction: (1) normalized code text for TF-IDF, (2) AST structure signals, (3) execution-behaviour signals."""
import ast, re
import numpy as np

BUILTIN_KEEP = {"len", "range", "print", "sum", "min", "max", "abs", "int", "float", "str", "list", "dict", "set", "tuple",
                "sorted", "enumerate", "zip", "round", "bool", "reversed", "any", "all", "True", "False", "None"}
STR_METHODS = {"upper", "lower", "capitalize", "title", "strip", "lstrip", "rstrip", "replace", "swapcase", "zfill", "center"}
LIST_MUT = {"append", "extend", "insert", "sort", "reverse", "pop", "remove"}


def parse(code):
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


# ---------- normalized text ----------
class _Norm(ast.NodeTransformer):
    def __init__(self, params):
        self.params = params

    def visit_FunctionDef(self, n):
        n.name = "FN"
        n.body = [s for s in n.body if not (isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None), ast.Constant)
                                            and isinstance(s.value.value, str))] or [ast.Pass()]
        self.generic_visit(n)
        return n

    def visit_arg(self, n):
        n.arg = "ARG"
        return n

    def visit_Name(self, n):
        if n.id in BUILTIN_KEEP:
            return n
        n.id = "ARG" if n.id in self.params else "VAR"
        return n

    def visit_Constant(self, n):
        v = n.value
        if isinstance(v, str):
            return ast.copy_location(ast.Constant("S"), n)
        if isinstance(v, bool) or v is None:
            return n
        if isinstance(v, (int, float)) and v not in (0, 1, 2, -1, 5, 9, 32, 100):
            return ast.copy_location(ast.Constant(7), n)
        return n


def normalize(code):
    tree = parse(code)
    if tree is None:
        return "SYNTAXERROR " + re.sub(r"[A-Za-z_]\w*", "id", code)
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)), None)
    params = {a.arg for a in fn.args.args} if fn else set()
    tree = _Norm(params).visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


TOKEN_RE = r"[A-Za-z_]+|\d+|==|<=|>=|!=|//|\*\*|\+=|-=|\*=|[^\s\w]"


def tokens(text):
    return re.findall(TOKEN_RE, text)


# ---------- AST features ----------
def _contains_len(n):
    return any(_is_len_call(x) for x in ast.walk(n))


def _is_const(n, v):
    return isinstance(n, ast.Constant) and n.value == v and not isinstance(n.value, bool)


def _is_len_call(n):
    return isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "len"


def _binop(n, op, right=None):
    return isinstance(n, ast.BinOp) and isinstance(n.op, op) and (right is None or _is_const(n.right, right))


AST_KEYS = ["syntax_error", "n_for", "n_while", "n_print", "has_return", "n_return", "ret_in_loop", "ret_direct_in_loop",
            "ret_in_if_in_loop", "ret_after_loop", "ret_if_else_both", "reset_in_loop", "init_before_loop", "n_range",
            "range_len_minus1", "range_start1_len", "range_start1_plus1", "range_start1_bare", "range_onearg_bare",
            "range_onearg_plus1", "range_onearg_len", "range_3arg_bare", "range_3arg_plus1", "range_bare_any",
            "sub_idx_len", "sub_idx_len_m1", "sub_idx_c1", "sub_idx_c0", "sub_idx_neg1", "sub_idx_name_m1",
            "sub_idx_bare_param", "sub_idx_bare_name", "sub_slice_copy", "sub_idx_name_plus1", "n_floordiv", "n_truediv",
            "floordiv_const", "floordiv_nonconst", "int_call", "round_call", "float_call", "sub_store", "sub_store_on_param",
            "discarded_str_method", "alias_assign", "alias_of_param", "mutate_param", "mutate_alias", "copy_idiom",
            "list_call_param", "concat_list", "list_comp", "list_mult_container", "append_outer_name", "while_lt", "while_le",
            "n_nodes", "print_no_return", "print_and_return",
            "sig_M1", "sig_M2", "sig_M3", "sig_M4", "sig_M5", "sig_M6", "sig_M7", "sig_M8", "sig_any"]

# The AST features that ARE the misconceptions. Aggregated per misconception (sig_M1..sig_M8, sig_any) so the model can
# generalise "some M2-style indexing signature fired" to problems whose exact pattern it never saw. OTHER_BUG samples are
# defined as wrong programs that fire none of these (see mutants.py).
SIGNATURE_KEYS = {
    "M1": ["range_len_minus1", "range_start1_bare", "range_3arg_bare"],
    "M2": ["sub_idx_len", "sub_idx_c1", "range_start1_len", "sub_idx_bare_param"],
    "M3": ["print_no_return"],
    "M4": ["reset_in_loop"],
    "M5": ["ret_direct_in_loop", "ret_if_else_both"],
    "M6": ["n_floordiv", "int_call"],
    "M7": ["sub_store_on_param", "discarded_str_method"],
    "M8": ["alias_of_param", "mutate_param", "list_mult_container", "append_outer_name"],
}


def _range(f, n):
    f["n_range"] += 1
    a = n.args
    stop = a[1] if len(a) >= 2 else (a[0] if a else None)
    if stop is None:
        return
    plus1 = _binop(stop, ast.Add, 1)
    haslen = _contains_len(stop)
    minus1 = _binop(stop, ast.Sub, 1) and haslen
    bare = not plus1 and not haslen and not _binop(stop, ast.Sub)
    if len(a) == 1:
        if minus1:
            f["range_len_minus1"] += 1
        elif haslen:
            f["range_onearg_len"] += 1
        elif plus1:
            f["range_onearg_plus1"] += 1
        elif bare:
            f["range_onearg_bare"] += 1
            f["range_bare_any"] += 1
    elif len(a) == 2:
        if minus1:
            f["range_len_minus1"] += 1
        if _is_const(a[0], 1):
            if haslen and not minus1:
                f["range_start1_len"] += 1
            elif plus1:
                f["range_start1_plus1"] += 1
            elif bare:
                f["range_start1_bare"] += 1
                f["range_bare_any"] += 1
        elif bare:
            f["range_bare_any"] += 1
    else:
        if plus1:
            f["range_3arg_plus1"] += 1
        elif bare:
            f["range_3arg_bare"] += 1
            f["range_bare_any"] += 1


def _is_simple_init(s):
    return (isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name)
            and isinstance(s.value, (ast.Constant, ast.List)))


def ast_features(code):
    f = dict.fromkeys(AST_KEYS, 0)
    tree = parse(code)
    if tree is None:
        f["syntax_error"] = 1
        return f
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)), None)
    if fn is None:
        f["n_nodes"] = sum(1 for _ in ast.walk(tree))
        return f
    params = {a.arg for a in fn.args.args}
    parent = {}
    for p in ast.walk(fn):
        for c in ast.iter_child_nodes(p):
            parent[c] = p

    def loops_above(n):
        out = []
        while n in parent:
            n = parent[n]
            if isinstance(n, (ast.For, ast.While)):
                out.append(n)
        return out

    f["n_nodes"] = sum(1 for _ in ast.walk(fn))
    outer_assigned = {t.id for a in ast.walk(fn) if isinstance(a, ast.Assign) and not loops_above(a)
                      for t in a.targets if isinstance(t, ast.Name)}
    for n in ast.walk(fn):
        if isinstance(n, ast.For):
            f["n_for"] += 1
        if isinstance(n, ast.While):
            f["n_while"] += 1
            for c in ast.walk(n.test):
                if isinstance(c, ast.Compare):
                    for o in c.ops:
                        if isinstance(o, ast.Lt):
                            f["while_lt"] += 1
                        if isinstance(o, ast.LtE):
                            f["while_le"] += 1
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            nm = n.func.id
            if nm == "print":
                f["n_print"] += 1
            elif nm == "int":
                f["int_call"] += 1
            elif nm == "round":
                f["round_call"] += 1
            elif nm == "float":
                f["float_call"] += 1
            elif nm == "list" and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id in params:
                f["list_call_param"] += 1
                f["copy_idiom"] += 1
            elif nm == "range":
                _range(f, n)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr == "copy":
                f["copy_idiom"] += 1
            if n.func.attr == "append" and n.args and isinstance(n.args[0], ast.Name) and loops_above(n):
                if n.args[0].id in outer_assigned:
                    f["append_outer_name"] += 1
        if isinstance(n, ast.Return):
            f["n_return"] += 1
            f["has_return"] = 1
            lo = loops_above(n)
            if lo:
                f["ret_in_loop"] += 1
                if parent.get(n) in lo:
                    f["ret_direct_in_loop"] += 1
                if isinstance(parent.get(n), ast.If):
                    f["ret_in_if_in_loop"] += 1
            elif parent.get(n) is fn and any(isinstance(s, (ast.For, ast.While)) for s in fn.body):
                f["ret_after_loop"] += 1
        if isinstance(n, ast.If) and loops_above(n):
            has = lambda body: any(isinstance(s, ast.Return) for s in body)
            if has(n.body) and has(n.orelse):
                f["ret_if_else_both"] += 1
        if isinstance(n, ast.BinOp):
            if isinstance(n.op, ast.FloorDiv):
                f["n_floordiv"] += 1
                if isinstance(n.left, ast.Constant) and isinstance(n.right, ast.Constant):
                    f["floordiv_const"] += 1
                else:
                    f["floordiv_nonconst"] += 1
            if isinstance(n.op, ast.Div):
                f["n_truediv"] += 1
            if isinstance(n.op, ast.Mult):
                for a, b in ((n.left, n.right), (n.right, n.left)):
                    if isinstance(a, ast.List) and len(a.elts) == 1 and not isinstance(a.elts[0], ast.Constant):
                        f["list_mult_container"] += 1
            if isinstance(n.op, ast.Add) and (isinstance(n.left, ast.List) or isinstance(n.right, ast.List)):
                f["concat_list"] += 1
                f["copy_idiom"] += 1
        if isinstance(n, ast.ListComp):
            f["list_comp"] += 1
        if isinstance(n, ast.Subscript):
            idx = n.slice
            if isinstance(idx, ast.Slice):
                if idx.lower is None and idx.upper is None:
                    f["sub_slice_copy"] += 1
                    f["copy_idiom"] += 1
            else:
                if _is_len_call(idx):
                    f["sub_idx_len"] += 1
                elif _binop(idx, ast.Sub, 1) and _is_len_call(idx.left):
                    f["sub_idx_len_m1"] += 1
                elif _binop(idx, ast.Sub, 1) and isinstance(idx.left, ast.Name):
                    f["sub_idx_name_m1"] += 1
                elif _binop(idx, ast.Add, 1):
                    f["sub_idx_name_plus1"] += 1
                elif _is_const(idx, 1):
                    f["sub_idx_c1"] += 1
                elif _is_const(idx, 0):
                    f["sub_idx_c0"] += 1
                elif (isinstance(idx, ast.UnaryOp) and isinstance(idx.op, ast.USub)) or _is_const(idx, -1):
                    f["sub_idx_neg1"] += 1
                elif isinstance(idx, ast.Name):
                    f["sub_idx_bare_param" if idx.id in params else "sub_idx_bare_name"] += 1
            if isinstance(n.ctx, ast.Store):
                f["sub_store"] += 1
                if isinstance(n.value, ast.Name) and n.value.id in params:
                    f["sub_store_on_param"] += 1
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute):
            if n.value.func.attr in STR_METHODS:
                f["discarded_str_method"] += 1

    aliases = set()
    for n in ast.walk(fn):
        if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Name) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)):
            f["alias_assign"] += 1
            if n.value.id in params:
                f["alias_of_param"] += 1
                aliases.add(n.targets[0].id)
    for n in ast.walk(fn):
        tgt = None
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in LIST_MUT
                and isinstance(n.func.value, ast.Name)):
            tgt = n.func.value.id
        elif isinstance(n, (ast.Assign, ast.AugAssign)):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                    tgt = t.value.id
        if tgt in params:
            f["mutate_param"] += 1
        if tgt in aliases:
            f["mutate_alias"] += 1

    for lp in (n for n in ast.walk(fn) if isinstance(n, (ast.For, ast.While))):
        updated = set()
        for x in ast.walk(lp):
            if isinstance(x, ast.AugAssign) and isinstance(x.target, ast.Name):
                updated.add(x.target.id)
            if (isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == "append"
                    and isinstance(x.func.value, ast.Name)):
                updated.add(x.func.value.id)
            if (isinstance(x, ast.Assign) and len(x.targets) == 1 and isinstance(x.targets[0], ast.Name)
                    and any(isinstance(y, ast.Name) and y.id == x.targets[0].id for y in ast.walk(x.value))):
                updated.add(x.targets[0].id)
        for s in lp.body:
            if _is_simple_init(s) and s.targets[0].id in updated:
                f["reset_in_loop"] += 1
        for s in fn.body:
            if _is_simple_init(s) and s.targets[0].id in updated:
                f["init_before_loop"] += 1
    f["print_no_return"] = int(f["n_print"] > 0 and f["n_return"] == 0)
    f["print_and_return"] = int(f["n_print"] > 0 and f["n_return"] > 0)
    for m, keys in SIGNATURE_KEYS.items():
        f[f"sig_{m}"] = int(sum(1 for k in keys if f[k]))
    f["sig_any"] = int(sum(f[f"sig_{m}"] for m in SIGNATURE_KEYS))
    return f


# ---------- execution features ----------
EXEC_KEYS = ["pass_frac", "exc_type", "exc_index", "exc_other", "exc_timeout", "none_frac", "printed_frac", "mutated_frac",
             "alias_frac", "typemis_frac", "wrong_noexc_frac", "status_bad", "any_pass", "all_pass"]


def exec_features(res):
    f = dict.fromkeys(EXEC_KEYS, 0.0)
    if res["status"] != "ok" or not res["tests"]:
        f["status_bad"] = 1.0
        return f
    t = res["tests"]
    n = len(t)
    frac = lambda pred: sum(1 for x in t if pred(x)) / n
    f["pass_frac"] = frac(lambda x: x["ok"])
    f["exc_type"] = frac(lambda x: x["exc"] == "TypeError")
    f["exc_index"] = frac(lambda x: x["exc"] == "IndexError")
    f["exc_timeout"] = frac(lambda x: x["exc"] == "Timeout")
    f["exc_other"] = frac(lambda x: bool(x["exc"]) and x["exc"] not in ("TypeError", "IndexError", "Timeout"))
    f["none_frac"] = frac(lambda x: x["none"])
    f["printed_frac"] = frac(lambda x: x["printed"])
    f["mutated_frac"] = frac(lambda x: x["mutated"])
    f["alias_frac"] = frac(lambda x: x["alias"])
    f["typemis_frac"] = frac(lambda x: x["type_mismatch"])
    f["wrong_noexc_frac"] = frac(lambda x: (not x["ok"]) and not x["exc"] and not x["none"])
    f["any_pass"] = float(any(x["ok"] for x in t))
    f["all_pass"] = float(all(x["ok"] for x in t))
    return f


PROB_KEYS = ["p_str_param", "p_list_param", "p_ret_float", "p_ret_list", "p_ret_bool", "p_no_mutate"]


def problem_features(p):
    return dict(p_str_param=float("str" in p["param_types"]), p_list_param=float("list" in p["param_types"]),
                p_ret_float=float(p["return_type"] == "float"), p_ret_list=float(p["return_type"] == "list"),
                p_ret_bool=float(p["return_type"] == "bool"), p_no_mutate=float(bool(p["checks"].get("no_mutate"))))


def dense_matrix(rows, use_ast=True, use_exec=True, use_prob=True):
    keys = (AST_KEYS if use_ast else []) + (EXEC_KEYS if use_exec else []) + (PROB_KEYS if use_prob else [])
    return np.array([[r[k] for k in keys] for r in rows], dtype=np.float32), keys


def featurize(code, problem, exec_res):
    r = {}
    r.update(ast_features(code))
    r.update(exec_features(exec_res))
    r.update(problem_features(problem))
    r["norm"] = normalize(code)
    return r
