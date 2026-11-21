# Notes

## Time spent

TODO: fill in hours.

## What I did

I focused on two things Nora needs: an answer she can trust, and that answer within seconds of opening a plan.

- **Schedule.** OR-Tools CP-SAT with one interval per task, a no-overlap constraint per owner, and dependencies as precedence constraints. A greedy serial schedule is the solver's hint and also the fallback if the 7 s limit runs out (the contract allows 10 s). Cycles are found before solving and returned by name. Each response also carries a `proof` field that shows why the end day can't be earlier: the lower bound, the chain of tasks that drives it, and the days of work each owner has. A test compares the end day with brute force on random small plans.
- **Review.** The model proposes and code decides. Structured output gives the fixed format. Code then checks the ids, the dependencies, the durations, and that every quote appears word for word in the plan. Small typographic differences, such as curly quotes, are snapped to the plan's own text. Any other problem goes back to the model as a sentence, with up to 3 attempts inside 270 s. If no attempt passes, `./review` exits 1 and writes nothing. The prompt treats the plan as untrusted data and reports instructions hidden in it as findings. It also tells the model that tasks and dependencies stated only in the prose still count. On the samples, harbour-run's injection is flagged rather than obeyed, and its hidden insurance/approval cycle is named. Lantern-festival's four prose-only tasks and three prose-only dependencies are picked up, which turns it from on time into 7 days late.
- **Page.** The verdict comes first: can the plan make its date, and by how many days. Findings follow, sorted by severity. Clicking a finding or task highlights its quote in the plan text. In the task table Nora can change durations, owners, dependencies and the deadline. The schedule and timeline update live, and she can reset to the review.
- **API.** `POST /api/schedule` returns a 422 that lists readable problems. An unknown plan id gets a 404. Tests cover both contracts and the refusals.

## What I cut and why

- **The model is never called from the page.** The page shows the stored reviews. Calling the model live would add a key, cost and minutes of waiting to the web app, and the brief didn't need it.
- **Findings can't be dismissed or edited**, and task edits aren't saved after a reload. Correcting the tasks and seeing the effect on the date mattered more to Nora.
- **No uploading new plans in the page.** They go through `./review`.
- **No working calendar.** Days count from kickoff, as the plans state them, so weekends and holidays aren't modelled.

## What is not ready

- The review depends on the model to find tasks that appear only in the prose. Code can check that each task is quoted correctly, but it can't detect a task the model missed.
- When a request has several validation errors, the 422 sometimes lists only the first kind. For example, a bad duration hides an unknown dependency.
- Severity is the model's judgement and isn't checked by code.

## What I would do next and a rough estimate

- Let Nora dismiss or edit findings, and save her changes per plan (half a day).
- Re-check each finding against the schedule. For example, raise "Ruth is overloaded" to high when the solver confirms she is the bottleneck (2 h).
- A small evaluation set of plans with known traps, run on each prompt change (half a day).
- An upload page that runs the review in the background (1 day).

## How I used AI tools

I used Claude Code (Claude Opus 5.5) to write most of the code, the tests and this deploy. I checked its work in these ways:

- The scheduler is tested against brute force on random small plans, and against the contract checker locally, in Docker with `PORT=8000`, and on the live URL.
- The review pipeline's checks have their own tests: bad ids, unknown dependencies and quotes that don't match.
- I read the three generated reviews against the plans by hand. Every quote matched and every planted trap was caught. I also ran each review's tasks through the scheduler and checked that the results make sense: harbour-run returns the T2/T3 cycle, lantern-festival ends on day 52 against a deadline of 45 (Ruth alone has 52 days of work), and spring-market ends on day 18 against 21.
- The stored reviews in `data/reviews/` were written by `./review` and not edited by hand.

The review model is Claude Opus 5.5. These plans hide tasks and traps in long prose, so reading quality matters most, and the review runs offline, so its speed and cost don't affect Nora.

## Environment variables my review command needs

- `ANTHROPIC_API_KEY` (required).
- `REVIEW_MODEL` (optional, default `claude-opus-5-5`).

The web app needs neither. It reads `PORT` (default 8000).
