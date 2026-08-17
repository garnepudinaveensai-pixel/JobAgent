from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.application_execution_router import (
    APPLY,
    OUTREACH,
    REVIEW,
    SKIP,
    ApplicationExecutionRouter,
)


# ============================================================
# HELPERS
# ============================================================


def make_job(
    *,
    url="https://example.com/jobs/1",
):
    return {
        "job_id": "job-001",
        "title": "Electrical Engineer",
        "company": "Example Energy",
        "location": "Hyderabad",
        "url": url,
    }


def make_ranked_result(
    *,
    score=90,
    url="https://example.com/jobs/1",
    eligible=True,
    missing=None,
):
    return {
        "ranking_score": score,
        "job": make_job(url=url),
        "match": {
            "match_score": score,
            "eligible": eligible,
            "missing_required_skills": (
                missing or []
            ),
            "selected_resume": {
                "filename": "technical_resume.pdf",
                "name": "Naveen Sai",
                "skills": [
                    "Electrical Engineering",
                    "Python",
                ],
            },
        },
        "resume": {
            "filename": "technical_resume.pdf",
        },
    }


def make_application_pipeline():
    pipeline = MagicMock()

    pipeline.prepare_application_for_job.return_value = {
        "success": True,
        "status": "ready_for_submission",
        "validation": {
            "ready": True,
        },
        "submitter": MagicMock(),
        "resume_pdf": (
            "data/resumes/tailored.pdf"
        ),
    }

    pipeline.prepare_application_for_job.return_value[
        "submitter"
    ].submit.return_value = {
        "success": True,
        "status": "applied",
        "submitted": True,
    }

    return pipeline


def make_outreach_pipeline():
    pipeline = MagicMock()

    pipeline.prepare_outreach.return_value = {
        "success": True,
        "status": "prepared",
        "recipient": "recruiter@example.com",
    }

    pipeline.send_outreach.return_value = {
        "success": True,
        "status": "sent",
        "sent": True,
    }

    return pipeline


# ============================================================
# INPUT VALIDATION
# ============================================================


def test_route_requires_mapping():

    router = ApplicationExecutionRouter()

    with pytest.raises(
        TypeError,
        match="ranked_result must be a mapping",
    ):
        router.route(None)


def test_route_many_requires_list():

    router = ApplicationExecutionRouter()

    with pytest.raises(
        TypeError,
        match="ranked_results must be a list",
    ):
        router.route_many(None)


# ============================================================
# APPLY
# ============================================================


def test_apply_prepares_without_confirmation():

    application = make_application_pipeline()

    router = ApplicationExecutionRouter(
        application_pipeline=application
    )

    result = router.route(
        make_ranked_result(),
        page=MagicMock(),
        fields={
            "full_name": "Naveen Sai"
        },
        resume={
            "filename": "technical_resume.pdf"
        },
        confirm=False,
    )

    assert result.success is True
    assert result.decision == APPLY
    assert result.status == (
        "confirmation_required"
    )
    assert result.prepared is True
    assert result.submitted is False
    assert result.confirmation_required is True

    application.prepare_application_for_job.assert_called_once()


def test_apply_does_not_submit_without_confirmation():

    application = make_application_pipeline()

    router = ApplicationExecutionRouter(
        application_pipeline=application
    )

    result = router.route(
        make_ranked_result(),
        page=MagicMock(),
        fields={},
        confirm=False,
    )

    assert result.success is True
    assert result.status == (
        "confirmation_required"
    )

    submitter = (
        application
        .prepare_application_for_job
        .return_value["submitter"]
    )

    submitter.submit.assert_not_called()


def test_apply_submits_when_confirmed():

    application = make_application_pipeline()

    router = ApplicationExecutionRouter(
        application_pipeline=application
    )

    result = router.route(
        make_ranked_result(),
        page=MagicMock(),
        fields={},
        confirm=True,
    )

    assert result.success is True
    assert result.decision == APPLY
    assert result.status == "applied"
    assert result.submitted is True
    assert result.executed is True

    submitter = (
        application
        .prepare_application_for_job
        .return_value["submitter"]
    )

    submitter.submit.assert_called_once_with(
        confirm=True
    )


