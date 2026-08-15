from __future__ import annotations

import pytest

from app.jobs.application_status_monitor import (
    ApplicationStatusMonitor,
)
from app.jobs.job_store import JobStore
from app.notifications.email_notification import (
    EmailNotification,
)


# ============================================================
# HELPERS
# ============================================================

def make_store(tmp_path):
    return JobStore(
        storage_path=str(
            tmp_path / "jobs.json"
        )
    )


def sample_job(
    title="Electrical Engineer",
    company="Example Energy",
):
    """
    Create a unique job.

    The URL MUST be unique because JobStore uses the URL
    as the stable job ID.
    """

    safe_title = (
        title.lower()
        .replace(" ", "-")
    )

    safe_company = (
        company.lower()
        .replace(" ", "-")
    )

    return {
        "title": title,
        "company": company,
        "location": "Hyderabad",
        "description": (
            "Electrical engineering role."
        ),
        "url": (
            f"https://example.com/jobs/"
            f"{safe_company}/"
            f"{safe_title}"
        ),
    }


# ============================================================
# REGISTRATION
# ============================================================

def test_applied_job_can_be_registered(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    assert monitor.get_status(job_id) == (
        "applied"
    )

    assert monitor.get_job(job_id) is not None


# ============================================================
# STATUS DETECTION
# ============================================================

def test_detect_shortlisted_status(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    result = monitor.detect_status(
        job_id=job_id,
        detected_status="shortlisted",
    )

    assert result["success"] is True
    assert result["changed"] is True
    assert result["old_status"] == "applied"
    assert result["new_status"] == "shortlisted"
    assert (
        result["notification_required"]
        is True
    )

    assert monitor.get_status(job_id) == (
        "shortlisted"
    )


def test_detect_rejected_status(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    result = monitor.detect_status(
        job_id=job_id,
        detected_status="rejected",
    )

    assert result["success"] is True
    assert result["changed"] is True
    assert result["new_status"] == "rejected"
    assert (
        result["notification_required"]
        is True
    )


# ============================================================
# NOTIFIABLE STATUSES
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
def test_notifiable_statuses_require_notification(
    tmp_path,
    status,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    result = monitor.detect_status(
        job_id=job_id,
        detected_status=status,
    )

    assert result["success"] is True
    assert result["changed"] is True

    assert (
        result["notification_required"]
        is True
    )


# ============================================================
# NON-NOTIFIABLE STATUSES
# ============================================================

@pytest.mark.parametrize(
    "status",
    [
        "discovered",
        "matched",
        "selected",
        "application_started",
        "applied",
        "application_failed",
    ],
)
def test_non_notification_statuses_do_not_require_notification(
    tmp_path,
    status,
):
    store = make_store(tmp_path)

    # Make sure detected status is different from
    # the existing status.
    initial_status = (
        "matched"
        if status == "applied"
        else "applied"
    )

    job_id = store.add_job(
        sample_job(
            title=f"Test {status}",
            company="Status Test Company",
        ),
        status=initial_status,
    )

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    result = monitor.detect_status(
        job_id=job_id,
        detected_status=status,
    )

    assert result["success"] is True
    assert result["changed"] is True

    assert (
        result["notification_required"]
        is False
    )

    assert (
        monitor.get_status(job_id)
        == status
    )


# ============================================================
# NO STATUS CHANGE
# ============================================================

def test_same_status_does_not_create_notification(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="shortlisted",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    result = monitor.detect_status(
        job_id=job_id,
        detected_status="shortlisted",
    )

    assert result["success"] is True
    assert result["changed"] is False

    assert (
        result["notification_required"]
        is False
    )

    assert result["old_status"] == (
        "shortlisted"
    )

    assert result["new_status"] == (
        "shortlisted"
    )


# ============================================================
# UNKNOWN JOB
# ============================================================

def test_unknown_job_returns_failure(
    tmp_path,
):
    store = make_store(tmp_path)

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    result = monitor.detect_status(
        job_id="does-not-exist",
        detected_status="shortlisted",
    )

    assert result["success"] is False
    assert result["changed"] is False

    assert (
        result["notification_required"]
        is False
    )


# ============================================================
# INVALID STATUS
# ============================================================

def test_invalid_status_is_rejected(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    with pytest.raises(ValueError):
        monitor.detect_status(
            job_id=job_id,
            detected_status="invalid_status",
        )


# ============================================================
# REQUIRES NOTIFICATION
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
def test_requires_notification_returns_true(
    tmp_path,
    status,
):
    store = make_store(tmp_path)

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    assert (
        monitor.requires_notification(status)
        is True
    )


def test_requires_notification_returns_false_for_applied(
    tmp_path,
):
    store = make_store(tmp_path)

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    assert (
        monitor.requires_notification(
            "applied"
        )
        is False
    )


# ============================================================
# TRACKED APPLICATIONS
# ============================================================

def test_get_tracked_applications(
    tmp_path,
):
    store = make_store(tmp_path)

    store.add_job(
        sample_job(
            "Electrical Engineer",
            "Company A",
        ),
        status="applied",
    )

    store.add_job(
        sample_job(
            "Automation Engineer",
            "Company B",
        ),
        status="shortlisted",
    )

    store.add_job(
        sample_job(
            "Graduate Engineer Trainee",
            "Company C",
        ),
        status="discovered",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    tracked = (
        monitor.get_tracked_applications()
    )

    assert len(tracked) == 2

    statuses = {
        job["status"]
        for job in tracked
    }

    assert "applied" in statuses
    assert "shortlisted" in statuses
    assert "discovered" not in statuses


# ============================================================
# SCAN
# ============================================================

def test_scan_detects_status_change(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    def provider(job):
        assert job["job_id"] == job_id
        return "shortlisted"

    events = monitor.scan(
        status_provider=provider
    )

    assert len(events) == 1

    event = events[0]

    assert event["job_id"] == job_id
    assert event["old_status"] == "applied"
    assert event["new_status"] == (
        "shortlisted"
    )

    assert (
        event["notification_required"]
        is True
    )

    assert monitor.get_status(job_id) == (
        "shortlisted"
    )


def test_scan_ignores_jobs_without_new_status(
    tmp_path,
):
    store = make_store(tmp_path)

    store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    events = monitor.scan(
        status_provider=lambda job: None
    )

    assert events == []


# ============================================================
# MULTIPLE APPLICATIONS
# ============================================================

def test_scan_multiple_applications(
    tmp_path,
):
    store = make_store(tmp_path)

    first_id = store.add_job(
        sample_job(
            "Electrical Engineer",
            "Company A",
        ),
        status="applied",
    )

    second_id = store.add_job(
        sample_job(
            "Automation Engineer",
            "Company B",
        ),
        status="applied",
    )

    third_id = store.add_job(
        sample_job(
            "Graduate Engineer Trainee",
            "Company C",
        ),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    status_map = {
        first_id: "shortlisted",
        second_id: "rejected",
        third_id: None,
    }

    def provider(job):
        return status_map[
            job["job_id"]
        ]

    events = monitor.scan(
        status_provider=provider
    )

    assert len(events) == 2

    changed_ids = {
        event["job_id"]
        for event in events
    }

    assert first_id in changed_ids
    assert second_id in changed_ids
    assert third_id not in changed_ids

    assert monitor.get_status(first_id) == (
        "shortlisted"
    )

    assert monitor.get_status(second_id) == (
        "rejected"
    )

    assert monitor.get_status(third_id) == (
        "applied"
    )


# ============================================================
# EMAIL NOTIFICATION
# ============================================================

def test_email_notification_can_be_created(
    tmp_path,
):
    notification = EmailNotification(
        sender="sender@example.com",
        password="test-password",
        recipient="user@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        enabled=True,
    )

    assert notification.is_enabled() is True
    assert notification.channel_name == (
        "Email"
    )


def test_email_notification_can_be_disabled(
    tmp_path,
):
    notification = EmailNotification(
        sender="sender@example.com",
        password="test-password",
        recipient="user@example.com",
        enabled=False,
    )

    assert notification.is_enabled() is False

    result = notification.send(
        title="Application Update",
        message=(
            "Your application was shortlisted."
        ),
    )

    assert result is False


# ============================================================
# EMAIL STRUCTURED RESULT
# ============================================================

def test_email_notification_send_result_captures_failure(
    tmp_path,
):
    notification = EmailNotification(
        sender="sender@example.com",
        password="test-password",
        recipient="user@example.com",
        smtp_host="invalid.smtp.example",
        smtp_port=1,
        enabled=True,
    )

    result = notification.send_result(
        title="Application Update",
        message=(
            "Your application was shortlisted."
        ),
    )

    assert result.success is False
    assert result.channel == "Email"

    assert result.title == (
        "Application Update"
    )

    assert result.message == (
        "Your application was shortlisted."
    )

    assert result.error is not None


# ============================================================
# COMPLETE STATUS → NOTIFICATION EVENT
# ============================================================

def test_complete_status_notification_flow(
    tmp_path,
):
    """
    Integration checkpoint:

        Applied Application
                ↓
        Status Monitor
                ↓
        Detected Shortlisted
                ↓
        JobStore Updated
                ↓
        Notification Required
    """

    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store,
    )

    result = monitor.detect_status(
        job_id=job_id,
        detected_status="shortlisted",
    )

    assert result["success"] is True
    assert result["changed"] is True

    assert result["old_status"] == (
        "applied"
    )

    assert result["new_status"] == (
        "shortlisted"
    )

    assert (
        result["notification_required"]
        is True
    )

    stored_job = store.get_job(
        job_id
    )

    assert stored_job is not None

    assert stored_job["status"] == (
        "shortlisted"
    )