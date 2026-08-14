from datetime import datetime, timezone
from typing import Optional

from app.jobs.job import Job
from app.jobs.job_store import JobStore


class ApplicationTracker:
    """
    Tracks the complete application lifecycle for JobAgent.

    Uses JobStore as the single source of persistent storage.

    Typical lifecycle:

        discovered
        -> matched
        -> selected
        -> application_started
        -> applied
        -> assessment
        -> interview
        -> shortlisted
        -> rejected
        -> walk_in
    """

    VALID_STATUSES = JobStore.VALID_STATUSES

    def __init__(self, store: Optional[JobStore] = None):
        self.store = store or JobStore()

    # ========================================================
    # JOB REGISTRATION
    # ========================================================

    def register_job(
        self,
        job: Job | dict,
        status: str = "discovered",
    ) -> str:
        """
        Register a discovered job in persistent storage.

        Returns:
            Stable job ID.
        """

        return self.store.add_job(
            job,
            status=status,
        )

    # ========================================================
    # APPLICATION LIFECYCLE
    # ========================================================

    def mark_matched(
        self,
        job_id: str,
    ) -> bool:
        return self._set_status(
            job_id,
            "matched",
        )

    def mark_selected(
        self,
        job_id: str,
    ) -> bool:
        return self._set_status(
            job_id,
            "selected",
        )

    def mark_application_started(
        self,
        job_id: str,
    ) -> bool:
        return self._set_status(
            job_id,
            "application_started",
        )

    def mark_applied(
        self,
        job_id: str,
    ) -> bool:
        return self._set_status(
            job_id,
            "applied",
        )

    def mark_application_failed(
        self,
        job_id: str,
    ) -> bool:
        return self._set_status(
            job_id,
            "application_failed",
        )

    # ========================================================
    # POST-APPLICATION STATUS
    # ========================================================

    def mark_shortlisted(
        self,
        job_id: str,
    ) -> bool:
        return self._set_status(
            job_id,
            "shortlisted",
        )

    def mark_rejected(
        self,
        job_id: str,
    ) -> bool:
        return self._set_status(
            job_id,
            "rejected",
        )

    def mark_interview(
        self,
        job_id: str,
    ) -> bool:
        return self._set_status(
            job_id,
            "interview",
        )

    def mark_assessment(
        self,
        job_id: str,
    ) -> bool:
        return self._set_status(
            job_id,
            "assessment",
        )

    def mark_walk_in(
        self,
        job_id: str,
    ) -> bool:
        return self._set_status(
            job_id,
            "walk_in",
        )

    def mark_status_changed(
        self,
        job_id: str,
    ) -> bool:
        return self._set_status(
            job_id,
            "status_changed",
        )

    # ========================================================
    # GENERIC STATUS UPDATE
    # ========================================================

    def update_status(
        self,
        job_id: str,
        status: str,
    ) -> bool:
        """
        Update a job to any supported status.
        """

        return self._set_status(
            job_id,
            status,
        )

    def _set_status(
        self,
        job_id: str,
        status: str,
    ) -> bool:
        """
        Internal status update helper.

        Stores timestamp information so later notification
        and monitoring systems can determine when a status
        changed.
        """

        if status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid application status: {status}"
            )

        job = self.store.get_job(job_id)

        if job is None:
            return False

        old_status = job.get("status")

        changed = self.store.update_status(
            job_id,
            status,
        )

        if not changed:
            return False

        # Re-fetch because JobStore persists the record.
        updated_job = self.store.get_job(job_id)

        if updated_job is not None:
            updated_job["status_updated_at"] = (
                datetime.now(timezone.utc).isoformat()
            )

            if old_status != status:
                updated_job["previous_status"] = old_status

            # Persist metadata through the store.
            self.store._save()

        return True

    # ========================================================
    # STATUS QUERIES
    # ========================================================

    def get_status(
        self,
        job_id: str,
    ) -> Optional[str]:
        """
        Return the current application status.
        """

        return self.store.get_status(
            job_id
        )

    def get_application(
        self,
        job_id: str,
    ) -> Optional[dict]:
        """
        Return the complete stored application record.
        """

        return self.store.get_job(
            job_id
        )

    # ========================================================
    # APPLICATION LISTS
    # ========================================================

    def get_applied_jobs(self) -> list[dict]:
        """
        Return jobs that have successfully been applied to.
        """

        return self.store.get_jobs_by_status(
            "applied"
        )

    def get_pending_applications(self) -> list[dict]:
        """
        Return applications that are still in progress.
        """

        pending_statuses = {
            "application_started",
            "applied",
            "assessment",
            "interview",
            "status_changed",
        }

        return [
            job
            for job in self.store.get_all_jobs()
            if job.get("status") in pending_statuses
        ]

    def get_shortlisted_jobs(self) -> list[dict]:
        return self.store.get_jobs_by_status(
            "shortlisted"
        )

    def get_rejected_jobs(self) -> list[dict]:
        return self.store.get_jobs_by_status(
            "rejected"
        )

    def get_interview_jobs(self) -> list[dict]:
        return self.store.get_jobs_by_status(
            "interview"
        )

    def get_assessment_jobs(self) -> list[dict]:
        return self.store.get_jobs_by_status(
            "assessment"
        )

    def get_walk_in_jobs(self) -> list[dict]:
        return self.store.get_jobs_by_status(
            "walk_in"
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    def summary(self) -> dict:
        """
        Return a compact application-status summary.
        """

        return {
            "total": self.store.count(),
            "discovered": len(
                self.store.get_jobs_by_status(
                    "discovered"
                )
            ),
            "matched": len(
                self.store.get_jobs_by_status(
                    "matched"
                )
            ),
            "selected": len(
                self.store.get_jobs_by_status(
                    "selected"
                )
            ),
            "application_started": len(
                self.store.get_jobs_by_status(
                    "application_started"
                )
            ),
            "applied": len(
                self.store.get_jobs_by_status(
                    "applied"
                )
            ),
            "application_failed": len(
                self.store.get_jobs_by_status(
                    "application_failed"
                )
            ),
            "shortlisted": len(
                self.store.get_jobs_by_status(
                    "shortlisted"
                )
            ),
            "rejected": len(
                self.store.get_jobs_by_status(
                    "rejected"
                )
            ),
            "interview": len(
                self.store.get_jobs_by_status(
                    "interview"
                )
            ),
            "assessment": len(
                self.store.get_jobs_by_status(
                    "assessment"
                )
            ),
            "walk_in": len(
                self.store.get_jobs_by_status(
                    "walk_in"
                )
            ),
        }