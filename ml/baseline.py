"""Zero-shot LLM baseline (Gemini) on the SAME held-out problems used by train.py.

    cd ml && .venv/Scripts/python baseline.py [--max N] [--delay SECONDS]

Needs GEMINI_API_KEY (env var, or a line in ml/.env or the repo-root .env). Without a key it writes
docs/baseline.json {"status": "not_run"} and exits 0, so the Eval page can say "baseline not run".

Fairness notes (also written to docs/metrics.md): Gemini sees the task statement, the learner's code and one-line
label definitions - no examples (zero-shot) and no test-execution results. Our model sees execution features.
Both are scored on the same unique held-out code snippets. Responses are cached so reruns cost nothing.
"""
import argparse, hashlib, json, os, pathlib, re, sys, time, urllib.error, urllib.request
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent
DOCS = ROOT.parent / "docs"
START, END = "<!-- baseline:start -->", "<!-- baseline:end -->"
DEFAULT_BASE = "https://generativelanguage.googleapis.com"

DEFINITIONS = {
    "CORRECT": "The solution is correct and has no misconception.",
    "M1_RANGE_OFF_BY_ONE": "Loop bound is off by one: e.g. range(1, n) when n must be included, or range(len(x) - 1) skipping the last item.",
    "M2_INDEX_FROM_ONE": "Treats list indexes as starting at 1: x[1] as the first item, x[len(x)] as the last, or loops from index 1.",
    "M3_PRINT_NOT_RETURN": "Uses print() to deliver the result instead of returning it (function returns None).",
    "M4_ACCUMULATOR_RESET": "The running total/count/product is re-initialised inside the loop, so earlier iterations are lost.",
    "M5_RETURN_IN_LOOP": "A return inside the loop body ends the function on the first iteration (early return where it is not valid).",
    "M6_FLOAT_DIVISION": "Uses // or int() where the exact decimal quotient is needed (averages, percentages, conversions).",
    "M7_STRING_MUTABLE": "Tries to change a string in place: s[i] = ..., or calls s.upper()/s.replace() and discards the result.",
    "M8_LIST_ALIASING": "Believes 'b = a' copies a list (mutates the original through an alias), or builds a grid with [[0]*n]*m.",
}
LABELS = list(DEFINITIONS)
TWINS = [("M1_RANGE_OFF_BY_ONE", "M2_INDEX_FROM_ONE"), ("M4_ACCUMULATOR_RESET", "M5_RETURN_IN_LOOP")]


# ---------------------------------------------------------------- config / IO
def env_files():
    """Files that may hold a GEMINI_API_KEY line. Re-read on every call, so adding a key needs no restart."""
    if os.environ.get("RELEARN_NO_DOTENV"):
        return []
    return [ROOT / ".env", ROOT.parent / ".env", ROOT.parent / "server" / ".env"]


def _key_from(f):
    for line in f.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*(?:export\s+)?GEMINI_API_KEY\s*=\s*(.*)\s*$", line)
        if m and m.group(1).strip().strip("'\""):
            return m.group(1).strip().strip("'\"")
    return None


def read_key():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"].strip()
    for f in env_files():
        if f.exists() and _key_from(f):
            return _key_from(f)
    return None


def key_source():
    """Where the key comes from (never the key itself): 'environment variable', a .env path such as 'ml/.env', or None."""
    if os.environ.get("GEMINI_API_KEY"):
        return "environment variable"
    for f in env_files():
        if f.exists() and _key_from(f):
            return f.relative_to(ROOT.parent).as_posix()
    return None


