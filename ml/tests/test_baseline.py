import json, os, pathlib, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

ML = pathlib.Path(__file__).resolve().parents[1]
PY = sys.executable


class Mock(BaseHTTPRequestHandler):
    calls, throttled, keys = 0, False, set()

    def log_message(self, *a): pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        Mock.keys.add(self.headers.get("x-goog-api-key"))
        self._send(200, {"models": [
            {"name": "models/gemini-9-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-9-flash-lite", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-9-pro", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/embed-flash", "supportedGenerationMethods": ["embedContent"]}]})

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        assert "gemini-9-flash:generateContent" in self.path  # auto-picked the plain flash model
        if not Mock.throttled:  # first call is rate-limited -> client must retry
            Mock.throttled = True
            return self._send(429, {"error": "slow down"})
        Mock.calls += 1
        self._send(200, {"candidates": [{"content": {"parts": [{"text": json.dumps({"label": "M5_RETURN_IN_LOOP"})}]}}]})


def run(tmp, env_extra):
    env = {**os.environ, "RELEARN_NO_DOTENV": "1", "BASELINE_BACKOFF": "0.01", **env_extra}
    env.pop("GEMINI_API_KEY", None) if "GEMINI_API_KEY" not in env_extra else None
    return subprocess.run([PY, "baseline.py", "--max", "10", "--delay", "0", "--out-dir", str(tmp), "--cache", str(tmp / "cache.json")],
                          cwd=ML, env=env, capture_output=True, text=True, timeout=120)


def test_no_key_skips_gracefully(tmp_path):
    r = run(tmp_path, {})
    assert r.returncode == 0, r.stderr
    j = json.loads((tmp_path / "baseline.json").read_text())
    assert j["status"] == "not_run" and "GEMINI_API_KEY" in j["reason"]


def test_full_path_against_mock_gemini(tmp_path):
    srv = HTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    env = {"GEMINI_API_KEY": "test-key", "GEMINI_API_BASE": f"http://127.0.0.1:{srv.server_port}"}
    r = run(tmp_path, env)
    assert r.returncode == 0, r.stderr + r.stdout
    j = json.loads((tmp_path / "baseline.json").read_text())
    assert j["status"] == "ok" and j["gemini_model"] == "gemini-9-flash"
    assert j["n_unique"] == 10 and j["api_calls_made"] == 10 and Mock.calls == 10  # 429 was retried, not counted
    assert j["invalid_responses"] == 0 and Mock.keys == {"test-key"}
    assert 0 <= j["gemini"]["accuracy"] <= 1 and j["ours"]["accuracy"] > 0.5
    # second run is served from cache: zero API calls
    j2 = json.loads((run(tmp_path, env) and (tmp_path / "baseline.json")).read_text())
    assert j2["api_calls_made"] == 0
    srv.shutdown()


def test_markdown_sections():
    sys.path.insert(0, str(ML))
    import baseline
    assert "Baseline not run" in baseline.render_md({"status": "not_run", "reason": "no key"})
    ok = {"status": "ok", "holdout_problems": ["a"], "n_unique": 3, "gemini_model": "m", "protocol": "p", "invalid_responses": 0,
          "ours": {"accuracy": 1, "macro_f1": 1, "twin_exact": {"M1_M2": {"n": 2, "exact": 1.0}}},
          "gemini": {"accuracy": .5, "macro_f1": .4, "twin_exact": {"M1_M2": {"n": 2, "exact": None}}}}
    md = baseline.render_md(ok)
    assert "| accuracy | 1.000 | 0.500 |" in md and "M1 vs M2" in md and "| - |" in md
