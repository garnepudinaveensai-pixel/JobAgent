from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from app.browser.application_submitter import ApplicationSubmitter
from app.core.matcher import match_job
from app.jobs.application_tracker import ApplicationTracker
from app.jobs.job import Job
from app.jobs.job_store import JobStore


class ApplicationPipeline:
    """
    Coordinates the JobAgent application workflow.

    Workflow:

        Job
          ↓
        Match
          ↓
        Register
          ↓
        Prepare
          ↓
        Validate
          ↓
        Confirmation
          ↓
        Submit
          ↓
        Track
    """

    def __init__(
        self,
        job_store: Optional[JobStore] = None,
        application_tracker: Optional[ApplicationTracker] = None,
    ):
        # ONE shared store for the entire application lifecycle.
        self.job_store = job_store or JobStore()

        # Critical fix:
        # If a tracker is not supplied, it MUST use the same
        # JobStore instance.
        self.application_tracker = (
            application_tracker
            or ApplicationTracker(
                store=self.job_store,
            )
        )

    # ========================================================
    # MATCHING
    # ========================================================

    def evaluate_job(
        self,
        resume: Dict,
        job: Dict,
    ) -> Dict:
        return match_job(
            resume=resume,
            job=job,
        )

    # ========================================================
    # REGISTER
    # ========================================================

    def register_job(
        self,
        job: Job | Dict,
        status: str = "discovered",
    ) -> str:
        return self.job_store.add_job(
            job=job,
            status=status,
        )

    # ========================================================
    # PREPARE
    # ========================================================

    def prepare_application(
        self,
        page,
        job: Job | Dict,
        resume_path: str,
        fields: Dict[str, str],
    ) -> Dict:
        resume_file = Path(resume_path)

        if not resume_file.exists():
            raise FileNotFoundError(
                f"Resume not found: {resume_path}"
            )

        submitter = ApplicationSubmitter(page)

        submitter.discover()

        result = submitter.prepare_application(
            resume_path=str(resume_file),
            fields=fields,
        )

        job_id = self.register_job(
            job=job,
            status="application_started",
        )

        result["job_id"] = job_id

        return result

    # ========================================================
    # SUBMIT
    # ========================================================

    def submit_application(
        self,
        page,
        job_id: str,
        confirm: bool = False,
    ) -> Dict:
        if not job_id:
            raise ValueError(
                "job_id cannot be empty."
            )

        if self.job_store.get_job(job_id) is None:
            return {
                "success": False,
                "status": "job_not_found",
                "job_id": job_id,
            }

        submitter = ApplicationSubmitter(page)

        result = submitter.submit(
            confirm=confirm,
        )

        if result.get("success"):
            self.job_store.update_status(
                job_id,
                "applied",
            )

            self.application_tracker.record_application(
                job_id=job_id,
                status="applied",
            )

        elif result.get("status") == "confirmation_required":
            self.job_store.update_status(
                job_id,
                "application_started",
            )

        elif result.get("status") == "not_ready":
            self.job_store.update_status(
                job_id,
                "application_started",
            )

        else:
            self.job_store.update_status(
                job_id,
                "application_failed",
            )

            self.application_tracker.record_application(
                job_id=job_id,
                status="application_failed",
            )

        return {
            **result,
            "job_id": job_id,
        }

    # ========================================================
    # STATUS
    # ========================================================

    def update_application_status(
        self,
        job_id: str,
        status: str,
        details: Optional[Dict] = None,
    ) -> bool:

        if self.job_store.get_job(job_id) is None:
            return False

        updated = self.job_store.update_status(
            job_id,
            status,
        )

        if not updated:
            return False

        self.application_tracker.record_application(
            job_id=job_id,
            status=status,
            details=details,
        )

        return True

    def get_application_status(
        self,
        job_id: str,
    ) -> Optional[str]:
        return self.job_store.get_status(
            job_id,
        )

    # ========================================================
    # PRE-CHECK
    # ========================================================

    def prepare_and_check(
        self,
        resume: Dict,
        job: Dict,
    ) -> Dict:
        match_result = self.evaluate_job(
            resume=resume,
            job=job,
        )

        return {
            "eligible": match_result.get(
                "eligible",
                False,
            ),
            "match_score": match_result.get(
                "match_score",
                0,
            ),
            "recommendation": match_result.get(
                "recommendation",
                "",
            ),
            "matched_required_skills": match_result.get(
                "matched_required_skills",
                [],
            ),
            "missing_required_skills": match_result.get(
                "missing_required_skills",
                [],
            ),
            "matched_preferred_skills": match_result.get(
                "matched_preferred_skills",
                [],
            ),
            "missing_preferred_skills": match_result.get(
                "missing_preferred_skills",
                [],
            ),
        }