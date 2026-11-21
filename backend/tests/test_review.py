import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import review as rv  # noqa: E402

PLAN = "# Fair\n\nAnn books   the hall, which takes three days.\nBob’s team – the crew – sets up.\n"


def task(id="T1", quote="Ann books the hall", deps=(), duration=3):
    return {"id": id, "name": "Book", "owner": "Ann", "duration_days": duration, "depends_on": list(deps), "quote": quote}


def finding(quote=None, severity="medium"):
    return {"title": "t", "detail": "d", "quote": quote, "severity": severity}


def reply(tasks, findings=(), deadline=10, stop="end_turn"):
    parsed = rv.Review.model_validate({"deadline_day": deadline, "tasks": tasks, "findings": list(findings)})
    return SimpleNamespace(parsed_output=parsed, stop_reason=stop, content=[])


class FakeClient:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs):
        self.calls.append([dict(m) for m in kwargs["messages"]])
        return self.replies.pop(0)


def test_quote_rule_collapses_whitespace_and_is_case_sensitive():
    assert rv.quote_in_plan("Ann books the hall,", PLAN)
    assert not rv.quote_in_plan("ann books the hall", PLAN)
    assert not rv.quote_in_plan("   ", PLAN)


def test_snap_returns_the_plans_own_characters():
    snapped = rv.snap_quote("Bob's team - the crew - sets up.", PLAN)
    assert snapped == "Bob’s team – the crew – sets up."
    assert rv.quote_in_plan(snapped, PLAN)
    assert rv.snap_quote("Carol books the hall", PLAN) is None


def test_check_catches_every_kind_of_problem():
    bad = {"deadline_day": 3, "tasks": [task(), task(quote="invented"), task("T2", deps=["T9"], duration=0)],
           "findings": [finding("made up")]}
    problems = " ".join(rv.check_review(bad, PLAN))
    assert "greater than or equal to 1" in problems
    good_shape = {"deadline_day": 3, "tasks": [task(), task(quote="invented"), task("T2", deps=["T9"])],
                  "findings": [finding("made up")]}
    problems = " ".join(rv.check_review(good_shape, PLAN))
    for needle in ["more than once", "'T9'", "task T1 is not word for word", "'t' is not word for word"]:
        assert needle in problems


def test_a_good_review_is_accepted_and_findings_sorted():
    client = FakeClient(reply([task()], [finding(severity="low"), finding("Ann books", "high")]))
    out = rv.review_plan(PLAN, client)
    assert [f["severity"] for f in out["findings"]] == ["high", "low"]
    assert len(client.calls) == 1


def test_a_bad_quote_is_sent_back_and_the_correction_accepted():
    client = FakeClient(reply([task(quote="Ann reserves the hall")]), reply([task()]))
    out = rv.review_plan(PLAN, client)
    assert out["tasks"][0]["quote"] == "Ann books the hall"
    feedback = client.calls[1][-1]["content"]
    assert "not word for word" in feedback and "Ann reserves the hall" in feedback


def test_unusable_answers_are_refused_not_shown():
    client = FakeClient(*[reply([task(deps=["T1"]), task()])] * rv.MAX_ATTEMPTS)
    with pytest.raises(rv.ReviewError, match="No usable review"):
        rv.review_plan(PLAN, client)


def test_refusal_and_truncation_are_errors():
    with pytest.raises(rv.ReviewError, match="declined"):
        rv.review_plan(PLAN, FakeClient(reply([task()], stop="refusal")))
    with pytest.raises(rv.ReviewError, match="cut off"):
        rv.review_plan(PLAN, FakeClient(*[reply([task()], stop="max_tokens")] * rv.MAX_ATTEMPTS))


def test_command_exits_non_zero_and_writes_nothing_on_failure(tmp_path, monkeypatch):
    plan = tmp_path / "p.md"
    plan.write_text(PLAN)
    out = tmp_path / "out.json"
    monkeypatch.setattr(rv, "review_plan", lambda *a, **k: (_ for _ in ()).throw(rv.ReviewError("nope")))
    assert rv.main(["review", str(plan), str(out)]) == 1
    assert not out.exists()
    assert rv.main(["review", str(tmp_path / "missing.md"), str(out)]) == 2
    assert rv.main(["review"]) == 2
