"""Generates problems.json (single source of truth for training, server and client)."""
import json, pathlib

def P(id, fn, title, prompt, params, tests, tags, ptypes, rtype, **checks):
    starter = f"def {fn}({', '.join(params)}):\n    # your code here\n    pass\n"
    return dict(id=id, fn=fn, title=title, prompt=prompt, params=params, starter=starter,
                tests=[dict(args=a, expected=e) for a, e in tests], tags=tags,
                param_types=ptypes, return_type=rtype, checks=checks)

L = lambda *a: list(a)
problems = [
 P("sum_to_n","sum_to_n","Sum 1 to n","Return the sum of all integers from 1 up to **and including** `n`.",["n"],
   [([1],1),([5],15),([10],55),([3],6)],["M1","M3","M4","M5"],["int"],"int"),
 P("one_to_n","one_to_n","List 1..n","Return a list containing 1, 2, ..., n (including `n`).",["n"],
   [([1],[1]),([4],[1,2,3,4]),([6],[1,2,3,4,5,6])],["M1","M3","M4","M5"],["int"],"list"),
 P("multiples","multiples","Multiples up to n","Return a list of the multiples of `k` that are less than or equal to `n`, in order.",["k","n"],
   [([3,10],[3,6,9]),([5,25],[5,10,15,20,25]),([2,2],[2]),([4,16],[4,8,12,16])],["M1","M3","M4","M5"],["int","int"],"list"),
 P("sum_list","sum_list","Sum a list","Return the sum of all numbers in the list `nums` (0 for an empty list). Do not use `sum()`.",["nums"],
   [([[1,2,3]],6),([[5]],5),([[4,0,7,1]],12),([[10,20]],30),([[]],0)],["M1","M2","M3","M4","M5"],["list"],"int"),
 P("last_item","last_item","Last item","Return the last element of the non-empty list `items`.",["items"],
   [([[1,2,3]],3),([["a","b"]],"b"),([[7]],7)],["M2","M3"],["list"],"any"),
 P("nth_item","nth_item","The n-th item","Return the n-th item of `items`, counting from 1 (so `n=1` is the first item).",["items","n"],
   [([[10,20,30],1],10),([[10,20,30],3],30),([["a","b","c","d"],2],"b")],["M2","M3"],["list","int"],"any"),
 P("swap_ends","swap_ends","Swap the ends","Return a NEW list where the first and last items of `items` are swapped. Do not change the original list.",["items"],
   [([[1,2,3]],[3,2,1]),([[1,2,3,4]],[4,2,3,1]),([[5,6]],[6,5])],["M2","M3","M8"],["list"],"list",no_mutate=True),
 P("square","square","Square it","Return `n` squared.",["n"],
   [([3],9),([-4],16),([0],0)],["M3"],["int"],"int"),
 P("is_even","is_even","Is it even?","Return `True` if `n` is even, otherwise `False`.",["n"],
   [([4],True),([7],False),([0],True)],["M3"],["int"],"bool"),
 P("greet","greet","Greeting","Return the string `Hello, <name>!` for the given `name`.",["name"],
   [(["Ada"],"Hello, Ada!"),(["Sam"],"Hello, Sam!")],["M3"],["str"],"str"),
 P("count_evens","count_evens","Count evens","Return how many even numbers are in `nums`.",["nums"],
   [([[1,2,3,4]],2),([[2]],1),([[1,3]],0),([[2,4,6]],3),([[]],0)],["M1","M2","M3","M4","M5"],["list"],"int"),
 P("product","product","Product of a list","Return the product of all numbers in `nums` (1 for an empty list).",["nums"],
   [([[2,3,4]],24),([[5]],5),([[1,2,3,4]],24),([[]],1)],["M1","M2","M3","M4","M5"],["list"],"int"),
 P("contains_negative","contains_negative","Any negatives?","Return `True` if `nums` contains at least one negative number, else `False`.",["nums"],
   [([[1,-2,3]],True),([[1,2,3]],False),([[-1]],True),([[]],False),([[1,2,-3]],True)],["M1","M2","M3","M5"],["list"],"bool"),
 P("average","average","Average","Return the average (mean) of the non-empty list `nums`, including any fractional part.",["nums"],
   [([[1,2]],1.5),([[2,4,6]],4.0),([[1,2,4]],7/3),([[3,3,4,4]],3.5)],["M1","M3","M4","M5","M6"],["list"],"float"),
 P("percentage","percentage","Percentage","Return `part` as a percentage of `whole` (e.g. 1 of 4 is 25.0).",["part","whole"],
   [([1,4],25.0),([1,3],100/3),([3,8],37.5)],["M3","M6"],["int","int"],"float"),
 P("celsius_to_f","celsius_to_f","C to F","Convert Celsius `c` to Fahrenheit: F = C * 9/5 + 32.",["c"],
   [([100],212.0),([37],98.6),([0],32.0),([-40],-40.0)],["M3","M6"],["int"],"float"),
 P("capitalize_first","capitalize_first","Capitalize first letter","Return `s` with its first letter upper-cased (`'hello'` -> `'Hello'`).",["s"],
   [(["hello"],"Hello"),(["a"],"A"),(["python"],"Python")],["M3","M7"],["str"],"str"),
 P("replace_at","replace_at","Replace one character","Return a new string equal to `s` but with the character at index `i` replaced by `ch`.",["s","i","ch"],
   [(["cat",0,"b"],"bat"),(["hello",4,"y"],"helly"),(["dog",1,"u"],"dug")],["M3","M7"],["str","int","str"],"str"),
 P("shout","shout","Shout","Return `s` in upper case followed by an exclamation mark (`'hi'` -> `'HI!'`).",["s"],
   [(["hi"],"HI!"),(["wow"],"WOW!")],["M3","M7"],["str"],"str"),
 P("append_copy","append_copy","Append to a copy","Return a NEW list made of `lst` followed by `x`. The original `lst` must stay unchanged.",["lst","x"],
   [([[1,2],3],[1,2,3]),([[],"a"],["a"]),([[9],9],[9,9])],["M3","M8"],["list","any"],"list",no_mutate=True),
 P("double_all","double_all","Double everything","Return a NEW list with every number in `lst` doubled. The original `lst` must stay unchanged.",["lst"],
   [([[1,2,3]],[2,4,6]),([[5]],[10]),([[0,-1]],[0,-2])],["M1","M2","M3","M8"],["list"],"list",no_mutate=True),
 P("make_grid","make_grid","Make a grid","Return a `rows` x `cols` grid (list of lists) filled with 0. Changing one cell must not change any other cell.",["rows","cols"],
   [([2,3],[[0,0,0],[0,0,0]]),([3,1],[[0],[0],[0]]),([2,2],[[0,0],[0,0]])],["M1","M3","M8"],["int","int"],"list",independent_rows=True),
]
pathlib.Path(__file__).with_name("problems.json").write_text(json.dumps(problems, indent=1))
print(len(problems), "problems")
