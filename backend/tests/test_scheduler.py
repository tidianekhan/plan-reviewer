import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scheduler import schedule  # noqa: E402


def task(id, duration_days, depends_on=()):
    return {"id": id, "name": id, "owner": None, "duration_days": duration_days, "depends_on": list(depends_on)}


def test_single_task_ends_after_its_duration():
    result = schedule([task("A", 3)], 10)
    assert result["schedule"] == [{"id": "A", "start_day": 0, "end_day": 3}]
    assert result["end_day"] == 3


def test_dependent_task_starts_after_its_dependency():
    result = schedule([task("A", 3), task("B", 2, ["A"])], 10)
    by_id = {item["id"]: item for item in result["schedule"]}
    assert by_id["B"]["start_day"] == 3
    assert result["end_day"] == 5
