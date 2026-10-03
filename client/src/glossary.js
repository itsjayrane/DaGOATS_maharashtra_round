import { useEffect, useState } from 'react'
import { api } from './api'

let cache = null
let pending = null

// Plain-language definitions from GET /glossary (content/glossary.json), fetched once per page load.
export function useGlossary() {
  const [g, setG] = useState(cache)
  useEffect(() => {
    if (cache) return undefined
    let live = true
    pending = pending || api.glossary().then((d) => { cache = d; return d }).catch(() => { pending = null; return null })
    pending.then((d) => { if (live && d) setG(d) })
    return () => { live = false }
  }, [])
  return g || {}
}

// Find glossary terms in plain text: whole words, optional plural "s"; "None" must match exactly.
export function findTerms(text, terms) {
  const keys = Object.keys(terms).sort((a, b) => b.length - a.length)
  if (!keys.length) return []
  const re = new RegExp(`\\b(${keys.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})s?\\b`, 'gi')
  const out = []
  let m
  while ((m = re.exec(text))) {
    const key = keys.find((k) => k.toLowerCase() === m[1].toLowerCase())
    if (key === 'None' && m[1] !== 'None') continue
    out.push({ start: m.index, end: m.index + m[0].length, key })
  }
  return out
}
