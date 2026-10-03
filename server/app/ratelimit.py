"""In-memory token-bucket rate limits, per client IP and per learner id (single process; resets on restart).

Client IP = first entry of X-Forwarded-For (Render's proxy sets it), else the socket peer.
Limits per minute: /hint 10, /diagnose and /intervene 30, /custom/* 5. Over the limit -> HTTP 429 with Retry-After.
RELEARN_RATE_LIMIT=off disables it (the test-suite does this; rate-limit tests switch it back on).
"""
import math
import os
import threading
import time

from fastapi import HTTPException, Request

PER_MINUTE = {"hint": 10, "diagnose": 30, "intervene": 30, "custom": 5, "draft": 5, "practice": 5, "solution": 20}
_buckets = {}  # key -> [tokens, last_refill_monotonic]
_lock = threading.Lock()


def enabled():
    return os.environ.get("RELEARN_RATE_LIMIT", "on").strip().lower() not in ("0", "off", "false", "no")


def client_ip(request: Request):
    xff = request.headers.get("x-forwarded-for", "")
    if xff.strip():
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _now():
    return time.monotonic()


def _take(key, per_minute):
    """Takes one token. Returns 0 if allowed, else the seconds until a token is available."""
    rate = per_minute / 60.0
    now = _now()
    with _lock:
        tokens, last = _buckets.get(key, (float(per_minute), now))
        tokens = min(float(per_minute), tokens + (now - last) * rate)
        if tokens >= 1:
            _buckets[key] = (tokens - 1, now)
            return 0
        _buckets[key] = (tokens, now)
        return max(1, math.ceil((1 - tokens) / rate))


def check(request: Request, name: str, learner_id=None):
    if not enabled():
        return
    per = PER_MINUTE[name]
    keys = [f"{name}|ip|{client_ip(request)}"] + ([f"{name}|learner|{learner_id}"] if learner_id else [])
    for key in keys:
        wait = _take(key, per)
        if wait:
            raise HTTPException(429, detail=f"Too many requests - please wait {wait} seconds and try again.",
                                headers={"Retry-After": str(wait)})


def reset():
    with _lock:
        _buckets.clear()
