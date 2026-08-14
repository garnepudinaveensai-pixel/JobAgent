from app.core.application_orchestrator import (
    ApplicationOrchestrator,
)


# ============================================================
# FAKE SUBMITTER
# ============================================================

class FakeSubmitter:

    def __init__(
        self,
        prepare_success=True,
        submit_success=True,
    ):
        self.prepare_success = prepare_success
        self.submit_success = submit_success

        self.prepare_calls = []
        self.submit_calls = []

    def prepare_application(
        self,
        resume_path,
        fields,
    ):
        self.prepare_calls.append(
            {
                "resume_path": resume_path,
                "fields": fields,
            }
        )

        return {
            "success": self.prepare_success,
            "filled_fields": list(fields.keys()),
            "resume_uploaded": True,
            "validation": {
                "ready": self.prepare_success,
                "missing_required_fields": [],
            },
        }

    def submit(
        self,
        confirm=False,
    ):
        self.submit_calls.append(
            {
                "confirm": confirm,
            }
        )

        return {
            "success": self.submit_success,
            "status": (
                "submitted"
                if self.submit_success
                else "submission_failed"
            ),
        }


# ============================================================
# FAKE JOB STORE
# ============================================================

class FakeJobStore:

    def __init__(self):
        self.statuses = {}

    def update_status(
        self,
        job_id,
        status,
    ):
        self.statuses[job_id] = status
        return True


# ============================================================
# FAKE NOTIFIER
# ============================================================

class FakeNotifier:

    def __init__(self):
        self.notifications = []

    def notify(
        self,
        event,
        data,
    ):
        self.notifications.append(
            {
                "event": event,
                "data": data,
            }
        )


# ============================================================
# JOB
# ============================================================

def make_job():
    return {
        "job_id": "job-001",
        "title": "Automation Engineer",
        "company": "Example Company",
        "location": "Hyderabad",
        "url": "https://example.com/job-001",
        "description": "Automation engineering role.",
    }


# ============================================================
# TESTS
# ============================================================

def test_initialization():

    submitter = FakeSubmitter()

    orchestrator = ApplicationOrchestrator(
        submitter
    )

    assert orchestrator.submitter == submitter
    assert orchestrator.current_job is None
    assert orchestrator.current_job_id is None


def test_set_job():

    submitter = FakeSubmitter()

    orchestrator = ApplicationOrchestrator(
        submitter
    )

    result = orchestrator.set_job(
        make_job()
    )

    assert result["success"] is True
    assert result["job_id"] == "job-001"

    assert (
        orchestrator.current_job["title"]
        == "Automation Engineer"
    )


def test_set_job_requires_dict():

    submitter = FakeSubmitter()

    orchestrator = ApplicationOrchestrator(
        submitter
    )

    try:
        orchestrator.set_job(
            "invalid"
        )
        assert False
    except TypeError:
        assert True


def test_prepare_application():

    submitter = FakeSubmitter()

    orchestrator = ApplicationOrchestrator(
        submitter
    )

    orchestrator.set_job(
        make_job()
    )

    result = orchestrator.prepare_application(
        resume_path="resume.pdf",
        fields={
            "First Name": "Naveen",
            "Email": "test@example.com",
        },
    )

    assert result["success"] is True

    assert (
        result["status"]
        == "ready_for_submission"
    )

    assert result["resume_uploaded"] is True

    assert result["filled_fields"] == [
        "First Name",
        "Email",
    ]


def test_preparation_requires_job():

    submitter = FakeSubmitter()

    orchestrator = ApplicationOrchestrator(
        submitter
    )

    try:
        orchestrator.prepare_application(
            resume_path="resume.pdf",
            fields={},
        )
        assert False
    except RuntimeError:
        assert True


def test_confirmation_required_before_submission():

    submitter = FakeSubmitter()

    orchestrator = ApplicationOrchestrator(
        submitter
    )

    orchestrator.set_job(
        make_job()
    )

    orchestrator.prepare_application(
        resume_path="resume.pdf",
        fields={
            "First Name": "Naveen",
        },
    )

    result = orchestrator.submit_application()

    assert result["success"] is False

    assert (
        result["status"]
        == "confirmation_required"
    )

    assert submitter.submit_calls == []


