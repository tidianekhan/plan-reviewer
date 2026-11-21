import itertools
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.scheduler import find_cycle, schedule  # noqa: E402
from check_contract import validate_schedule_response  # noqa: E402


def task(id, duration_days, depends_on=(), owner=None):
    return {"id": id, "name": id, "owner": owner, "duration_days": duration_days, "depends_on": list(depends_on)}


def by_id(result):
    return {item["id"]: item for item in result["schedule"]}


def random_plan(rng, n, owners="ABC", edge_p=0.3):
    tasks = []
    for i in range(n):
        deps = [f"T{j}" for j in range(i) if rng.random() < edge_p]
        owner = rng.choice(list(owners) + [None])
        tasks.append(task(f"T{i}", rng.randint(1, 6), deps, owner))
    rng.shuffle(tasks)
    return tasks


def brute_force_end(tasks):
    """Best end day over every task order, placing each task at its earliest free slot.

    Every active schedule comes from some order, and an optimal schedule can always be made active,
    so this is the true optimum (exponential, fine for 7 tasks).
    """
    best = None
    t_by_id = {t["id"]: t for t in tasks}
    for order in itertools.permutations(t_by_id):
        pos = {tid: k for k, tid in enumerate(order)}
        if any(pos[d] > pos[t["id"]] for t in tasks for d in t["depends_on"]):
            continue
        start, busy = {}, {}
        for tid in order:
            t = t_by_id[tid]
            s = max((start[d] + t_by_id[d]["duration_days"] for d in t["depends_on"]), default=0)
            if t["owner"] is not None:
                for bs, be in sorted(busy.get(t["owner"], [])):
                    if s + t["duration_days"] <= bs:
                        break
                    s = max(s, be)
                busy.setdefault(t["owner"], []).append((s, s + t["duration_days"]))
            start[tid] = s
        end = max(start[i] + t_by_id[i]["duration_days"] for i in start)
        best = end if best is None else min(best, end)
    return best


def test_single_task_ends_after_its_duration():
    result = schedule([task("A", 3)], 10)
    assert result["schedule"] == [{"id": "A", "start_day": 0, "end_day": 3}]
    assert result["end_day"] == 3


def test_dependent_task_starts_after_its_dependency():
    result = schedule([task("A", 3), task("B", 2, ["A"])], 10)
    assert by_id(result)["B"]["start_day"] == 3
    assert result["end_day"] == 5


def test_one_person_does_one_task_at_a_time():
    result = schedule([task("A", 3, owner="Ann"), task("B", 4, owner="Ann")], 5)
    assert result["end_day"] == 7
    assert result["meets_deadline"] is False and result["days_late"] == 2
    assert result["proof"]["lower_bound"] == {"day": 7, "kind": "owner", "tasks": ["A", "B"], "owner": "Ann"}


def test_tasks_without_owner_run_in_parallel():
    result = schedule([task("A", 3), task("B", 4)], 5)
    assert result["end_day"] == 4


def test_contract_example_is_optimal():
    tasks = [task("A", 3, owner="Ann"), task("B", 2, ["A"], "Ann"), task("C", 4, owner="Ann"), task("D", 2, ["C"], "Bob")]
    result = schedule(tasks, 10)
    assert result["end_day"] == 9 and result["proof"]["optimal"]
    assert validate_schedule_response({"tasks": tasks, "deadline_day": 10}, result) == []


def test_ordering_matters_greedy_by_chain_is_not_enough():
    # Ann's short task unlocks Bob's long one, so it must go first even though her long task heads a longer chain alone.
    tasks = [task("A", 5, owner="Ann"), task("B", 1, owner="Ann"), task("C", 6, ["B"], "Bob")]
    assert schedule(tasks, 10)["end_day"] == 7


def test_empty_plan():
    result = schedule([], 3)
    assert result["end_day"] == 0 and result["schedule"] == [] and result["meets_deadline"] is True


def test_two_task_cycle_is_named():
    result = schedule([task("A", 1, ["B"]), task("B", 1, ["A"])], 10)
    assert result["status"] == "cycle" and sorted(result["cycle"]) == ["A", "B"]
    assert result["end_day"] is None and result["schedule"] == []


def test_self_dependency_is_a_cycle():
    assert find_cycle([task("A", 1, ["A"])]) == ["A"]


def test_cycle_lists_only_tasks_on_the_circle():
    tasks = [task("X", 1), task("A", 1, ["X", "C"]), task("B", 1, ["A"]), task("C", 1, ["B"]), task("D", 1, ["C"])]
    assert sorted(find_cycle(tasks)) == ["A", "B", "C"]


def test_matches_brute_force_on_random_small_plans():
    rng = random.Random(7)
    for _ in range(60):
        tasks = random_plan(rng, rng.randint(1, 7))
        result = schedule(tasks, 10)
        assert validate_schedule_response({"tasks": tasks, "deadline_day": 10}, result) == []
        assert result["end_day"] == brute_force_end(tasks), tasks


def test_sixty_tasks_answer_quickly_and_follow_the_rules():
    rng = random.Random(1)
    for _ in range(3):
        tasks = random_plan(rng, 60, owners="ABCDEF", edge_p=0.06)
        started = time.monotonic()
        result = schedule(tasks, 100)
        assert time.monotonic() - started < 9
        assert validate_schedule_response({"tasks": tasks, "deadline_day": 100}, result) == []
        assert result["end_day"] >= result["proof"]["lower_bound"]["day"]
