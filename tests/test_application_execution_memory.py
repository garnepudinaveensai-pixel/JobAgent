from app.agents.agent_memory import AgentMemory
from app.core.application_execution_router import (
    ApplicationExecutionRouter,
)
from app.core.application_decision_engine import (
    ApplicationDecision,
    APPLY,
    OUTREACH,
    REVIEW,
    SKIP,
)


class FakeApplicationPipeline:
    def prepare_application(self, **kwargs):
        return {
            "success": True,
            "status": "prepared",
        }

    def submit_application(self, prepared, confirm=False):
        assert confirm is True
        return {
            "success": True,
            "submitted": True,
            "status": "applied",
        }


class FakeFailingApplicationPipeline:
    def prepare_application(self, **kwargs):
        return {
            "success": True,
            "status": "prepared",
        }

    def submit_application(self, prepared, confirm=False):
        assert confirm is True
        return {
            "success": False,
            "submitted": False,
            "status": "application_submit_failed",
        }


class FakeOutreachPipeline:
    def prepare_outreach(self, **kwargs):
        return {
            "success": True,
            "status": "prepared",
        }

    def send_outreach(self, **kwargs):
        assert kwargs.get("confirm") is True
        return {
            "success": True,
            "sent": True,
            "status": "sent",
        }


class FakeReviewHandler:
    def add(self, ranked_result):
        return {
            "success": True,
            "queued": True,
        }


def make_decision(value):
    return ApplicationDecision(
        decision=value,
        reason="test decision",
        ranking_score=90.0,
        match_score=90.0,
        eligible=True,
    )


def electrical_job():
    return {
        "title": "Electrical Engineer",
        "description": (
            "Electrical engineering, "
            "power systems and maintenance."
        ),
        "role_class": "electrical_core",
    }


def get_history(memory):
    return memory.history(
        event="application_outcome"
    )


def test_successful_application_is_recorded_in_memory(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    router = ApplicationExecutionRouter(
        application_pipeline=FakeApplicationPipeline(),
        memory=memory,
    )

    result = router.route(
        {
            "job": electrical_job(),
            "ranking_score": 90,
        },
        decision=make_decision(APPLY),
        confirm=True,
    )

    assert result.success is True
    assert result.submitted is True

    history = get_history(memory)

    assert len(history) == 1
    assert (
        history[0]["role_class"]
        == "electrical_core"
    )
    assert (
        history[0]["outcome"]
        == "applied"
    )


def test_failed_application_is_recorded_in_memory(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    router = ApplicationExecutionRouter(
        application_pipeline=(
            FakeFailingApplicationPipeline()
        ),
        memory=memory,
    )

    result = router.route(
        {
            "job": electrical_job(),
            "ranking_score": 90,
        },
        decision=make_decision(APPLY),
        confirm=True,
    )

    assert result.success is False

    history = get_history(memory)

    assert len(history) == 1
    assert (
        history[0]["role_class"]
        == "electrical_core"
    )
    assert (
        history[0]["outcome"]
        == "failed"
    )


def test_dry_run_does_not_record_real_application(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    router = ApplicationExecutionRouter(
        application_pipeline=FakeApplicationPipeline(),
        memory=memory,
    )

    result = router.route(
        {
            "job": electrical_job(),
            "ranking_score": 90,
        },
        decision=make_decision(APPLY),
        confirm=True,
        dry_run=True,
    )

    assert result.success is True
    assert result.submitted is False

    history = get_history(memory)

    assert history == []


def test_confirmation_required_does_not_record_application(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    router = ApplicationExecutionRouter(
        application_pipeline=FakeApplicationPipeline(),
        memory=memory,
    )

    result = router.route(
        {
            "job": electrical_job(),
            "ranking_score": 90,
        },
        decision=make_decision(APPLY),
        confirm=False,
    )

    assert (
        result.status
        == "confirmation_required"
    )

    history = get_history(memory)

    assert history == []


def test_successful_outreach_is_recorded(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    router = ApplicationExecutionRouter(
        outreach_pipeline=FakeOutreachPipeline(),
        memory=memory,
    )

    result = router.route(
        {
            "job": electrical_job(),
            "ranking_score": 75,
        },
        decision=make_decision(OUTREACH),
        contacts=[
            {
                "name": "Recruiter",
                "email": "recruiter@example.com",
            }
        ],
        confirm=True,
    )

    assert result.success is True
    assert result.sent is True

    history = get_history(memory)

    assert len(history) == 1
    assert (
        history[0]["role_class"]
        == "electrical_core"
    )
    assert (
        history[0]["outcome"]
        == "outreach_sent"
    )


def test_outreach_confirmation_does_not_record_send(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    router = ApplicationExecutionRouter(
        outreach_pipeline=FakeOutreachPipeline(),
        memory=memory,
    )

    result = router.route(
        {
            "job": electrical_job(),
            "ranking_score": 75,
        },
        decision=make_decision(OUTREACH),
        contacts=[],
        confirm=False,
    )

    assert (
        result.status
        == "confirmation_required"
    )

    history = get_history(memory)

    assert history == []


def test_review_is_recorded(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    router = ApplicationExecutionRouter(
        review_handler=FakeReviewHandler(),
        memory=memory,
    )

    result = router.route(
        {
            "job": electrical_job(),
            "ranking_score": 50,
        },
        decision=make_decision(REVIEW),
    )

    assert result.success is True
    assert (
        result.status
        == "manual_review"
    )

    history = get_history(memory)

    assert len(history) == 1
    assert (
        history[0]["role_class"]
        == "electrical_core"
    )
    assert (
        history[0]["outcome"]
        == "review"
    )


def test_skip_is_not_recorded_as_application_success(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    router = ApplicationExecutionRouter(
        memory=memory,
    )

    result = router.route(
        {
            "job": electrical_job(),
            "ranking_score": 10,
        },
        decision=make_decision(SKIP),
    )

    assert result.success is True
    assert result.status == "skipped"

    history = get_history(memory)

    assert history == []


def test_memory_failure_does_not_break_execution(
    tmp_path,
):
    class BrokenMemory:
        def record_execution_outcome(
            self,
            **kwargs,
        ):
            raise RuntimeError(
                "memory storage unavailable"
            )

        def record_application_outcome(
            self,
            **kwargs,
        ):
            raise RuntimeError(
                "memory storage unavailable"
            )

    router = ApplicationExecutionRouter(
        application_pipeline=FakeApplicationPipeline(),
        memory=BrokenMemory(),
    )

    result = router.route(
        {
            "job": electrical_job(),
            "ranking_score": 90,
        },
        decision=make_decision(APPLY),
        confirm=True,
    )

    assert result.success is True
    assert result.submitted is True


def test_memory_is_optional():
    router = ApplicationExecutionRouter(
        application_pipeline=FakeApplicationPipeline(),
    )

    result = router.route(
        {
            "job": electrical_job(),
            "ranking_score": 90,
        },
        decision=make_decision(APPLY),
        confirm=True,
    )

    assert result.success is True
    assert result.submitted is True