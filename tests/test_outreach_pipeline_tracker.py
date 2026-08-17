from __future__ import annotations

from unittest.mock import MagicMock

from app.outreach.outreach_pipeline import (
    OutreachPipeline,
)
from app.outreach.outreach_tracker import (
    OutreachTracker,
)


# ============================================================
# HELPERS
# ============================================================


def make_job():
    return {
        "job_id": "job-001",
        "title": "Electrical Engineer",
        "company": "Example Company",
        "location": "Hyderabad",
        "url": (
            "https://example.com/jobs/1"
        ),
        "description": (
            "Electrical engineering role."
        ),
    }


def make_candidate():
    return {
        "name": "Naveen Sai",
        "email": "naveen@example.com",
        "skills": [
            "Electrical Engineering",
            "Automation",
            "Python",
        ],
    }


def make_contact():
    return {
        "email": "recruiter@example.com",
        "name": "Recruiter",
        "role": "Talent Acquisition",
        "source": "Hunter",
    }


def make_selection():
    selection = MagicMock()

    selection.email = (
        "recruiter@example.com"
    )

    selection.score = 90

    selection.reason = (
        "Recruiter contact"
    )

    selection.contact = make_contact()

    return selection


def make_composed():
    return {
        "recipient": (
            "recruiter@example.com"
        ),
        "subject": (
            "Application for Electrical Engineer"
        ),
        "message": (
            "Dear Recruiter,\n\n"
            "I am interested in the role."
        ),
        "attachment": (
            "data/resumes/master_resume.pdf"
        ),
    }


def make_pipeline(
    tracker=None,
    sender=None,
):
    selector = MagicMock()

    selector.select_best_contact.return_value = (
        make_selection()
    )

    composer = MagicMock()

    composer.compose.return_value = (
        make_composed()
    )

    if sender is None:
        sender = MagicMock()

    pipeline = OutreachPipeline(
        contact_selector=selector,
        email_composer=composer,
        email_sender=sender,
        outreach_tracker=tracker,
    )

    return (
        pipeline,
        selector,
        composer,
        sender,
    )


# ============================================================
# PREPARED TRACKING
# ============================================================


