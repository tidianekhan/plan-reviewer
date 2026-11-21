"""Earliest finish for a plan where tasks wait on each other and one person does one task at a time.

This is a resource-constrained scheduling problem (NP-hard in general), so we:
1. refuse circular dependencies and name the tasks on the circle,
2. build a good greedy schedule (serial schedule generation, longest remaining chain first),
3. hand that to OR-Tools CP-SAT as a starting point and let it search for, and usually prove, the optimum,
4. explain the answer: a lower bound no schedule can beat, and the chain of tasks that sets the end day.
"""

from collections import defaultdict

from ortools.sat.python import cp_model

SOLVER_SECONDS = 7.0  # the contract allows 10 s per answer


def find_cycle(tasks) -> list[str]:
    """Ids on one circular dependency, in dependency order, or [] if there is none."""
    deps = {t["id"]: t["depends_on"] for t in tasks}
    state = {}  # id -> 1 while on the DFS path, 2 when done
    for root in deps:
        if root in state:
            continue
        path, stack = [root], [(root, iter(deps[root]))]
        state[root] = 1
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                state[node] = 2
                path.pop()
                stack.pop()
            elif state.get(child) == 1:
                return path[path.index(child):]
            elif child not in state:
                state[child] = 1
                path.append(child)
                stack.append((child, iter(deps[child])))
    return []


def _tails(tasks, by_id):
    """Longest chain from the start of each task to the end of the plan, ignoring people."""
    children = defaultdict(list)
    for t in tasks:
        for d in t["depends_on"]:
            children[d].append(t["id"])
    memo = {}
    for t in reversed(_topo_order(tasks)):
        memo[t] = by_id[t]["duration_days"] + max((memo[c] for c in children[t]), default=0)
    return memo, children


def _topo_order(tasks):
    order, seen = [], set()
    deps = {t["id"]: t["depends_on"] for t in tasks}
    for root in deps:
        stack = [(root, False)]
        while stack:
            node, done = stack.pop()
            if done:
                order.append(node)
            elif node not in seen:
                seen.add(node)
                stack.append((node, True))
                stack.extend((d, False) for d in deps[node] if d not in seen)
    return order


def greedy_schedule(tasks) -> dict[str, int]:
    """Serial schedule generation: place tasks one by one, each at the earliest gap its owner has free."""
    by_id = {t["id"]: t for t in tasks}
    tail, _ = _tails(tasks, by_id)
    start, busy = {}, defaultdict(list)  # owner -> [(start, end)]
    remaining = set(by_id)
    while remaining:
        ready = [i for i in remaining if all(d in start for d in by_id[i]["depends_on"])]
        tid = max(ready, key=lambda i: (tail[i], i))
        t = by_id[tid]
        s = max((start[d] + by_id[d]["duration_days"] for d in t["depends_on"]), default=0)
        if t["owner"] is not None:
            for bs, be in sorted(busy[t["owner"]]):
                if s + t["duration_days"] <= bs:
                    break
                s = max(s, be)
            busy[t["owner"]].append((s, s + t["duration_days"]))
        start[tid] = s
        remaining.remove(tid)
    return start


def lower_bound(tasks):
    """A day no schedule can beat, and why: the longest dependency chain or the busiest person."""
    by_id = {t["id"]: t for t in tasks}
    tail, children = _tails(tasks, by_id)
    best = {"day": 0, "kind": "empty", "tasks": [], "owner": None}
    if tasks:
        tid = max(tail, key=lambda i: (tail[i], i))
        chain = [tid]
        while children[tid]:
            tid = max(children[tid], key=lambda i: (tail[i], i))
            chain.append(tid)
        best = {"day": tail[chain[0]], "kind": "chain", "tasks": chain, "owner": None}
    load = defaultdict(int)
    for t in tasks:
        if t["owner"] is not None:
            load[t["owner"]] += t["duration_days"]
    for owner, days in sorted(load.items()):
        if days > best["day"]:
            ids = [t["id"] for t in tasks if t["owner"] == owner]
            best = {"day": days, "kind": "owner", "tasks": ids, "owner": owner}
    return best


