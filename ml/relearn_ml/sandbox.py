"""Subprocess entry point used by the server: JSON on stdin -> JSON on stdout.

On POSIX (Linux, e.g. Render) the child process also gets OS limits before any learner code runs:
address space ~512 MB, 3 s of CPU time, and no file writes. On Windows these limits are not available
(the server's 2 s wall-clock timeout and the in-process step limit still apply).
"""
import json
import os
import sys

from .execute import run_submission

MEM_BYTES = 512 * 1024 * 1024
CPU_SECONDS = 3


def apply_limits():
    if os.name != "posix":
        return False
    import resource  # POSIX-only module
    for lim, val in ((resource.RLIMIT_AS, MEM_BYTES), (resource.RLIMIT_CPU, CPU_SECONDS), (resource.RLIMIT_FSIZE, 0)):
        try:
            resource.setrlimit(lim, (val, val))
        except (ValueError, OSError):
            pass
    return True


if __name__ == "__main__":
    req = json.loads(sys.stdin.read())
    apply_limits()
    sys.stdout.write(json.dumps(run_submission(req["code"], req["problem"]), default=repr))