def test_submit_after_confirmation():

    submitter = FakeSubmitter()
    store = FakeJobStore()

    orchestrator = ApplicationOrchestrator(
        submitter=submitter,
        job_store=store,
    )

    orchestrator.set_job(
        make_job()
    )

    orchestrator.prepare_application(
        resume_path="resume.pdf",
        fields={
            "First Name": "Naveen",
        },
    )

    result = orchestrator.submit_application(
        confirm=True
    )

    assert result["success"] is True
    assert result["status"] == "submitted"

    assert submitter.submit_calls == [
        {
            "confirm": True,
        }
    ]

    assert (
        store.statuses["job-001"]
        == "applied"
    )


def test_notification_after_successful_submission():

    submitter = FakeSubmitter()
    notifier = FakeNotifier()

    orchestrator = ApplicationOrchestrator(
        submitter=submitter,
        notifier=notifier,
    )

    orchestrator.set_job(
        make_job()
    )

    orchestrator.prepare_application(
        resume_path="resume.pdf",
        fields={
            "First Name": "Naveen",
        },
    )

    orchestrator.submit_application(
        confirm=True
    )

    assert len(
        notifier.notifications
    ) == 1

    assert (
        notifier.notifications[0]["event"]
        == "application_submitted"
    )


def test_failed_preparation_does_not_submit():

    submitter = FakeSubmitter(
        prepare_success=False
    )

    orchestrator = ApplicationOrchestrator(
        submitter
    )

    result = orchestrator.run(
        job=make_job(),
        resume_path="resume.pdf",
        fields={
            "First Name": "Naveen",
        },
        confirm=True,
    )

    assert result["success"] is False

    assert (
        result["status"]
        == "validation_failed"
    )

    assert submitter.submit_calls == []


def test_run_without_confirmation_stops_safely():

    submitter = FakeSubmitter()

    orchestrator = ApplicationOrchestrator(
        submitter
    )

    result = orchestrator.run(
        job=make_job(),
        resume_path="resume.pdf",
        fields={
            "First Name": "Naveen",
            "Email": "test@example.com",
        },
    )

    assert result["success"] is True

    assert (
        result["status"]
        == "confirmation_required"
    )

    assert result["submitted"] is False

    assert submitter.submit_calls == []


def test_run_with_confirmation_submits():

    submitter = FakeSubmitter()
    store = FakeJobStore()

    orchestrator = ApplicationOrchestrator(
        submitter=submitter,
        job_store=store,
    )

    result = orchestrator.run(
        job=make_job(),
        resume_path="tailored_resume.pdf",
        fields={
            "First Name": "Naveen",
            "Email": "test@example.com",
        },
        confirm=True,
    )

    assert result["success"] is True

    assert result["submitted"] is True

    assert (
        result["status"]
        == "submitted"
    )

    assert (
        store.statuses["job-001"]
        == "applied"
    )


def test_get_state_before_preparation():

    submitter = FakeSubmitter()

    orchestrator = ApplicationOrchestrator(
        submitter
    )

    state = orchestrator.get_state()

    assert state["prepared"] is False
    assert state["submitted"] is False

    assert (
        state["status"]
        == "not_prepared"
    )


def test_get_state_after_preparation():

    submitter = FakeSubmitter()

    orchestrator = ApplicationOrchestrator(
        submitter
    )

    orchestrator.set_job(
        make_job()
    )

    orchestrator.prepare_application(
        resume_path="resume.pdf",
        fields={
            "First Name": "Naveen",
        },
    )

    state = orchestrator.get_state()

    assert state["prepared"] is True
    assert state["submitted"] is False

    assert (
        state["requires_confirmation"]
        is True
    )

    assert (
        state["status"]
        == "ready_for_submission"
    )


def test_notification_failure_does_not_break_submission():

    class BrokenNotifier:

        def notify(
            self,
            event,
            data,
        ):
            raise RuntimeError(
                "Email service unavailable"
            )

    submitter = FakeSubmitter()

    orchestrator = ApplicationOrchestrator(
        submitter=submitter,
        notifier=BrokenNotifier(),
    )

    orchestrator.set_job(
        make_job()
    )

    orchestrator.prepare_application(
        resume_path="resume.pdf",
        fields={
            "First Name": "Naveen",
        },
    )

    result = orchestrator.submit_application(
        confirm=True
    )

    assert result["success"] is True
    assert result["status"] == "submitted"