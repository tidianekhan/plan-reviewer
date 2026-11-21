# Contracts

The application uses two fixed JSON formats: a schedule request and response, and a review output. The example files in `examples/` show these formats. All fields shown below are required.

## Scheduling

Send a JSON request to `POST /api/schedule` with a `Content-Type` of `application/json`:

```json
{"tasks": [
   {"id": "A", "name": "Book the hall", "owner": "Ann", "duration_days": 3, "depends_on": []},
   {"id": "B", "name": "Sign the contract", "owner": "Ann", "duration_days": 2, "depends_on": ["A"]},
   {"id": "C", "name": "Design the poster", "owner": "Ann", "duration_days": 4, "depends_on": []},
   {"id": "D", "name": "Print the poster", "owner": "Bob", "duration_days": 2, "depends_on": ["C"]}
 ],
 "deadline_day": 10}
```

`tasks` is a list of at most 60 tasks. Each task has a unique string `id`, a string `name`, an `owner` that is a string or `null`, an integer `duration_days` of at least 1, and a `depends_on` list of string ids present in the request. `deadline_day` is an integer. The endpoint must answer within 10 seconds.

A successful schedule returns HTTP 200 with this format, as shown in `examples/schedule-response.json`:

```json
{"status": "scheduled",
 "schedule": [
   {"id": "C", "start_day": 0, "end_day": 4},
   {"id": "A", "start_day": 4, "end_day": 7},
   {"id": "B", "start_day": 7, "end_day": 9},
   {"id": "D", "start_day": 4, "end_day": 6}],
 "end_day": 9, "deadline_day": 10, "meets_deadline": true, "days_late": 0, "cycle": []}
```

Each requested task id appears exactly once in `schedule`, with no additional ids. Each entry contains `id`, `start_day`, and `end_day`. Times are integer days from day 0, and `start_day` is at least 0. A week is 7 days. A task starting on day `s` with duration `d` occupies days from `s` up to, but not including, `s + d`. Its `end_day` is `s + d`, so `end_day - start_day` must equal `duration_days`.

A task starts at or after the `end_day` of every task in its `depends_on` list. Two tasks with the same non-null owner never overlap. One may start exactly when the other ends. Tasks with owner `null` have no person limit. The goal is the smallest overall `end_day`.

The response's top-level `end_day` is the largest task `end_day` (0 for an empty schedule). Its `deadline_day` equals the request's deadline. `meets_deadline` is the boolean result of `end_day <= deadline_day`, and the integer `days_late` is `max(0, end_day - deadline_day)`. The `cycle` list is empty when `status` is `"scheduled"`.

A circular dependency also returns HTTP 200. For example, if A depends on B and B depends on A, a response is:

```json
{"status": "cycle", "schedule": [], "end_day": null, "deadline_day": 10, "meets_deadline": null, "days_late": null, "cycle": ["B", "A"]}
```

Here `schedule` is empty, `end_day`, `meets_deadline`, and `days_late` are null, and `cycle` is a non-empty list of request ids that lie on one circular dependency. A task that depends on itself is a cycle.

Invalid input, including duplicate task ids, an unknown id in `depends_on`, a `duration_days` below 1, or more than 60 tasks, returns any HTTP 4xx status with a JSON body.

## Review output

Run `./review <plan.md> <out.json>` from the repository root. It writes JSON in this format, as shown in `examples/review-output.json`:

```json
{"deadline_day": 10,
 "tasks": [{"id": "T1", "name": "Book the hall", "owner": "Ann", "duration_days": 3,
            "depends_on": [], "quote": "Ann books the hall, which takes three days."}],
 "findings": [{"title": "No owner for the clean-up", "detail": "Nobody is named for it.",
               "quote": "Clean-up happens the morning after."}]}
```

`deadline_day` is an integer, or `null` when the plan does not clearly state one. `tasks` and `findings` are lists. Each task has the same fields and types as a scheduling request task, plus a required string `quote` from the plan. Each finding has string `title` and `detail` fields and a required `quote` field that is a string or `null`.

Task ids must be unique, and every id in `depends_on` must identify a task in the same review.

A plan is the whole document. A task, an owner, a duration or a dependency can be stated in a table or in a sentence, and all of it counts.

When `./review` cannot produce a review, it exits with a non-zero status. We then do not read the output file.

For every non-null quote, collapse every run of whitespace in both the quote and the plan text to one space. The resulting quote must be a case-sensitive substring of the resulting plan text.

## Contract checks

Both formats may carry extra fields. The checks ignore them.

Run these commands from the repository root with Python 3. The checker uses only the standard library:

```sh
python3 check_contract.py schedule http://localhost:8000
python3 check_contract.py review examples/review-output.json
```

The schedule command posts `examples/schedule-request.json` to `<base_url>/api/schedule` and checks the response. It locates the example relative to the checker file. The review command checks the JSON file supplied. Both commands exit with code 0 when no errors are found and code 1 otherwise, printing any errors.

`validate_schedule_response(request: dict, response: dict) -> list[str]` returns shape and scheduling rule errors for a valid request, or an empty list when valid. It checks task coverage, timing, dependencies, owner overlap, and response totals. It does not prove that a schedule has the smallest possible end day. For a cycle response, it checks the response shape and that all listed ids lie on the same circular dependency in the request; a subset of its ids is acceptable.

`validate_review_shape(review: dict) -> list[str]` checks required fields and their types and returns an empty list when valid. It does not check quotes against the source plan.
