"""The app's one shared Gemini client (used by AI hints and concept checks).

- Key: GEMINI_API_KEY from the environment, or from ml/.env, .env or server/.env (python-dotenv; real environment
  variables always win). Files are re-read on every call, so adding a key needs no restart.
- Model: GEMINI_MODEL, else "gemini-flash-latest" (Google's alias for the current Flash model). No model-listing call.
- Free tier: one attempt, 10 s timeout (RELEARN_LLM_TIMEOUT), no retries. Every failure raises LLMError with a reason:
  no_api_key, rate_limited (429), overloaded (503), timeout, api_error (other HTTP / network), bad_response.
  Callers fall back to built-in content and log the reason. The key is never logged or returned.
"""
import json
import logging
import os
import pathlib
import socket
import urllib.error
import urllib.request

from dotenv import dotenv_values, load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[2]  # repository root
ENV_FILES = [ROOT / "ml" / ".env", ROOT / ".env", ROOT / "server" / ".env"]
DEFAULT_BASE = "https://generativelanguage.googleapis.com"
DEFAULT_MODEL = "gemini-flash-latest"
log = logging.getLogger("relearn.llm")
_STATE = {"key_in_env_at_start": bool(os.environ.get("GEMINI_API_KEY")), "dotenv_loaded": [], "last_model_version": None, "no_thinking": set()}


class LLMError(Exception):
    def __init__(self, reason, detail=""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason, self.detail = reason, detail


def _rel(f):
    try:
        return pathlib.Path(f).relative_to(ROOT).as_posix()
    except ValueError:
        return str(f)


def env_files():
    return [] if os.environ.get("RELEARN_NO_DOTENV") else list(ENV_FILES)


def load_env():
    """Load .env files into the process environment with python-dotenv (never overriding real env vars)."""
    loaded = [_rel(f) for f in env_files() if f.exists() and load_dotenv(f, override=False)]
    _STATE["dotenv_loaded"] = loaded
    return loaded


def _file_key(f):
    return (dotenv_values(f).get("GEMINI_API_KEY") or "").strip()


def read_key():
    if os.environ.get("GEMINI_API_KEY", "").strip():
        return os.environ["GEMINI_API_KEY"].strip()
    for f in env_files():  # a key added after startup is picked up without a restart
        if f.exists() and _file_key(f):
            return _file_key(f)
    return None


def key_source():
    """Where the key comes from - never the key itself."""
    if _STATE["key_in_env_at_start"] and os.environ.get("GEMINI_API_KEY"):
        return "environment variable"
    for f in env_files():
        if f.exists() and _file_key(f):
            return _rel(f)
    return "environment variable" if os.environ.get("GEMINI_API_KEY") else None


def model():
    return os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL


def timeout_s():
    return float(os.environ.get("RELEARN_LLM_TIMEOUT", "10"))


def status():
    return dict(configured=bool(read_key()), key_source=key_source(), model=model(), last_model_version=_STATE["last_model_version"],
                timeout_s=timeout_s(), dotenv_loaded=_STATE["dotenv_loaded"],
                places_checked=["environment variable GEMINI_API_KEY"] + [_rel(f) for f in env_files()])


def _post(url, key, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s()) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = " ".join(e.read()[:400].decode(errors="replace").replace(key, "<key>").split())[:220]
        raise LLMError({429: "rate_limited", 503: "overloaded"}.get(e.code, "api_error"), f"HTTP {e.code}: {detail}")
    except (TimeoutError, socket.timeout):
        raise LLMError("timeout", f"no answer within {timeout_s():g}s")
    except urllib.error.URLError as e:
        if isinstance(e.reason, (TimeoutError, socket.timeout)):
            raise LLMError("timeout", f"no answer within {timeout_s():g}s")
        raise LLMError("api_error", f"network: {e.reason}")
    except json.JSONDecodeError:
        raise LLMError("bad_response", "response body is not JSON")


def generate_json(prompt, schema, max_output_tokens=1024, temperature=0.4):
    """One structured-output call. Returns the parsed JSON object, or raises LLMError(reason)."""
    key = read_key()
    if not key:
        raise LLMError("no_api_key")
    base = os.environ.get("GEMINI_API_BASE", DEFAULT_BASE).rstrip("/")
    m = model()
    gen = {"temperature": temperature, "maxOutputTokens": max_output_tokens, "responseMimeType": "application/json", "responseSchema": schema}
    if m not in _STATE["no_thinking"]:
        gen["thinkingConfig"] = {"thinkingLevel": "low"}  # Flash 3.x "thinks" by default and would eat the output budget
    url = f"{base}/v1beta/models/{m}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen}
    try:
        out = _post(url, key, body)
    except LLMError as e:
        if e.reason != "api_error" or "thinking" not in e.detail.lower():
            raise
        _STATE["no_thinking"].add(m)  # this model has no thinking levels: ask again without them (one extra call, once per model)
        gen.pop("thinkingConfig")
        out = _post(url, key, body)
    _STATE["last_model_version"] = out.get("modelVersion") or m
    cand = (out.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    if not text:
        raise LLMError("bad_response", f"no text (finishReason={cand.get('finishReason')})")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise LLMError("bad_response", f"invalid JSON (finishReason={cand.get('finishReason')})")
    if not isinstance(data, dict):
        raise LLMError("bad_response", "JSON is not an object")
    return data


load_env()