def test_prepare_creates_tracker_record(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    (
        pipeline,
        selector,
        composer,
        sender,
    ) = make_pipeline(
        tracker=tracker,
    )

    result = pipeline.prepare_outreach(
        contacts=[make_contact()],
        job=make_job(),
    )

    assert result.success is True

    assert result.status == (
        "prepared"
    )

    assert result.tracker_id is not None

    assert result.email == (
        "recruiter@example.com"
    )

    assert result.subject == (
        "Application for Electrical Engineer"
    )

    assert result.attachment == (
        "data/resumes/master_resume.pdf"
    )

    selector.select_best_contact.assert_called_once()

    composer.compose.assert_called_once()

    sender.send.assert_not_called()

    record = tracker.get(
        result.tracker_id
    )

    assert record is not None

    assert record.status == (
        "prepared"
    )

    assert record.job_id == (
        "job-001"
    )

    assert record.contact_email == (
        "recruiter@example.com"
    )


# ============================================================
# CANDIDATE FORWARDING
# ============================================================


def test_prepare_forwards_candidate():

    (
        pipeline,
        selector,
        composer,
        sender,
    ) = make_pipeline()

    candidate = make_candidate()

    result = pipeline.prepare_outreach(
        contacts=[make_contact()],
        job=make_job(),
        candidate=candidate,
    )

    assert result.success is True

    kwargs = (
        composer.compose.call_args.kwargs
    )

    assert kwargs["job"] == make_job()

    assert kwargs["candidate"] == candidate

    assert kwargs["contact"] == (
        make_selection().contact
    )


# ============================================================
# EXPLICIT RESUME
# ============================================================


def test_prepare_uses_explicit_resume(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    (
        pipeline,
        selector,
        composer,
        sender,
    ) = make_pipeline(
        tracker=tracker,
    )

    resume_path = (
        "data/resumes/tailored/"
        "electrical_engineer.pdf"
    )

    result = pipeline.prepare_outreach(
        contacts=[make_contact()],
        job=make_job(),
        candidate=make_candidate(),
        resume_path=resume_path,
    )

    assert result.success is True

    assert result.attachment == (
        resume_path
    )

    kwargs = (
        composer.compose.call_args.kwargs
    )

    assert kwargs["resume_path"] == (
        resume_path
    )


# ============================================================
# CONFIRMATION
# ============================================================


def test_confirmation_required_is_tracked(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    sender = MagicMock()

    sender.send.return_value = True

    (
        pipeline,
        selector,
        composer,
        sender,
    ) = make_pipeline(
        tracker=tracker,
        sender=sender,
    )

    result = pipeline.send_outreach(
        contacts=[make_contact()],
        job=make_job(),
        candidate=make_candidate(),
        confirm=False,
    )

    assert result.success is True

    assert result.status == (
        "confirmation_required"
    )

    assert result.tracker_id is not None

    # CRITICAL SAFETY CHECK
    sender.send.assert_not_called()

    record = tracker.get(
        result.tracker_id
    )

    assert record is not None

    assert record.status == (
        "confirmation_required"
    )


# ============================================================
# SUCCESSFUL SEND
# ============================================================


def test_successful_send_updates_tracker(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    sender = MagicMock()

    sender.send.return_value = {
        "success": True,
        "recipient": (
            "recruiter@example.com"
        ),
        "subject": (
            "Application for Electrical Engineer"
        ),
        "dry_run": True,
    }

    (
        pipeline,
        selector,
        composer,
        sender,
    ) = make_pipeline(
        tracker=tracker,
        sender=sender,
    )

    result = pipeline.send_outreach(
        contacts=[make_contact()],
        job=make_job(),
        candidate=make_candidate(),
        confirm=True,
    )

    assert result.success is True

    assert result.status == "sent"

    assert result.tracker_id is not None

    assert result.email == (
        "recruiter@example.com"
    )

    assert result.dry_run is True

    sender.send.assert_called_once()

    record = tracker.get(
        result.tracker_id
    )

    assert record is not None

    assert record.status == "sent"

    assert record.send_attempts == 1

    assert record.sent_at is not None

    assert record.dry_run is True


# ============================================================
# FAILED SEND
# ============================================================


def test_failed_send_updates_tracker(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    sender = MagicMock()

    sender.send.return_value = {
        "success": False,
        "error": "SMTP failed",
    }

    (
        pipeline,
        selector,
        composer,
        sender,
    ) = make_pipeline(
        tracker=tracker,
        sender=sender,
    )

    result = pipeline.send_outreach(
        contacts=[make_contact()],
        job=make_job(),
        candidate=make_candidate(),
        confirm=True,
    )

    assert result.success is False

    assert result.status == (
        "send_failed"
    )

    assert result.tracker_id is not None

    assert result.error == (
        "SMTP failed"
    )

    record = tracker.get(
        result.tracker_id
    )

    assert record is not None

    assert record.status == (
        "send_failed"
    )

    assert record.send_attempts == 1

    assert record.error == (
        "SMTP failed"
    )


# ============================================================
# SENDER EXCEPTION
# ============================================================


def test_sender_exception_updates_tracker(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    sender = MagicMock()

    sender.send.side_effect = (
        RuntimeError(
            "SMTP connection failed"
        )
    )

    (
        pipeline,
        selector,
        composer,
        sender,
    ) = make_pipeline(
        tracker=tracker,
        sender=sender,
    )

    result = pipeline.send_outreach(
        contacts=[make_contact()],
        job=make_job(),
        candidate=make_candidate(),
        confirm=True,
    )

    assert result.success is False

    assert result.status == (
        "send_failed"
    )

    assert result.tracker_id is not None

    assert result.error == (
        "SMTP connection failed"
    )

    record = tracker.get(
        result.tracker_id
    )

    assert record is not None

    assert record.status == (
        "send_failed"
    )

    assert record.send_attempts == 1

    assert record.error == (
        "SMTP connection failed"
    )


# ============================================================
# TRACKING DISABLED
# ============================================================


def test_pipeline_works_without_tracker():

    (
        pipeline,
        selector,
        composer,
        sender,
    ) = make_pipeline()

    result = pipeline.prepare_outreach(
        contacts=[make_contact()],
        job=make_job(),
        candidate=make_candidate(),
    )

    assert result.success is True

    assert result.status == (
        "prepared"
    )

    assert result.tracker_id is None


# ============================================================
# TRACKER FAILURE MUST NOT BREAK OUTREACH
# ============================================================


def test_tracker_failure_does_not_break_prepare():

    tracker = MagicMock()

    tracker.create.side_effect = (
        RuntimeError(
            "Tracker storage failed"
        )
    )

    (
        pipeline,
        selector,
        composer,
        sender,
    ) = make_pipeline(
        tracker=tracker,
    )

    result = pipeline.prepare_outreach(
        contacts=[make_contact()],
        job=make_job(),
    )

    assert result.success is True

    assert result.status == (
        "prepared"
    )

    assert result.tracker_id is None


# ============================================================
# TRACKER FAILURE DOES NOT BREAK SEND
# ============================================================


def test_tracker_failure_does_not_break_send():

    tracker = MagicMock()

    tracker.create.side_effect = (
        RuntimeError(
            "Tracker storage failed"
        )
    )

    sender = MagicMock()

    sender.send.return_value = {
        "success": True,
        "dry_run": True,
    }

    (
        pipeline,
        selector,
        composer,
        sender,
    ) = make_pipeline(
        tracker=tracker,
        sender=sender,
    )

    result = pipeline.send_outreach(
        contacts=[make_contact()],
        job=make_job(),
        confirm=True,
    )

    assert result.success is True

    assert result.status == "sent"

    assert result.dry_run is True

    sender.send.assert_called_once()


# ============================================================
# NO CONTACT
# ============================================================


def test_prepare_without_contact():

    selector = MagicMock()

    selector.select_best_contact.return_value = None

    composer = MagicMock()

    sender = MagicMock()

    pipeline = OutreachPipeline(
        contact_selector=selector,
        email_composer=composer,
        email_sender=sender,
    )

    result = pipeline.prepare_outreach(
        contacts=[],
        job=make_job(),
    )

    assert result.success is False

    assert result.status == (
        "no_suitable_contact"
    )

    composer.compose.assert_not_called()

    sender.send.assert_not_called()


# ============================================================
# INVALID CANDIDATE
# ============================================================


def test_invalid_candidate_is_rejected():

    pipeline = OutreachPipeline()

    try:

        pipeline.prepare_outreach(
            contacts=[],
            job=make_job(),
            candidate=None,
        )

    except TypeError as exc:

        assert "candidate" in str(
            exc
        )

    else:

        assert False, (
            "Expected TypeError"
        )


# ============================================================
# INVALID JOB
# ============================================================


def test_invalid_job_is_rejected():

    pipeline = OutreachPipeline()

    try:

        pipeline.prepare_outreach(
            contacts=[],
            job=None,
        )

    except TypeError as exc:

        assert "job" in str(
            exc
        )

    else:

        assert False, (
            "Expected TypeError"
        )