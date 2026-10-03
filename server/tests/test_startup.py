"""Production startup: every artifact is committed, nothing needs a removed env var, and a missing file fails loudly."""
import os, pathlib, subprocess, sys

import pytest

from app import artifacts

SERVER = pathlib.Path(__file__).resolve().parents[1]
ROOT = SERVER.parent


def run_py(code, env=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("GEMINI", "LLM_"))}
    e.update(env or {})
    return subprocess.run([sys.executable, "-c", code], cwd=SERVER, env=e, capture_output=True, text=True, timeout=120)


def test_all_required_files_exist_and_are_tracked_by_git():
    assert artifacts.check() == len(artifacts.REQUIRED) >= 9
    for p in artifacts.REQUIRED:
        ignored = subprocess.run(["git", "check-ignore", "-q", str(p.relative_to(ROOT))], cwd=ROOT).returncode == 0
        assert not ignored, f"{p} is gitignored - production would not have it"


def test_model_was_trained_with_the_pinned_versions():
    art = artifacts.load_model()
    pins = dict(l.split("==") for l in (ROOT / "ml" / "requirements.txt").read_text().splitlines() if "==" in l)
    for lib in artifacts.LIBS:
        assert art["versions"][lib] == pins[lib] == artifacts.installed_versions()[lib], lib
    assert "temperature" in art and art["model"].T == art["temperature"], "the calibrator (temperature) ships inside the model"


def test_missing_files_are_all_listed_with_the_fix(tmp_path):
    with pytest.raises(artifacts.MissingArtifact) as e:
        artifacts.check([tmp_path / "a.joblib", artifacts.THRESHOLD_PATH, tmp_path / "b.json"])
    msg = str(e.value)
    assert "2 required file(s) missing" in msg and "a.joblib" in msg and "b.json" in msg and "python ml/train.py" in msg


def test_a_corrupt_model_fails_with_a_clear_message(tmp_path):
    bad = tmp_path / "diagnoser.joblib"
    bad.write_bytes(b"not a pickle")
    with pytest.raises(artifacts.MissingArtifact, match="loading .* failed"):
        artifacts.load_model(bad)


def test_server_refuses_to_start_when_an_artifact_is_missing():
    r = run_py("import pathlib, app.paths as P; P.MODEL_PATH = pathlib.Path('gone/diagnoser.joblib'); import app.main")
    assert r.returncode != 0 and "Re:Learn cannot start" in r.stderr and "diagnoser.joblib" in r.stderr


def test_startup_needs_no_api_key_or_gemini_variable():
    r = run_py("from fastapi.testclient import TestClient\nfrom app.main import app\n"
               "with TestClient(app) as c:\n    print(c.get('/health').json())",
               env={"RELEARN_DB": str(ROOT / ".run" / "startup-test.db") if (ROOT / ".run").exists() else ":memory:"})
    assert r.returncode == 0, r.stderr[-2000:]
    assert "'model_loaded': True" in r.stdout
    src = "\n".join(p.read_text(encoding="utf-8") for p in (SERVER / "app").glob("*.py"))
    assert "GEMINI" not in src  # the optional drafting LLM (LLM_*) is never needed to start - see the run above


def test_env_file_loader_parses_and_never_overrides(tmp_path, monkeypatch):
    from app import envfile
    f = tmp_path / ".env"
    f.write_text("# comment\n\nRELEARN_T1=plain\nexport RELEARN_T2='quoted value'\nRELEARN_T3=\"keep\"\nnot a line\n", encoding="utf-8")
    monkeypatch.setenv("RELEARN_T3", "from-real-env")
    for k in ("RELEARN_T1", "RELEARN_T2"):
        monkeypatch.delenv(k, raising=False)
    assert envfile.load(f) == ["RELEARN_T1", "RELEARN_T2"]
    assert os.environ["RELEARN_T1"] == "plain" and os.environ["RELEARN_T2"] == "quoted value" and os.environ["RELEARN_T3"] == "from-real-env"
    assert envfile.load(tmp_path / "missing.env") == []


def test_vercel_proxies_api_before_the_spa_fallback():
    import json
    rw = json.loads((ROOT / "client" / "vercel.json").read_text(encoding="utf-8"))["rewrites"]
    assert rw[0]["source"] == "/api/:path*" and rw[0]["destination"].endswith(".onrender.com/:path*")
    assert rw[-1] == {"source": "/(.*)", "destination": "/index.html"}
