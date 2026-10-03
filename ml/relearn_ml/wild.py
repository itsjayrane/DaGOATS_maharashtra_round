"""Hand-written, student-style snippets that are NOT produced by templates.py (different structure/style).
Used only as an out-of-template sanity check (never for training). Labels are execution-checked in evaluate."""

WILD = [
 # --- CORRECT
 ("sum_list", "CORRECT", "def sum_list(nums):\n    answer = 0\n    for n in nums:\n        answer = answer + n\n    print('done')\n    return answer\n"),
 ("count_evens", "CORRECT", "def count_evens(nums):\n    # count them\n    evens = 0\n    idx = 0\n    for idx in range(0, len(nums)):\n        if nums[idx] % 2 == 0: evens = evens + 1\n    return evens\n"),
 ("append_copy", "CORRECT", "def append_copy(lst, x):\n    new = []\n    for item in lst:\n        new.append(item)\n    new.append(x)\n    return new\n"),
 ("average", "CORRECT", "def average(nums):\n    s = 0.0\n    for v in nums:\n        s += v\n    return s / len(nums)\n"),
 ("contains_negative", "CORRECT", "def contains_negative(nums):\n    for v in nums:\n        if v < 0:\n            return True\n    return False\n"),
 ("sum_to_n", "CORRECT", "def sum_to_n(n):\n    total = 0\n    for k in range(n):\n        total += k + 1\n    return total\n"),
 # --- M1
 ("sum_to_n", "M1_RANGE_OFF_BY_ONE", "def sum_to_n(n):\n    s = 0\n    for number in range(1, n):\n        s = s + number\n    return s\n"),
 ("count_evens", "M1_RANGE_OFF_BY_ONE", "def count_evens(nums):\n    c = 0\n    for i in range(len(nums) - 1):\n        if nums[i] % 2 == 0:\n            c = c + 1\n    return c\n"),
 ("multiples", "M1_RANGE_OFF_BY_ONE", "def multiples(k, n):\n    out = []\n    cur = k\n    while cur < n:\n        out.append(cur)\n        cur = cur + k\n    return out\n"),
 ("one_to_n", "M1_RANGE_OFF_BY_ONE", "def one_to_n(n):\n    return [v for v in range(1, n)]\n"),
 # --- M2
 ("last_item", "M2_INDEX_FROM_ONE", "def last_item(items):\n    length = len(items)\n    return items[length]\n"),
 ("sum_list", "M2_INDEX_FROM_ONE", "def sum_list(numbers):\n    total = 0\n    for idx in range(1, len(numbers)):\n        total += numbers[idx]\n    return total\n"),
 ("nth_item", "M2_INDEX_FROM_ONE", "def nth_item(items, n):\n    return items[n]\n"),
 ("product", "M2_INDEX_FROM_ONE", "def product(nums):\n    p = 1\n    for i in range(1, len(nums)):\n        p = p * nums[i]\n    return p\n"),
 # --- M3
 ("square", "M3_PRINT_NOT_RETURN", "def square(n):\n    result = n * n\n    print(result)\n"),
 ("greet", "M3_PRINT_NOT_RETURN", "def greet(name):\n    print('Hello, ' + name + '!')\n"),
 ("sum_list", "M3_PRINT_NOT_RETURN", "def sum_list(nums):\n    t = 0\n    for n in nums:\n        t += n\n    print('The sum is', t)\n"),
 ("is_even", "M3_PRINT_NOT_RETURN", "def is_even(n):\n    if n % 2 == 0:\n        print('True')\n    else:\n        print('False')\n"),
 # --- M4
 ("sum_list", "M4_ACCUMULATOR_RESET", "def sum_list(nums):\n    for n in nums:\n        total = 0\n        total = total + n\n    return total\n"),
 ("count_evens", "M4_ACCUMULATOR_RESET", "def count_evens(nums):\n    for n in nums:\n        count = 0\n        if n % 2 == 0:\n            count += 1\n    return count\n"),
 ("product", "M4_ACCUMULATOR_RESET", "def product(nums):\n    for x in nums:\n        res = 1\n        res = res * x\n    return res\n"),
 # --- M5
 ("sum_list", "M5_RETURN_IN_LOOP", "def sum_list(nums):\n    total = 0\n    for n in nums:\n        total = total + n\n        return total\n"),
 ("contains_negative", "M5_RETURN_IN_LOOP", "def contains_negative(nums):\n    for n in nums:\n        if n < 0:\n            return True\n        return False\n"),
 ("product", "M5_RETURN_IN_LOOP", "def product(nums):\n    res = 1\n    for x in nums:\n        res *= x\n        return res\n"),
 # --- M6
 ("average", "M6_FLOAT_DIVISION", "def average(nums):\n    total = 0\n    for n in nums:\n        total += n\n    avg = total // len(nums)\n    return avg\n"),
 ("percentage", "M6_FLOAT_DIVISION", "def percentage(part, whole):\n    frac = part // whole\n    return frac * 100\n"),
 ("celsius_to_f", "M6_FLOAT_DIVISION", "def celsius_to_f(c):\n    return c * (9 // 5) + 32\n"),
 # --- M7
 ("capitalize_first", "M7_STRING_MUTABLE", "def capitalize_first(word):\n    word[0] = word[0].upper()\n    return word\n"),
 ("shout", "M7_STRING_MUTABLE", "def shout(text):\n    text.upper()\n    return text + '!'\n"),
 ("replace_at", "M7_STRING_MUTABLE", "def replace_at(s, i, ch):\n    s[i] = ch\n    return s\n"),
 # --- M8
 ("append_copy", "M8_LIST_ALIASING", "def append_copy(lst, x):\n    other = lst\n    other.append(x)\n    return other\n"),
 ("double_all", "M8_LIST_ALIASING", "def double_all(lst):\n    doubled = lst\n    for i in range(len(doubled)):\n        doubled[i] = doubled[i] * 2\n    return doubled\n"),
 ("make_grid", "M8_LIST_ALIASING", "def make_grid(rows, cols):\n    line = [0] * cols\n    board = []\n    for r in range(rows):\n        board.append(line)\n    return board\n"),
 ("swap_ends", "M8_LIST_ALIASING", "def swap_ends(items):\n    new_items = items\n    new_items[0], new_items[-1] = new_items[-1], new_items[0]\n    return new_items\n"),
]
