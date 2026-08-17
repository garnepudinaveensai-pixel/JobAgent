from pathlib import Path
from typing import Any

from app.core.application_history import ApplicationHistory
from app.core.application_execution_router import ExecutionResult
from app.core.job_agent_service import JobAgentService


# ============================================================
# TEST DATA
# ============================================================


def make_job():
    return {
        "job_id": "job-history-001",
        "title": "Electrical Engineer",
        "company": "Example Energy",
        "location": "Hyderabad",
        "url": "https://example.com/jobs/1",
    }


def make_ranked():
    return {
        "ranking_score": 91.5,
        "job": make_job(),
        "match": {
            "selected_resume": {
                "filename": "technical_resume.pdf",
            }
        },
    }


# ============================================================
# FAKES
# ============================================================


class FakeRunner:
    """
    Minimal runner.

    The service tests below do not exercise discovery or ranking,
    so the runner only needs to exist.
    """

    pass


class FakeEndToEnd:
    """
    Minimal EndToEndPipeline replacement.

    Injecting this prevents JobAgentService from constructing the
    real EndToEndPipeline during isolated service tests.
    """

    def __init__(self):
        self.discover_calls = []
        self.contact_calls = []
        self.resume_calls = []

    def discover_and_rank(
        self,
        **kwargs,
    ):
        self.discover_calls.append(kwargs)
        return []

    def discover_contacts(
        self,
        job,
        **kwargs,
    ):
        self.contact_calls.append(
            (
                job,
                kwargs,
            )
        )
        return []

    def resolve_resume_path(
        self,
        ranked_result,
    ):
        self.resume_calls.append(
            ranked_result
        )
        return None


class FakeDecision:
    def __init__(
        self,
        decision,
    ):
        self.decision = decision


class FakeDecisionEngine:
    def __init__(
        self,
        decision="apply",
    ):
        self.decision = decision
        self.calls = 0

    def decide(
        self,
        ranked_result,
    ):
        self.calls += 1

        return FakeDecision(
            self.decision
        )


class FakeRouter:
    def __init__(
        self,
        result=None,
    ):
        self.calls = []

        self.result = (
            result
            if result is not None
            else ExecutionResult(
                success=True,
                decision="apply",
                status="prepared",
                message="Prepared.",
                job=make_job(),
                ranking_score=91.5,
            )
        )

    def route(
        self,
        ranked_result,
        **kwargs,
    ):
        self.calls.append(
            (
                ranked_result,
                kwargs,
            )
        )

        return self.result


# ============================================================
# SERVICE FACTORY
# ============================================================


def make_service(
    tmp_path,
    *,
    router=None,
    decision="apply",
):
    history = ApplicationHistory(
        storage_path=str(
            tmp_path
            / "application_history.json"
        )
    )

    runner = FakeRunner()
    end_to_end = FakeEndToEnd()

    engine = FakeDecisionEngine(
        decision
    )

    router = (
        router
        if router is not None
        else FakeRouter()
    )

    service = JobAgentService(
        runner,
        end_to_end_pipeline=end_to_end,
        decision_engine=engine,
        execution_router=router,
        application_history=history,
    )

    return (
        service,
        history,
        engine,
        router,
    )


# ============================================================
# NEW JOB
# ============================================================


def test_new_job_is_executed_and_recorded(
    tmp_path,
):
    service, history, engine, router = (
        make_service(tmp_path)
    )

    result = service.execute_ranked_job(
        make_ranked(),
        page=object(),
    )

    assert result.success is True

    assert len(
        router.calls
    ) == 1

    assert engine.calls == 1

    record = history.get(
        make_job()
    )

    assert record is not None

    assert record.status == (
        "prepared"
    )

    assert record.decision == (
        "apply"
    )


# ============================================================
# DUPLICATE APPLICATION
# ============================================================


def test_applied_job_is_blocked_before_decision_or_router(
    tmp_path,
):
    service, history, engine, router = (
        make_service(tmp_path)
    )

    history.record(
        make_job(),
        decision="apply",
        status="applied",
        submitted=True,
    )

    result = service.execute_ranked_job(
        make_ranked(),
        page=object(),
    )

    assert result.success is True

    assert result.decision == (
        "skip"
    )

    assert result.status == (
        "duplicate_prevented"
    )

    assert (
        result.metadata[
            "duplicate_prevented"
        ]
        is True
    )

    assert (
        result.metadata[
            "history_status"
        ]
        == "applied"
    )

    assert result.submitted is False

    assert len(
        router.calls
    ) == 0

    assert engine.calls == 0


