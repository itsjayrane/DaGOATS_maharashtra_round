// Python-style literals <-> JSON values, for the Teach form (and anything else that shows test inputs).

// 'text' -> "text", True/False/None -> true/false/null. Works character by character, so quotes INSIDE strings survive:
// "don't" stays "don't" and 'say "hi"' becomes "say \"hi\"".
export function pyToJson(text) {
  let out = ''
  let i = 0
  const s = String(text).trim()
  while (i < s.length) {
    const ch = s[i]
    if (ch === "'" || ch === '"') {
      let j = i + 1
      let body = ''
      while (j < s.length && s[j] !== ch) {
        if (s[j] === '\\' && j + 1 < s.length) { body += s[j] + s[j + 1]; j += 2; continue }
        body += s[j]
        j += 1
      }
      // re-encode: undo Python escapes of the opening quote, then let JSON escape what it needs
      const raw = body.replace(/\\(['"\\nt])/g, (_, c) => ({ n: '\n', t: '\t' }[c] ?? c))
      out += JSON.stringify(raw)
      i = j + 1
      continue
    }
    const word = /^(True|False|None)\b/.exec(s.slice(i))
    if (word && !/\w/.test(s[i - 1] || '')) {
      out += { True: 'true', False: 'false', None: 'null' }[word[1]]
      i += word[1].length
      continue
    }
    out += ch
    i += 1
  }
  return out
}

// JSON value -> Python literal (strings with double quotes, so apostrophes are safe)
export function toPy(v) {
  if (v === null || v === undefined) return 'None'
  if (v === true) return 'True'
  if (v === false) return 'False'
  if (typeof v === 'string') return JSON.stringify(v)
  if (Array.isArray(v)) return `[${v.map(toPy).join(', ')}]`
  return String(v)
}
