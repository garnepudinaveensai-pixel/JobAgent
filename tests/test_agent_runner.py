from pathlib import Path

import pytest

from app.config import (
    JobAgentConfig,
    NotificationConfig,
    StorageConfig,
)
from app.core.agent_runner import AgentRunner
from app.jobs.job_store import JobStore


# ============================================================
# HELPERS
# ============================================================

def make_runner(tmp_path):
    jobs_file = (
        tmp_path
        / "jobs"
        / "jobs.json"
    )

    applications_file = (
        tmp_path
        / "jobs"
        / "applications.json"
    )

    config = JobAgentConfig(
        notification=NotificationConfig(
            email="test@example.com"
        ),
        storage=StorageConfig(
            jobs_file=str(jobs_file),
            applications_file=str(
                applications_file
            ),
        ),
    )

    store = JobStore(
        storage_path=str(jobs_file)
    )

    return AgentRunner(
        config=config,
        job_store=store,
    )


def sample_job():
    return {
        "title": "Electrical Engineer",
        "company": "Example Company",
        "location": "Hyderabad",
        "description": "Electrical engineering role.",
        "url": "https://example.com/jobs/1",
    }


# ============================================================
# INITIALIZATION
# ============================================================

def test_runner_initialization(tmp_path):
    runner = make_runner(tmp_path)

    assert runner.config is not None
    assert runner.job_store is not None
    assert runner.job_agent is None


# ============================================================
# CONFIGURATION
# ============================================================

def test_validate_config(tmp_path):
    runner = make_runner(tmp_path)

    runner.validate_config()


# ============================================================
# STORE JOBS
# ============================================================

def test_store_jobs(tmp_path):
    runner = make_runner(tmp_path)

    job_ids = runner.store_jobs(
        [
            sample_job(),
        ]
    )

    assert len(job_ids) == 1

    stored = runner.get_jobs()

    assert len(stored) == 1
    assert stored[0]["title"] == "Electrical Engineer"
    assert stored[0]["company"] == "Example Company"
    assert stored[0]["status"] == "discovered"


def test_store_multiple_jobs(tmp_path):
    runner = make_runner(tmp_path)

    jobs = [
        sample_job(),
        {
            "title": "Automation Engineer",
            "company": "Another Company",
            "location": "Bangalore",
            "url": "https://example.com/jobs/2",
        },
    ]

    job_ids = runner.store_jobs(jobs)

    assert len(job_ids) == 2
    assert len(runner.get_jobs()) == 2


def test_store_jobs_ignores_invalid_items(tmp_path):
    runner = make_runner(tmp_path)

    job_ids = runner.store_jobs(
        [
            sample_job(),
            None,
            "invalid",
            123,
        ]
    )

    assert len(job_ids) == 1
    assert len(runner.get_jobs()) == 1


# ============================================================
# GET JOBS
# ============================================================

def test_get_jobs_returns_all_jobs(tmp_path):
    runner = make_runner(tmp_path)

    runner.store_jobs(
        [
            sample_job(),
        ]
    )

    jobs = runner.get_jobs()

    assert len(jobs) == 1


def test_get_jobs_by_status(tmp_path):
    runner = make_runner(tmp_path)

    job_ids = runner.store_jobs(
        [
            sample_job(),
        ]
    )

    runner.update_job_status(
        job_ids[0],
        "shortlisted",
    )

    shortlisted = runner.get_jobs(
        status="shortlisted"
    )

    assert len(shortlisted) == 1
    assert (
        shortlisted[0]["status"]
        == "shortlisted"
    )


# ============================================================
# STATUS
# ============================================================

def test_update_job_status(tmp_path):
    runner = make_runner(tmp_path)

    job_ids = runner.store_jobs(
        [
            sample_job(),
        ]
    )

    result = runner.update_job_status(
        job_ids[0],
        "matched",
    )

    assert result is True

    jobs = runner.get_jobs()

    assert jobs[0]["status"] == "matched"


def test_update_unknown_job(tmp_path):
    runner = make_runner(tmp_path)

    result = runner.update_job_status(
        "does-not-exist",
        "matched",
    )

    assert result is False


