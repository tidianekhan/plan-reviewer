import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .scheduler import schedule

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
DIST = ROOT / "frontend" / "dist"

app = FastAPI()


@app.get("/api/plans")
def list_plans():
    plans = []
    for path in sorted((DATA / "plans").glob("*.md"), reverse=True):
        title = next((line.lstrip("# ").strip() for line in path.read_text().splitlines() if line.startswith("#")), path.stem)
        plans.append({"id": path.stem, "title": title})
    return plans


@app.get("/api/plans/{plan_id}")
def get_plan(plan_id: str):
    text = (DATA / "plans" / f"{plan_id}.md").read_text()
    review = json.loads((DATA / "reviews" / f"{plan_id}.json").read_text())
    return {
        "id": plan_id,
        "text": text,
        "review": review,
        "schedule": schedule(review["tasks"], review["deadline_day"]),
    }


@app.post("/api/schedule")
def post_schedule(body: dict):
    return schedule(body["tasks"], body["deadline_day"])


if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True))
