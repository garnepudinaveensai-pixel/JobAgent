from app.jobs.application_tracker import ApplicationTracker
from app.jobs.job_store import JobStore


def make_tracker(tmp_path):
    store = JobStore(
        storage_path=str(
            tmp_path / "jobs.json"
        )
    )

    tracker = ApplicationTracker(
        store=store
    )

    return tracker


def make_job():
    return {
        "title": "Graduate Engineer Trainee",
        "company": "Test Company",
        "location": "Hyderabad",
        "url": "https://example.com/job/123",
        "description": "Electrical engineering role",
    }


# ============================================================
# REGISTRATION
# ============================================================

def test_register_job(tmp_path):
    tracker = make_tracker(tmp_path)

    job_id = tracker.register_job(
        make_job()
    )

    assert job_id
    assert (
        tracker.get_status(job_id)
        == "discovered"
    )


# ============================================================
# APPLICATION LIFECYCLE
# ============================================================

def test_application_lifecycle(tmp_path):
    tracker = make_tracker(tmp_path)

    job_id = tracker.register_job(
        make_job()
    )

    assert tracker.mark_matched(job_id)
    assert tracker.get_status(job_id) == "matched"

    assert tracker.mark_selected(job_id)
    assert tracker.get_status(job_id) == "selected"

    assert tracker.mark_application_started(job_id)
    assert (
        tracker.get_status(job_id)
        == "application_started"
    )

    assert tracker.mark_applied(job_id)
    assert tracker.get_status(job_id) == "applied"


# ============================================================
# POST-APPLICATION STATUS
# ============================================================

def test_post_application_statuses(tmp_path):
    tracker = make_tracker(tmp_path)

    job_id = tracker.register_job(
        make_job()
    )

    tracker.mark_applied(job_id)

    assert tracker.mark_shortlisted(job_id)
    assert (
        tracker.get_status(job_id)
        == "shortlisted"
    )

    assert tracker.mark_interview(job_id)
    assert (
        tracker.get_status(job_id)
        == "interview"
    )

    assert tracker.mark_assessment(job_id)
    assert (
        tracker.get_status(job_id)
        == "assessment"
    )

    assert tracker.mark_walk_in(job_id)
    assert (
        tracker.get_status(job_id)
        == "walk_in"
    )


# ============================================================
# REJECTION / FAILURE
# ============================================================

def test_rejected_application(tmp_path):
    tracker = make_tracker(tmp_path)

    job_id = tracker.register_job(
        make_job()
    )

    tracker.mark_application_started(job_id)

    assert tracker.mark_application_failed(job_id)
    assert (
        tracker.get_status(job_id)
        == "application_failed"
    )

    assert tracker.mark_rejected(job_id)
    assert (
        tracker.get_status(job_id)
        == "rejected"
    )


# ============================================================
# STATUS TIMESTAMP
# ============================================================

def test_status_timestamp_is_recorded(tmp_path):
    tracker = make_tracker(tmp_path)

    job_id = tracker.register_job(
        make_job()
    )

    tracker.mark_applied(job_id)

    application = tracker.get_application(
        job_id
    )

    assert application is not None
    assert "status_updated_at" in application
    assert application["status_updated_at"]


# ============================================================
# STATUS QUERIES
# ============================================================

def test_status_queries(tmp_path):
    tracker = make_tracker(tmp_path)

    job1 = tracker.register_job(
        make_job()
    )

    job2 = tracker.register_job(
        {
            **make_job(),
            "url": "https://example.com/job/456",
        }
    )

    tracker.mark_applied(job1)
    tracker.mark_shortlisted(job2)

    assert len(
        tracker.get_applied_jobs()
    ) == 1

    assert len(
        tracker.get_shortlisted_jobs()
    ) == 1


# ============================================================
# PENDING APPLICATIONS
# ============================================================

def test_pending_applications(tmp_path):
    tracker = make_tracker(tmp_path)

    job_id = tracker.register_job(
        make_job()
    )

    tracker.mark_application_started(
        job_id
    )

    pending = tracker.get_pending_applications()

    assert len(pending) == 1
    assert pending[0]["job_id"] == job_id


# ============================================================
# SUMMARY
# ============================================================

def test_summary(tmp_path):
    tracker = make_tracker(tmp_path)

    job1 = tracker.register_job(
        make_job()
    )

    job2 = tracker.register_job(
        {
            **make_job(),
            "url": "https://example.com/job/456",
        }
    )

    tracker.mark_applied(job1)
    tracker.mark_shortlisted(job2)

    summary = tracker.summary()

    assert summary["total"] == 2
    assert summary["applied"] == 1
    assert summary["shortlisted"] == 1


# ============================================================
# UNKNOWN JOB
# ============================================================

def test_unknown_job_returns_false(tmp_path):
    tracker = make_tracker(tmp_path)

    assert (
        tracker.mark_applied(
            "does-not-exist"
        )
        is False
    )


# ============================================================
# INVALID STATUS
# ============================================================

def test_invalid_status_raises_error(tmp_path):
    tracker = make_tracker(tmp_path)

    job_id = tracker.register_job(
        make_job()
    )

    try:
        tracker.update_status(
            job_id,
            "invalid_status",
        )
        assert False
    except ValueError:
        assert True