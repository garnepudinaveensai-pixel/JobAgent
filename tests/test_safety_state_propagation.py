from __future__ import annotations

from app.core.application_execution_router import (
    ApplicationExecutionRouter,
    ExecutionResult,
)
from app.core.application_workflow import ApplicationWorkflow
from app.core.job_agent_service import JobAgentService


def _apply_ranked():
    return {
        "ranking_score": 90.0,
        "job": {
            "job_id": "job-001",
            "title": "Electrical Engineer",
            "company": "Example Energy",
            "url": "https://example.com/apply",
        },
    }


class ApplyDecision:
    decision = "apply"


class FakeDecisionEngine:
    def decide(self, ranked_result):
        return ApplyDecision()


class FakeApplicationPipeline:
    def __init__(self, preparation):
        self.preparation = preparation

    def prepare_application_for_job(
        self,
        *args,
        **kwargs,
    ):
        return dict(self.preparation)


def _router(preparation):
    return ApplicationExecutionRouter(
        decision_engine=FakeDecisionEngine(),
        application_pipeline=FakeApplicationPipeline(
            preparation
        ),
    )


def test_execution_result_serializes_human_action_state():
    result = ExecutionResult(
        success=False,
        decision="apply",
        status="captcha_detected",
        requires_human_action=True,
    )

    data = result.to_dict()

    assert data["status"] == "captcha_detected"
    assert data["requires_human_action"] is True


def test_router_propagates_captcha_from_preparation():
    result = _router(
        {
            "success": False,
            "status": "captcha_detected",
            "message": "CAPTCHA detected.",
            "requires_human_action": True,
            "page_analysis": {
                "captcha_detected": True,
                "requires_human_action": True,
            },
        }
    ).route(
        _apply_ranked(),
        page=object(),
    )

    assert result.success is False
    assert result.status == "captcha_detected"
    assert result.submitted is False
    assert result.requires_human_action is True
    assert result.result["page_analysis"]["captcha_detected"] is True


def test_router_propagates_login_required_from_preparation():
    result = _router(
        {
            "success": False,
            "status": "login_required",
            "requires_human_action": True,
        }
    ).route(
        _apply_ranked(),
        page=object(),
    )

    assert result.status == "login_required"
    assert result.requires_human_action is True
    assert result.submitted is False


def test_router_propagates_job_unavailable_from_preparation():
    result = _router(
        {
            "success": False,
            "status": "job_unavailable",
        }
    ).route(
        _apply_ranked(),
        page=object(),
    )

    assert result.status == "job_unavailable"
    assert result.requires_human_action is False
    assert result.submitted is False


def test_router_propagates_form_not_found_from_preparation():
    result = _router(
        {
            "success": False,
            "status": "form_not_found",
        }
    ).route(
        _apply_ranked(),
        page=object(),
    )

    assert result.status == "form_not_found"
    assert result.submitted is False


def test_workflow_submit_preserves_captcha():
    result = ApplicationWorkflow.submit(
        {
            "status": "captcha_detected",
            "requires_human_action": True,
            "page_analysis": {
                "captcha_detected": True,
            },
            "validation": {
                "ready": False,
            },
            "submitter": object(),
        },
        confirm=True,
    )

    assert result["success"] is False
    assert result["status"] == "captcha_detected"
    assert result["submitted"] is False
    assert result["requires_human_action"] is True


def test_workflow_submit_preserves_login_required():
    result = ApplicationWorkflow.submit(
        {
            "status": "login_required",
            "requires_human_action": True,
            "validation": {
                "ready": False,
            },
            "submitter": object(),
        },
        confirm=True,
    )

    assert result["success"] is False
    assert result["status"] == "login_required"
    assert result["requires_human_action"] is True


class FakeRunner:
    pass


class FakePipeline:
    pass


class FakeEngine:
    pass


class FakeRouter:
    pass


def test_service_counts_human_action_results():
    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakePipeline(),
        decision_engine=FakeEngine(),
        execution_router=FakeRouter(),
    )

    executions = [
        ExecutionResult(
            success=False,
            decision="apply",
            status="captcha_detected",
            requires_human_action=True,
        ),
        ExecutionResult(
            success=False,
            decision="apply",
            status="login_required",
            requires_human_action=True,
        ),
        ExecutionResult(
            success=False,
            decision="apply",
            status="job_unavailable",
        ),
    ]

    result = service._build_run_result(
        keywords="Electrical Engineer",
        location="Hyderabad",
        ranked_jobs=[
            {"job": {"job_id": "job-001"}},
            {"job": {"job_id": "job-002"}},
            {"job": {"job_id": "job-003"}},
        ],
        executions=executions,
        dry_run=False,
        confirm=True,
    )

    assert result.human_action_required_count == 2
    assert (
        result.metadata[
            "human_action_required_count"
        ]
        == 2
    )
    assert (
        result.errors[0][
            "requires_human_action"
        ]
        is True
    )


def test_service_dry_run_still_reports_safety_errors():
    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakePipeline(),
        decision_engine=FakeEngine(),
        execution_router=FakeRouter(),
    )

    execution = ExecutionResult(
        success=False,
        decision="apply",
        status="captcha_detected",
        requires_human_action=True,
    )

    result = service._build_run_result(
        keywords="Electrical Engineer",
        location="Hyderabad",
        ranked_jobs=[
            {"job": {"job_id": "job-001"}},
        ],
        executions=[execution],
        dry_run=True,
        confirm=False,
    )

    assert result.success is True
    assert result.status == "dry_run_completed"
    assert result.human_action_required_count == 1
    assert result.errors[0]["status"] == "captcha_detected"
