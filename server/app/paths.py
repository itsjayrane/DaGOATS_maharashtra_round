import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
ML_DIR = ROOT / "ml"
CONTENT = ROOT / "content"
DOCS = ROOT / "docs"
MODEL_PATH = ML_DIR / "artifacts" / "diagnoser.joblib"
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))
