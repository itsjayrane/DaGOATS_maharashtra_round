import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
PROBLEMS_PATH = ROOT / "content" / "problems.json"
def load_problems():
    return {p["id"]: p for p in json.loads(PROBLEMS_PATH.read_text(encoding="utf-8"))}
