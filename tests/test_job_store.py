from pathlib import Path

import pytest

from app.jobs.job import Job
from app.jobs.job_store import JobStore


def make_job():
    return Job(
        title="Graduate Engineer Trainee",
        company="Example Company",
        location="India",
        description="Electrical engineering role",
        url="https://example.com/jobs/123",
        source="Greenhouse",
        required_skills=[
            "Python",
            "Electrical Engineering",
        ],
        preferred_skills=[
            "Automation",
        ],
    )


def test_store_creates_storage(tmp_path):
    path = tmp_path / "jobs.json"

    store = JobStore(str(path))

    assert path.parent.exists()
    assert store.count() == 0


def test_add_job(tmp_path):
    store = JobStore(
        str(tmp_path / "jobs.json")
    )

    job = make_job()

    job_id = store.add_job(job)

    assert job_id == job.url
    assert store.count() == 1
    assert store.has_job(job_id)


def test_get_job(tmp_path):
    store = JobStore(
        str(tmp_path / "jobs.json")
    )

    job = make_job()
    job_id = store.add_job(job)

    result = store.get_job(job_id)

    assert result is not None
    assert result["title"] == job.title
    assert result["company"] == job.company
    assert result["status"] == "discovered"


def test_duplicate_job_is_not_created(tmp_path):
    store = JobStore(
        str(tmp_path / "jobs.json")
    )

    job = make_job()

    first_id = store.add_job(job)
    second_id = store.add_job(job)

    assert first_id == second_id
    assert store.count() == 1


def test_update_status(tmp_path):
    store = JobStore(
        str(tmp_path / "jobs.json")
    )

    job_id = store.add_job(make_job())

    result = store.update_status(
        job_id,
        "applied",
    )

    assert result is True
    assert store.get_status(job_id) == "applied"


def test_update_missing_job(tmp_path):
    store = JobStore(
        str(tmp_path / "jobs.json")
    )

    assert (
        store.update_status(
            "does-not-exist",
            "applied",
        )
        is False
    )


def test_invalid_status(tmp_path):
    store = JobStore(
        str(tmp_path / "jobs.json")
    )

    with pytest.raises(ValueError):
        store.add_job(
            make_job(),
            status="invalid",
        )


def test_get_jobs_by_status(tmp_path):
    store = JobStore(
        str(tmp_path / "jobs.json")
    )

    job1 = make_job()

    job2 = Job(
        title="Software Engineer",
        company="Another Company",
        url="https://example.com/jobs/456",
    )

    id1 = store.add_job(job1)
    store.add_job(job2)

    store.update_status(
        id1,
        "applied",
    )

    applied = store.get_jobs_by_status(
        "applied"
    )

    assert len(applied) == 1
    assert applied[0]["title"] == job1.title


def test_persistence(tmp_path):
    path = tmp_path / "jobs.json"

    store1 = JobStore(str(path))

    job = make_job()
    job_id = store1.add_job(job)

    store2 = JobStore(str(path))

    result = store2.get_job(job_id)

    assert result is not None
    assert result["title"] == job.title
    assert result["status"] == "discovered"


def test_dictionary_job(tmp_path):
    store = JobStore(
        str(tmp_path / "jobs.json")
    )

    job = {
        "title": "Electrical Engineer",
        "company": "Test Company",
        "location": "Hyderabad",
        "url": "https://example.com/job/1",
    }

    job_id = store.add_job(job)

    result = store.get_job(job_id)

    assert result["title"] == "Electrical Engineer"
    assert result["company"] == "Test Company"


def test_get_all_jobs(tmp_path):
    store = JobStore(
        str(tmp_path / "jobs.json")
    )

    store.add_job(make_job())

    jobs = store.get_all_jobs()

    assert isinstance(jobs, list)
    assert len(jobs) == 1