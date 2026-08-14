from pathlib import Path

import pytest

from app.core.application_pipeline import ApplicationPipeline
from app.jobs.job_store import JobStore


class FakeTracker:
    def __init__(self):
        self.records = []

    def record_application(
        self,
        job_id,
        status,
        details=None,
    ):
        self.records.append(
            {
                "job_id": job_id,
                "status": status,
                "details": details,
            }
        )


def make_pipeline(tmp_path):
    store = JobStore(
        storage_path=str(
            tmp_path / "jobs.json"
        )
    )

    tracker = FakeTracker()

    pipeline = ApplicationPipeline(
        job_store=store,
        application_tracker=tracker,
    )

    return pipeline, store, tracker


def make_job():
    return {
        "title": "Automation Engineer",
        "company": "Example Company",
        "location": "India",
        "url": "https://example.com/jobs/123",
        "description": (
            "Automation Engineer with "
            "Python, SQL and Git."
        ),
        "required_skills": [
            "Python",
            "SQL",
        ],
        "preferred_skills": [
            "Git",
        ],
    }


def make_resume():
    return {
        "skills": "Python, SQL, Git",
        "core_competencies": (
            "Problem-Solving, Communication"
        ),
    }


def test_pipeline_initialization(tmp_path):
    pipeline, store, tracker = make_pipeline(
        tmp_path
    )

    assert pipeline.job_store is store
    assert pipeline.application_tracker is tracker


def test_evaluate_job(tmp_path):
    pipeline, _, _ = make_pipeline(
        tmp_path
    )

    result = pipeline.evaluate_job(
        resume=make_resume(),
        job=make_job(),
    )

    assert result["eligible"] is True
    assert result["match_score"] == 100.0
    assert result["recommendation"] == "APPLY"


def test_register_job(tmp_path):
    pipeline, store, _ = make_pipeline(
        tmp_path
    )

    job_id = pipeline.register_job(
        make_job()
    )

    assert job_id
    assert store.has_job(job_id)


def test_prepare_and_check(tmp_path):
    pipeline, _, _ = make_pipeline(
        tmp_path
    )

    result = pipeline.prepare_and_check(
        resume=make_resume(),
        job=make_job(),
    )

    assert result["eligible"] is True
    assert result["match_score"] == 100.0
    assert result["recommendation"] == "APPLY"


def test_update_application_status(tmp_path):
    pipeline, store, tracker = make_pipeline(
        tmp_path
    )

    job_id = pipeline.register_job(
        make_job()
    )

    result = pipeline.update_application_status(
        job_id=job_id,
        status="shortlisted",
    )

    assert result is True

    assert (
        store.get_status(job_id)
        == "shortlisted"
    )

    assert tracker.records[-1]["status"] == (
        "shortlisted"
    )


def test_update_interview_status(tmp_path):
    pipeline, store, tracker = make_pipeline(
        tmp_path
    )

    job_id = pipeline.register_job(
        make_job()
    )

    result = pipeline.update_application_status(
        job_id=job_id,
        status="interview",
        details={
            "message": "Interview scheduled"
        },
    )

    assert result is True

    assert (
        store.get_status(job_id)
        == "interview"
    )

    assert tracker.records[-1]["details"] == {
        "message": "Interview scheduled"
    }


def test_update_walk_in_status(tmp_path):
    pipeline, store, _ = make_pipeline(
        tmp_path
    )

    job_id = pipeline.register_job(
        make_job()
    )

    assert pipeline.update_application_status(
        job_id,
        "walk_in",
    )

    assert (
        store.get_status(job_id)
        == "walk_in"
    )


def test_update_rejected_status(tmp_path):
    pipeline, store, _ = make_pipeline(
        tmp_path
    )

    job_id = pipeline.register_job(
        make_job()
    )

    assert pipeline.update_application_status(
        job_id,
        "rejected",
    )

    assert (
        store.get_status(job_id)
        == "rejected"
    )


def test_unknown_job_status_update(tmp_path):
    pipeline, _, _ = make_pipeline(
        tmp_path
    )

    result = pipeline.update_application_status(
        "does-not-exist",
        "shortlisted",
    )

    assert result is False


def test_get_application_status(tmp_path):
    pipeline, _, _ = make_pipeline(
        tmp_path
    )

    job_id = pipeline.register_job(
        make_job()
    )

    pipeline.update_application_status(
        job_id,
        "assessment",
    )

    assert (
        pipeline.get_application_status(job_id)
        == "assessment"
    )


def test_missing_resume(tmp_path):
    pipeline, _, _ = make_pipeline(
        tmp_path
    )

    with pytest.raises(FileNotFoundError):
        pipeline.prepare_application(
            page=None,
            job=make_job(),
            resume_path=str(
                tmp_path / "missing.pdf"
            ),
            fields={},
        )