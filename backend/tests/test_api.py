import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402
from check_contract import validate_schedule_response  # noqa: E402

client = TestClient(app)


def t(id, deps=(), duration=1, owner=None):
    return {"id": id, "name": id, "owner": owner, "duration_days": duration, "depends_on": list(deps)}


def test_plans_are_listed():
    response = client.get("/api/plans")
    assert response.status_code == 200
    assert {plan["id"] for plan in response.json()} == {"spring-market", "lantern-festival", "harbour-run"}


def test_unknown_plan_is_404():
    assert client.get("/api/plans/nope").status_code == 404
    assert client.get("/api/plans/..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_example_request_follows_the_contract():
    request = json.loads((ROOT / "examples" / "schedule-request.json").read_text())
    response = client.post("/api/schedule", json=request)
    assert response.status_code == 200
    assert validate_schedule_response(request, response.json()) == []
    assert response.json()["end_day"] == 9


def test_cycle_is_200_with_names():
    response = client.post("/api/schedule", json={"tasks": [t("A", ["B"]), t("B", ["A"])], "deadline_day": 5})
    assert response.status_code == 200
    assert response.json()["status"] == "cycle"


@pytest.mark.parametrize("body,needle", [
    ({"tasks": [t("A"), t("A")], "deadline_day": 5}, "more than once"),
    ({"tasks": [t("A", ["Z"])], "deadline_day": 5}, "not a task in this list"),
    ({"tasks": [t("A", duration=0)], "deadline_day": 5}, "greater than or equal to 1"),
    ({"tasks": [t("A", duration=2.5)], "deadline_day": 5}, "integer"),
    ({"tasks": [t("A", duration="3")], "deadline_day": 5}, "integer"),
    ({"tasks": [t("A", duration=True)], "deadline_day": 5}, "integer"),
    ({"tasks": [t(f"T{i}") for i in range(61)], "deadline_day": 5}, "at most 60"),
    ({"tasks": [t("A")]}, "deadline_day"),
    ({"tasks": [t("A")], "deadline_day": None}, "deadline_day"),
    ({"tasks": [{"id": "A", "name": "A", "duration_days": 1, "depends_on": []}], "deadline_day": 5}, "owner"),
    ({"tasks": [t(1)], "deadline_day": 5}, "string"),
    ({"tasks": "A,B"}, "tasks"),
    ([], ""),
])
def test_bad_input_is_refused_clearly(body, needle):
    response = client.post("/api/schedule", json=body)
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]
    assert needle in " ".join(payload["problems"])


def test_malformed_json_is_refused():
    response = client.post("/api/schedule", content=b"{not json", headers={"Content-Type": "application/json"})
    assert 400 <= response.status_code < 500
    assert response.json()


def test_extra_fields_are_ignored():
    body = {"tasks": [dict(t("A", duration=2), colour="red")], "deadline_day": 1, "note": "x"}
    response = client.post("/api/schedule", json=body)
    assert response.status_code == 200 and response.json()["days_late"] == 1
