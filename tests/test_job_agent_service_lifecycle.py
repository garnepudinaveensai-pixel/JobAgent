from app.core.application_execution_router import ExecutionResult
from app.core.application_history import ApplicationHistory
from app.core.application_lifecycle import ApplicationLifecycle
from app.core.job_agent_service import JobAgentService


def make_job(job_id="job-001"):
    return {
        "job_id": job_id,
        "title": "Electrical Engineer",
        "company": "Example Energy",
        "location": "Hyderabad",
        "url": f"https://example.com/jobs/{job_id}",
    }


def make_ranked(job_id="job-001"):
    return {
        "ranking_score": 91.5,
        "job": make_job(job_id),
        "match": {
            "selected_resume": {
                "filename": "technical_resume.pdf",
            }
        },
    }


class FakeRunner:
    """
    Minimal runner for service-unit tests.

    The lifecycle tests do not exercise discovery, so the real
    EndToEndPipeline must not be constructed from this fake.
    """


class FakeEndToEndPipeline:
    """
    Minimal pipeline stub required by JobAgentService.

    It is intentionally small because these tests exercise
    lifecycle/history/decision/router orchestration only.
    """

    outreach_pipeline = None

    def resolve_resume_path(self, ranked_result):
        return None


class FakeDecision:
    def __init__(self, decision):
        self.decision = decision


class FakeDecisionEngine:
    def __init__(self, decision="apply"):
        self.decision = decision
        self.calls = 0

    def decide(self, ranked_result):
        self.calls += 1
        return FakeDecision(self.decision)


class FakeRouter:
    def __init__(self, result=None):
        self.calls = []

        self.result = result or ExecutionResult(
            success=True,
            decision="apply",
            status="prepared",
            message="Prepared.",
            job=make_job(),
            ranking_score=91.5,
        )

    def route(self, ranked_result, **kwargs):
        self.calls.append(
            (ranked_result, kwargs)
        )
        return self.result


def make_service(tmp_path, router=None):
    history = ApplicationHistory(
        storage_path=str(
            tmp_path / "history.json"
        )
    )

    lifecycle = ApplicationLifecycle(
        history,
        retry_delay_minutes=0,
        follow_up_delay_days=0,
    )

    engine = FakeDecisionEngine()
    router = router or FakeRouter()

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakeEndToEndPipeline(),
        decision_engine=engine,
        execution_router=router,
        application_history=history,
        application_lifecycle=lifecycle,
    )

    return (
        service,
        history,
        lifecycle,
        engine,
        router,
    )


def test_new_job_reaches_router(tmp_path):
    (
        service,
        _,
        _,
        engine,
        router,
    ) = make_service(tmp_path)

    result = service.execute_ranked_job(
        make_ranked(),
        page=object(),
    )

    assert result.success is True
    assert result.status == "prepared"
    assert engine.calls == 1
    assert len(router.calls) == 1


def test_applied_job_is_blocked_by_lifecycle(tmp_path):
    (
        service,
        history,
        _,
        engine,
        router,
    ) = make_service(tmp_path)

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
    assert result.status == "duplicate_prevented"
    assert result.decision == "skip"
    assert result.metadata[
        "duplicate_prevented"
    ] is True
    assert result.metadata[
        "history_status"
    ] == "applied"
    assert engine.calls == 0
    assert len(router.calls) == 0


def test_captcha_requires_human_action(tmp_path):
    (
        service,
        history,
        _,
        engine,
        router,
    ) = make_service(tmp_path)

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

    assert result.success is False
    assert result.status == "human_action_required"
    assert result.requires_human_action is True
    assert engine.calls == 0
    assert len(router.calls) == 0


def test_failed_application_can_retry(tmp_path):
    failure = ExecutionResult(
        success=False,
        decision="apply",
        status="submission_failed",
        message="Submission failed.",
        job=make_job(),
        ranking_score=91.5,
        error="browser failure",
    )

    (
        service,
        history,
        _,
        engine,
        router,
    ) = make_service(
        tmp_path,
        router=FakeRouter(
            result=failure
        ),
    )

    history.record(
        make_job(),
        decision="apply",
        status="submission_failed",
    )

    result = service.execute_ranked_job(
        make_ranked(),
        page=object(),
    )

    assert result.success is False
    assert result.status == "submission_failed"
    assert result.error == "browser failure"
    assert engine.calls == 1
    assert len(router.calls) == 1


def test_closed_job_is_not_executed(tmp_path):
    (
        service,
        history,
        _,
        engine,
        router,
    ) = make_service(tmp_path)

    history.record(
        make_job(),
        decision="apply",
        status="job_unavailable",
    )

    result = service.execute_ranked_job(
        make_ranked(),
        page=object(),
    )

    assert result.status == "closed"
    assert result.success is True
    assert result.decision == "skip"
    assert engine.calls == 0
    assert len(router.calls) == 0


def test_lifecycle_can_be_disabled(tmp_path):
    history = ApplicationHistory(
        storage_path=str(
            tmp_path / "history.json"
        )
    )

    engine = FakeDecisionEngine()
    router = FakeRouter()

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakeEndToEndPipeline(),
        decision_engine=engine,
        execution_router=router,
        application_history=history,
        application_lifecycle=None,
    )

    result = service.execute_ranked_job(
        make_ranked(),
        page=object(),
    )

    assert result.success is True
    assert result.status == "prepared"
    assert engine.calls == 1
    assert len(router.calls) == 1
