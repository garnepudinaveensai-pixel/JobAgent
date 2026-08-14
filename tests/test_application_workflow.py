from pathlib import Path

from app.core.application_workflow import (
    ApplicationWorkflow,
)


class FakeSubmitter:
    """
    Fake submitter used for testing.

    No real website is contacted.
    """

    def __init__(self, page):
        self.page = page
        self.opened_url = None
        self.prepared = False
        self.submitted = False

    def open(self, url):
        self.opened_url = url
        return True

    def prepare_application(
        self,
        resume_path,
        fields,
    ):
        self.prepared = True

        return {
            "filled_fields": list(
                fields.keys()
            ),
            "resume_uploaded": True,
            "validation": {
                "ready": True,
                "missing_required_fields": [],
            },
            "status": "ready_for_submission",
            "success": True,
        }

    def submit(self, confirm=False):
        if not confirm:
            return {
                "success": False,
                "status": "confirmation_required",
            }

        self.submitted = True

        return {
            "success": True,
            "status": "submitted",
        }


def sample_resume():
    return {
        "name": "GARNEPUDI NAVEEN SAI",
        "email": "test@example.com",
        "degree": "B.Tech",
        "skills": [
            "Python",
            "C",
            "MATLAB",
            "Simulink",
        ],
        "core_competencies": [
            "Electrical Engineering",
            "Automation",
            "Predictive Maintenance",
        ],
    }


def sample_job():
    return {
        "title": "Graduate Engineer Trainee",
        "company": "Example Company",
        "location": "Hyderabad",
        "url": "https://example.com/jobs/123",
        "description": (
            "Graduate Engineer Trainee "
            "Electrical Engineering"
        ),
        "required_skills": [
            "Python",
            "Electrical Engineering",
        ],
        "preferred_skills": [
            "Automation",
        ],
    }


def test_tailor_and_generate_resume(
    tmp_path,
):
    output = (
        tmp_path
        / "tailored_resume.pdf"
    )

    result = (
        ApplicationWorkflow
        .tailor_and_generate_resume(
            resume=sample_resume(),
            job=sample_job(),
            output_path=str(output),
        )
    )

    assert (
        result["resume"]["name"]
        == "GARNEPUDI NAVEEN SAI"
    )

    assert (
        result["resume"]["tailored_for"]
        == "Graduate Engineer Trainee"
    )

    assert Path(
        result["pdf_path"]
    ).exists()


def test_prepare_application(
    tmp_path,
):
    submitter = None

    workflow = ApplicationWorkflow(
        submitter_factory=FakeSubmitter
    )

    output = (
        tmp_path
        / "tailored_resume.pdf"
    )

    result = workflow.prepare_application(
        page="fake-page",
        resume=sample_resume(),
        job=sample_job(),
        fields={
            "First Name": "Naveen",
            "Email": "test@example.com",
        },
        resume_output_path=str(output),
    )

    assert result["success"] is True

    assert (
        result["status"]
        == "ready_for_submission"
    )

    assert (
        result["resume_uploaded"]
        is True
    )

    assert result["filled_fields"] == [
        "First Name",
        "Email",
    ]

    assert result["validation"]["ready"] is True

    assert output.exists()

    assert (
        result["submitter"].opened_url
        == "https://example.com/jobs/123"
    )


def test_prepare_requires_job_url(
    tmp_path,
):
    workflow = ApplicationWorkflow(
        submitter_factory=FakeSubmitter
    )

    job = sample_job()
    job["url"] = ""

    try:
        workflow.prepare_application(
            page="fake-page",
            resume=sample_resume(),
            job=job,
            fields={},
            resume_output_path=str(
                tmp_path
                / "resume.pdf"
            ),
        )

        assert False

    except ValueError as exc:
        assert "URL" in str(exc)


def test_submit_requires_confirmation(
    tmp_path,
):
    workflow = ApplicationWorkflow(
        submitter_factory=FakeSubmitter
    )

    prepared = workflow.prepare_application(
        page="fake-page",
        resume=sample_resume(),
        job=sample_job(),
        fields={
            "First Name": "Naveen",
            "Email": "test@example.com",
        },
        resume_output_path=str(
            tmp_path
            / "resume.pdf"
        ),
    )

    result = workflow.submit(
        prepared,
        confirm=False,
    )

    assert result["success"] is False

    assert (
        result["status"]
        == "confirmation_required"
    )


def test_submit_success(
    tmp_path,
):
    workflow = ApplicationWorkflow(
        submitter_factory=FakeSubmitter
    )

    prepared = workflow.prepare_application(
        page="fake-page",
        resume=sample_resume(),
        job=sample_job(),
        fields={
            "First Name": "Naveen",
            "Email": "test@example.com",
        },
        resume_output_path=str(
            tmp_path
            / "resume.pdf"
        ),
    )

    result = workflow.submit(
        prepared,
        confirm=True,
    )

    assert result["success"] is True

    assert (
        result["status"]
        == "submitted"
    )


def test_submit_without_preparation():
    result = ApplicationWorkflow.submit(
        {},
        confirm=True,
    )

    assert result["success"] is False

    assert (
        result["status"]
        == "not_prepared"
    )


def test_submit_rejects_invalid_preparation():
    submitter = FakeSubmitter(
        "fake-page"
    )

    prepared = {
        "submitter": submitter,
        "validation": {
            "ready": False,
        },
    }

    result = ApplicationWorkflow.submit(
        prepared,
        confirm=True,
    )

    assert result["success"] is False

    assert (
        result["status"]
        == "validation_failed"
    )