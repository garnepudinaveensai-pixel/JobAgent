from app.core.application_decision_engine import (
    APPLY,
    ApplicationDecision,
)
from app.core.application_execution_router import (
    ApplicationExecutionRouter,
)


class FakeApplicationPipeline:
    def prepare_application_for_job(
        self,
        ranked_result,
        *,
        page,
        fields,
        resume,
        resume_output_path,
    ):
        return {
            "success": True,
            "status": "prepared",
            "submitter": FakeSubmitter(),
        }


class FakeSubmitter:
    def submit(self, *, confirm):
        assert confirm is True

        return {
            "success": True,
            "status": "applied",
            "submitted": True,
        }


class FakeOutreach:
    def prepare_outreach(
        self,
        *,
        contacts,
        job,
        resume,
    ):
        assert contacts

        return {
            "success": True,
            "status": "prepared",
        }

    def send_outreach(
        self,
        *,
        contacts,
        job,
        resume,
        confirm,
    ):
        assert confirm is True

        return {
            "success": True,
            "status": "sent",
            "sent": True,
        }


def test_apply_can_also_send_outreach():
    router = ApplicationExecutionRouter(
        application_pipeline=FakeApplicationPipeline(),
        outreach_pipeline=FakeOutreach(),
    )

    ranked = {
        "ranking_score": 92.0,
        "job": {
            "title": "Electrical Engineer",
            "company": "Example",
            "url": "https://example.com/job",
        },
    }

    decision = ApplicationDecision(
        decision=APPLY,
        reason="strong match",
        ranking_score=92.0,
        match_score=92.0,
        eligible=True,
    )

    result = router.route(
        ranked,
        decision=decision,
        page=object(),
        contacts=[
            {
                "email": "careers@example.com",
            }
        ],
        resume={
            "filename": "technical_resume.pdf",
        },
        confirm=True,
        dry_run=False,
        also_outreach=True,
    )

    assert result.success is True
    assert result.submitted is True
    assert result.sent is True

    assert (
        result.metadata["outreach_status"]
        == "sent"
    )