"""Tests must never use a real Gemini key (ml/.env may hold one): no .env loading, no key, no model override.
Runs before any test module imports the app, so the shared LLM client starts unconfigured; tests that need an
LLM point it at a local mock server explicitly."""
import os

os.environ["RELEARN_NO_DOTENV"] = "1"
for var in ("GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_API_BASE"):
    os.environ.pop(var, None)
