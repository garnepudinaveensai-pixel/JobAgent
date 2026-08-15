from __future__ import annotations

import pytest

from app.jobs.application_status_monitor import (
    ApplicationStatusMonitor,
)
from app.jobs.email_status_reader import (
    EmailMessage,
    EmailStatusReader,
)
from app.jobs.job_store import JobStore


# ============================================================
# FIXTURES / HELPERS
# ============================================================


def make_store(tmp_path):
    return JobStore(
        storage_path=str(
            tmp_path / "jobs.json"
        )
    )


def make_monitor(tmp_path):
    store = make_store(tmp_path)

    return (
        store,
        ApplicationStatusMonitor(
            job_store=store
        ),
    )


def make_reader(tmp_path):
    store, monitor = make_monitor(
        tmp_path
    )

    return (
        store,
        monitor,
        EmailStatusReader(
            monitor=monitor
        ),
    )


def sample_job(
    title="Electrical Engineer",
    company="ABC Technologies",
    url=None,
):
    """
    Create a unique test job.

    JobStore uses URL as the preferred stable
    identifier, so different logical jobs must
    have different URLs.
    """

    if url is None:
        company_slug = (
            str(company)
            .strip()
            .lower()
            .replace(" ", "-")
            .replace("/", "-")
        )

        title_slug = (
            str(title)
            .strip()
            .lower()
            .replace(" ", "-")
            .replace("/", "-")
        )

        url = (
            "https://example.com/jobs/"
            f"{company_slug}-{title_slug}"
        )

    return {
        "title": title,
        "company": company,
        "location": "Hyderabad",
        "url": url,
        "description": (
            f"{title} role at {company}."
        ),
    }


def make_email(
    sender="hr@abctechnologies.com",
    subject="Application Update",
    body="Thank you for applying.",
):
    return EmailMessage(
        sender=sender,
        subject=subject,
        body=body,
    )


# ============================================================
# EMAIL NORMALIZATION
# ============================================================


def test_normalize_text():
    result = EmailStatusReader.normalize_text(
        "  Hello\r\n\r\nWorld   Test  "
    )

    assert result == (
        "hello\n\nworld test"
    )


def test_email_validation_rejects_invalid_email():
    email = EmailMessage(
        sender="",
        subject="Application",
        body="Test",
    )

    with pytest.raises(ValueError):
        EmailStatusReader.validate_email(
            email
        )


# ============================================================
# STATUS DETECTION
# ============================================================


@pytest.mark.parametrize(
    "body, expected_status",
    [
        (
            "Congratulations! You have been "
            "shortlisted for the next round.",
            "shortlisted",
        ),
        (
            "We regret to inform you that your "
            "application was not successful.",
            "rejected",
        ),
        (
            "We would like to invite you to an "
            "interview with our hiring team.",
            "interview",
        ),
        (
            "You are invited to complete the "
            "online assessment.",
            "assessment",
        ),
        (
            "Please attend our walk-in interview "
            "drive.",
            "walk_in",
        ),
    ],
)
def test_detect_supported_statuses(
    tmp_path,
    body,
    expected_status,
):
    _, _, reader = make_reader(
        tmp_path
    )

    result = reader.detect_status(
        make_email(
            body=body
        )
    )

    assert result.status == expected_status
    assert result.confidence > 0
    assert result.reason


def test_detect_status_returns_none_for_normal_email(
    tmp_path,
):
    _, _, reader = make_reader(
        tmp_path
    )

    result = reader.detect_status(
        make_email(
            subject="Application Received",
            body=(
                "Thank you for applying. "
                "We have received your application."
            ),
        )
    )

    assert result.status is None
    assert result.confidence == 0.0


def test_subject_can_trigger_status_detection(
    tmp_path,
):
    _, _, reader = make_reader(
        tmp_path
    )

    email = make_email(
        subject="Interview Invitation",
        body="Please confirm your availability.",
    )

    result = reader.detect_status(
        email
    )

    assert result.status == "interview"


# ============================================================
# SUPPORTED STATUS CHECK
# ============================================================


@pytest.mark.parametrize(
    "status",
    [
        "shortlisted",
        "rejected",
        "interview",
        "assessment",
        "walk_in",
    ],
)
def test_trackable_statuses(
    tmp_path,
    status,
):
    _, _, reader = make_reader(
        tmp_path
    )

    assert reader.is_trackable_status(
        status
    )


def test_unknown_status_is_not_trackable(
    tmp_path,
):
    _, _, reader = make_reader(
        tmp_path
    )

    assert not reader.is_trackable_status(
        "application_started"
    )


def test_supported_statuses_contains_expected_values(
    tmp_path,
):
    _, _, reader = make_reader(
        tmp_path
    )

    statuses = reader.supported_statuses()

    assert set(statuses) == {
        "shortlisted",
        "rejected",
        "interview",
        "assessment",
        "walk_in",
    }


