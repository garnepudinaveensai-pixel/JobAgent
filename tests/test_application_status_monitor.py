from pathlib import Path

import pytest

from app.jobs.application_status_monitor import (
    ApplicationStatusMonitor,
)
from app.jobs.job_store import JobStore


# ============================================================
# HELPERS
# ============================================================


def create_store(tmp_path: Path) -> JobStore:

    return JobStore(
        storage_path=str(
            tmp_path / "jobs.json"
        )
    )


def create_job(store: JobStore):

    return store.add_job(
        {
            "title": "Graduate Engineer Trainee",
            "company": "Siemens",
            "location": "India",
            "url": "https://example.com/job/123",
            "description": "Electrical engineering role.",
        },
        status="applied",
    )


# ============================================================
# INITIALIZATION
# ============================================================


def test_initialization(tmp_path):

    store = create_store(tmp_path)

    monitor = ApplicationStatusMonitor(
        store
    )

    assert monitor.job_store is store


# ============================================================
# VALIDATION
# ============================================================


def test_valid_status():

    ApplicationStatusMonitor.validate_status(
        "shortlisted"
    )


def test_invalid_status():

    with pytest.raises(ValueError):

        ApplicationStatusMonitor.validate_status(
            "something_random"
        )


def test_invalid_status_type():

    with pytest.raises(TypeError):

        ApplicationStatusMonitor.validate_status(
            123
        )


# ============================================================
# CURRENT STATUS
# ============================================================


def test_get_status(tmp_path):

    store = create_store(tmp_path)

    job_id = create_job(store)

    monitor = ApplicationStatusMonitor(
        store
    )

    assert (
        monitor.get_status(job_id)
        == "applied"
    )


# ============================================================
# STATUS UPDATE
# ============================================================


def test_update_status(tmp_path):

    store = create_store(tmp_path)

    job_id = create_job(store)

    monitor = ApplicationStatusMonitor(
        store
    )

    result = monitor.update_status(
        job_id,
        "shortlisted",
    )

    assert result["success"] is True
    assert result["changed"] is True
    assert result["old_status"] == "applied"
    assert result["new_status"] == "shortlisted"
    assert result["notification_required"] is True

    assert (
        store.get_status(job_id)
        == "shortlisted"
    )


def test_update_same_status(tmp_path):

    store = create_store(tmp_path)

    job_id = create_job(store)

    monitor = ApplicationStatusMonitor(
        store
    )

    result = monitor.update_status(
        job_id,
        "applied",
    )

    assert result["success"] is True
    assert result["changed"] is False
    assert result["notification_required"] is False


def test_update_missing_job(tmp_path):

    store = create_store(tmp_path)

    monitor = ApplicationStatusMonitor(
        store
    )

    result = monitor.update_status(
        "does-not-exist",
        "shortlisted",
    )

    assert result["success"] is False
    assert result["changed"] is False
    assert result["error"] == "Job not found."


# ============================================================
# DETECT STATUS
# ============================================================


def test_detect_status(tmp_path):

    store = create_store(tmp_path)

    job_id = create_job(store)

    monitor = ApplicationStatusMonitor(
        store
    )

    result = monitor.detect_status(
        job_id,
        "interview",
    )

    assert result["changed"] is True
    assert result["new_status"] == "interview"


# ============================================================
# NOTIFICATION
# ============================================================


@pytest.mark.parametrize(
    "status",
    [
        "shortlisted",
        "rejected",
        "interview",
        "assessment",
        "walk_in",
        "status_changed",
    ],
)
def test_notification_statuses(
    tmp_path,
    status,
):

    store = create_store(tmp_path)

    monitor = ApplicationStatusMonitor(
        store
    )

    assert (
        monitor.requires_notification(status)
        is True
    )


def test_non_notification_status(tmp_path):

    store = create_store(tmp_path)

    monitor = ApplicationStatusMonitor(
        store
    )

    assert (
        monitor.requires_notification(
            "applied"
        )
        is False
    )


# ============================================================
# JOB
# ============================================================


def test_get_job(tmp_path):

    store = create_store(tmp_path)

    job_id = create_job(store)

    monitor = ApplicationStatusMonitor(
        store
    )

    job = monitor.get_job(
        job_id
    )

    assert job is not None
    assert (
        job["company"]
        == "Siemens"
    )


# ============================================================
# TRACKED APPLICATIONS
# ============================================================


def test_get_tracked_applications(
    tmp_path,
):

    store = create_store(tmp_path)

    create_job(store)

    # This job should not appear because it
    # hasn't reached the application lifecycle.
    store.add_job(
        {
            "title": "Another Job",
            "company": "ABB",
            "url": "https://example.com/job/456",
        },
        status="discovered",
    )

    monitor = ApplicationStatusMonitor(
        store
    )

    applications = (
        monitor.get_tracked_applications()
    )

    assert len(applications) == 1

    assert (
        applications[0]["company"]
        == "Siemens"
    )


# ============================================================
# SCAN
# ============================================================


def test_scan_detects_status_change(
    tmp_path,
):

    store = create_store(tmp_path)

    job_id = create_job(store)

    monitor = ApplicationStatusMonitor(
        store
    )

    def status_provider(job):

        assert (
            job["job_id"]
            == job_id
        )

        return "shortlisted"

    events = monitor.scan(
        status_provider
    )

    assert len(events) == 1

    assert (
        events[0]["job_id"]
        == job_id
    )

    assert (
        events[0]["new_status"]
        == "shortlisted"
    )

    assert (
        store.get_status(job_id)
        == "shortlisted"
    )


def test_scan_ignores_no_new_status(
    tmp_path,
):

    store = create_store(tmp_path)

    create_job(store)

    monitor = ApplicationStatusMonitor(
        store
    )

    events = monitor.scan(
        lambda job: None
    )

    assert events == []


def test_scan_ignores_same_status(
    tmp_path,
):

    store = create_store(tmp_path)

    create_job(store)

    monitor = ApplicationStatusMonitor(
        store
    )

    events = monitor.scan(
        lambda job: "applied"
    )

    assert events == []