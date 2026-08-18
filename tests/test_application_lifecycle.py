from types import SimpleNamespace

import pytest

from app.core.application_history import (
    ApplicationHistory,
)
from app.core.application_lifecycle import (
    ApplicationLifecycle,
)


def job():
    return {
        "job_id": "job-001",
        "title": "Electrical Engineer",
        "company": "Example Energy",
        "location": "Hyderabad",
        "url": "https://example.com/jobs/1",
    }


class FakeHistory:
    """
    Lightweight history adapter used only to test
    lifecycle classification for states that are not
    currently part of ApplicationHistory's persisted
    status vocabulary.
    """

    def __init__(self):
        self.records = {}

    @staticmethod
    def _key(job_data):
        return (
            job_data.get("job_id")
            or job_data.get("url")
            or job_data.get("title")
        )

    def get(self, job_data):
        return self.records.get(
            self._key(job_data)
        )

    def set(
        self,
        job_data,
        *,
        status,
        attempts=0,
        updated_at=None,
    ):
        self.records[
            self._key(job_data)
        ] = SimpleNamespace(
            status=status,
            attempts=attempts,
            updated_at=updated_at,
        )


@pytest.fixture
def history(tmp_path):
    return ApplicationHistory(
        storage_path=str(
            tmp_path / "history.json"
        )
    )


@pytest.fixture
def lifecycle(history):
    return ApplicationLifecycle(
        history,
        retry_delay_minutes=0,
        follow_up_delay_days=0,
        max_retries=3,
    )


@pytest.fixture
def fake_lifecycle():
    history = FakeHistory()

    return (
        ApplicationLifecycle(
            history,
            retry_delay_minutes=0,
            follow_up_delay_days=0,
            max_retries=3,
        ),
        history,
    )


def test_new_job_is_applyable(
    lifecycle,
):
    result = lifecycle.evaluate(
        job()
    )

    assert result.action == "apply"
    assert result.eligible is True
    assert result.status == "new"


@pytest.mark.parametrize(
    "status",
    [
        "captcha_detected",
        "login_required",
        "human_action_required",
        "confirmation_required",
    ],
)
def test_human_action_states_are_blocked(
    lifecycle,
    history,
    status,
):
    history.record(
        job(),
        decision="apply",
        status=status,
        human_action_required=True,
    )

    result = lifecycle.evaluate(
        job()
    )

    assert result.action == (
        "human_action"
    )
    assert result.eligible is False
    assert (
        result.requires_human_action
        is True
    )


def test_job_unavailable_is_closed(
    lifecycle,
    history,
):
    history.record(
        job(),
        decision="apply",
        status="job_unavailable",
    )

    result = lifecycle.evaluate(
        job()
    )

    assert result.action == "closed"
    assert result.eligible is False


@pytest.mark.parametrize(
    "status",
    [
        "rejected",
        "withdrawn",
        "closed",
    ],
)
def test_external_closed_states_are_blocked(
    fake_lifecycle,
    status,
):
    lifecycle, history = (
        fake_lifecycle
    )

    history.set(
        job(),
        status=status,
    )

    result = lifecycle.evaluate(
        job()
    )

    assert result.action == "closed"
    assert result.eligible is False


@pytest.mark.parametrize(
    "status",
    [
        "submission_failed",
        "send_failed",
        "navigation_failed",
        "application_prepare_failed",
        "validation_failed",
    ],
)
def test_retryable_states_are_retryable(
    lifecycle,
    history,
    status,
):
    history.record(
        job(),
        decision="apply",
        status=status,
    )

    result = lifecycle.evaluate(
        job()
    )

    assert result.action == "retry"
    assert result.eligible is True


def test_retry_exhaustion(
    history,
):
    lifecycle = ApplicationLifecycle(
        history,
        retry_delay_minutes=0,
        max_retries=1,
    )

    history.record(
        job(),
        decision="apply",
        status="submission_failed",
    )

    history.record(
        job(),
        decision="apply",
        status="submission_failed",
    )

    result = lifecycle.evaluate(
        job()
    )

    assert result.action == (
        "retry_exhausted"
    )
    assert result.eligible is False


def test_applied_application_is_follow_up_eligible(
    lifecycle,
    history,
):
    history.record(
        job(),
        decision="apply",
        status="applied",
        submitted=True,
    )

    result = lifecycle.evaluate(
        job()
    )

    assert result.action == "follow_up"
    assert result.eligible is True


def test_follow_up_due(
    lifecycle,
    history,
):
    history.record(
        job(),
        decision="apply",
        status="applied",
        submitted=True,
    )

    result = lifecycle.follow_up_due(
        job()
    )

    assert result.action == (
        "follow_up"
    )
    assert result.eligible is True


def test_follow_up_not_due(
    history,
):
    lifecycle = ApplicationLifecycle(
        history,
        follow_up_delay_days=7,
    )

    history.record(
        job(),
        decision="apply",
        status="applied",
        submitted=True,
    )

    result = lifecycle.follow_up_due(
        job()
    )

    assert result.action == (
        "wait_follow_up"
    )
    assert result.eligible is False
    assert result.due_at is not None


def test_unknown_status_requires_review(
    fake_lifecycle,
):
    lifecycle, history = (
        fake_lifecycle
    )

    history.set(
        job(),
        status="something_unknown",
    )

    result = lifecycle.evaluate(
        job()
    )

    assert result.action == "review"
    assert result.eligible is False
    assert (
        result.requires_human_action
        is True
    )


def test_evaluate_many_requires_list(
    lifecycle,
):
    with pytest.raises(
        TypeError,
        match="jobs must be a list",
    ):
        lifecycle.evaluate_many(
            tuple()
        )


def test_follow_ups_due_returns_only_due_jobs(
    lifecycle,
    history,
):
    first = job()

    second = {
        **job(),
        "job_id": "job-002",
        "url": "https://example.com/jobs/2",
    }

    history.record(
        first,
        decision="apply",
        status="applied",
        submitted=True,
    )

    history.record(
        second,
        decision="apply",
        status="submission_failed",
    )

    results = (
        lifecycle.follow_ups_due(
            [
                first,
                second,
            ]
        )
    )

    assert len(results) == 1

    assert (
        results[0]["job"]["job_id"]
        == "job-001"
    )

    assert (
        results[0]["action"].action
        == "follow_up"
    )