from __future__ import annotations

from typing import Iterable, Optional

from app.config import (
    JobAgentConfig,
    create_default_config,
)
from app.core.application_pipeline import ApplicationPipeline
from app.core.job_match_pipeline import JobMatchPipeline
from app.jobs.job_store import JobStore
from app.outreach.outreach_pipeline import OutreachResult


class AgentRunner:
    """
    High-level orchestration layer for JobAgent.

    Pipeline:

        Discovery
            ↓
        Storage
            ↓
        Matching
            ↓
        Selection
            ↓
        Application preparation
            ↓
        Explicit confirmation
            ↓
        Submission
            ↓
        Tracking
            ↓
        Email status / notification

    Browser automation is delegated to the appropriate
    browser/pipeline components.
    """

    def __init__(
        self,
        config: Optional[JobAgentConfig] = None,
        job_store: Optional[JobStore] = None,
        job_match_pipeline: Optional[JobMatchPipeline] = None,
        application_pipeline: Optional[ApplicationPipeline] = None,
        job_agent=None,
    ):
        self.config = (
            config
            if config is not None
            else create_default_config()
        )

        self.job_store = (
            job_store
            if job_store is not None
            else JobStore(
                storage_path=self.config.storage.jobs_file
            )
        )

        self.job_match_pipeline = (
            job_match_pipeline
        )

        # Shared JobStore is critical.
        self.application_pipeline = (
            application_pipeline
            if application_pipeline is not None
            else ApplicationPipeline(
                job_store=self.job_store
            )
        )

        # Backward compatibility.
        self.job_agent = job_agent

    # ========================================================
    # CONFIG
    # ========================================================

    def validate_config(self) -> None:
        self.config.validate()

    # ========================================================
    # STORAGE
    # ========================================================

    def store_jobs(
        self,
        jobs: Iterable[dict],
    ) -> list[str]:

        if jobs is None:
            return []

        job_ids = []

        for job in jobs:

            if not isinstance(job, dict):
                continue

            try:
                job_id = self.job_store.add_job(
                    job,
                    status="discovered",
                )

            except (
                TypeError,
                ValueError,
            ):
                # One malformed job must not destroy
                # an entire discovery batch.
                continue

            job_ids.append(job_id)

        return job_ids

    # ========================================================
    # JOBS
    # ========================================================

    def get_jobs(
        self,
        status: Optional[str] = None,
    ) -> list[dict]:

        if status is not None:
            return self.job_store.get_jobs_by_status(
                status
            )

        return self.job_store.get_all_jobs()

    def get_job(
        self,
        job_id: str,
    ) -> Optional[dict]:

        return self.job_store.get_job(
            job_id
        )

    def update_job_status(
        self,
        job_id: str,
        status: str,
    ) -> bool:

        return self.job_store.update_status(
            job_id,
            status,
        )

    # ========================================================
    # DISCOVERY
    # ========================================================

    def discover_jobs(
        self,
        board_url: str,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:

        # Preferred modern pipeline.
        if self.job_match_pipeline is not None:

            method = getattr(
                self.job_match_pipeline,
                "job_pipeline",
                None,
            )

            if method is not None:
                discover = getattr(
                    method,
                    "discover_greenhouse_jobs",
                    None,
                )

                if callable(discover):
                    jobs = discover(
                        board_url=board_url,
                        keywords=keywords,
                        location=location,
                    )

                    return list(
                        jobs or []
                    )

        # Backward-compatible JobAgent.
        if self.job_agent is not None:

            discover = getattr(
                self.job_agent,
                "discover_jobs",
                None,
            )

            if callable(discover):
                jobs = discover(
                    board_url=board_url,
                    keywords=keywords,
                    location=location,
                )

                return list(
                    jobs or []
                )

        raise RuntimeError(
            "No job discovery pipeline is configured."
        )

    # ========================================================
    # DISCOVER + STORE
    # ========================================================

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

        return self.store_jobs(
            jobs
        )

    # ========================================================
    # DISCOVER + MATCH
    # ========================================================

    def discover_and_match(
        self,
        board_url: str,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:

        if self.job_match_pipeline is None:
            raise RuntimeError(
                "JobMatchPipeline is not configured."
            )

        results = (
            self.job_match_pipeline
            .discover_and_match_greenhouse(
                board_url=board_url,
                keywords=keywords,
                location=location,
            )
        )

        return list(
            results or []
        )

    # ========================================================
    # MATCH STORED JOB
    # ========================================================

    def match_job(
        self,
        resume: dict,
        job_id: str,
    ) -> dict:

        job = self.get_job(
            job_id
        )

        if job is None:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        result = self.application_pipeline.evaluate_job(
            resume=resume,
            job=job,
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

        job = self.get_job(
            job_id
        )

        if job is None:
            return False

        return self.job_store.update_status(
            job_id,
            "selected",
        )

    def select_eligible_jobs(
        self,
        results: Iterable[dict],
    ) -> list[str]:

        selected = []

        for result in results:

            if not isinstance(
                result,
                dict,
            ):
                continue

            match = result.get(
                "match",
                {},
            )

            if not isinstance(
                match,
                dict,
            ):
                continue

            if not match.get(
                "eligible",
                False,
            ):
                continue

            job = result.get(
                "job",
                {},
            )

            if not isinstance(
                job,
                dict,
            ):
                continue

            job_id = job.get(
                "job_id"
            ) or job.get(
                "url"
            )

            if not job_id:
                continue

            # Ensure job exists first.
            if self.job_store.get_job(
                job_id
            ) is None:
                self.job_store.add_job(
                    job,
                    status="matched",
                )

            if self.select_job(
                job_id
            ):
                selected.append(
                    job_id
                )

        return selected

    # ========================================================
    # APPLICATION PREPARATION
    # ========================================================

    def prepare_application(
        self,
        page,
        job_id: str,
        resume_path: str,
        fields: dict,
    ) -> dict:

        job = self.get_job(
            job_id
        )

        if job is None:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        return self.application_pipeline.prepare_application(
            page=page,
            job=job,
            resume_path=resume_path,
            fields=fields,
        )

    # ========================================================
    # APPLICATION SUBMISSION
    # ========================================================

    def submit_application(
        self,
        page,
        job_id: str,
        confirm: bool = False,
    ) -> dict:

        return self.application_pipeline.submit_application(
            page=page,
            job_id=job_id,
            confirm=confirm,
        )

    # ========================================================
    # APPLICATION STATUS
    # ========================================================

    def update_application_status(
        self,
        job_id: str,
        status: str,
        details: Optional[dict] = None,
    ) -> bool:

        return self.application_pipeline.update_application_status(
            job_id=job_id,
            status=status,
            details=details,
        )

    def get_application_status(
        self,
        job_id: str,
    ) -> Optional[str]:

        return self.application_pipeline.get_application_status(
            job_id
        )

    # ========================================================
    # OUTREACH
    # ========================================================

    def prepare_outreach(
        self,
        job_id: str,
        contacts: Iterable[dict],
        candidate: Optional[dict] = None,
        resume_path: Optional[str] = None,
    ) -> OutreachResult:

        if self.job_agent is None:
            raise RuntimeError(
                "JobAgent outreach component is not configured."
            )

        return self.job_agent.prepare_outreach(
            job_id=job_id,
            contacts=contacts,
            candidate=candidate or {},
            resume_path=resume_path,
        )

    def send_outreach(
        self,
        job_id: str,
        contacts: Iterable[dict],
        candidate: Optional[dict] = None,
        resume_path: Optional[str] = None,
        confirm: bool = False,
    ) -> OutreachResult:

        if self.job_agent is None:
            raise RuntimeError(
                "JobAgent outreach component is not configured."
            )

        return self.job_agent.send_outreach(
            job_id=job_id,
            contacts=contacts,
            candidate=candidate or {},
            resume_path=resume_path,
            confirm=confirm,
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    def summary(self) -> dict:

        jobs = self.job_store.get_all_jobs()

        statuses = [
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
        ]

        summary = {
            "total": len(jobs)
        }

        for status in statuses:
            summary[status] = sum(
                1
                for job in jobs
                if job.get("status") == status
            )

        return summary