# ============================================================
# JOB MATCHING
# ============================================================


def test_email_matches_job_by_company(
    tmp_path,
):
    _, _, reader = make_reader(
        tmp_path
    )

    email = make_email(
        body=(
            "ABC Technologies would like to "
            "invite you to an interview."
        )
    )

    assert reader.email_matches_job(
        email,
        sample_job(),
    )


def test_email_matches_job_by_title(
    tmp_path,
):
    _, _, reader = make_reader(
        tmp_path
    )

    email = make_email(
        body=(
            "Regarding your Electrical Engineer "
            "application, you have been shortlisted."
        )
    )

    assert reader.email_matches_job(
        email,
        sample_job(),
    )


def test_email_does_not_match_unrelated_job(
    tmp_path,
):
    _, _, reader = make_reader(
        tmp_path
    )

    email = make_email(
        sender="hr@othercompany.com",
        body=(
            "You have been shortlisted for "
            "the position."
        ),
    )

    unrelated_job = sample_job(
        title="Software Engineer",
        company="XYZ Systems",
    )

    assert not reader.email_matches_job(
        email,
        unrelated_job,
    )


# ============================================================
# FIND MATCHING JOB
# ============================================================


def test_find_matching_job(
    tmp_path,
):
    store, _, reader = make_reader(
        tmp_path
    )

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    email = make_email(
        body=(
            "ABC Technologies has shortlisted "
            "your Electrical Engineer application."
        )
    )

    job = reader.find_matching_job(
        email
    )

    assert job is not None
    assert job["job_id"] == job_id


def test_find_matching_job_returns_none(
    tmp_path,
):
    _, _, reader = make_reader(
        tmp_path
    )

    email = make_email(
        sender="hr@unknown.com",
        body=(
            "Congratulations, you have been "
            "shortlisted."
        ),
    )

    job = reader.find_matching_job(
        email,
        jobs=[
            sample_job(
                title="Software Engineer",
                company="XYZ Systems",
            )
        ],
    )

    assert job is None


# ============================================================
# PROCESS EMAIL
# ============================================================


def test_process_email_detects_status_without_match(
    tmp_path,
):
    _, _, reader = make_reader(
        tmp_path
    )

    email = make_email(
        sender="hr@unknown.com",
        subject="Application Update",
        body=(
            "You have been shortlisted for "
            "the next round."
        ),
    )

    result = reader.process_email(
        email
    )

    assert result["success"] is True
    assert result["status_detected"] is True
    assert result["status"] == "shortlisted"
    assert result["job_id"] is None
    assert result["job"] is None


def test_process_email_matches_application(
    tmp_path,
):
    store, _, reader = make_reader(
        tmp_path
    )

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    email = make_email(
        body=(
            "ABC Technologies has shortlisted "
            "your Electrical Engineer application."
        )
    )

    result = reader.process_email(
        email
    )

    assert result["success"] is True
    assert result["status_detected"] is True
    assert result["status"] == "shortlisted"
    assert result["job_id"] == job_id
    assert result["job"]["job_id"] == job_id


def test_process_email_without_status(
    tmp_path,
):
    _, _, reader = make_reader(
        tmp_path
    )

    email = make_email(
        subject="Application Received",
        body=(
            "We have received your application "
            "and will review it."
        ),
    )

    result = reader.process_email(
        email
    )

    assert result["success"] is True
    assert result["status_detected"] is False
    assert result["status"] is None
    assert result["job_id"] is None


# ============================================================
# UPDATE APPLICATION FROM EMAIL
# ============================================================


def test_update_application_from_email(
    tmp_path,
):
    store, monitor, reader = make_reader(
        tmp_path
    )

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    email = make_email(
        body=(
            "Congratulations! ABC Technologies "
            "has shortlisted you for the next round "
            "for the Electrical Engineer position."
        )
    )

    result = (
        reader.update_application_from_email(
            email
        )
    )

    assert result["success"] is True
    assert result["status"] == "shortlisted"
    assert result["job_id"] == job_id
    assert result["changed"] is True
    assert result["notification_required"] is True

    assert (
        monitor.get_status(job_id)
        == "shortlisted"
    )


def test_rejection_updates_application(
    tmp_path,
):
    store, _, reader = make_reader(
        tmp_path
    )

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    email = make_email(
        body=(
            "We regret to inform you that "
            "your application with ABC Technologies "
            "was not selected."
        )
    )

    result = (
        reader.update_application_from_email(
            email
        )
    )

    assert result["success"] is True
    assert result["status"] == "rejected"
    assert result["job_id"] == job_id
    assert result["changed"] is True
    assert result["notification_required"] is True

    assert (
        store.get_status(job_id)
        == "rejected"
    )


