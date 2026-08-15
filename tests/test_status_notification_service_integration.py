from __future__ import annotations

from unittest.mock import Mock

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
    number="1",
):
    return {
        "title": title,
        "company": company,
        "location": "Hyderabad",
        "description": (
            "Electrical engineering position."
        ),
        "url": (
            f"https://example.com/jobs/{number}"
        ),
    }


# ============================================================
# NOTIFICATION SERVICE
# ============================================================

class StatusNotificationService:
    """
    Connects ApplicationStatusMonitor with an email
    notification channel.

    Flow:

        Status Monitor
              ↓
        Status Change Event
              ↓
        Notification Required?
              ↓
        Build Notification
              ↓
        Send Notification
    """

    def __init__(
        self,
        monitor,
        notification,
    ):
        self.monitor = monitor
        self.notification = notification

    # --------------------------------------------------------
    # MESSAGE
    # --------------------------------------------------------

    @staticmethod
    def build_message(
        job,
        old_status,
        new_status,
    ):
        company = str(
            job.get("company", "")
        ).strip()

        title = str(
            job.get("title", "")
        ).strip()

        subject = (
            f"Application Status Update: "
            f"{title}"
        )

        message = (
            "Your job application status has "
            "changed.\n\n"
            f"Position: {title}\n"
            f"Company: {company}\n"
            f"Previous status: {old_status}\n"
            f"New status: {new_status}\n\n"
            "Please check the application portal "
            "or your email for further details."
        )

        return subject, message

    # --------------------------------------------------------
    # PROCESS EVENT
    # --------------------------------------------------------

    def process_status_event(
        self,
        event,
    ):
        if not event.get("success"):
            return {
                "success": False,
                "notification_sent": False,
                "event": event,
                "error": event.get(
                    "error"
                ),
            }

        if not event.get("changed"):
            return {
                "success": True,
                "notification_sent": False,
                "event": event,
                "reason": "status_unchanged",
            }

        if not event.get(
            "notification_required"
        ):
            return {
                "success": True,
                "notification_sent": False,
                "event": event,
                "reason": (
                    "notification_not_required"
                ),
            }

        job = self.monitor.get_job(
            event["job_id"]
        )

        if job is None:
            return {
                "success": False,
                "notification_sent": False,
                "event": event,
                "error": "Job not found.",
            }

        subject, message = (
            self.build_message(
                job=job,
                old_status=event[
                    "old_status"
                ],
                new_status=event[
                    "new_status"
                ],
            )
        )

        result = self.notification.send_result(
            title=subject,
            message=message,
        )

        return {
            "success": result.success,
            "notification_sent": (
                result.success
            ),
            "event": event,
            "notification": result,
        }

    # --------------------------------------------------------
    # DETECT + NOTIFY
    # --------------------------------------------------------

    def detect_and_notify(
        self,
        job_id,
        detected_status,
    ):
        event = self.monitor.detect_status(
            job_id=job_id,
            detected_status=detected_status,
        )

        return self.process_status_event(
            event
        )

    # --------------------------------------------------------
    # SCAN + NOTIFY
    # --------------------------------------------------------

    def scan_and_notify(
        self,
        status_provider,
    ):
        events = self.monitor.scan(
            status_provider=status_provider
        )

        results = []

        for event in events:
            results.append(
                self.process_status_event(
                    event
                )
            )

        return results


# ============================================================
# MESSAGE BUILDING
# ============================================================

def test_build_notification_message(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store
    )

    notification = Mock()

    service = StatusNotificationService(
        monitor=monitor,
        notification=notification,
    )

    job = monitor.get_job(job_id)

    subject, message = (
        service.build_message(
            job=job,
            old_status="applied",
            new_status="shortlisted",
        )
    )

    assert subject == (
        "Application Status Update: "
        "Electrical Engineer"
    )

    assert (
        "Electrical Engineer"
        in message
    )

    assert (
        "Example Energy"
        in message
    )

    assert (
        "Previous status: applied"
        in message
    )

    assert (
        "New status: shortlisted"
        in message
    )


# ============================================================
# SHORTLISTED
# ============================================================

def test_detect_and_notify_shortlisted(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store
    )

    notification = Mock()

    notification_result = Mock()
    notification_result.success = True
    notification_result.channel = "Email"
    notification_result.title = (
        "Application Status Update: "
        "Electrical Engineer"
    )
    notification_result.message = (
        "Your application was shortlisted."
    )

    notification.send_result.return_value = (
        notification_result
    )

    service = StatusNotificationService(
        monitor=monitor,
        notification=notification,
    )

    result = service.detect_and_notify(
        job_id=job_id,
        detected_status="shortlisted",
    )

    assert result["success"] is True
    assert (
        result["notification_sent"]
        is True
    )

    notification.send_result.assert_called_once()

    assert monitor.get_status(
        job_id
    ) == "shortlisted"


# ============================================================
# REJECTED
# ============================================================

def test_detect_and_notify_rejected(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store
    )

    notification = Mock()

    notification_result = Mock()
    notification_result.success = True
    notification_result.channel = "Email"
    notification_result.title = (
        "Application Status Update"
    )
    notification_result.message = (
        "Application rejected."
    )

    notification.send_result.return_value = (
        notification_result
    )

    service = StatusNotificationService(
        monitor=monitor,
        notification=notification,
    )

    result = service.detect_and_notify(
        job_id=job_id,
        detected_status="rejected",
    )

    assert result["success"] is True
    assert (
        result["notification_sent"]
        is True
    )

    notification.send_result.assert_called_once()

    assert monitor.get_status(
        job_id
    ) == "rejected"


# ============================================================
# INTERVIEW
# ============================================================

