"""Builds ml/data/realistic_test.csv: 40 hand-written, messier snippets that do NOT come from templates.py.

Written independently of the model and never used for training or model selection. Labels are the learner's
*intended* misconception (primary cause); `python build_realistic_test.py` additionally checks each label by
execution (CORRECT must pass every test, a misconception sample must fail at least one) and refuses to write a
CSV with an inconsistent label.
"""
import csv, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from relearn_ml.execute import run_submission  # noqa: E402
from relearn_ml.problems import load_problems  # noqa: E402

C, M1, M2, M3, M4, M5, M6, M7, M8 = ("CORRECT", "M1_RANGE_OFF_BY_ONE", "M2_INDEX_FROM_ONE", "M3_PRINT_NOT_RETURN",
                                      "M4_ACCUMULATOR_RESET", "M5_RETURN_IN_LOOP", "M6_FLOAT_DIVISION",
                                      "M7_STRING_MUTABLE", "M8_LIST_ALIASING")

# (problem_id, label, note, code)
S = [
# ---------------------------------------------------------------- CORRECT (9)
("sum_list", C, "enumerate + debug print, still returns", '''def sum_list(nums):
    s = 0
    for idx, n in enumerate(nums):
        print("adding", idx, n)  # debug
        s = s + n
    return s
'''),
("count_evens", C, "nested helper function", '''def count_evens(numbers):
    # helper
    def is_ev(k):
        return k % 2 == 0
    c = 0
    for k in numbers:
        if is_ev(k):
            c += 1
    return c
'''),
("average", C, "empty-list guard, float()", '''def average(nums):
    if len(nums) == 0:
        return 0
    return float(sum(nums)) / len(nums)
'''),
("contains_negative", C, "any() with generator", '''def contains_negative(nums):
    return any(n < 0 for n in nums)
'''),
("append_copy", C, "extend into a fresh list", '''def append_copy(lst, x):
    result = []
    result.extend(lst)
    result.append(x)
    return result
'''),
("make_grid", C, "while loop + comprehension rows", '''def make_grid(rows, cols):
    g = []
    r = 0
    while r < rows:
        g.append([0 for _ in range(cols)])
        r += 1
    return g
'''),
("sum_to_n", C, "recursion", '''def sum_to_n(n):
    if n <= 0:
        return 0
    return n + sum_to_n(n - 1)
'''),
("capitalize_first", C, "guard + slicing", '''def capitalize_first(s):
    if not s:
        return s
    return s[:1].upper() + s[1:]
'''),
("nth_item", C, "converts to 0-based, prints AND returns", '''def nth_item(items, n):
    idx = n - 1   # python is 0-based
    print("getting", idx)
    return items[idx]
'''),
# ---------------------------------------------------------------- M1 range off by one (4)
("sum_to_n", M1, "comment claims inclusive; range(1, n)", '''def sum_to_n(n):
    answer = 0
    for num in range(1, n):   # numbers from 1 to n
        answer += num
    return answer
'''),
("one_to_n", M1, "while with <, odd names", '''def one_to_n(n):
    out = list()
    count = 1
    while count < n:
        out.append(count)
        count += 1
    return out
'''),
("multiples", M1, "comprehension, n // k excludes last multiple", '''def multiples(k, n):
    return [k * i for i in range(1, n // k)]
'''),
("count_evens", M1, "bound computed in a variable (len - 1)", '''def count_evens(nums):
    n_even = 0
    last = len(nums) - 1
    for i in range(last):
        if nums[i] % 2 == 0:
            n_even += 1
    return n_even
'''),
# ---------------------------------------------------------------- M2 index from one (4)
("last_item", M2, "position = len, extra print before the crash", '''def last_item(items):
    # last = position len
    pos = len(items)
    print("last position is", pos)
    return items[pos]
'''),
("nth_item", M2, "items[n] with try/except fallback", '''def nth_item(items, n):
    try:
        return items[n]
    except IndexError:
        return items[-1]
'''),
("sum_list", M2, "while starting at 1", '''def sum_list(numbers):
    total = 0
    i = 1
    while i < len(numbers):
        total += numbers[i]
        i += 1
    return total
'''),
("product", M2, "enumerate(start=1) used as an index", '''def product(nums):
    result = 1
    for i, x in enumerate(nums, 1):
        result *= nums[i]   # i is the position, starting from 1
    return result
'''),
# ---------------------------------------------------------------- M3 print not return (4)
("is_even", M3, "prints strings, returns nothing", '''def is_even(n):
    remainder = n % 2
    if remainder == 0:
        print("True")
    else:
        print("False")
'''),
("greet", M3, ".format + print", '''def greet(name):
    message = "Hello, {}!".format(name)
    print(message)
'''),
("sum_list", M3, "prints running totals, never returns", '''def sum_list(nums):
    t = 0
    for n in nums:
        t += n
        print(t)
'''),
("square", M3, "print with label and explicit return None", '''def square(n):
    print("square is", n ** 2)
    return None
'''),
# ---------------------------------------------------------------- M4 accumulator reset (4)
("count_evens", M4, "while loop, counter reset every pass", '''def count_evens(nums):
    i = 0
    while i < len(nums):
        found = 0
        if nums[i] % 2 == 0:
            found += 1
        i += 1
    return found
'''),
("average", M4, "reset inside loop, then divides", '''def average(nums):
    for n in nums:
        total = 0
        total += n
    return total / len(nums)
'''),
("sum_list", M4, "reset + debug print each pass", '''def sum_list(numbers):
    for v in numbers:
        subtotal = 0
        subtotal += v
        print("subtotal", subtotal)
    return subtotal
'''),
("sum_to_n", M4, "while loop, s = 0 inside", '''def sum_to_n(n):
    i = 1
    while i <= n:
        s = 0
        s = s + i
        i += 1
    return s
'''),
# ---------------------------------------------------------------- M5 return in loop (4)
("contains_negative", M5, "result flag returned inside the loop", '''def contains_negative(nums):
    result = False
    for n in nums:
        if n < 0:
            result = True
        return result
'''),
("product", M5, "return in loop with debug print", '''def product(nums):
    p = 1
    for n in nums:
        p = p * n
        print("running product", p)
        return p
'''),
("count_evens", M5, "return directly in while body", '''def count_evens(nums):
    count = 0
    i = 0
    while i < len(nums):
        if nums[i] % 2 == 0:
            count = count + 1
        i = i + 1
        return count
    return count
'''),
("sum_list", M5, "return in loop plus unreachable fallback", '''def sum_list(nums):
    total = 0
    for n in nums:
        total += n
        return total
    return 0
'''),
# ---------------------------------------------------------------- M6 float division (4)
("average", M6, "round() around a floor division", '''def average(nums):
    return round(sum(nums) // len(nums), 2)
'''),
("percentage", M6, "floors after scaling", '''def percentage(part, whole):
    pct = (part * 100) // whole
    return pct
'''),
("celsius_to_f", M6, "int() truncates the fraction", '''def celsius_to_f(c):
    f = c * 9 / 5 + 32
    return int(f)
'''),
("average", M6, "loop with counters, floor division, debug print", '''def average(nums):
    total = 0
    count = 0
    for n in nums:
        total += n
        count += 1
    print("total", total, "count", count)
    return total // count
'''),
# ---------------------------------------------------------------- M7 string mutable (3)
("capitalize_first", M7, "upper() on a copy of the first letter, result dropped", '''def capitalize_first(word):
    first = word[0]
    first.upper()
    return first + word[1:]
'''),
("replace_at", M7, "item assignment on a string alias", '''def replace_at(s, i, ch):
    chars = s
    chars[i] = ch
    return "".join(chars)
'''),
("shout", M7, "upper() result dropped", '''def shout(s):
    s = s + "!"
    s.upper()
    return s
'''),
# ---------------------------------------------------------------- M8 list aliasing (4)
("append_copy", M8, "alias + insert, returns the alias", '''def append_copy(lst, x):
    copy = lst
    copy.insert(len(copy), x)
    return copy
'''),
("make_grid", M8, "one row object appended repeatedly", '''def make_grid(rows, cols):
    grid = []
    row = []
    for c in range(cols):
        row.append(0)
    for r in range(rows):
        grid.append(row)
    return grid
'''),
("double_all", M8, "result is an alias; doubles the input in place", '''def double_all(lst):
    result = lst
    i = 0
    for item in lst:
        result[i] = item * 2
        i += 1
    return result
'''),
("swap_ends", M8, "alias; right answer but the input is changed", '''def swap_ends(items):
    new = items
    first = new.pop(0)
    last = new.pop()
    new.insert(0, last)
    new.append(first)
    return new
'''),
]


def main():
    problems = load_problems()
    bad = []
    for n, (pid, label, note, code) in enumerate(S, 1):
        res = run_submission(code, problems[pid])
        if res["status"] != "ok":
            bad.append((n, pid, label, f"does not run: {res.get('error')}"))
            continue
        passed = all(t["ok"] for t in res["tests"])
        if (label == "CORRECT") != passed:
            bad.append((n, pid, label, f"label/behaviour mismatch (passes all tests: {passed})"))
    if bad:
        for b in bad:
            print("LABEL PROBLEM:", b)
        sys.exit(1)
    with open(HERE / "realistic_test.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "problem_id", "label", "note", "code"])
        for n, (pid, label, note, code) in enumerate(S, 1):
            w.writerow([f"R{n:02d}", pid, label, note, code])
    from collections import Counter
    print(f"wrote {len(S)} samples:", dict(Counter(s[1] for s in S)))


if __name__ == "__main__":
    main()
