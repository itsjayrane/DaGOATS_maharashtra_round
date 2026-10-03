"""Item 8: twin probes - GET /probe/{a}/{b}, POST /probe/answer."""
import os, tempfile

os.environ.setdefault("RELEARN_DB", os.path.join(tempfile.mkdtemp(), "own.db"))  # never the dev database

import pytest
from fastapi.testclient import TestClient

from app.main import PROBES, app


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def test_probe_for_a_twin_pair_hides_the_answer(c):
    r = c.get("/probe/M1/M2").json()
    assert set(r["pair"]) == {"M1_RANGE_OFF_BY_ONE", "M2_INDEX_FROM_ONE"} and len(r["options"]) == 4
    assert "implies" not in str(r) and "explanation" not in r
    assert c.get("/probe/M5/M4").json()["probe_id"].startswith("m4m5"), "order does not matter"
    assert c.get("/probe/M1/M3").status_code == 404 and c.get("/probe/M9/M1").status_code == 404


def test_answers_map_to_the_twin_they_reveal(c):
    pid = "m4m5-1"
    texts = [o["text"] for o in PROBES[pid]["options"]]
    right = c.post("/probe/answer", json={"probe_id": pid, "choice": texts.index("6 4")}).json()
    assert right["correct"] and right["suggested_label"] is None and right["implies"] == []
    m4 = c.post("/probe/answer", json={"probe_id": pid, "choice": texts.index("15 4")}).json()
    assert not m4["correct"] and m4["suggested_label"] == "M4_ACCUMULATOR_RESET" and m4["answer"] == "6 4" and m4["explanation"]
    m5 = c.post("/probe/answer", json={"probe_id": pid, "choice": texts.index("6 15")}).json()
    assert m5["suggested_label"] == "M5_RETURN_IN_LOOP"
    both = c.post("/probe/answer", json={"probe_id": pid, "choice": texts.index("15 15")}).json()
    assert both["suggested_label"] is None and len(both["implies"]) == 2
    assert c.post("/probe/answer", json={"probe_id": pid, "choice": 9}).status_code == 422
    assert c.post("/probe/answer", json={"probe_id": "nope", "choice": 0}).status_code == 404


def test_a_learner_gets_a_different_probe_next_time(c):
    a = c.get("/probe/M1/M2", params={"learner_id": "p1"}).json()
    c.post("/probe/answer", json={"probe_id": a["probe_id"], "choice": 0, "learner_id": "p1"})
    b = c.get("/probe/M1/M2", params={"learner_id": "p1"}).json()
    assert a["probe_id"] != b["probe_id"]
