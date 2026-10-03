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
export const short = (l) => (l === 'CORRECT' ? 'OK' : l.split('_')[0])
export const nice = (l) => {
  if (l === 'CORRECT') return 'Correct'
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