# ============================================================
# CAPTCHA / HUMAN ACTION
# ============================================================


def test_captcha_history_requires_human_action_and_blocks_retry(
    tmp_path,
):
    service, history, engine, router = (
        make_service(tmp_path)
    )

    history.record(
        make_job(),
        decision="apply",
        status="captcha_detected",
        human_action_required=True,
    )

    result = service.execute_ranked_job(
        make_ranked(),
        page=object(),
    )

    assert result.status == (
        "duplicate_prevented"
    )

    assert (
        result.requires_human_action
        is True
    )

    assert (
        result.metadata[
            "history_status"
        ]
        == "captcha_detected"
    )

    assert len(
        router.calls
    ) == 0

    assert engine.calls == 0


# ============================================================
# SUBMISSION FAILURE
# ============================================================


def test_submission_failure_is_recorded_and_remains_retryable(
    tmp_path,
):
    failure = ExecutionResult(
        success=False,
        decision="apply",
        status="submission_failed",
        message="Submission failed.",
        job=make_job(),
        ranking_score=91.5,
        error="SMTP/browser failure",
    )

    router = FakeRouter(
        result=failure
    )

    service, history, engine, _ = (
        make_service(
            tmp_path,
            router=router,
        )
    )

    result = service.execute_ranked_job(
        make_ranked(),
        page=object(),
    )

    assert result.status == (
        "submission_failed"
    )

    record = history.get(
        make_job()
    )

    assert record is not None

    assert record.status == (
        "submission_failed"
    )

    assert record.error == (
        "SMTP/browser failure"
    )


# ============================================================
# VALIDATION FAILURE
# ============================================================


def test_validation_failure_does_not_permanently_block_retry(
    tmp_path,
):
    service, history, engine, router = (
        make_service(tmp_path)
    )

    history.record(
        make_job(),
        decision="apply",
        status="validation_failed",
    )

    result = service.execute_ranked_job(
        make_ranked(),
        page=object(),
    )

    assert result.status == (
        "prepared"
    )

    assert len(
        router.calls
    ) == 1

    assert engine.calls == 1

    record = history.get(
        make_job()
    )

    assert record is not None

    assert record.status == (
        "prepared"
    )


# ============================================================
# BATCH DUPLICATE PREVENTION
# ============================================================


def test_batch_prevents_duplicate_without_skipping_other_jobs(
    tmp_path,
):
    history = ApplicationHistory(
        storage_path=str(
            tmp_path
            / "application_history.json"
        )
    )

    first = make_ranked()

    second = make_ranked()

    second["job"] = {
        **make_job(),
        "job_id": "job-history-002",
        "url": "https://example.com/jobs/2",
        "title": "Power Engineer",
    }

    history.record(
        first["job"],
        decision="apply",
        status="applied",
        submitted=True,
    )

    router = FakeRouter()

    engine = FakeDecisionEngine(
        "apply"
    )

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakeEndToEnd(),
        decision_engine=engine,
        execution_router=router,
        application_history=history,
    )

    results = (
        service.execute_ranked_jobs(
            [first, second],
            page_factory=(
                lambda ranked: object()
            ),
        )
    )

    assert len(results) == 2

    assert (
        results[0].status
        == "duplicate_prevented"
    )

    assert (
        results[1].status
        == "prepared"
    )

    assert len(
        router.calls
    ) == 1

    assert engine.calls == 1


# ============================================================
# HISTORY DISABLED
# ============================================================


def test_history_disabled_preserves_existing_behavior(
    tmp_path,
):
    router = FakeRouter()

    engine = FakeDecisionEngine(
        "apply"
    )

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakeEndToEnd(),
        decision_engine=engine,
        execution_router=router,
        application_history=None,
    )

    result = service.execute_ranked_job(
        make_ranked(),
        page=object(),
    )

    assert result.status == (
        "prepared"
    )

    assert len(
        router.calls
    ) == 1

    assert engine.calls == 1