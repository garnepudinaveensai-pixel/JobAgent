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

    Current workflow:

        Job
          ↓
        Match against resume
          ↓
        Register job
          ↓
        Prepare application
          ↓
        Validate application
          ↓
        Explicit confirmation
          ↓
        Submit
          ↓
        Track application status

    This class does NOT automatically submit an application
    without explicit confirmation.
    """

    def __init__(
        self,
        job_store: Optional[JobStore] = None,
        application_tracker: Optional[ApplicationTracker] = None,
    ):
        self.job_store = job_store or JobStore()

        self.application_tracker = (
            application_tracker
            or ApplicationTracker()
        )

    # ========================================================
    # MATCHING
    # ========================================================

    def evaluate_job(
        self,
        resume: Dict,
        job: Dict,
    ) -> Dict:
        """
        Evaluate how well a resume matches a job.
        """

        return match_job(
            resume=resume,
            job=job,
        )

    # ========================================================
    # REGISTER JOB
    # ========================================================

    def register_job(
        self,
        job: Job | Dict,
        status: str = "discovered",
    ) -> str:
        """
        Store a job and return its stable job ID.
        """

        return self.job_store.add_job(
            job=job,
            status=status,
        )

    # ========================================================
    # PREPARE APPLICATION
    # ========================================================

    def prepare_application(
        self,
        page,
        job: Job | Dict,
        resume_path: str,
        fields: Dict[str, str],
    ) -> Dict:
        """
        Prepare an application.

        This:

        1. Checks the resume exists.
        2. Discovers the application form.
        3. Fills application fields.
        4. Uploads the resume.
        5. Validates the form.

        It does NOT click the final submit button.
        """

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
    # SUBMIT APPLICATION
    # ========================================================

    def submit_application(
        self,
        page,
        job_id: str,
        confirm: bool = False,
    ) -> Dict:
        """
        Submit a prepared application.

        Final submission requires explicit confirmation.
        """

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

        else:

            self.job_store.update_status(
                job_id,
                "application_failed",
            )

            self.application_tracker.record_application(
                job_id=job_id,
                status="application_failed",
            )

        return result

    # ========================================================
    # UPDATE APPLICATION STATUS
    # ========================================================

    def update_application_status(
        self,
        job_id: str,
        status: str,
        details: Optional[Dict] = None,
    ) -> bool:
        """
        Update the current status of an application.

        Examples:

            shortlisted
            rejected
            interview
            assessment
            walk_in
        """

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

    # ========================================================
    # GET APPLICATION STATUS
    # ========================================================

    def get_application_status(
        self,
        job_id: str,
    ) -> Optional[str]:
        """
        Return the current application status.
        """

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
        """
        Evaluate a job before starting an application.

        This does NOT submit anything.
        """

        match_result = self.evaluate_job(
            resume=resume,
            job=job,
        )

        return {
            "eligible": match_result["eligible"],
            "match_score": match_result["match_score"],
            "recommendation": match_result[
                "recommendation"
            ],
            "matched_required_skills": match_result[
                "matched_required_skills"
            ],
            "missing_required_skills": match_result[
                "missing_required_skills"
            ],
            "matched_preferred_skills": match_result[
                "matched_preferred_skills"
            ],
            "missing_preferred_skills": match_result[
                "missing_preferred_skills"
            ],
        }