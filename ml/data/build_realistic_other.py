"""Builds ml/data/realistic_other.csv: 10 hand-written WRONG-FORMULA snippets - real bugs that are none of the 8
misconceptions (label OTHER_BUG). Evaluated separately (ml/realistic_eval.py), never used for training or tuning.
Each snippet must run and fail at least one test (checked here)."""
import csv, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from relearn_ml.execute import run_submission  # noqa: E402
from relearn_ml.problems import load_problems  # noqa: E402

S = [
    ("sum_to_n", "squares n instead of adding 1..n", "def sum_to_n(n):\n    return n * n\n"),
    ("average", "divides by one too many", "def average(nums):\n    total = 0\n    for x in nums:\n        total += x\n    return total / (len(nums) + 1)\n"),
    ("celsius_to_f", "fraction upside down", "def celsius_to_f(c):\n    return c * 5 / 9 + 32\n"),
    ("percentage", "part and whole swapped", "def percentage(part, whole):\n    return whole / part * 100\n"),
    ("square", "doubles instead of squaring", "def square(n):\n    result = n * 2\n    return result\n"),
    ("is_even", "tests for odd", "def is_even(n):\n    return n % 2 == 1\n"),
    ("count_evens", "counts the odd numbers", "def count_evens(nums):\n    count = 0\n    for x in nums:\n        if x % 2 == 1:\n            count += 1\n    return count\n"),
    ("product", "adds instead of multiplying", "def product(nums):\n    p = 1\n    for x in nums:\n        p = p + x\n    return p\n"),
    ("greet", "missing comma in the text", "def greet(name):\n    return 'Hello ' + name + '!'\n"),
    ("multiples", "makes n multiples instead of stopping at n", "def multiples(k, n):\n    out = []\n    for i in range(1, n + 1):\n        out.append(k * i)\n    return out\n"),
]


def main():
    problems = load_problems()
    for pid, note, code in S:
        res = run_submission(code, problems[pid])
        assert res["status"] == "ok" and not all(t["ok"] for t in res["tests"]), (pid, note, "must run and fail at least one test")
    with open(HERE / "realistic_other.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "problem_id", "label", "note", "code"])
        for n, (pid, note, code) in enumerate(S, 1):
            w.writerow([f"O{n:02d}", pid, "OTHER_BUG", note, code])
    print(f"wrote {len(S)} OTHER_BUG snippets")


if __name__ == "__main__":
    main()
