from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.outreach.outreach_tracker import (
    OUTREACH_STATUSES,
    OutreachRecord,
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
    }


def make_contact():
    return {
        "email": "recruiter@example.com",
        "name": "Recruiter",
        "role": "Talent Acquisition",
        "company": "Example Company",
        "source": "Hunter",
    }


# ============================================================
# CREATION
# ============================================================


def test_tracker_creation(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    assert tracker is not None
    assert tracker.get_all() == []


def test_tracker_rejects_empty_storage_path():

    with pytest.raises(
        ValueError,
        match="storage_path cannot be empty",
    ):
        OutreachTracker(
            storage_path=""
        )


# ============================================================
# CREATE
# ============================================================


def test_create_outreach_record(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
        subject=(
            "Application for Electrical Engineer"
        ),
        resume_path=(
            "data/resumes/master_resume.pdf"
        ),
    )

    assert isinstance(
        record,
        OutreachRecord,
    )

    assert record.job_id == "job-001"
    assert record.job_title == (
        "Electrical Engineer"
    )
    assert record.company == (
        "Example Company"
    )
    assert record.contact_email == (
        "recruiter@example.com"
    )
    assert record.status == "prepared"


def test_create_persists_record(tmp_path):

    path = (
        tmp_path
        / "outreach.json"
    )

    tracker = OutreachTracker(
        storage_path=str(path)
    )

    tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    assert path.exists()

    second = OutreachTracker(
        storage_path=str(path)
    )

    records = second.get_all()

    assert len(records) == 1
    assert records[0].job_id == (
        "job-001"
    )


# ============================================================
# VALIDATION
# ============================================================


def test_create_requires_job_dict(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    with pytest.raises(
        TypeError,
        match="job must be a dictionary",
    ):
        tracker.create(
            job="invalid",
            contact=make_contact(),
        )


def test_create_requires_contact_dict(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    with pytest.raises(
        TypeError,
        match="contact must be a dictionary",
    ):
        tracker.create(
            job=make_job(),
            contact="invalid",
        )


def test_create_requires_job_identifier(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    job = {
        "title": "Engineer",
        "company": "Example",
    }

    with pytest.raises(
        ValueError,
        match="job must contain job_id",
    ):
        tracker.create(
            job=job,
            contact=make_contact(),
        )


def test_create_requires_contact_email(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    with pytest.raises(
        ValueError,
        match="contact must contain an email",
    ):
        tracker.create(
            job=make_job(),
            contact={
                "name": "Recruiter"
            },
        )


def test_invalid_status_rejected(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    with pytest.raises(
        ValueError,
        match="Invalid outreach status",
    ):
        tracker.create(
            job=make_job(),
            contact=make_contact(),
            status="invalid",
        )


# ============================================================
# DUPLICATE PROTECTION
# ============================================================


def test_duplicate_job_contact_returns_existing_record(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    first = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    second = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    assert first.outreach_id == (
        second.outreach_id
    )

    assert len(
        tracker.get_all()
    ) == 1


def test_same_job_different_contact_creates_second_record(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    first = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    second_contact = make_contact()

    second_contact[
        "email"
    ] = "hr@example.com"

    second = tracker.create(
        job=make_job(),
        contact=second_contact,
    )

    assert first.outreach_id != (
        second.outreach_id
    )

    assert len(
        tracker.get_all()
    ) == 2


# ============================================================
# GET / FIND
# ============================================================


def test_get_record(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    found = tracker.get(
        record.outreach_id
    )

    assert found is record


def test_get_unknown_record_returns_none(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    assert tracker.get(
        "does-not-exist"
    ) is None


def test_find_by_job_and_email(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    found = tracker.find(
        job_id="job-001",
        contact_email=(
            "RECRUITER@EXAMPLE.COM"
        ),
    )

    assert found is record


# ============================================================
# LIST / FILTER
# ============================================================


def test_list_by_status(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    records = tracker.list(
        status="prepared"
    )

    assert len(records) == 1
    assert records[0].status == (
        "prepared"
    )


def test_list_by_company(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    records = tracker.list(
        company="example company"
    )

    assert len(records) == 1


def test_list_by_email(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    records = tracker.list(
        contact_email=(
            "RECRUITER@EXAMPLE.COM"
        )
    )

    assert len(records) == 1


# ============================================================
# STATUS
# ============================================================


def test_update_status(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    updated = tracker.update_status(
        record.outreach_id,
        "sent",
    )

    assert updated is not None
    assert updated.status == "sent"
    assert updated.sent_at is not None


def test_update_unknown_status_record(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    result = tracker.update_status(
        "does-not-exist",
        "sent",
    )

    assert result is None


def test_update_invalid_status_raises(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    with pytest.raises(
        ValueError,
        match="Invalid outreach status",
    ):
        tracker.update_status(
            record.outreach_id,
            "invalid",
        )


# ============================================================
# SEND RESULT
# ============================================================


def test_record_successful_send(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    updated = tracker.record_send_result(
        record.outreach_id,
        success=True,
        dry_run=True,
    )

    assert updated.status == "sent"
    assert updated.send_attempts == 1
    assert updated.sent_at is not None
    assert updated.dry_run is True


def test_record_failed_send(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    updated = tracker.record_send_result(
        record.outreach_id,
        success=False,
        error="SMTP failed",
    )

    assert updated.status == (
        "send_failed"
    )
    assert updated.send_attempts == 1
    assert updated.error == (
        "SMTP failed"
    )


# ============================================================
# FOLLOW-UP
# ============================================================


def test_schedule_follow_up(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    updated = tracker.schedule_follow_up(
        record.outreach_id,
        follow_up_days=7,
    )

    assert updated.follow_up_at is not None


def test_negative_follow_up_days_rejected(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        tracker.schedule_follow_up(
            record.outreach_id,
            follow_up_days=-1,
        )


def test_due_follow_up_detection(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
        status="sent",
    )

    record.follow_up_at = (
        datetime.now(
            timezone.utc
        )
        - timedelta(
            days=1
        )
    ).isoformat()

    # Save through a normal state-changing call.
    tracker.update_status(
        record.outreach_id,
        "sent",
    )

    due = tracker.get_due_follow_ups()

    assert len(due) == 1
    assert due[0].outreach_id == (
        record.outreach_id
    )


def test_mark_follow_up_due(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
        status="sent",
    )

    record.follow_up_at = (
        datetime.now(
            timezone.utc
        )
        - timedelta(
            days=1
        )
    ).isoformat()

    tracker.update_status(
        record.outreach_id,
        "sent",
    )

    updated = (
        tracker.mark_follow_up_due()
    )

    assert len(updated) == 1
    assert updated[0].status == (
        "follow_up_due"
    )


# ============================================================
# REPLY
# ============================================================


def test_record_reply(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
        status="sent",
    )

    updated = tracker.record_reply(
        record.outreach_id,
        response_status="replied",
        notes="Recruiter responded.",
    )

    assert updated.status == (
        "replied"
    )

    assert updated.response_status == (
        "replied"
    )

    assert updated.replied_at is not None

    assert "Recruiter responded." in (
        updated.notes
    )


def test_record_interview_response(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
        status="sent",
    )

    updated = tracker.record_reply(
        record.outreach_id,
        response_status="interview",
    )

    assert updated.status == (
        "interview"
    )


def test_invalid_response_status_rejected(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
        status="sent",
    )

    with pytest.raises(
        ValueError,
        match="response_status must be",
    ):
        tracker.record_reply(
            record.outreach_id,
            response_status="prepared",
        )


# ============================================================
# NOTES
# ============================================================


def test_add_note(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    updated = tracker.add_note(
        record.outreach_id,
        "Sent personalized email.",
    )

    assert (
        "Sent personalized email."
        in updated.notes
    )


def test_empty_note_rejected(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    with pytest.raises(
        ValueError,
        match="note cannot be empty",
    ):
        tracker.add_note(
            record.outreach_id,
            "   ",
        )


# ============================================================
# DELETE
# ============================================================


def test_delete_record(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    assert tracker.delete(
        record.outreach_id
    ) is True

    assert tracker.get(
        record.outreach_id
    ) is None


def test_delete_unknown_record(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    assert tracker.delete(
        "does-not-exist"
    ) is False


# ============================================================
# SUMMARY
# ============================================================


def test_empty_summary(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    summary = tracker.summary()

    assert summary["total"] == 0

    for status in OUTREACH_STATUSES:
        assert summary[status] == 0

    assert summary[
        "send_attempts"
    ] == 0


def test_summary_counts_statuses(
    tmp_path,
):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    first = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    second_contact = make_contact()
    second_contact[
        "email"
    ] = "hr@example.com"

    second = tracker.create(
        job={
            **make_job(),
            "job_id": "job-002",
        },
        contact=second_contact,
        status="prepared",
    )

    tracker.update_status(
        first.outreach_id,
        "sent",
    )

    tracker.update_status(
        second.outreach_id,
        "follow_up_due",
    )

    summary = tracker.summary()

    assert summary["total"] == 2
    assert summary["sent"] == 1
    assert summary[
        "follow_up_due"
    ] == 1


# ============================================================
# SERIALIZATION
# ============================================================


def test_to_dict(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    record = tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    data = tracker.to_dict(
        record
    )

    assert isinstance(
        data,
        dict,
    )

    assert data[
        "outreach_id"
    ] == record.outreach_id

    assert data[
        "contact_email"
    ] == (
        "recruiter@example.com"
    )


def test_to_list(tmp_path):

    tracker = OutreachTracker(
        storage_path=str(
            tmp_path
            / "outreach.json"
        )
    )

    tracker.create(
        job=make_job(),
        contact=make_contact(),
    )

    result = tracker.to_list()

    assert isinstance(
        result,
        list,
    )

    assert len(result) == 1
    assert isinstance(
        result[0],
        dict,
    )


# ============================================================
# CORRUPT STORAGE
# ============================================================


def test_invalid_json_starts_empty(
    tmp_path,
):

    path = (
        tmp_path
        / "outreach.json"
    )

    path.write_text(
        "not valid json",
        encoding="utf-8",
    )

    tracker = OutreachTracker(
        storage_path=str(path)
    )

    assert tracker.get_all() == []


def test_invalid_record_is_ignored(
    tmp_path,
):

    path = (
        tmp_path
        / "outreach.json"
    )

    path.write_text(
        '[{"invalid": true}]',
        encoding="utf-8",
    )

    tracker = OutreachTracker(
        storage_path=str(path)
    )

    assert tracker.get_all() == []