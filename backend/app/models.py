"""Request and review shapes shared by the API, the scheduler and the review command."""

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

MAX_TASKS = 60


class Task(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: StrictStr
    name: StrictStr
    owner: StrictStr | None
    duration_days: StrictInt = Field(ge=1)
    depends_on: list[StrictStr]


def check_task_refs(tasks: list[Task]) -> list[str]:
    """Problems with ids and dependencies, as plain sentences."""
    errors = []
    seen = set()
    for t in tasks:
        if t.id in seen:
            errors.append(f"Task id {t.id!r} is used more than once.")
        seen.add(t.id)
    for t in tasks:
        for dep in t.depends_on:
            if dep not in seen:
                errors.append(f"Task {t.id!r} depends on {dep!r}, which is not a task in this list.")
        if len(set(t.depends_on)) != len(t.depends_on):
            errors.append(f"Task {t.id!r} lists the same dependency twice.")
    return errors


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tasks: list[Task] = Field(max_length=MAX_TASKS)
    deadline_day: StrictInt

    @model_validator(mode="after")
    def _refs(self):
        errors = check_task_refs(self.tasks)
        if errors:
            raise ValueError(" ".join(errors))
        return self
