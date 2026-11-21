def schedule(tasks, deadline_day):
    by_id = {t["id"]: t for t in tasks}

    def end_of(task):
        start = max([end_of(by_id[d]) for d in task["depends_on"]], default=0)
        return start + task["duration_days"]

    items = []
    for t in tasks:
        end = end_of(t)
        items.append({"id": t["id"], "start_day": end - t["duration_days"], "end_day": end})

    end_day = max([i["end_day"] for i in items], default=0)
    return {
        "status": "scheduled",
        "schedule": items,
        "end_day": end_day,
        "deadline_day": deadline_day,
        "meets_deadline": end_day <= deadline_day,
        "days_late": max(0, end_day - deadline_day),
        "cycle": [],
    }