def test_invalid_status_raises_error(tmp_path):
    runner = make_runner(tmp_path)

    job_ids = runner.store_jobs(
        [
            sample_job(),
        ]
    )

    with pytest.raises(ValueError):
        runner.update_job_status(
            job_ids[0],
            "not-a-real-status",
        )


# ============================================================
# DISCOVERY
# ============================================================

def test_discover_requires_job_agent(tmp_path):
    runner = make_runner(tmp_path)

    with pytest.raises(RuntimeError):
        runner.discover_jobs(
            board_url="https://example.com",
            keywords="Electrical Engineer",
        )


def test_discover_jobs_delegates_to_job_agent(
    tmp_path,
):
    class FakeJobAgent:

        def discover_jobs(
            self,
            board_url,
            keywords,
            location=None,
        ):
            return [
                sample_job()
            ]

    runner = make_runner(tmp_path)

    runner.job_agent = FakeJobAgent()

    jobs = runner.discover_jobs(
        board_url="https://example.com",
        keywords="Electrical Engineer",
        location="Hyderabad",
    )

    assert len(jobs) == 1
    assert (
        jobs[0]["title"]
        == "Electrical Engineer"
    )


def test_discover_jobs_returns_empty_when_agent_returns_none(
    tmp_path,
):
    class FakeJobAgent:

        def discover_jobs(
            self,
            board_url,
            keywords,
            location=None,
        ):
            return None

    runner = make_runner(tmp_path)

    runner.job_agent = FakeJobAgent()

    jobs = runner.discover_jobs(
        board_url="https://example.com",
        keywords="Electrical Engineer",
    )

    assert jobs == []


# ============================================================
# DISCOVER + STORE
# ============================================================

def test_discover_and_store(tmp_path):
    class FakeJobAgent:

        def discover_jobs(
            self,
            board_url,
            keywords,
            location=None,
        ):
            return [
                sample_job()
            ]

    runner = make_runner(tmp_path)

    runner.job_agent = FakeJobAgent()

    job_ids = runner.discover_and_store(
        board_url="https://example.com",
        keywords="Electrical Engineer",
        location="Hyderabad",
    )

    assert len(job_ids) == 1

    jobs = runner.get_jobs()

    assert len(jobs) == 1
    assert jobs[0]["status"] == "discovered"


# ============================================================
# SUMMARY
# ============================================================

def test_empty_summary(tmp_path):
    runner = make_runner(tmp_path)

    summary = runner.summary()

    assert summary["total"] == 0
    assert summary["discovered"] == 0
    assert summary["matched"] == 0
    assert summary["applied"] == 0
    assert summary["shortlisted"] == 0
    assert summary["rejected"] == 0


def test_summary_counts_statuses(tmp_path):
    runner = make_runner(tmp_path)

    jobs = [
        sample_job(),
        {
            "title": "Automation Engineer",
            "company": "Company B",
            "location": "Bangalore",
            "url": "https://example.com/jobs/2",
        },
        {
            "title": "Graduate Engineer Trainee",
            "company": "Company C",
            "location": "Chennai",
            "url": "https://example.com/jobs/3",
        },
    ]

    job_ids = runner.store_jobs(jobs)

    runner.update_job_status(
        job_ids[0],
        "matched",
    )

    runner.update_job_status(
        job_ids[1],
        "shortlisted",
    )

    runner.update_job_status(
        job_ids[2],
        "rejected",
    )

    summary = runner.summary()

    assert summary["total"] == 3
    assert summary["matched"] == 1
    assert summary["shortlisted"] == 1
    assert summary["rejected"] == 1
    assert summary["discovered"] == 0


def test_summary_contains_all_supported_statuses(
    tmp_path,
):
    runner = make_runner(tmp_path)

    summary = runner.summary()

    expected_statuses = {
        "total",
        "discovered",
        "matched",
        "selected",
        "application_started",
        "applied",
        "application_failed",
        "shortlisted",
        "rejected",
        "interview",
        "assessment",
        "walk_in",
        "status_changed",
    }

    assert expected_statuses.issubset(
        summary.keys()
    )