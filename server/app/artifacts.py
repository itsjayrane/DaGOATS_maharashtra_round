"""Startup check: every file the server needs is committed; fail loudly (with the fix) if one is missing.

Run it on its own (no server):  python -m app.artifacts   (from server/)
"""
import importlib.metadata as md
import logging
import sys

from .paths import CONTENT, ML_DIR, MODEL_PATH

log = logging.getLogger("relearn.startup")

THRESHOLD_PATH = ML_DIR / "artifacts" / "threshold.json"
CONTENT_FILES = ["problems.json", "misconceptions.json", "hints.json", "concept_pool.json", "glossary.json",
                 "problem_meta.json", "probes.json"]
REQUIRED = [MODEL_PATH, THRESHOLD_PATH] + [CONTENT / f for f in CONTENT_FILES]
LIBS = ["scikit-learn", "lightgbm", "numpy", "scipy", "joblib"]
FIX = ("These files are committed to the repo. If one is missing, the checkout is incomplete or a .gitignore rule "
       "excluded it. Regenerate the model with `python ml/train.py` (writes ml/artifacts/diagnoser.joblib and "
       "threshold.json) and commit it.")


class MissingArtifact(RuntimeError):
    pass


def installed_versions():
    out = {}
    for lib in LIBS:
        try:
            out[lib] = md.version(lib)
        except md.PackageNotFoundError:
            out[lib] = None
    return out


def check(required=None):
    """Raise MissingArtifact listing every missing file (not just the first)."""
    missing = [p for p in (required or REQUIRED) if not p.exists()]
    if missing:
        lines = "\n".join(f"  - {p}" for p in missing)
        raise MissingArtifact(f"Re:Learn cannot start: {len(missing)} required file(s) missing:\n{lines}\n{FIX}")
    return len(required or REQUIRED)


def load_model(path=MODEL_PATH):
    """joblib.load with a clear error; warns when the libraries differ from the ones the model was trained with."""
    import joblib
    try:
        art = joblib.load(path)
    except Exception as e:  # noqa: BLE001 - re-raised with context
        raise MissingArtifact(f"Re:Learn cannot start: loading {path} failed ({type(e).__name__}: {e}). "
                              f"Installed: {installed_versions()}. Retrain with `python ml/train.py` using the pinned "
                              f"ml/requirements.txt and commit the new file.") from e
    trained = art.get("versions") or {}
    now = installed_versions()
    diff = {k: (trained.get(k), now.get(k)) for k in LIBS if trained.get(k) and trained.get(k) != now.get(k)}
    if diff:
        log.warning("model was trained with different library versions (trained, installed): %s", diff)
    return art


if __name__ == "__main__":
    try:
        n = check()
        art = load_model()
    except MissingArtifact as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    print(f"OK: {n} required files present; model trained with {art.get('versions')}; installed {installed_versions()}")
