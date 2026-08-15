from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from app.jobs.application_status_monitor import (
    ApplicationStatusMonitor,
)
from app.notifications.notification import (
    Notification,
    NotificationResult,
)


@dataclass(frozen=True)
class StatusNotificationEvent:
    """
    Represents one application-status notification event.
    """

    job_id: str
    title: str
    company: str
    old_status: Optional[str]
    new_status: str
    message: str


class StatusNotificationService:
    """
    Connects application-status monitoring with notification channels.

    Flow:

        Application Status Monitor
                  ↓
        Status Change Detection
                  ↓
        Notification Event
                  ↓
        Email / Other Notification Channel

    Responsibilities:
        - Scan tracked applications.
        - Detect status changes.
        - Determine whether notification is required.
        - Build user-friendly notification messages.
        - Send notifications through configured channels.
        - Return structured results.

    This service does NOT:
        - Submit applications.
        - Read email inboxes directly.
        - Discover jobs.
        - Modify resumes.
    """

    def __init__(
        self,
        monitor: ApplicationStatusMonitor,
        notifications: Optional[
            Iterable[Notification]
        ] = None,
    ):
        if monitor is None:
            raise ValueError(
                "monitor cannot be None."
            )

        self.monitor = monitor

        self.notifications = list(
            notifications
            if notifications is not None
            else []
        )

    # ========================================================
    # NOTIFICATION CHANNEL MANAGEMENT
    # ========================================================

    def add_notification(
        self,
        notification: Notification,
    ) -> None:
        """
        Add a notification channel.
        """

        if notification is None:
            raise ValueError(
                "notification cannot be None."
            )

        if not isinstance(
            notification,
            Notification,
        ):
            raise TypeError(
                "notification must inherit from Notification."
            )

        self.notifications.append(
            notification
        )

    def get_notifications(
        self,
    ) -> list[Notification]:
        """
        Return configured notification channels.
        """

        return list(
            self.notifications
        )

    # ========================================================
    # STATUS MESSAGE
    # ========================================================

    @staticmethod
    def build_message(
        job: dict,
        old_status: Optional[str],
        new_status: str,
    ) -> str:
        """
        Build a notification message for a status change.
        """

        title = str(
            job.get(
                "title",
                "Unknown position",
            )
        ).strip()

        company = str(
            job.get(
                "company",
                "Unknown company",
            )
        ).strip()

        location = str(
            job.get(
                "location",
                "",
            )
        ).strip()

        job_reference = title

        if company:
            if title:
                job_reference = (
                    f"{title} at {company}"
                )
            else:
                job_reference = company

        lines = [
            "JobAgent Application Status Update",
            "",
            f"Position: {job_reference}",
        ]

        if location:
            lines.append(
                f"Location: {location}"
            )

        if old_status:
            lines.append(
                f"Previous status: {old_status}"
            )

        lines.append(
            f"New status: {new_status}"
        )

        lines.extend(
            [
                "",
                "Your application status has changed.",
            ]
        )

        return "\n".join(lines)

    # ========================================================
    # SUBJECT
    # ========================================================

    @staticmethod
    def build_subject(
        job: dict,
        new_status: str,
    ) -> str:
        """
        Build the notification email subject.
        """

        title = str(
            job.get(
                "title",
                "",
            )
        ).strip()

        company = str(
            job.get(
                "company",
                "",
            )
        ).strip()

        if title and company:
            return (
                f"JobAgent: {new_status.title()} - "
                f"{title} at {company}"
            )

        if title:
            return (
                f"JobAgent: {new_status.title()} - "
                f"{title}"
            )

        if company:
            return (
                f"JobAgent: {new_status.title()} - "
                f"{company}"
            )

        return (
            f"JobAgent: Application {new_status.title()}"
        )

    # ========================================================
    # EVENT CREATION
    # ========================================================

    def create_event(
        self,
        result: dict,
    ) -> Optional[StatusNotificationEvent]:
        """
        Convert a monitor result into a notification event.

        Returns None when the result does not represent
        a notification-worthy status change.
        """

        if not isinstance(
            result,
            dict,
        ):
            raise TypeError(
                "result must be a dictionary."
            )

        if not result.get(
            "success",
            False,
        ):
            return None

        if not result.get(
            "changed",
            False,
        ):
            return None

        if not result.get(
            "notification_required",
            False,
        ):
            return None

        job_id = result.get(
            "job_id"
        )

        if not job_id:
            return None

        job = self.monitor.get_job(
            job_id
        )

        if job is None:
            return None

        old_status = result.get(
            "old_status"
        )

        new_status = result.get(
            "new_status"
        )

        if not new_status:
            return None

        message = self.build_message(
            job=job,
            old_status=old_status,
            new_status=new_status,
        )

        title = self.build_subject(
            job=job,
            new_status=new_status,
        )

        return StatusNotificationEvent(
            job_id=str(job_id),
            title=title,
            company=str(
                job.get(
                    "company",
                    "",
                )
            ).strip(),
            old_status=old_status,
            new_status=str(new_status),
            message=message,
        )

    # ========================================================
    # SEND ONE EVENT
    # ========================================================

    def send_event(
        self,
        event: StatusNotificationEvent,
    ) -> list[NotificationResult]:
        """
        Send one status notification through every
        configured notification channel.
        """

        if not isinstance(
            event,
            StatusNotificationEvent,
        ):
            raise TypeError(
                "event must be a StatusNotificationEvent."
            )

        results = []

        for notification in self.notifications:

            if not notification.is_enabled():
                continue

            try:
                result = notification.send_result(
                    title=event.title,
                    message=event.message,
                )

            except AttributeError:
                # Backward-compatible fallback for custom
                # Notification implementations that only
                # implement send().
                try:
                    success = notification.send(
                        title=event.title,
                        message=event.message,
                    )

                    result = NotificationResult(
                        success=success,
                        channel=notification.channel_name,
                        title=event.title,
                        message=event.message,
                    )

                except Exception as exc:
                    result = NotificationResult(
                        success=False,
                        channel=notification.channel_name,
                        title=event.title,
                        message=event.message,
                        error=str(exc),
                    )

            except Exception as exc:
                result = NotificationResult(
                    success=False,
                    channel=notification.channel_name,
                    title=event.title,
                    message=event.message,
                    error=str(exc),
                )

            results.append(
                result
            )

        return results

    # ========================================================
    # PROCESS MONITOR RESULT
    # ========================================================

    def process_result(
        self,
        result: dict,
    ) -> dict:
        """
        Process one status-monitor result.

        Returns a structured dictionary containing:
            - whether a notification was required
            - generated event
            - notification delivery results
        """

        event = self.create_event(
            result
        )

        if event is None:
            return {
                "success": bool(
                    result.get(
                        "success",
                        False,
                    )
                ),
                "notification_required": False,
                "event": None,
                "notifications": [],
            }

        notification_results = (
            self.send_event(
                event
            )
        )

        return {
            "success": True,
            "notification_required": True,
            "event": event,
            "notifications": [
                notification.to_dict()
                for notification
                in notification_results
            ],
        }

    # ========================================================
    # DETECT ONE APPLICATION
    # ========================================================

    def detect_and_notify(
        self,
        job_id: str,
        detected_status: str,
    ) -> dict:
        """
        Detect a status for one application and notify
        the user when the status changed.
        """

        result = self.monitor.detect_status(
            job_id=job_id,
            detected_status=detected_status,
        )

        return self.process_result(
            result
        )

    # ========================================================
    # SCAN ALL APPLICATIONS
    # ========================================================

    def scan_and_notify(
        self,
        status_provider,
    ) -> list[dict]:
        """
        Scan every tracked application and send notifications
        for newly detected notification-worthy statuses.

        The status provider receives a job dictionary and
        returns either:

            None
                No new status.

            status string
                Newly detected application status.
        """

        monitor_results = self.monitor.scan(
            status_provider=status_provider
        )

        processed = []

        for result in monitor_results:
            processed.append(
                self.process_result(
                    result
                )
            )

        return processed

    # ========================================================
    # NOTIFICATION STATUS
    # ========================================================

    def requires_notification(
        self,
        status: str,
    ) -> bool:
        """
        Determine whether a status requires notification.
        """

        return self.monitor.requires_notification(
            status
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    def summary(self) -> dict:
        """
        Return notification-service configuration summary.
        """

        enabled_channels = [
            notification.channel_name
            for notification
            in self.notifications
            if notification.is_enabled()
        ]

        return {
            "notification_channels": len(
                self.notifications
            ),
            "enabled_channels": enabled_channels,
            "notification_statuses": sorted(
                self.monitor.NOTIFICATION_STATUSES
            ),
        }