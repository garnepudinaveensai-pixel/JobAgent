from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.core.application_workflow import (
    ApplicationWorkflow,
)
from app.core.job_match_pipeline import match_job
from app.jobs.job_store import JobStore
from app.outreach.outreach_pipeline import (
    OutreachPipeline,
    OutreachResult,
)


class JobAgent:
    """
    Main coordinator for JobAgent.

    Connects the major stages:

        Jobs
          ↓
        Matching
          ↓
        Selection
          ↓
        Application preparation
          ↓
        Application submission
          ↓
        Outreach
          ↓
        Tracking

    Website-specific browser logic remains outside this class.

    Outreach sending always requires explicit confirmation.
    """

    def __init__(
        self,
        job_store: Optional[JobStore] = None,
        application_workflow: Optional[
            ApplicationWorkflow
        ] = None,
        outreach_pipeline: Optional[
            OutreachPipeline
        ] = None,
    ):
        self.job_store = (
            job_store
            if job_store is not None
            else JobStore()
        )

        self.application_workflow = (
            application_workflow
            if application_workflow is not None
            else ApplicationWorkflow()
        )

        self.outreach_pipeline = (
            outreach_pipeline
            if outreach_pipeline is not None
            else OutreachPipeline()
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
        Store a job.
        """

        if not isinstance(job, dict):
            raise TypeError(
                "job must be a dictionary."
            )

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

    def get_jobs(
        self,
    ) -> List[Dict]:
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

        The stored job is marked as matched.
        """

        job = self.get_job(
            job_id
        )

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
        Mark a job as selected.
        """

        if self.get_job(job_id) is None:
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
        Prepare an application.

        Nothing is submitted automatically.
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
            return (
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

        Explicit confirmation is required by the
        application workflow.
        """

        if self.get_job(job_id) is None:
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
    # OUTREACH
    # ========================================================

    def prepare_outreach(
        self,
        job_id: str,
        contacts: Iterable[dict],
        candidate: Optional[Dict] = None,
        resume_path: Optional[str] = None,
    ) -> OutreachResult:
        """
        Prepare outreach for a stored job.

        No email is sent.
        """

        job = self.get_job(
            job_id
        )

        if job is None:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        if candidate is None:
            candidate = {}

        if not isinstance(candidate, dict):
            raise TypeError(
                "candidate must be a dictionary."
            )

        return self.outreach_pipeline.prepare_outreach(
            contacts=contacts,
            job=job,
            candidate=candidate,
            resume_path=resume_path,
        )

    def send_outreach(
        self,
        job_id: str,
        contacts: Iterable[dict],
        candidate: Optional[Dict] = None,
        resume_path: Optional[str] = None,
        confirm: bool = False,
    ) -> OutreachResult:
        """
        Send outreach for a stored job.

        Explicit confirmation is required.
        """

        job = self.get_job(
            job_id
        )

        if job is None:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        if candidate is None:
            candidate = {}

        if not isinstance(candidate, dict):
            raise TypeError(
                "candidate must be a dictionary."
            )

        return self.outreach_pipeline.send_outreach(
            contacts=contacts,
            job=job,
            candidate=candidate,
            resume_path=resume_path,
            confirm=confirm,
        )

    # ========================================================
    # APPLICATION STATUS
    # ========================================================

    def update_application_status(
        self,
        job_id: str,
        status: str,
    ) -> bool:
        """
        Update application status.
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
        Return current application status.
        """

        return self.job_store.get_status(
            job_id
        )

    # ========================================================
    # PROCESS JOB
    # ========================================================

    def process_job(
        self,
        resume: Dict,
        job_id: str,
    ) -> Dict:
        """
        Run matching for one stored job.
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