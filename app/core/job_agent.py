from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from app.core.application_workflow import ApplicationWorkflow
from app.core.job_match_pipeline import JobMatchPipeline
from app.core.job_match_pipeline import JobMatchPipeline
from app.core.job_match_pipeline import JobMatchPipeline
from app.core.matcher import match_job
from app.jobs.job_store import JobStore
from app.outreach.outreach_pipeline import (
    OutreachPipeline,
    OutreachResult,
)


class JobAgent:
    """
    Main high-level JobAgent coordinator.

    Responsibilities:

        Discovery
            ↓
        Storage
            ↓
        Matching
            ↓
        Selection
            ↓
        Application
            ↓
        Outreach
            ↓
        Tracking
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
        job_match_pipeline: Optional[
            JobMatchPipeline
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

        self.job_match_pipeline = (
            job_match_pipeline
        )

    # ========================================================
    # JOB STORAGE
    # ========================================================

    def add_job(
        self,
        job: Dict,
        status: str = "discovered",
    ) -> str:

        if not isinstance(
            job,
            dict,
        ):
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

        return self.job_store.get_job(
            job_id
        )

    def get_jobs(self) -> List[Dict]:

        return self.job_store.get_all_jobs()

    # ========================================================
    # DISCOVERY
    # ========================================================

    def discover_jobs(
        self,
        board_url: str,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:

        if self.job_match_pipeline is None:
            raise RuntimeError(
                "JobMatchPipeline is not configured."
            )

        pipeline = self.job_match_pipeline.job_pipeline

        jobs = pipeline.discover_greenhouse_jobs(
            board_url=board_url,
            keywords=keywords,
            location=location,
        )

        return list(
            jobs or []
        )

    def discover_and_store(
        self,
        board_url: str,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[str]:

        jobs = self.discover_jobs(
            board_url=board_url,
            keywords=keywords,
            location=location,
        )

        return [
            self.add_job(
                job,
                status="discovered",
            )
            for job in jobs
            if isinstance(job, dict)
        ]

    # ========================================================
    # MATCHING
    # ========================================================

    @staticmethod
    def match(
        resume: Dict,
        job: Dict,
    ) -> Dict:

        return match_job(
            resume,
            job,
        )

    def match_and_store(
        self,
        resume: Dict,
        job_id: str,
    ) -> Dict:

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

        if result.get("eligible"):
            self.job_store.update_status(
                job_id,
                "matched",
            )

        return result

    # ========================================================
    # SELECTION
    # ========================================================

    def select_job(
        self,
        job_id: str,
    ) -> bool:

        if self.get_job(
            job_id
        ) is None:
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
                    resume_output_path=resume_output_path,
                )
            )

        except Exception:
            self.job_store.update_status(
                job_id,
                "application_failed",
            )
            raise

    # ========================================================
    # SUBMISSION
    # ========================================================

    def submit_application(
        self,
        job_id: str,
        prepared_application: Dict,
        confirm: bool = False,
    ) -> Dict:

        if self.get_job(
            job_id
        ) is None:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        result = self.application_workflow.submit(
            prepared_application,
            confirm=confirm,
        )

        if result.get("success"):
            self.job_store.update_status(
                job_id,
                "applied",
            )

        elif result.get("status") == "validation_failed":
            self.job_store.update_status(
                job_id,
                "application_failed",
            )

        return result

    # ========================================================
    # STATUS
    # ========================================================

    def update_application_status(
        self,
        job_id: str,
        status: str,
    ) -> bool:

        return self.job_store.update_status(
            job_id,
            status,
        )

    def get_application_status(
        self,
        job_id: str,
    ) -> Optional[str]:

        return self.job_store.get_status(
            job_id
        )

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

        job = self.get_job(
            job_id
        )

        if job is None:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        return self.outreach_pipeline.prepare_outreach(
            contacts=contacts,
            job=job,
            candidate=candidate or {},
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

        job = self.get_job(
            job_id
        )

        if job is None:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        return self.outreach_pipeline.send_outreach(
            contacts=contacts,
            job=job,
            candidate=candidate or {},
            resume_path=resume_path,
            confirm=confirm,
        )

    # ========================================================
    # PROCESS
    # ========================================================

    def process_job(
        self,
        resume: Dict,
        job_id: str,
    ) -> Dict:

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