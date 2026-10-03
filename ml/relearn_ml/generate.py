"""Synthetic dataset builder with execution-validated labels.

python -m relearn_ml.generate  ->  ml/data/dataset.jsonl
"""
import json, pathlib, random, re, string
from collections import Counter

from .execute import run_submission
from .features import featurize
from .problems import load_problems
from .mutants import other_bug_rows
from .templates import TEMPLATES

DATA = pathlib.Path(__file__).resolve().parents[1] / "data"

POOLS = {
    "nums": ["nums", "numbers", "lst", "values", "data", "xs", "a", "arr"],
    "items": ["items", "lst", "data", "seq", "arr", "values", "xs", "my_list"],
    "lst": ["lst", "items", "data", "xs", "original", "the_list"],
    "n": ["n", "num", "number", "limit", "x", "N", "m"],
    "k": ["k", "step", "base", "d"],
    "m": ["m", "cur", "val", "nxt"],
    "x": ["x", "num", "item", "v", "value", "e", "elem"],
    "tot": ["total", "s", "result", "acc", "answer", "res", "summ", "t"],
    "i": ["i", "idx", "j", "index", "pos"],
    "j": ["j", "jj", "col", "c2"],
    "res": ["result", "new_list", "out", "copy", "new", "res", "ans"],
    "row": ["row", "r", "line"],
    "rows": ["rows", "r", "height", "nrows"],
    "cols": ["cols", "c", "width", "ncols"],
    "grid": ["grid", "board", "matrix", "g"],
    "cnt": ["count", "c", "cnt", "evens", "num_even"],
    "prod": ["prod", "result", "p", "acc", "answer"],
    "name": ["name", "person", "who", "user"],
    "c": ["c", "celsius", "temp", "deg"],
    "part": ["part", "p", "top", "num"], "whole": ["whole", "w", "den", "total"],
    "s": ["s", "text", "word", "st", "string"],
    "ch": ["ch", "letter", "new_char", "char"],
    "t": ["t", "tmp", "other", "u"], "parts": ["parts", "chars", "letters", "lst2"],
    "msg": ["msg", "message", "out", "text2"], "r": ["r", "sq", "val", "answer"],
    "tmp": ["tmp", "temp", "hold", "t"], "last": ["last", "end_item", "final", "x"],
    "found": ["found", "flag", "has_neg", "neg"], "first": ["first", "head", "f"],
    "avg": ["avg", "mean", "average_val", "result"], "f": ["f", "fahr", "temp_f", "result"],
    "ratio": ["ratio", "factor", "r", "k"],
}
FIXED_PARAMS = {"k", "rows", "cols", "part", "whole", "ch", "name", "c", "s", "i"}  # placeholders left as pool picks too


def render(code, rng):
    keys = sorted(set(re.findall(r"\$([a-z]+)", code)), key=len, reverse=True)
    for _ in range(30):
        pick = {k: rng.choice(POOLS[k]) for k in keys}
        if len(set(pick.values())) == len(pick):
            break
    else:
        return None
    return re.sub(r"\$([a-z]+)", lambda m: pick[m.group(1)], code)


def augment(code, rng, label):
    lines = code.split("\n")
    # += expansion
    if rng.random() < 0.35:
        lines = [re.sub(r"^(\s*)(\w+) ([+\-*])= (.+)$", r"\1\2 = \2 \3 \4", l) for l in lines]
    # debug print before the return (never for M3 samples, keeps labels honest)
    if label != "M3_PRINT_NOT_RETURN" and rng.random() < 0.18:
        for idx in range(len(lines) - 1, 0, -1):
            m = re.match(r"^(\s*)return (.+)$", lines[idx])
            if m and len(m.group(1)) == 4:
                lines.insert(idx, f'{m.group(1)}print("debug", {m.group(2)})')
                break
    # unused helper variable / comment / docstring
    if rng.random() < 0.2:
        lines.insert(1, "    # TODO: check this")
    if rng.random() < 0.12:
        lines.insert(1, '    """Solve the task."""')
    if rng.random() < 0.15:
        lines.insert(1, "    unused = 0")
    out = "\n".join(lines)
    if rng.random() < 0.15:
        out = out.replace("    ", "  ")
    return out + "\n"


def build(seed=7, per_template=14):
    rng = random.Random(seed)
    problems = load_problems()
    rows, seen, dropped = [], set(), Counter()
    for pid, by_label in TEMPLATES.items():
        prob = problems[pid]
        for label, codes in by_label.items():
            for tmpl in codes:
                made = 0
                for attempt in range(per_template * 3):
                    if made >= per_template:
                        break
                    code = render(tmpl, rng)
                    if code is None:
                        continue
                    code = augment(code, rng, label)
                    key = (pid, label, re.sub(r"\s+", "", code))
                    if key in seen:
                        continue
                    seen.add(key)
                    res = run_submission(code, prob)
                    if res["status"] != "ok":
                        dropped[(pid, label, res.get("error", res["status"]))] += 1
                        continue
                    passed = all(t["ok"] for t in res["tests"])
                    if (label == "CORRECT") != passed:
                        dropped[(pid, label, "label/behaviour mismatch")] += 1
                        continue
                    f = featurize(code, prob, res)
                    rows.append(dict(problem=pid, label=label, code=code, **f))
                    made += 1
    # OTHER_BUG: mutated correct programs that fail tests but look like none of M1..M8, balanced to a typical class size
    sizes = sorted(Counter(r["label"] for r in rows if r["label"].startswith("M")).values())
    other, ops = other_bug_rows(rng, problems, TEMPLATES, render, target=sizes[len(sizes) // 2])
    rows += other
    dropped[("*", "OTHER_BUG", "kept per mutation operator: " + ", ".join(f"{k}={v}" for k, v in sorted(ops.items())))] = len(other)
    return rows, dropped


def main():
    DATA.mkdir(exist_ok=True)
    rows, dropped = build()
    with open(DATA / "dataset.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"{len(rows)} samples; label counts:", dict(Counter(r["label"] for r in rows)))
    if dropped:
        print("DROPPED (template bugs / label mismatches):")
        for k, v in dropped.items():
            print("  ", k, v)


if __name__ == "__main__":
    main()