def _http(url, key, body=None, retries=5, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(min(2 ** attempt, 20) * float(os.environ.get("BASELINE_BACKOFF", "1")))
                continue
            raise RuntimeError(f"Gemini API HTTP {e.code}: {e.read()[:300].decode(errors='replace')}")
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(min(2 ** attempt, 20) * float(os.environ.get("BASELINE_BACKOFF", "1")))
                continue
            raise RuntimeError(f"Cannot reach Gemini API: {e.reason}")


def pick_model(base, key):
    if os.environ.get("GEMINI_MODEL"):
        return os.environ["GEMINI_MODEL"]
    models = _http(f"{base}/v1beta/models?pageSize=200", key).get("models", [])
    bad = ("lite", "image", "tts", "live", "audio", "exp", "embedding", "thinking", "robotics", "computer", "learn")
    ok = [m["name"].split("/")[-1] for m in models
          if "generateContent" in m.get("supportedGenerationMethods", []) and "flash" in m["name"] and not any(b in m["name"] for b in bad)]
    if not ok:
        raise RuntimeError("Could not auto-pick a Gemini model; set GEMINI_MODEL (e.g. a current 'flash' model id).")
    return sorted(ok, reverse=True)[0]


def prompt_for(problem, code):
    defs = "\n".join(f"- {k}: {v}" for k, v in DEFINITIONS.items())
    return (f"You are diagnosing the misconception behind a beginner's Python code.\n\nTask given to the learner:\n{problem['prompt']}\n"
            f"(function `{problem['fn']}({', '.join(problem['params'])})`)\n\nLearner's code:\n```python\n{code}\n```\n\n"
            f"Choose exactly ONE label for the root cause of any bug:\n{defs}\n\nAnswer as JSON: {{\"label\": \"<LABEL>\"}}")


def classify(base, key, model, problem, code):
    body = {"contents": [{"parts": [{"text": prompt_for(problem, code)}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                 "responseSchema": {"type": "OBJECT", "properties": {"label": {"type": "STRING", "enum": LABELS}}, "required": ["label"]}}}
    out = _http(f"{base}/v1beta/models/{model}:generateContent", key, body)
    try:
        text = out["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return "INVALID"
    try:
        lab = json.loads(text).get("label", "")
    except Exception:
        lab = next((l for l in LABELS if l in text), "")
    return lab if lab in LABELS else "INVALID"


# ---------------------------------------------------------------- evaluation
def metrics(y, pred):
    from sklearn.metrics import accuracy_score, f1_score
    present = sorted(set(y))
    out = dict(n=len(y), accuracy=float(accuracy_score(y, pred)), macro_f1=float(f1_score(y, pred, labels=present, average="macro", zero_division=0)),
               per_class_f1={l: float(f1_score(y, pred, labels=[l], average="macro", zero_division=0)) for l in present}, twin_exact={})
    for a, b in TWINS:
        idx = [i for i, t in enumerate(y) if t in (a, b)]
        out["twin_exact"][f"{a[:2]}_{b[:2]}"] = dict(n=len(idx), exact=(sum(pred[i] == y[i] for i in idx) / len(idx)) if idx else None)
    return out


def load_holdout():
    mj = DOCS / "metrics.json"
    if not mj.exists():
        sys.exit("docs/metrics.json missing - run `python train.py` first.")
    hold = json.loads(mj.read_text(encoding="utf-8"))["holdout_problems"]
    rows = [json.loads(l) for l in open(ROOT / "data" / "dataset.jsonl", encoding="utf-8")]
    return hold, [r for r in rows if r["problem"] in hold]


def run(args):
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    key = read_key()
    if not key:
        res = dict(status="not_run", reason="GEMINI_API_KEY not found (set it in ml/.env or the environment, then run `python baseline.py`).")
        (out_dir / "baseline.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        print("baseline not run: no GEMINI_API_KEY")
        return res

    import joblib, numpy as np
    sys.path.insert(0, str(ROOT))
    from relearn_ml.labels import LABELS as OUR
    from relearn_ml.problems import load_problems
    problems = load_problems()
    hold, rows = load_holdout()
    model = joblib.load(ROOT / "artifacts" / "diagnoser_holdout.joblib")["model"]
    pred_ours_rows = [OUR[i] for i in model.predict_proba(rows).argmax(1)]

    groups = defaultdict(list)  # unique (problem, normalised code) -> row indexes
    for i, r in enumerate(rows):
        groups[(r["problem"], r["norm"])].append(i)
    keys = sorted(groups)
    if args.max:
        step = max(1, len(keys) // args.max)
        keys = keys[::step][: args.max]
    base = os.environ.get("GEMINI_API_BASE", DEFAULT_BASE).rstrip("/")
    mdl = pick_model(base, key)
    cache_f = pathlib.Path(args.cache)
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    calls = 0
    y, g_pred, o_pred = [], [], []
    for n, k in enumerate(keys, 1):
        i = groups[k][0]
        r = rows[i]
        ck = hashlib.sha1(f"{mdl}|{r['problem']}|{r['code']}".encode()).hexdigest()
        if ck not in cache:
            cache[ck] = classify(base, key, mdl, problems[r["problem"]], r["code"])
            calls += 1
            cache_f.parent.mkdir(parents=True, exist_ok=True)
            cache_f.write_text(json.dumps(cache))
            time.sleep(args.delay)
        y.append(r["label"]); g_pred.append(cache[ck]); o_pred.append(pred_ours_rows[i])
        if n % 20 == 0:
            print(f"  {n}/{len(keys)} unique snippets")
    invalid = sum(p == "INVALID" for p in g_pred)
    res = dict(status="ok", gemini_model=mdl, holdout_problems=hold, n_unique=len(keys), n_rows_covered=sum(len(groups[k]) for k in keys),
               api_calls_made=calls, invalid_responses=invalid, protocol="zero-shot; task + code + label definitions; no execution results",
               ours=metrics(y, o_pred), gemini=metrics(y, g_pred))
    (out_dir / "baseline.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"gemini={res['gemini']['accuracy']:.3f} acc / {res['gemini']['macro_f1']:.3f} F1   ours={res['ours']['accuracy']:.3f} / {res['ours']['macro_f1']:.3f}   (n={len(keys)}, invalid={invalid})")
    return res


# ---------------------------------------------------------------- docs
def render_md(b):
    if not b or b.get("status") != "ok":
        reason = (b or {}).get("reason", "baseline.json missing")
        return f"## Our model vs Gemini baseline\n\n**Baseline not run.** {reason}\n"
    o, g = b["ours"], b["gemini"]
    f = lambda x: "-" if x is None else f"{x:.3f}"
    rows = [("accuracy", o["accuracy"], g["accuracy"]), ("macro-F1", o["macro_f1"], g["macro_f1"])]
    for k in o["twin_exact"]:
        rows.append((f"{k.replace('_', ' vs ')} exact accuracy (n={o['twin_exact'][k]['n']})", o["twin_exact"][k]["exact"], g["twin_exact"][k]["exact"]))
    L = ["## Our model vs Gemini baseline", "",
         f"Same held-out problems (`{', '.join(b['holdout_problems'])}`), scored on {b['n_unique']} unique code snippets. "
         f"Gemini model: `{b['gemini_model']}`, {b['protocol']}. Invalid/unparseable Gemini responses ({b['invalid_responses']}) count as wrong.", "",
         "| metric | Our model | Gemini (zero-shot) |", "|---|---|---|"]
    L += [f"| {n} | {f(a)} | {f(c)} |" for n, a, c in rows]
    L += ["", "Caveats: our model also sees test-execution features that Gemini does not, so this compares systems, not just text understanding; "
          "one prompt, temperature 0, single run; the held-out set is synthetic and template-derived."]
    return "\n".join(L) + "\n"


def sync_md(out_dir=DOCS):
    out_dir = pathlib.Path(out_dir)
    md, bj = out_dir / "metrics.md", out_dir / "baseline.json"
    if not md.exists():
        return
    b = json.loads(bj.read_text(encoding="utf-8")) if bj.exists() else None
    section = f"{START}\n{render_md(b)}{END}\n"
    s = md.read_text(encoding="utf-8")
    if START in s and END in s:
        s = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?", lambda _: section, s, flags=re.S)
    else:
        s = s.rstrip() + "\n\n" + section
    md.write_text(s, encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=0, help="limit number of unique snippets (0 = all)")
    ap.add_argument("--delay", type=float, default=0.2, help="seconds between API calls")
    ap.add_argument("--out-dir", default=str(DOCS))
    ap.add_argument("--cache", default=str(ROOT / "artifacts" / "gemini_cache.json"))
    a = ap.parse_args()
    run(a)
    sync_md(a.out_dir)
