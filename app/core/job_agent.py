from typing import Dict, List, Optional

from app.core.job_match_pipeline import match_job
from app.core.application_workflow import ApplicationWorkflow
from app.jobs.job_store import JobStore


class JobAgent:
    """
    Main coordinator for JobAgent.

    Connects the major stages of the system:

        Jobs
          ↓
        Matching
          ↓
        Selection
          ↓
        Application preparation
          ↓
        Optional submission
          ↓
        Tracking

    This class coordinates existing components.
    It does not contain website-specific browser logic.
    """

    def __init__(
        self,
        job_store: Optional[JobStore] = None,
        application_workflow: Optional[
            ApplicationWorkflow
        ] = None,
    ):
        self.job_store = (
            job_store
            or JobStore()
        )

        self.application_workflow = (
            application_workflow
            or ApplicationWorkflow()
        )

    # ========================================================
    # JOB STORAGE
    # ========================================================

    def add_job(
        self,
        job: Dict,
        status: str = "discovered",
    ) -> str:
        """
        Store a discovered job.
        """

        return self.job_store.add_job(
            job,
            status=status,
        )

    def get_job(
        self,
        job_id: str,
    ) -> Optional[Dict]:
        """
        Retrieve one stored job.
        """

        return self.job_store.get_job(
            job_id
        )

    def get_jobs(self) -> List[Dict]:
        """
        Return all stored jobs.
        """

        return self.job_store.get_all_jobs()

    # ========================================================
    # MATCHING
    # ========================================================

    @staticmethod
    def match(
        resume: Dict,
        job: Dict,
    ) -> Dict:
        """
        Match a resume against a job.
        """

        return match_job(
            resume,
            job,
        )

    def match_and_store(
        self,
        resume: Dict,
        job_id: str,
    ) -> Dict:
        """
        Match a stored job against a resume.

        The stored job is marked as 'matched'.
        """

        job = self.get_job(job_id)

        if job is None:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        result = self.match(
            resume,
            job,
        )

        self.job_store.update_status(
            job_id,
            "matched",
        )

        return result

    # ========================================================
    # JOB SELECTION
    # ========================================================

    def select_job(
        self,
        job_id: str,
    ) -> bool:
        """
        Mark a matched job as selected.
        """

        job = self.get_job(job_id)

        if job is None:
            return False

        return self.job_store.update_status(
            job_id,
            "selected",
        )

    # ========================================================
    # APPLICATION PREPARATION
    # ========================================================

    def prepare_application(
        self,
        page,
        resume: Dict,
        job_id: str,
        fields: Dict[str, str],
        resume_output_path: str,
    ) -> Dict:
        """
        Prepare an application for a stored job.

        Steps:

        1. Retrieve job.
        2. Mark application as started.
        3. Tailor resume.
        4. Generate tailored PDF.
        5. Open application page.
        6. Fill application fields.
        7. Upload tailored resume.
        8. Validate application.

        Nothing is submitted automatically here.
        """

        job = self.get_job(
            job_id
        )

        if job is None:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        self.job_store.update_status(
            job_id,
            "application_started",
        )

        try:
            result = (
                self.application_workflow
                .prepare_application(
                    page=page,
                    resume=resume,
                    job=job,
                    fields=fields,
                    resume_output_path=(
                        resume_output_path
                    ),
                )
            )

            return result

        except Exception:
            self.job_store.update_status(
                job_id,
                "application_failed",
            )
            raise

    # ========================================================
    # APPLICATION SUBMISSION
    # ========================================================

    def submit_application(
        self,
        job_id: str,
        prepared_application: Dict,
        confirm: bool = False,
    ) -> Dict:
        """
        Submit a prepared application.

        Explicit confirmation is required.

        Successful submission changes the stored
        job status to 'applied'.
        """

        job = self.get_job(
            job_id
        )

        if job is None:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        result = (
            self.application_workflow.submit(
                prepared_application,
                confirm=confirm,
            )
        )

        if result.get("success"):
            self.job_store.update_status(
                job_id,
                "applied",
            )

        elif result.get("status") == (
            "validation_failed"
        ):
            self.job_store.update_status(
                job_id,
                "application_failed",
            )

        return result

    # ========================================================
    # APPLICATION STATUS
    # ========================================================

    def update_application_status(
        self,
        job_id: str,
        status: str,
    ) -> bool:
        """
        Update the tracked application status.

        Supported examples:

            applied
            shortlisted
            rejected
            interview
            assessment
            walk_in
        """

        return self.job_store.update_status(
            job_id,
            status,
        )

    def get_application_status(
        self,
        job_id: str,
    ) -> Optional[str]:
        """
        Return the current application status.
        """

        return self.job_store.get_status(
            job_id
        )

    # ========================================================
    # PIPELINE SUMMARY
    # ========================================================

    def process_job(
        self,
        resume: Dict,
        job_id: str,
    ) -> Dict:
        """
        Run the matching stage for one stored job.

        This method does not apply automatically.

        Returns:

            {
                "job": ...,
                "match": ...,
                "status": ...
            }
        """

        job = self.get_job(
            job_id
        )

        if job is None:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        match_result = self.match_and_store(
            resume,
            job_id,
        )

        return {
            "job": job,
            "match": match_result,
            "status": self.get_application_status(
                job_id
            ),
        }