def test_interview_updates_application(
    tmp_path,
):
    store, _, reader = make_reader(
        tmp_path
    )

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    email = make_email(
        subject="Interview Invitation",
        body=(
            "ABC Technologies would like to "
            "schedule an interview for the "
            "Electrical Engineer position."
        ),
    )

    result = (
        reader.update_application_from_email(
            email
        )
    )

    assert result["success"] is True
    assert result["status"] == "interview"
    assert result["job_id"] == job_id
    assert result["changed"] is True

    assert (
        store.get_status(job_id)
        == "interview"
    )


def test_unknown_application_is_not_updated(
    tmp_path,
):
    store, _, reader = make_reader(
        tmp_path
    )

    email = make_email(
        sender="hr@unknown.com",
        body=(
            "You have been shortlisted for "
            "the next round."
        ),
    )

    result = reader.update_application_from_email(
        email
    )

    assert result["success"] is True
    assert result["status_detected"] is True
    assert result["job_id"] is None
    assert result["changed"] is False

    assert store.count() == 0


# ============================================================
# DUPLICATE STATUS
# ============================================================


def test_duplicate_status_does_not_create_change(
    tmp_path,
):
    store, _, reader = make_reader(
        tmp_path
    )

    job_id = store.add_job(
        sample_job(),
        status="shortlisted",
    )

    email = make_email(
        body=(
            "ABC Technologies has shortlisted "
            "your Electrical Engineer application."
        )
    )

    result = (
        reader.update_application_from_email(
            email
        )
    )

    assert result["success"] is True
    assert result["status"] == "shortlisted"
    assert result["job_id"] == job_id
    assert result["changed"] is False
    assert (
        result["notification_required"]
        is False
    )


# ============================================================
# MULTIPLE EMAILS
# ============================================================


def test_process_multiple_emails(
    tmp_path,
):
    store, _, reader = make_reader(
        tmp_path
    )

    first_id = store.add_job(
        sample_job(
            title="Electrical Engineer",
            company="ABC Technologies",
        ),
        status="applied",
    )

    second_id = store.add_job(
        sample_job(
            title="Automation Engineer",
            company="XYZ Systems",
        ),
        status="applied",
    )

    # Sanity check:
    # The two logical jobs MUST have different IDs.
    assert first_id != second_id

    emails = [
        EmailMessage(
            sender="hr@abctechnologies.com",
            subject="Application Update",
            body=(
                "You have been shortlisted for "
                "the Electrical Engineer position "
                "at ABC Technologies."
            ),
        ),
        EmailMessage(
            sender="hr@xyzsystems.com",
            subject="Interview Invitation",
            body=(
                "XYZ Systems would like to schedule "
                "an interview for the Automation Engineer "
                "position."
            ),
        ),
        EmailMessage(
            sender="notifications@example.com",
            subject="Newsletter",
            body=(
                "This is a general company newsletter."
            ),
        ),
    ]

    results = reader.process_emails(
        emails
    )

    assert len(results) == 3

    # First email -> ABC Technologies
    assert results[0]["success"] is True
    assert results[0]["status_detected"] is True
    assert results[0]["job_id"] == first_id
    assert results[0]["status"] == "shortlisted"

    # Second email -> XYZ Systems
    assert results[1]["success"] is True
    assert results[1]["status_detected"] is True
    assert results[1]["job_id"] == second_id
    assert results[1]["status"] == "interview"

    # Third email -> unrelated newsletter
    assert results[2]["success"] is True
    assert results[2]["status_detected"] is False
    assert results[2]["job_id"] is None
    assert results[2]["status"] is None

    # Verify persistent statuses
    assert (
        store.get_status(first_id)
        == "shortlisted"
    )

    assert (
        store.get_status(second_id)
        == "interview"
    )


# ============================================================
# END-TO-END STATUS FLOW
# ============================================================


def test_email_to_application_status_flow(
    tmp_path,
):
    store, monitor, reader = make_reader(
        tmp_path
    )

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    email = EmailMessage(
        sender="careers@abctechnologies.com",
        subject=(
            "Congratulations - Interview Invitation"
        ),
        body=(
            "Dear Candidate,\n\n"
            "ABC Technologies would like to invite "
            "you to an interview for the Electrical "
            "Engineer position.\n\n"
            "Regards,\n"
            "Recruitment Team"
        ),
    )

    result = (
        reader.update_application_from_email(
            email
        )
    )

    assert result["success"] is True
    assert result["status_detected"] is True
    assert result["status"] == "interview"
    assert result["job_id"] == job_id
    assert result["changed"] is True
    assert result["notification_required"] is True

    assert (
        monitor.get_status(job_id)
        == "interview"
    )

    stored_job = monitor.get_job(
        job_id
    )

    assert stored_job is not None
    assert (
        stored_job["status"]
        == "interview"
    )