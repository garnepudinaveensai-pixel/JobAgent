from typing import Callable, Optional

from app.jobs.job_store import JobStore


class ApplicationStatusMonitor:
    """
    Monitors application statuses stored in JobStore.

    Responsibilities:
    - Read tracked applications.
    - Compare known and newly detected statuses.
    - Update JobStore when a status changes.
    - Return structured status-change events.

    This class does NOT:
    - Send emails.
    - Read an email inbox.
    - Submit applications.

    Those responsibilities belong to separate components.
    """

    TRACKED_STATUSES = {
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

    NOTIFICATION_STATUSES = {
        "shortlisted",
        "rejected",
        "interview",
        "assessment",
        "walk_in",
        "status_changed",
    }

    def __init__(
        self,
        job_store: JobStore,
    ):
        self.job_store = job_store

    # ========================================================
    # STATUS VALIDATION
    # ========================================================

    @classmethod
    def validate_status(
        cls,
        status: str,
    ) -> None:
        """
        Validate an application status.
        """

        if not isinstance(status, str):
            raise TypeError(
                "status must be a string."
            )

        if status not in cls.TRACKED_STATUSES:
            raise ValueError(
                f"Invalid application status: {status}"
            )

    # ========================================================
    # CURRENT STATUS
    # ========================================================

    def get_status(
        self,
        job_id: str,
    ) -> Optional[str]:
        """
        Return the current stored status of a job.
        """

        return self.job_store.get_status(
            job_id
        )

    # ========================================================
    # STATUS CHANGE
    # ========================================================

    def update_status(
        self,
        job_id: str,
        new_status: str,
    ) -> dict:
        """
        Update a job's status and return a structured result.

        If the status has not changed, no update is performed.
        """

        self.validate_status(new_status)

        job = self.job_store.get_job(
            job_id
        )

        if job is None:
            return {
                "success": False,
                "changed": False,
                "job_id": job_id,
                "old_status": None,
                "new_status": new_status,
                "notification_required": False,
                "error": "Job not found.",
            }

        old_status = job.get("status")

        # ----------------------------------------------------
        # No change
        # ----------------------------------------------------

        if old_status == new_status:
            return {
                "success": True,
                "changed": False,
                "job_id": job_id,
                "old_status": old_status,
                "new_status": new_status,
                "notification_required": False,
                "error": None,
            }

        # ----------------------------------------------------
        # Update store
        # ----------------------------------------------------

        updated = self.job_store.update_status(
            job_id,
            new_status,
        )

        if not updated:
            return {
                "success": False,
                "changed": False,
                "job_id": job_id,
                "old_status": old_status,
                "new_status": new_status,
                "notification_required": False,
                "error": "Failed to update job status.",
            }

        notification_required = (
            new_status
            in self.NOTIFICATION_STATUSES
        )

        return {
            "success": True,
            "changed": True,
            "job_id": job_id,
            "old_status": old_status,
            "new_status": new_status,
            "notification_required": notification_required,
            "error": None,
        }

    # ========================================================
    # DETECT STATUS
    # ========================================================

    def detect_status(
        self,
        job_id: str,
        detected_status: str,
    ) -> dict:
        """
        Process a newly detected application status.

        This is the method that future email/inbox readers
        will call after interpreting a company email.
        """

        return self.update_status(
            job_id=job_id,
            new_status=detected_status,
        )

    # ========================================================
    # NOTIFICATION CHECK
    # ========================================================

    def requires_notification(
        self,
        status: str,
    ) -> bool:
        """
        Determine whether a status should generate a notification.
        """

        self.validate_status(status)

        return (
            status
            in self.NOTIFICATION_STATUSES
        )

    # ========================================================
    # JOB INFORMATION
    # ========================================================

    def get_job(
        self,
        job_id: str,
    ) -> Optional[dict]:
        """
        Return the complete stored job.
        """

        return self.job_store.get_job(
            job_id
        )

    # ========================================================
    # APPLICATIONS
    # ========================================================

    def get_tracked_applications(
        self,
    ) -> list[dict]:
        """
        Return jobs that have progressed into the application
        lifecycle.
        """

        application_statuses = {
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

        return [
            job
            for job in self.job_store.get_all_jobs()
            if job.get("status")
            in application_statuses
        ]

    # ========================================================
    # SCAN
    # ========================================================

    def scan(
        self,
        status_provider: Callable[[dict], Optional[str]],
    ) -> list[dict]:
        """
        Scan tracked applications using a status provider.

        The provider receives one job dictionary and should
        return:

            None
                if no new status is available.

            "shortlisted"
            "rejected"
            "interview"
            "assessment"
            "walk_in"
            etc.
                if a new status was detected.

        This design lets us later plug in an email reader
        without changing this monitoring engine.
        """

        events = []

        for job in self.get_tracked_applications():

            job_id = job.get("job_id")

            if not job_id:
                continue

            detected_status = status_provider(
                job
            )

            if detected_status is None:
                continue

            result = self.detect_status(
                job_id=job_id,
                detected_status=detected_status,
            )

            if result["changed"]:
                events.append(result)

        return events