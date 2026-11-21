import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import ScheduleRequest
from .scheduler import schedule

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="Plan reviewer")


def _describe(err) -> str:
    where = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
    msg = err.get("msg", "is not valid").removeprefix("Value error, ")
    return f"{where}: {msg}" if where else msg


@app.exception_handler(RequestValidationError)
async def refuse_bad_input(request: Request, exc: RequestValidationError):
    problems = [_describe(e) for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": "The request is not a valid task list.", "problems": problems})


def _plan_ids():
    return sorted(p.stem for p in (DATA / "plans").glob("*.md"))


@app.get("/api/plans")
def list_plans():
    plans = []
    for plan_id in _plan_ids():
        text = (DATA / "plans" / f"{plan_id}.md").read_text()
        title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")), plan_id)
        plans.append({"id": plan_id, "title": title})
    return plans


@app.get("/api/plans/{plan_id}")
def get_plan(plan_id: str):
    if plan_id not in _plan_ids():
        raise HTTPException(404, detail=f"No plan called {plan_id!r}.")
    text = (DATA / "plans" / f"{plan_id}.md").read_text()
    review_path = DATA / "reviews" / f"{plan_id}.json"
    if not review_path.exists():
        return {"id": plan_id, "text": text, "review": None, "schedule": None}
    review = json.loads(review_path.read_text())
    return {"id": plan_id, "text": text, "review": review, "schedule": schedule(review["tasks"], review["deadline_day"])}


@app.post("/api/schedule")
def post_schedule(body: ScheduleRequest):
    return schedule([t.model_dump() for t in body.tasks], body.deadline_day)


if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True))