def solve(tasks, time_limit=SOLVER_SECONDS):
    """Return ({id: start_day}, proven_optimal)."""
    hint = greedy_schedule(tasks)
    if not tasks:
        return hint, True
    horizon = sum(t["duration_days"] for t in tasks)
    m = cp_model.CpModel()
    start, end, iv = {}, {}, {}
    for t in tasks:
        i, d = t["id"], t["duration_days"]
        start[i] = m.new_int_var(0, horizon - d, f"s_{i}")
        end[i] = m.new_int_var(d, horizon, f"e_{i}")
        iv[i] = m.new_interval_var(start[i], d, end[i], f"i_{i}")
        m.add_hint(start[i], hint[i])
    for t in tasks:
        for dep in t["depends_on"]:
            m.add(start[t["id"]] >= end[dep])
    owners = defaultdict(list)
    for t in tasks:
        if t["owner"] is not None:
            owners[t["owner"]].append(iv[t["id"]])
    for intervals in owners.values():
        m.add_no_overlap(intervals)
    makespan = m.new_int_var(0, horizon, "makespan")
    m.add_max_equality(makespan, list(end.values()))
    m.minimize(makespan)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 8
    status = solver.solve(m)
    greedy_end = max(hint[t["id"]] + t["duration_days"] for t in tasks)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE) or solver.objective_value > greedy_end:
        return hint, False  # never worse than the greedy answer
    return {i: solver.value(v) for i, v in start.items()}, status == cp_model.OPTIMAL


def compact(tasks, start):
    """Pull each task as early as it can go without moving any other, so the page shows real slack."""
    by_id = {t["id"]: t for t in tasks}
    start = dict(start)
    changed = True
    while changed:
        changed = False
        for tid in sorted(start, key=lambda i: (start[i], i)):
            t = by_id[tid]
            earliest = max((start[d] + by_id[d]["duration_days"] for d in t["depends_on"]), default=0)
            if t["owner"] is not None:
                for o in tasks:
                    oe = start[o["id"]] + o["duration_days"]
                    if o["id"] != tid and o["owner"] == t["owner"] and oe <= start[tid]:
                        earliest = max(earliest, oe)
            if earliest < start[tid]:
                start[tid] = earliest
                changed = True
    return start


def driving_chain(tasks, start):
    """The tasks that set the end day: from the last task, walk back through whatever it waited for."""
    if not tasks:
        return []
    by_id = {t["id"]: t for t in tasks}
    end = {i: s + by_id[i]["duration_days"] for i, s in start.items()}
    tid = max(end, key=lambda i: (end[i], i))
    chain = [tid]
    while start[tid] > 0:
        t = by_id[tid]
        waits = [d for d in t["depends_on"] if end[d] == start[tid]]
        if not waits and t["owner"] is not None:
            waits = [o["id"] for o in tasks if o["owner"] == t["owner"] and end[o["id"]] == start[tid]]
        if not waits:
            break
        tid = waits[0]
        chain.append(tid)
    return list(reversed(chain))


def schedule(tasks, deadline_day, time_limit=SOLVER_SECONDS):
    """Tasks are dicts in the contract's request format and must already be validated.

    `deadline_day` may be None (a plan with no clear date); the totals that need it are then None too.
    """
    cycle = find_cycle(tasks)
    if cycle:
        return {
            "status": "cycle", "schedule": [], "end_day": None, "deadline_day": deadline_day,
            "meets_deadline": None, "days_late": None, "cycle": cycle,
        }
    start, optimal = solve(tasks, time_limit)
    start = compact(tasks, start)
    items = [{"id": t["id"], "start_day": start[t["id"]], "end_day": start[t["id"]] + t["duration_days"]}
             for t in tasks]
    end_day = max((i["end_day"] for i in items), default=0)
    bound = lower_bound(tasks)
    owners = sorted({t["owner"] for t in tasks if t["owner"] is not None})
    return {
        "status": "scheduled",
        "schedule": items,
        "end_day": end_day,
        "deadline_day": deadline_day,
        "meets_deadline": None if deadline_day is None else end_day <= deadline_day,
        "days_late": None if deadline_day is None else max(0, end_day - deadline_day),
        "cycle": [],
        # Extra field, allowed by the contract: why the end day can be trusted.
        "proof": {
            "optimal": optimal or end_day == bound["day"],
            "lower_bound": bound,
            "driving_chain": driving_chain(tasks, start),
            "owner_days": {o: sum(t["duration_days"] for t in tasks if t["owner"] == o) for o in owners},
        },
    }
