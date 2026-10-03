"""Hand-authored solution templates per (problem, label). `$name` placeholders are renamed at generation time.
Every wrong template is *validated by execution* in generate.py: it must fail >=1 test; every CORRECT one must pass all."""

C, M1, M2, M3, M4, M5, M6, M7, M8 = ("CORRECT", "M1_RANGE_OFF_BY_ONE", "M2_INDEX_FROM_ONE", "M3_PRINT_NOT_RETURN",
                                      "M4_ACCUMULATOR_RESET", "M5_RETURN_IN_LOOP", "M6_FLOAT_DIVISION",
                                      "M7_STRING_MUTABLE", "M8_LIST_ALIASING")

TEMPLATES = {
"sum_to_n": {
 C: ["""def sum_to_n($n):
    $tot = 0
    for $i in range(1, $n + 1):
        $tot += $i
    return $tot""",
     """def sum_to_n($n):
    $tot = 0
    $i = 1
    while $i <= $n:
        $tot += $i
        $i += 1
    return $tot""",
     """def sum_to_n($n):
    return $n * ($n + 1) // 2""",
     """def sum_to_n($n):
    $tot = 0
    for $i in range($n + 1):
        $tot = $tot + $i
    return $tot"""],
 M1: ["""def sum_to_n($n):
    $tot = 0
    for $i in range(1, $n):
        $tot += $i
    return $tot""",
      """def sum_to_n($n):
    $tot = 0
    for $i in range($n):
        $tot += $i
    return $tot""",
      """def sum_to_n($n):
    $tot = 0
    $i = 1
    while $i < $n:
        $tot += $i
        $i += 1
    return $tot"""],
 M3: ["""def sum_to_n($n):
    $tot = 0
    for $i in range(1, $n + 1):
        $tot += $i
    print($tot)""",
      """def sum_to_n($n):
    $tot = 0
    $i = 1
    while $i <= $n:
        $tot += $i
        $i += 1
    print("Sum is", $tot)"""],
 M4: ["""def sum_to_n($n):
    for $i in range(1, $n + 1):
        $tot = 0
        $tot += $i
    return $tot""",
      """def sum_to_n($n):
    $i = 1
    while $i <= $n:
        $tot = 0
        $tot = $tot + $i
        $i += 1
    return $tot"""],
 M5: ["""def sum_to_n($n):
    $tot = 0
    for $i in range(1, $n + 1):
        $tot += $i
        return $tot""",
      """def sum_to_n($n):
    $tot = 0
    $i = 1
    while $i <= $n:
        $tot += $i
        $i += 1
        return $tot"""],
},
"one_to_n": {
 C: ["""def one_to_n($n):
    $res = []
    for $i in range(1, $n + 1):
        $res.append($i)
    return $res""",
     """def one_to_n($n):
    return list(range(1, $n + 1))""",
     """def one_to_n($n):
    return [$i for $i in range(1, $n + 1)]""",
     """def one_to_n($n):
    $res = []
    $i = 1
    while $i <= $n:
        $res.append($i)
        $i += 1
    return $res"""],
 M1: ["""def one_to_n($n):
    $res = []
    for $i in range(1, $n):
        $res.append($i)
    return $res""",
      """def one_to_n($n):
    return list(range(1, $n))""",
      """def one_to_n($n):
    return [$i for $i in range($n)]""",
      """def one_to_n($n):
    $res = []
    $i = 1
    while $i < $n:
        $res.append($i)
        $i += 1
    return $res"""],
 M3: ["""def one_to_n($n):
    $res = []
    for $i in range(1, $n + 1):
        $res.append($i)
    print($res)""",
      """def one_to_n($n):
    print(list(range(1, $n + 1)))"""],
 M4: ["""def one_to_n($n):
    for $i in range(1, $n + 1):
        $res = []
        $res.append($i)
    return $res"""],
 M5: ["""def one_to_n($n):
    $res = []
    for $i in range(1, $n + 1):
        $res.append($i)
        return $res"""],
},
"multiples": {
 C: ["""def multiples($k, $n):
    $res = []
    for $i in range($k, $n + 1, $k):
        $res.append($i)
    return $res""",
     """def multiples($k, $n):
    return [$i for $i in range($k, $n + 1, $k)]""",
     """def multiples($k, $n):
    $res = []
    $m = $k
    while $m <= $n:
        $res.append($m)
        $m += $k
    return $res""",
     """def multiples($k, $n):
    $res = []
    for $i in range(1, $n + 1):
        if $i % $k == 0:
            $res.append($i)
    return $res"""],
 M1: ["""def multiples($k, $n):
    $res = []
    for $i in range($k, $n, $k):
        $res.append($i)
    return $res""",
      """def multiples($k, $n):
    return [$i for $i in range($k, $n, $k)]""",
      """def multiples($k, $n):
    $res = []
    $m = $k
    while $m < $n:
        $res.append($m)
        $m += $k
    return $res""",
      """def multiples($k, $n):
    $res = []
    for $i in range(1, $n):
        if $i % $k == 0:
            $res.append($i)
    return $res"""],
 M3: ["""def multiples($k, $n):
    $res = []
    for $i in range($k, $n + 1, $k):
        $res.append($i)
    print($res)"""],
 M4: ["""def multiples($k, $n):
    for $i in range($k, $n + 1, $k):
        $res = []
        $res.append($i)
    return $res"""],
 M5: ["""def multiples($k, $n):
    $res = []
    for $i in range($k, $n + 1, $k):
        $res.append($i)
        return $res"""],
},
"sum_list": {
 C: ["""def sum_list($nums):
    $tot = 0
    for $x in $nums:
        $tot += $x
    return $tot""",
     """def sum_list($nums):
    $tot = 0
    for $i in range(len($nums)):
        $tot += $nums[$i]
    return $tot""",
     """def sum_list($nums):
    $tot = 0
    $i = 0
    while $i < len($nums):
        $tot = $tot + $nums[$i]
        $i += 1
    return $tot""",
     """def sum_list($nums):
    $tot = 0
    for $i in range(0, len($nums)):
        $tot += $nums[$i]
    return $tot"""],
 M1: ["""def sum_list($nums):
    $tot = 0
    for $i in range(len($nums) - 1):
        $tot += $nums[$i]
    return $tot""",
      """def sum_list($nums):
    $tot = 0
    $i = 0
    while $i < len($nums) - 1:
        $tot += $nums[$i]
        $i += 1
    return $tot""",
      """def sum_list($nums):
    $tot = 0
    for $i in range(0, len($nums) - 1):
        $tot = $tot + $nums[$i]
    return $tot"""],
 M2: ["""def sum_list($nums):
    $tot = 0
    for $i in range(1, len($nums)):
        $tot += $nums[$i]
    return $tot""",
      """def sum_list($nums):
    $tot = 0
    for $i in range(1, len($nums) + 1):
        $tot += $nums[$i]
    return $tot""",
      """def sum_list($nums):
    $tot = 0
    $i = 1
    while $i <= len($nums):
        $tot += $nums[$i]
        $i += 1
    return $tot"""],
 M3: ["""def sum_list($nums):
    $tot = 0
    for $x in $nums:
        $tot += $x
    print($tot)""",
      """def sum_list($nums):
    $tot = 0
    for $i in range(len($nums)):
        $tot += $nums[$i]
    print("total:", $tot)"""],
 M4: ["""def sum_list($nums):
    for $x in $nums:
        $tot = 0
        $tot += $x
    return $tot""",
      """def sum_list($nums):
    for $i in range(len($nums)):
        $tot = 0
        $tot = $tot + $nums[$i]
    return $tot""",
      """def sum_list($nums):
    $i = 0
    while $i < len($nums):
        $tot = 0
        $tot += $nums[$i]
        $i += 1
    return $tot"""],
 M5: ["""def sum_list($nums):
    $tot = 0
    for $x in $nums:
        $tot += $x
        return $tot""",
      """def sum_list($nums):
    $tot = 0
    for $i in range(len($nums)):
        $tot = $tot + $nums[$i]
        return $tot""",
      """def sum_list($nums):
    $tot = 0
    $i = 0
    while $i < len($nums):
        $tot += $nums[$i]
        $i += 1
        return $tot"""],
},
"last_item": {
 C: ["""def last_item($items):
    return $items[-1]""",
     """def last_item($items):
    return $items[len($items) - 1]""",
     """def last_item($items):
    $n = len($items)
    return $items[$n - 1]""",
     """def last_item($items):
    for $x in $items:
        $last = $x
    return $last"""],
 M2: ["""def last_item($items):
    return $items[len($items)]""",
      """def last_item($items):
    $n = len($items)
    return $items[$n]""",
      """def last_item($items):
    $i = len($items)
    $last = $items[$i]
    return $last"""],
 M3: ["""def last_item($items):
    print($items[-1])""",
      """def last_item($items):
    print($items[len($items) - 1])"""],
},
"nth_item": {
 C: ["""def nth_item($items, $n):
    return $items[$n - 1]""",
     """def nth_item($items, $n):
    $i = $n - 1
    return $items[$i]""",
     """def nth_item($items, $n):
    $c = 1
    for $x in $items:
        if $c == $n:
            return $x
        $c += 1"""],
 M2: ["""def nth_item($items, $n):
    return $items[$n]""",
      """def nth_item($items, $n):
    $i = $n
    return $items[$i]""",
      """def nth_item($items, $n):
    $res = $items[$n]
    return $res"""],
 M3: ["""def nth_item($items, $n):
    print($items[$n - 1])""",
      """def nth_item($items, $n):
    $i = $n - 1
    print($items[$i])"""],
},
"swap_ends": {
 C: ["""def swap_ends($items):
    $res = $items[:]
    $res[0], $res[-1] = $res[-1], $res[0]
    return $res""",
     """def swap_ends($items):
    $res = list($items)
    $tmp = $res[0]
    $res[0] = $res[len($res) - 1]
    $res[len($res) - 1] = $tmp
    return $res""",
     """def swap_ends($items):
    return [$items[-1]] + $items[1:-1] + [$items[0]]"""],
 M2: ["""def swap_ends($items):
    $res = $items[:]
    $res[1], $res[-1] = $res[-1], $res[1]
    return $res""",
      """def swap_ends($items):
    $res = list($items)
    $res[1], $res[len($res)] = $res[len($res)], $res[1]
    return $res""",
      """def swap_ends($items):
    $res = $items[:]
    $tmp = $res[1]
    $res[1] = $res[len($res)]
    $res[len($res)] = $tmp
    return $res"""],
 M3: ["""def swap_ends($items):
    $res = $items[:]
    $res[0], $res[-1] = $res[-1], $res[0]
    print($res)"""],
 M8: ["""def swap_ends($items):
    $res = $items
    $res[0], $res[-1] = $res[-1], $res[0]
    return $res""",
      """def swap_ends($items):
    $res = $items
    $tmp = $res[0]
    $res[0] = $res[-1]
    $res[-1] = $tmp
    return $res""",
      """def swap_ends($items):
    $tmp = $items[0]
    $items[0] = $items[-1]
    $items[-1] = $tmp
    return $items"""],
},
"square": {
 C: ["""def square($n):
    return $n * $n""",
     """def square($n):
    return $n ** 2""",
     """def square($n):
    $r = $n * $n
    return $r"""],
 M3: ["""def square($n):
    print($n * $n)""",
      """def square($n):
    $r = $n * $n
    print($r)""",
      """def square($n):
    print($n ** 2)"""],
},
"is_even": {
 C: ["""def is_even($n):
    return $n % 2 == 0""",
     """def is_even($n):
    if $n % 2 == 0:
        return True
    return False""",
     """def is_even($n):
    if $n % 2 == 0:
        return True
    else:
        return False"""],
 M3: ["""def is_even($n):
    print($n % 2 == 0)""",
      """def is_even($n):
    if $n % 2 == 0:
        print(True)
    else:
        print(False)""",
      """def is_even($n):
    $r = $n % 2 == 0
    print($r)"""],
},
"greet": {
 C: ["""def greet($name):
    return "Hello, " + $name + "!\"""",
     """def greet($name):
    return f"Hello, {$name}!\"""",
     """def greet($name):
    $msg = "Hello, " + $name + "!"
    return $msg"""],
 M3: ["""def greet($name):
    print("Hello, " + $name + "!")""",
      """def greet($name):
    print(f"Hello, {$name}!")""",
      """def greet($name):
    $msg = "Hello, " + $name + "!"
    print($msg)"""],
},
"count_evens": {
 C: ["""def count_evens($nums):
    $cnt = 0
    for $x in $nums:
        if $x % 2 == 0:
            $cnt += 1
    return $cnt""",
     """def count_evens($nums):
    $cnt = 0
    for $i in range(len($nums)):
        if $nums[$i] % 2 == 0:
            $cnt = $cnt + 1
    return $cnt""",
     """def count_evens($nums):
    $cnt = 0
    $i = 0
    while $i < len($nums):
        if $nums[$i] % 2 == 0:
            $cnt += 1
        $i += 1
    return $cnt"""],
 M1: ["""def count_evens($nums):
    $cnt = 0
    for $i in range(len($nums) - 1):
        if $nums[$i] % 2 == 0:
            $cnt += 1
    return $cnt""",
      """def count_evens($nums):
    $cnt = 0
    $i = 0
    while $i < len($nums) - 1:
        if $nums[$i] % 2 == 0:
            $cnt += 1
        $i += 1
    return $cnt"""],
 M2: ["""def count_evens($nums):
    $cnt = 0
    for $i in range(1, len($nums)):
        if $nums[$i] % 2 == 0:
            $cnt += 1
    return $cnt""",
      """def count_evens($nums):
    $cnt = 0
    for $i in range(1, len($nums) + 1):
        if $nums[$i] % 2 == 0:
            $cnt += 1
    return $cnt"""],
 M3: ["""def count_evens($nums):
    $cnt = 0
    for $x in $nums:
        if $x % 2 == 0:
            $cnt += 1
    print($cnt)"""],
 M4: ["""def count_evens($nums):
    for $x in $nums:
        $cnt = 0
        if $x % 2 == 0:
            $cnt += 1
    return $cnt""",
      """def count_evens($nums):
    for $i in range(len($nums)):
        $cnt = 0
        if $nums[$i] % 2 == 0:
            $cnt = $cnt + 1
    return $cnt"""],
 M5: ["""def count_evens($nums):
    $cnt = 0
    for $x in $nums:
        if $x % 2 == 0:
            $cnt += 1
        return $cnt""",
      """def count_evens($nums):
    $cnt = 0
    for $x in $nums:
        if $x % 2 == 0:
            $cnt += 1
            return $cnt"""],
},
"product": {
 C: ["""def product($nums):
    $prod = 1
    for $x in $nums:
        $prod *= $x
    return $prod""",
     """def product($nums):
    $prod = 1
    for $i in range(len($nums)):
        $prod = $prod * $nums[$i]
    return $prod""",
     """def product($nums):
    $prod = 1
    $i = 0
    while $i < len($nums):
        $prod *= $nums[$i]
        $i += 1
    return $prod"""],
 M1: ["""def product($nums):
    $prod = 1
    for $i in range(len($nums) - 1):
        $prod *= $nums[$i]
    return $prod"""],
 M2: ["""def product($nums):
    $prod = 1
    for $i in range(1, len($nums)):
        $prod *= $nums[$i]
    return $prod""",
      """def product($nums):
    $prod = 1
    for $i in range(1, len($nums) + 1):
        $prod = $prod * $nums[$i]
    return $prod"""],
 M3: ["""def product($nums):
    $prod = 1
    for $x in $nums:
        $prod *= $x
    print($prod)"""],
 M4: ["""def product($nums):
    for $x in $nums:
        $prod = 1
        $prod *= $x
    return $prod""",
      """def product($nums):
    $i = 0
    while $i < len($nums):
        $prod = 1
        $prod = $prod * $nums[$i]
        $i += 1
    return $prod"""],
 M5: ["""def product($nums):
    $prod = 1
    for $x in $nums:
        $prod *= $x
        return $prod""",
      """def product($nums):
    $prod = 1
    for $i in range(len($nums)):
        $prod = $prod * $nums[$i]
        return $prod"""],
},
"contains_negative": {
 C: ["""def contains_negative($nums):
    for $x in $nums:
        if $x < 0:
            return True
    return False""",
     """def contains_negative($nums):
    for $i in range(len($nums)):
        if $nums[$i] < 0:
            return True
    return False""",
     """def contains_negative($nums):
    $found = False
    for $x in $nums:
        if $x < 0:
            $found = True
    return $found""",
     """def contains_negative($nums):
    $i = 0
    while $i < len($nums):
        if $nums[$i] < 0:
            return True
        $i += 1
    return False"""],
 M1: ["""def contains_negative($nums):
    for $i in range(len($nums) - 1):
        if $nums[$i] < 0:
            return True
    return False"""],
 M2: ["""def contains_negative($nums):
    for $i in range(1, len($nums)):
        if $nums[$i] < 0:
            return True
    return False"""],
 M3: ["""def contains_negative($nums):
    for $x in $nums:
        if $x < 0:
            print(True)
    print(False)""",
      """def contains_negative($nums):
    $found = False
    for $x in $nums:
        if $x < 0:
            $found = True
    print($found)"""],
 M5: ["""def contains_negative($nums):
    for $x in $nums:
        if $x < 0:
            return True
        else:
            return False""",
      """def contains_negative($nums):
    for $x in $nums:
        if $x >= 0:
            return False
    return True""",
      """def contains_negative($nums):
    for $i in range(len($nums)):
        if $nums[$i] < 0:
            return True
        else:
            return False"""],
},
"average": {
 C: ["""def average($nums):
    return sum($nums) / len($nums)""",
     """def average($nums):
    $tot = 0
    for $x in $nums:
        $tot += $x
    return $tot / len($nums)""",
     """def average($nums):
    $tot = 0
    for $i in range(len($nums)):
        $tot = $tot + $nums[$i]
    $avg = $tot / len($nums)
    return $avg"""],
 M1: ["""def average($nums):
    $tot = 0
    for $i in range(len($nums) - 1):
        $tot += $nums[$i]
    return $tot / len($nums)"""],
 M3: ["""def average($nums):
    print(sum($nums) / len($nums))""",
      """def average($nums):
    $tot = 0
    for $x in $nums:
        $tot += $x
    print($tot / len($nums))"""],
 M4: ["""def average($nums):
    for $x in $nums:
        $tot = 0
        $tot += $x
    return $tot / len($nums)"""],
 M5: ["""def average($nums):
    $tot = 0
    for $x in $nums:
        $tot += $x
        return $tot / len($nums)"""],
 M6: ["""def average($nums):
    return sum($nums) // len($nums)""",
      """def average($nums):
    $tot = 0
    for $x in $nums:
        $tot += $x
    return $tot // len($nums)""",
      """def average($nums):
    return int(sum($nums) / len($nums))""",
      """def average($nums):
    $tot = 0
    for $x in $nums:
        $tot += $x
    $avg = $tot // len($nums)
    return $avg"""],
},
"percentage": {
 C: ["""def percentage($part, $whole):
    return $part / $whole * 100""",
     """def percentage($part, $whole):
    return 100 * $part / $whole""",
     """def percentage($part, $whole):
    $r = $part / $whole
    return $r * 100"""],
 M3: ["""def percentage($part, $whole):
    print($part / $whole * 100)"""],
 M6: ["""def percentage($part, $whole):
    return $part // $whole * 100""",
      """def percentage($part, $whole):
    return 100 * ($part // $whole)""",
      """def percentage($part, $whole):
    $r = $part // $whole
    return $r * 100""",
      """def percentage($part, $whole):
    return int($part / $whole) * 100"""],
},
"celsius_to_f": {
 C: ["""def celsius_to_f($c):
    return $c * 9 / 5 + 32""",
     """def celsius_to_f($c):
    return $c * 1.8 + 32""",
     """def celsius_to_f($c):
    $f = ($c * 9) / 5 + 32
    return $f"""],
 M3: ["""def celsius_to_f($c):
    print($c * 9 / 5 + 32)"""],
 M6: ["""def celsius_to_f($c):
    return $c * (9 // 5) + 32""",
      """def celsius_to_f($c):
    return $c * 9 // 5 + 32""",
      """def celsius_to_f($c):
    $ratio = 9 // 5
    return $c * $ratio + 32""",
      """def celsius_to_f($c):
    return int($c * 9 / 5) + 32"""],
},
"capitalize_first": {
 C: ["""def capitalize_first($s):
    return $s[0].upper() + $s[1:]""",
     """def capitalize_first($s):
    $first = $s[0].upper()
    return $first + $s[1:]""",
     """def capitalize_first($s):
    return $s.capitalize()"""],
 M3: ["""def capitalize_first($s):
    print($s[0].upper() + $s[1:])"""],
 M7: ["""def capitalize_first($s):
    $s[0] = $s[0].upper()
    return $s""",
      """def capitalize_first($s):
    $s.capitalize()
    return $s""",
      """def capitalize_first($s):
    $s[0].upper()
    return $s""",
      """def capitalize_first($s):
    $s.upper()
    return $s"""],
},
"replace_at": {
 C: ["""def replace_at($s, $i, $ch):
    return $s[:$i] + $ch + $s[$i + 1:]""",
     """def replace_at($s, $i, $ch):
    $parts = list($s)
    $parts[$i] = $ch
    return "".join($parts)"""],
 M3: ["""def replace_at($s, $i, $ch):
    print($s[:$i] + $ch + $s[$i + 1:])"""],
 M7: ["""def replace_at($s, $i, $ch):
    $s[$i] = $ch
    return $s""",
      """def replace_at($s, $i, $ch):
    $s.replace($s[$i], $ch)
    return $s""",
      """def replace_at($s, $i, $ch):
    $s[$i] = $ch"""],
},
"shout": {
 C: ["""def shout($s):
    return $s.upper() + "!\"""",
     """def shout($s):
    $s = $s.upper()
    return $s + "!\"""",
     """def shout($s):
    $t = $s.upper()
    $t += "!"
    return $t"""],
 M3: ["""def shout($s):
    print($s.upper() + "!")"""],
 M7: ["""def shout($s):
    $s.upper()
    return $s + "!\"""",
      """def shout($s):
    $s.upper()
    $s += "!"
    return $s"""],
},
"append_copy": {
 C: ["""def append_copy($lst, $x):
    $res = $lst[:]
    $res.append($x)
    return $res""",
     """def append_copy($lst, $x):
    return $lst + [$x]""",
     """def append_copy($lst, $x):
    $res = list($lst)
    $res.append($x)
    return $res""",
     """def append_copy($lst, $x):
    $res = $lst.copy()
    $res.append($x)
    return $res"""],
 M3: ["""def append_copy($lst, $x):
    $res = $lst[:]
    $res.append($x)
    print($res)"""],
 M8: ["""def append_copy($lst, $x):
    $res = $lst
    $res.append($x)
    return $res""",
      """def append_copy($lst, $x):
    $lst.append($x)
    return $lst""",
      """def append_copy($lst, $x):
    $res = $lst
    $res += [$x]
    return $res"""],
},
"double_all": {
 C: ["""def double_all($lst):
    $res = []
    for $x in $lst:
        $res.append($x * 2)
    return $res""",
     """def double_all($lst):
    return [$x * 2 for $x in $lst]""",
     """def double_all($lst):
    $res = $lst[:]
    for $i in range(len($res)):
        $res[$i] *= 2
    return $res""",
     """def double_all($lst):
    $res = list($lst)
    for $i in range(len($lst)):
        $res[$i] = $lst[$i] * 2
    return $res"""],
 M1: ["""def double_all($lst):
    $res = $lst[:]
    for $i in range(len($res) - 1):
        $res[$i] *= 2
    return $res""",
      """def double_all($lst):
    $res = []
    for $i in range(len($lst) - 1):
        $res.append($lst[$i] * 2)
    return $res"""],
 M2: ["""def double_all($lst):
    $res = $lst[:]
    for $i in range(1, len($res)):
        $res[$i] *= 2
    return $res""",
      """def double_all($lst):
    $res = []
    for $i in range(1, len($lst) + 1):
        $res.append($lst[$i] * 2)
    return $res"""],
 M3: ["""def double_all($lst):
    $res = []
    for $x in $lst:
        $res.append($x * 2)
    print($res)"""],
 M8: ["""def double_all($lst):
    $res = $lst
    for $i in range(len($res)):
        $res[$i] *= 2
    return $res""",
      """def double_all($lst):
    $res = $lst
    for $i in range(len($lst)):
        $res[$i] = $lst[$i] * 2
    return $res""",
      """def double_all($lst):
    for $i in range(len($lst)):
        $lst[$i] = $lst[$i] * 2
    return $lst"""],
},
"make_grid": {
 C: ["""def make_grid($rows, $cols):
    $grid = []
    for $i in range($rows):
        $grid.append([0] * $cols)
    return $grid""",
     """def make_grid($rows, $cols):
    return [[0] * $cols for $i in range($rows)]""",
     """def make_grid($rows, $cols):
    $grid = []
    for $i in range($rows):
        $row = [0] * $cols
        $grid.append($row)
    return $grid""",
     """def make_grid($rows, $cols):
    $grid = []
    for $i in range($rows):
        $row = []
        for $j in range($cols):
            $row.append(0)
        $grid.append($row)
    return $grid"""],
 M1: ["""def make_grid($rows, $cols):
    $grid = []
    for $i in range($rows - 1):
        $grid.append([0] * $cols)
    return $grid""",
      """def make_grid($rows, $cols):
    return [[0] * ($cols - 1) for $i in range($rows)]"""],
 M3: ["""def make_grid($rows, $cols):
    $grid = [[0] * $cols for $i in range($rows)]
    print($grid)"""],
 M8: ["""def make_grid($rows, $cols):
    return [[0] * $cols] * $rows""",
      """def make_grid($rows, $cols):
    $row = [0] * $cols
    $grid = []
    for $i in range($rows):
        $grid.append($row)
    return $grid""",
      """def make_grid($rows, $cols):
    $row = [0] * $cols
    return [$row] * $rows""",
      """def make_grid($rows, $cols):
    $grid = [[0] * $cols]
    $grid = $grid * $rows
    return $grid"""],
},
}