def test_detect_and_notify_interview(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store
    )

    notification = Mock()

    notification_result = Mock()
    notification_result.success = True

    notification.send_result.return_value = (
        notification_result
    )

    service = StatusNotificationService(
        monitor=monitor,
        notification=notification,
    )

    result = service.detect_and_notify(
        job_id=job_id,
        detected_status="interview",
    )

    assert result["success"] is True
    assert (
        result["notification_sent"]
        is True
    )

    notification.send_result.assert_called_once()


# ============================================================
# NO NOTIFICATION FOR APPLIED
# ============================================================

def test_applied_status_does_not_send_notification(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="selected",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store
    )

    notification = Mock()

    service = StatusNotificationService(
        monitor=monitor,
        notification=notification,
    )

    result = service.detect_and_notify(
        job_id=job_id,
        detected_status="applied",
    )

    assert result["success"] is True
    assert (
        result["notification_sent"]
        is False
    )

    notification.send_result.assert_not_called()


# ============================================================
# NO NOTIFICATION WHEN STATUS UNCHANGED
# ============================================================

def test_unchanged_status_does_not_send_notification(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="shortlisted",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store
    )

    notification = Mock()

    service = StatusNotificationService(
        monitor=monitor,
        notification=notification,
    )

    result = service.detect_and_notify(
        job_id=job_id,
        detected_status="shortlisted",
    )

    assert result["success"] is True
    assert (
        result["notification_sent"]
        is False
    )

    assert result["reason"] == (
        "status_unchanged"
    )

    notification.send_result.assert_not_called()


# ============================================================
# NOTIFICATION FAILURE
# ============================================================

def test_notification_failure_is_reported(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store
    )

    notification = Mock()

    notification_result = Mock()
    notification_result.success = False
    notification_result.channel = "Email"
    notification_result.error = (
        "SMTP connection failed"
    )

    notification.send_result.return_value = (
        notification_result
    )

    service = StatusNotificationService(
        monitor=monitor,
        notification=notification,
    )

    result = service.detect_and_notify(
        job_id=job_id,
        detected_status="shortlisted",
    )

    assert result["success"] is False
    assert (
        result["notification_sent"]
        is False
    )

    assert monitor.get_status(
        job_id
    ) == "shortlisted"

    notification.send_result.assert_called_once()


# ============================================================
# MULTIPLE APPLICATIONS
# ============================================================

def test_scan_and_notify_multiple_applications(
    tmp_path,
):
    store = make_store(tmp_path)

    first_id = store.add_job(
        sample_job(
            "Electrical Engineer",
            "Company A",
            "1",
        ),
        status="applied",
    )

    second_id = store.add_job(
        sample_job(
            "Automation Engineer",
            "Company B",
            "2",
        ),
        status="applied",
    )

    third_id = store.add_job(
        sample_job(
            "Graduate Engineer Trainee",
            "Company C",
            "3",
        ),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store
    )

    notification = Mock()

    notification_result = Mock()
    notification_result.success = True

    notification.send_result.return_value = (
        notification_result
    )

    service = StatusNotificationService(
        monitor=monitor,
        notification=notification,
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

    results = service.scan_and_notify(
        status_provider=provider
    )

    assert len(results) == 2

    assert all(
        result["success"]
        for result in results
    )

    assert all(
        result["notification_sent"]
        for result in results
    )

    assert (
        notification.send_result.call_count
        == 2
    )

    assert monitor.get_status(
        first_id
    ) == "shortlisted"

    assert monitor.get_status(
        second_id
    ) == "rejected"

    assert monitor.get_status(
        third_id
    ) == "applied"


# ============================================================
# EMAIL NOTIFICATION ADAPTER
# ============================================================

def test_real_email_notification_can_be_injected(
    tmp_path,
):
    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store
    )

    email = EmailNotification(
        sender="sender@example.com",
        password="test-password",
        recipient="user@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        enabled=False,
    )

    service = StatusNotificationService(
        monitor=monitor,
        notification=email,
    )

    result = service.detect_and_notify(
        job_id=job_id,
        detected_status="shortlisted",
    )

    # Disabled notifications are safely ignored.
    assert result["success"] is False
    assert (
        result["notification_sent"]
        is False
    )

    assert monitor.get_status(
        job_id
    ) == "shortlisted"


# ============================================================
# COMPLETE FLOW
# ============================================================

def test_complete_status_notification_flow(
    tmp_path,
):
    """
    Complete integration checkpoint:

        Submitted Application
                ↓
        Application Status Monitor
                ↓
        Detect Shortlisted
                ↓
        Update JobStore
                ↓
        Build Notification
                ↓
        Email Notification
    """

    store = make_store(tmp_path)

    job_id = store.add_job(
        sample_job(),
        status="applied",
    )

    monitor = ApplicationStatusMonitor(
        job_store=store
    )

    notification = Mock()

    notification_result = Mock()
    notification_result.success = True
    notification_result.channel = "Email"
    notification_result.title = (
        "Application Status Update"
    )
    notification_result.message = (
        "Application shortlisted."
    )

    notification.send_result.return_value = (
        notification_result
    )

    service = StatusNotificationService(
        monitor=monitor,
        notification=notification,
    )

    result = service.detect_and_notify(
        job_id=job_id,
        detected_status="shortlisted",
    )

    # Status was updated.
    assert monitor.get_status(
        job_id
    ) == "shortlisted"

    # Notification was sent.
    assert result["notification_sent"] is True

    # Email channel was invoked.
    notification.send_result.assert_called_once()

    call = (
        notification.send_result.call_args
    )

    assert "Application Status Update" in (
        call.kwargs["title"]
    )

    assert "Electrical Engineer" in (
        call.kwargs["message"]
    )

    assert "Example Energy" in (
        call.kwargs["message"]
    )

    assert "shortlisted" in (
        call.kwargs["message"]
    )