"""Check schedule responses and review JSON with Python's standard library."""

import json
import os
import sys
import urllib.request


def validate_schedule_response(request: dict, response: dict) -> list[str]:
    """Return response shape and scheduling rule errors for a valid request."""
    if not isinstance(response, dict):
        return ["response must be an object"]

    errors = []
    fields = ("status", "schedule", "end_day", "deadline_day", "meets_deadline", "days_late", "cycle")
    for field in fields:
        if field not in response:
            errors.append(f"missing {field}")
    if errors:
        return errors

    tasks = {task["id"]: task for task in request["tasks"]}
    if type(response["deadline_day"]) is not int or response["deadline_day"] != request["deadline_day"]:
        errors.append("deadline_day must match the request integer")

    if response["status"] == "cycle":
        if response["schedule"] != []:
            errors.append("cycle schedule must be empty")
        for field in ("end_day", "meets_deadline", "days_late"):
            if response[field] is not None:
                errors.append(f"cycle {field} must be null")
        cycle = response["cycle"]
        if not isinstance(cycle, list) or not cycle:
            errors.append("cycle must be a non-empty list of request ids")
        elif any(not isinstance(task_id, str) or task_id not in tasks for task_id in cycle):
            errors.append("cycle must contain only request ids")
        else:
            reachable = {}
            for task_id, task in tasks.items():
                pending = list(task["depends_on"])
                visited = set()
                while pending:
                    dependency = pending.pop()
                    if dependency not in visited:
                        visited.add(dependency)
                        pending.extend(tasks[dependency]["depends_on"])
                reachable[task_id] = visited
            first = cycle[0]
            if first not in reachable[first] or any(
                task_id not in reachable[first] or first not in reachable[task_id]
                for task_id in cycle
            ):
                errors.append("cycle ids must lie on one circular dependency")
        return errors

    if response["status"] != "scheduled":
        return errors + ["status must be scheduled or cycle"]
    if response["cycle"] != []:
        errors.append("scheduled cycle must be empty")
    for field in ("end_day", "days_late"):
        if type(response[field]) is not int:
            errors.append(f"{field} must be an integer")
    if type(response["meets_deadline"]) is not bool:
        errors.append("meets_deadline must be a boolean")
    if not isinstance(response["schedule"], list):
        return errors + ["schedule must be a list"]

    scheduled = {}
    for index, entry in enumerate(response["schedule"]):
        prefix = f"schedule[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("id", "start_day", "end_day"):
            if field not in entry:
                errors.append(f"{prefix} missing {field}")
        task_id = entry.get("id")
        if not isinstance(task_id, str) or task_id not in tasks:
            errors.append(f"{prefix} id must be an id from the request")
            continue
        if task_id in scheduled:
            errors.append(f"{prefix} duplicate id {task_id}")
        scheduled[task_id] = entry
        if type(entry.get("start_day")) is not int or entry["start_day"] < 0:
            errors.append(f"{prefix} start_day must be a non-negative integer")
        if type(entry.get("end_day")) is not int:
            errors.append(f"{prefix} end_day must be an integer")

    for task_id in tasks:
        if task_id not in scheduled:
            errors.append(f"missing task {task_id} from schedule")
    if errors:
        return errors

    for task_id, entry in scheduled.items():
        task = tasks[task_id]
        if entry["end_day"] - entry["start_day"] != task["duration_days"]:
            errors.append(f"task {task_id} end_day must equal start_day + duration_days")
        for dependency in task["depends_on"]:
            if entry["start_day"] < scheduled[dependency]["end_day"]:
                errors.append(f"task {task_id} depends on {dependency} and starts before its end_day")

    entries = list(scheduled.values())
    for index, entry in enumerate(entries):
        owner = tasks[entry["id"]]["owner"]
        if owner is None:
            continue
        for other in entries[index + 1:]:
            if owner == tasks[other["id"]]["owner"] and max(entry["start_day"], other["start_day"]) < min(entry["end_day"], other["end_day"]):
                errors.append(f"tasks {entry['id']} and {other['id']} overlap for owner {owner}")

    end_day = max((entry["end_day"] for entry in entries), default=0)
    if response["end_day"] != end_day:
        errors.append("end_day must equal the largest task end_day")
    if response["meets_deadline"] != (response["end_day"] <= request["deadline_day"]):
        errors.append("meets_deadline must equal (end_day <= deadline_day)")
    if response["days_late"] != max(0, response["end_day"] - request["deadline_day"]):
        errors.append("days_late must equal max(0, end_day - deadline_day)")
    return errors


def validate_review_shape(review: dict) -> list[str]:
    """Check required fields and types without checking quotes against a plan."""
    if not isinstance(review, dict):
        return ["review must be an object"]
    errors = []
    if "deadline_day" not in review:
        errors.append("missing deadline_day")
    elif review["deadline_day"] is not None and type(review["deadline_day"]) is not int:
        errors.append("deadline_day must be an integer or null")

    tasks = review.get("tasks")
    task_ids = {
        task["id"] for task in tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    } if isinstance(tasks, list) else set()
    seen_ids = set()
    for collection, string_fields in (
        ("tasks", ("id", "name", "quote")),
        ("findings", ("title", "detail", "quote")),
    ):
        if collection not in review:
            errors.append(f"missing {collection}")
            continue
        if not isinstance(review[collection], list):
            errors.append(f"{collection} must be a list")
            continue
        for index, item in enumerate(review[collection]):
            prefix = f"{collection}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object")
                continue
            for field in string_fields:
                if field not in item:
                    errors.append(f"{prefix} missing {field}")
                elif collection == "findings" and field == "quote" and item[field] is None:
                    continue
                elif not isinstance(item[field], str):
                    errors.append(f"{prefix} {field} must be a string" + (" or null" if collection == "findings" and field == "quote" else ""))
            if collection == "tasks":
                task_id = item.get("id")
                if isinstance(task_id, str):
                    if task_id in seen_ids:
                        errors.append(f"{prefix} duplicate id {task_id}")
                    seen_ids.add(task_id)
                if "owner" not in item:
                    errors.append(f"{prefix} missing owner")
                elif item["owner"] is not None and not isinstance(item["owner"], str):
                    errors.append(f"{prefix} owner must be a string or null")
                if type(item.get("duration_days")) is not int or item["duration_days"] < 1:
                    errors.append(f"{prefix} duration_days must be an integer of at least 1")
                if not isinstance(item.get("depends_on"), list) or any(not isinstance(task_id, str) for task_id in item["depends_on"]):
                    errors.append(f"{prefix} depends_on must be a list of ids")
                else:
                    for dependency in item["depends_on"]:
                        if dependency not in task_ids:
                            errors.append(f"{prefix} unknown depends_on id {dependency}")
    return errors


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in ("schedule", "review"):
        print("Usage: python3 check_contract.py schedule <base_url> | review <file.json>")
        return 1
    try:
        if sys.argv[1] == "review":
            with open(sys.argv[2], encoding="utf-8") as source:
                errors = validate_review_shape(json.load(source))
        else:
            example = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples", "schedule-request.json")
            with open(example, encoding="utf-8") as source:
                request = json.load(source)
            http_request = urllib.request.Request(
                sys.argv[2].rstrip("/") + "/api/schedule",
                data=json.dumps(request).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(http_request, timeout=10) as result:
                errors = validate_schedule_response(request, json.load(result))
    except (OSError, ValueError) as error:
        errors = [str(error)]
    for error in errors:
        print(error)
    if not errors:
        print("Contract check passed.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