def test_apply_dry_run_never_submits():

    application = make_application_pipeline()

    router = ApplicationExecutionRouter(
        application_pipeline=application
    )

    result = router.route(
        make_ranked_result(),
        page=MagicMock(),
        fields={},
        confirm=True,
        dry_run=True,
    )

    assert result.success is True
    assert result.status == "dry_run_ready"
    assert result.submitted is False
    assert result.metadata["dry_run"] is True

    submitter = (
        application
        .prepare_application_for_job
        .return_value["submitter"]
    )

    submitter.submit.assert_not_called()


def test_apply_without_pipeline_fails():

    router = ApplicationExecutionRouter()

    result = router.route(
        make_ranked_result()
    )

    assert result.success is False
    assert result.decision == APPLY
    assert result.status == (
        "application_pipeline_missing"
    )


def test_apply_prepare_failure_is_handled():

    application = MagicMock()

    application.prepare_application_for_job.return_value = {
        "success": False,
        "status": "validation_failed",
        "error": "Required field missing",
    }

    router = ApplicationExecutionRouter(
        application_pipeline=application
    )

    result = router.route(
        make_ranked_result(),
        page=MagicMock(),
        fields={},
    )

    assert result.success is False
    assert result.status == (
        "application_prepare_failed"
    )


def test_apply_prepare_exception_is_handled():

    application = MagicMock()

    application.prepare_application_for_job.side_effect = (
        RuntimeError(
            "browser failure"
        )
    )

    router = ApplicationExecutionRouter(
        application_pipeline=application
    )

    result = router.route(
        make_ranked_result(),
        page=MagicMock(),
        fields={},
    )

    assert result.success is False
    assert result.status == (
        "application_prepare_failed"
    )
    assert "browser failure" in (
        result.error or ""
    )


# ============================================================
# OUTREACH
# ============================================================


def test_outreach_prepares_without_confirmation():

    outreach = make_outreach_pipeline()

    result = ApplicationExecutionRouter(
        outreach_pipeline=outreach
    ).route(
        make_ranked_result(
            score=90,
            url="",
        ),
        contacts=[
            {
                "email": "recruiter@example.com",
                "name": "Recruiter",
            }
        ],
        confirm=False,
    )

    assert result.success is True
    assert result.decision == OUTREACH
    assert result.status == (
        "confirmation_required"
    )
    assert result.prepared is True
    assert result.sent is False


def test_outreach_does_not_send_without_confirmation():

    outreach = make_outreach_pipeline()

    router = ApplicationExecutionRouter(
        outreach_pipeline=outreach
    )

    result = router.route(
        make_ranked_result(
            score=90,
            url="",
        ),
        contacts=[],
        confirm=False,
    )

    assert result.success is True
    assert result.status == (
        "confirmation_required"
    )

    outreach.send_outreach.assert_not_called()


def test_outreach_sends_when_confirmed():

    outreach = make_outreach_pipeline()

    router = ApplicationExecutionRouter(
        outreach_pipeline=outreach
    )

    result = router.route(
        make_ranked_result(
            score=90,
            url="",
        ),
        contacts=[
            {
                "email": "recruiter@example.com"
            }
        ],
        confirm=True,
    )

    assert result.success is True
    assert result.decision == OUTREACH
    assert result.status == "sent"
    assert result.sent is True
    assert result.executed is True

    outreach.send_outreach.assert_called_once()


def test_outreach_dry_run_never_sends():

    outreach = make_outreach_pipeline()

    router = ApplicationExecutionRouter(
        outreach_pipeline=outreach
    )

    result = router.route(
        make_ranked_result(
            score=90,
            url="",
        ),
        contacts=[],
        confirm=True,
        dry_run=True,
    )

    assert result.success is True
    assert result.status == "dry_run_ready"
    assert result.sent is False

    outreach.send_outreach.assert_not_called()


def test_outreach_without_pipeline_fails():

    router = ApplicationExecutionRouter()

    result = router.route(
        make_ranked_result(
            score=90,
            url="",
        )
    )

    assert result.success is False
    assert result.decision == OUTREACH
    assert result.status == (
        "outreach_pipeline_missing"
    )


def test_outreach_prepare_failure_is_handled():

    outreach = MagicMock()

    outreach.prepare_outreach.return_value = {
        "success": False,
        "status": "no_contact",
        "error": "No recruiter found",
    }

    router = ApplicationExecutionRouter(
        outreach_pipeline=outreach
    )

    result = router.route(
        make_ranked_result(
            score=90,
            url="",
        ),
        contacts=[],
    )

    assert result.success is False
    assert result.status == (
        "outreach_prepare_failed"
    )


