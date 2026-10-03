"""Subprocess entry point used by the server: JSON on stdin -> JSON on stdout."""
import json, sys
from .execute import run_submission
if __name__ == "__main__":
    req = json.loads(sys.stdin.read())
    sys.stdout.write(json.dumps(run_submission(req["code"], req["problem"]), default=repr))
