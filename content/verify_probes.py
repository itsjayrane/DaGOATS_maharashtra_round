"""Verify content/probes.json by running every snippet:  python content/verify_probes.py

For each probe: exactly one option implies nothing (the correct one) and it equals the real printed output;
options are distinct; every implied label belongs to the probe's twin pair; each twin is revealed by some option.
Exits 1 on any problem.
"""
import contextlib
import io
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def output_of(code):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(code, "<probe>", "exec"), {"__name__": "__probe__"})  # curated, trusted content only
    return " ".join(buf.getvalue().split())


def problems(probes):
    errs = []
    for p in probes:
        pid, pair, opts = p["id"], set(p["pair"]), p["options"]
        texts = [o["text"] for o in opts]
        if len(set(texts)) != len(texts):
            errs.append(f"{pid}: duplicate options")
        right = [o for o in opts if not o["implies"]]
        if len(right) != 1:
            errs.append(f"{pid}: needs exactly one correct option, has {len(right)}")
            continue
        try:
            got = output_of(p["code"])
        except Exception as e:  # noqa: BLE001
            errs.append(f"{pid}: code raises {type(e).__name__}: {e}")
            continue
        if right[0]["text"] != got:
            errs.append(f"{pid}: keyed answer {right[0]['text']!r} but the code prints {got!r}")
        wrong_outputs = [o["text"] for o in opts if o["implies"]]
        if got in wrong_outputs:
            errs.append(f"{pid}: a wrong option equals the real output")
        implied = {l for o in opts for l in o["implies"]}
        if not implied <= pair:
            errs.append(f"{pid}: implies labels outside its pair: {implied - pair}")
        if implied != pair:
            errs.append(f"{pid}: not every twin is revealed by an option: {pair - implied}")
        if not p.get("explanation"):
            errs.append(f"{pid}: missing explanation")
    return errs


def main():
    probes = json.loads((HERE / "probes.json").read_text(encoding="utf-8"))["probes"]
    errs = problems(probes)
    for e in errs:
        print("FAIL", e)
    print(f"{len(probes)} probes checked, {len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
