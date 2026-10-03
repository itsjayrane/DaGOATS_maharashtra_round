"""Load server/.env (if present) into os.environ at startup - a tiny stdlib loader (no python-dotenv dependency).

Lines are KEY=VALUE; blank lines and '#' comments are skipped; surrounding quotes are removed. Variables that are
already set in the real environment win. Values are never logged.
"""
import os

from .paths import ROOT

ENV_FILE = ROOT / "server" / ".env"


def load(path=ENV_FILE):
    if not path.exists():
        return []
    loaded = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.removeprefix("export ").partition("=")
        key, val = key.strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val
            loaded.append(key)
    return loaded  # names only, for a startup log line