# ============================================================
# REVIEW
# ============================================================


def test_review_returns_manual_review():

    router = ApplicationExecutionRouter()

    result = router.route(
        make_ranked_result(
            score=75
        )
    )

    assert result.success is True
    assert result.decision == REVIEW
    assert result.status == "manual_review"
    assert result.executed is False


def test_review_handler_is_called():

    handler = MagicMock()

    router = ApplicationExecutionRouter(
        review_handler=handler
    )

    ranked = make_ranked_result(
        score=75
    )

    result = router.route(
        ranked
    )

    assert result.success is True
    assert result.decision == REVIEW

    handler.add.assert_called_once_with(
        ranked
    )


def test_review_handler_exception_is_handled():

    handler = MagicMock()

    handler.add.side_effect = RuntimeError(
        "review storage failed"
    )

    router = ApplicationExecutionRouter(
        review_handler=handler
    )

    result = router.route(
        make_ranked_result(
            score=75
        )
    )

    assert result.success is False
    assert result.status == (
        "review_handler_failed"
    )


# ============================================================
# SKIP
# ============================================================


def test_skip_returns_skipped():

    router = ApplicationExecutionRouter()

    result = router.route(
        make_ranked_result(
            score=20
        )
    )

    assert result.success is True
    assert result.decision == SKIP
    assert result.status == "skipped"
    assert result.executed is False


def test_ineligible_job_is_skipped():

    router = ApplicationExecutionRouter()

    result = router.route(
        make_ranked_result(
            score=95,
            eligible=False,
        )
    )

    assert result.success is True
    assert result.decision == SKIP
    assert result.status == "skipped"


# ============================================================
# MISSING REQUIRED SKILLS
# ============================================================


def test_missing_required_skills_go_to_review():

    router = ApplicationExecutionRouter()

    result = router.route(
        make_ranked_result(
            score=95,
            missing=[
                "PLC",
                "SCADA",
            ],
        )
    )

    assert result.success is True
    assert result.decision == REVIEW
    assert result.status == "manual_review"


# ============================================================
# BATCH
# ============================================================


def test_route_many_routes_multiple_jobs():

    application = make_application_pipeline()

    router = ApplicationExecutionRouter(
        application_pipeline=application
    )

    results = router.route_many(
        [
            make_ranked_result(
                score=95
            ),
            make_ranked_result(
                score=75
            ),
            make_ranked_result(
                score=20
            ),
        ],
        page=MagicMock(),
        fields={},
        confirm=False,
    )

    assert len(results) == 3

    assert results[0].decision == APPLY
    assert results[1].decision == REVIEW
    assert results[2].decision == SKIP


# ============================================================
# SERIALIZATION
# ============================================================


def test_execution_result_to_dict():

    router = ApplicationExecutionRouter()

    result = router.route(
        make_ranked_result(
            score=20
        )
    )

    data = result.to_dict()

    assert isinstance(
        data,
        dict,
    )

    assert data["decision"] == SKIP
    assert data["status"] == "skipped"
    assert data["ranking_score"] == 20.0


# ============================================================
# CONVENIENCE ADAPTERS
# ============================================================


def test_application_pipeline_legacy_method_is_supported():

    application = MagicMock(
        spec=[
            "prepare_application"
        ]
    )

    application.prepare_application.return_value = {
        "success": True,
        "status": "ready",
        "submitter": MagicMock(),
    }

    application.prepare_application.return_value[
        "submitter"
    ].submit.return_value = {
        "success": True,
        "status": "applied",
        "submitted": True,
    }

    router = ApplicationExecutionRouter(
        application_pipeline=application
    )

    result = router.route(
        make_ranked_result(),
        page=MagicMock(),
        fields={},
        confirm=False,
    )

    assert result.success is True
    assert result.status == (
        "confirmation_required"
    )

    application.prepare_application.assert_called_once()


def test_outreach_legacy_compose_method_is_supported():

    outreach = MagicMock(
        spec=[
            "compose_outreach"
        ]
    )

    outreach.compose_outreach.return_value = {
        "success": True,
        "status": "prepared",
    }

    router = ApplicationExecutionRouter(
        outreach_pipeline=outreach
    )

    result = router.route(
        make_ranked_result(
            score=90,
            url="",
        ),
        contacts=[],
        confirm=False,
    )

    assert result.success is True
    assert result.status == (
        "confirmation_required"
    )

    outreach.compose_outreach.assert_called_once()