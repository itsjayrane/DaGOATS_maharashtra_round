"""Test-suite defaults: rate limits off (many requests come from one test client); rate-limit tests switch them on."""
import os

os.environ["RELEARN_RATE_LIMIT"] = "off"
