export const MISC = [
  ['M1_RANGE_OFF_BY_ONE', 'M1', 'range() stops before its end'],
  ['M2_INDEX_FROM_ONE', 'M2', 'List indexes start at 0'],
  ['M3_PRINT_NOT_RETURN', 'M3', 'print is not return'],
  ['M4_ACCUMULATOR_RESET', 'M4', 'Accumulator reset in loop'],
  ['M5_RETURN_IN_LOOP', 'M5', 'return exits on first pass'],
  ['M6_FLOAT_DIVISION', 'M6', '// drops the decimals'],
  ['M7_STRING_MUTABLE', 'M7', 'Strings are immutable'],
  ['M8_LIST_ALIASING', 'M8', 'b = a does not copy'],
]
export const short = (l) => (l === 'CORRECT' ? 'OK' : l === 'OTHER_BUG' ? 'Other' : l.split('_')[0])
export const nice = (l) => {
  if (l === 'CORRECT') return 'Correct'
  if (l === 'OTHER_BUG') return 'A different kind of bug'
  const m = MISC.find((x) => x[0] === l)
  return m ? `${m[1]} · ${m[2]}` : l
}

// Demo bugs all use sum_list. M1/M2 and M4/M5 are "twins": similar-looking wrong output, different cause.
export const DEMOS = [
  {
    pair: 'M1 vs M2', id: 'M1', problem: 'sum_list', blurb: 'Loop stops one item early (drops the LAST item).',
    code: 'def sum_list(nums):\n    total = 0\n    for i in range(len(nums) - 1):\n        total += nums[i]\n    return total\n',
  },
  {
    pair: 'M1 vs M2', id: 'M2', problem: 'sum_list', blurb: 'Loop starts at index 1 (drops the FIRST item).',
    code: 'def sum_list(nums):\n    total = 0\n    for i in range(1, len(nums)):\n        total += nums[i]\n    return total\n',
  },
  {
    pair: 'M4 vs M5', id: 'M4', problem: 'sum_list', blurb: 'total is reset inside the loop (keeps only the LAST item).',
    code: 'def sum_list(nums):\n    for x in nums:\n        total = 0\n        total += x\n    return total\n',
  },
  {
    pair: 'M4 vs M5', id: 'M5', problem: 'sum_list', blurb: 'return inside the loop (keeps only the FIRST item).',
    code: 'def sum_list(nums):\n    total = 0\n    for x in nums:\n        total += x\n        return total\n',
  },
]

// Learner-facing names: plain words, no M-codes (the Eval page keeps the codes).
export const PLAIN = {
  CORRECT: 'Correct',
  M1_RANGE_OFF_BY_ONE: 'Off by one with range()',
  M2_INDEX_FROM_ONE: 'Counting positions from 1',
  M3_PRINT_NOT_RETURN: 'Printing instead of returning',
  M4_ACCUMULATOR_RESET: 'Resetting the total inside the loop',
  M5_RETURN_IN_LOOP: 'Returning too early, inside the loop',
  M6_FLOAT_DIVISION: 'Whole-number division (//)',
  M7_STRING_MUTABLE: 'Trying to change a string in place',
  M8_LIST_ALIASING: 'Two names for one list',
  OTHER_BUG: 'A different kind of bug',
}
export const plain = (l) => PLAIN[l] || PLAIN[MISC.find((x) => x[1] === l)?.[0]] || l

export const DIFFICULTY = { easy: ['Easy', 'good', 0], medium: ['Medium', 'info', 1], harder: ['Harder', 'warn', 2] }
export const byDifficulty = (a, b) => (DIFFICULTY[a.difficulty]?.[2] ?? 3) - (DIFFICULTY[b.difficulty]?.[2] ?? 3)

// Python errors in plain English (12th-grade level)
const ERRORS = {
  NameError: 'it uses a name Python does not know - maybe a typo, or a variable that was never created',
  TypeError: 'it combines values that do not work together, like adding text to a number or changing a string in place',
  IndexError: 'it asks for a position the list or string does not have (positions go from 0 to length - 1)',
  ZeroDivisionError: 'it divides by zero',
  KeyError: 'it looks up a key that is not in the dictionary',
  AttributeError: 'it uses a method this kind of value does not have',
  ValueError: 'it got a value it cannot use',
  UnboundLocalError: 'it uses a variable before giving it a value',
  RecursionError: 'the function keeps calling itself and never stops',
  Timeout: 'it never finished - probably a loop that does not stop',
}
export const plainError = (name) => ERRORS[name] || 'it stopped with an error'

export const STATUS = {
  syntax_error: 'Python could not read your code. Check brackets, colons (:) and indentation.',
  timeout: 'Your code never finished - probably a loop that does not stop.',
  memory_limit: 'Your code used too much memory - for example a list that keeps growing.',
  no_function: 'We could not find the function with the expected name. Keep the first line (def ...) from the starter code.',
  rejected: 'Your code uses something that is not allowed here (like importing modules or opening files).',
  crash: 'Your code stopped unexpectedly.',
}

// Python-style value: 'text', True/False, None, [1, 2]
export function py(v) {
  if (v === null || v === undefined) return 'None'
  if (v === true) return 'True'
  if (v === false) return 'False'
  if (typeof v === 'string') return `'${v}'`
  if (Array.isArray(v)) return `[${v.map(py).join(', ')}]`
  return String(v)
}

// One test result as a sentence a beginner can read.
export function testSentence(fn, t) {
  const call = `${fn}(${t.args.map(py).join(', ')})`
  if (t.ok) return { ok: true, text: `${call} gave ${py(t.got)} - correct.` }
  if (t.error) return { ok: false, text: `${call} stopped with ${t.error}: ${plainError(t.error)}.`, technical: t.message ? `${t.error}: ${t.message}` : null }
  if (t.returned_none) {
    return { ok: false, text: `${call} should give back ${py(t.expected)}, but your function gave back nothing (None)${t.printed ? ' - it printed the answer instead of returning it' : ''}.` }
  }
  return { ok: false, text: `${call} should give ${py(t.expected)}, but your code gave ${py(t.got)}${t.modified_input ? ', and it changed the list it was given' : ''}.` }
}
