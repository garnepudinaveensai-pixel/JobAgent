from __future__ import annotations

from typing import Iterable, Optional

from app.config import (
    JobAgentConfig,
    create_default_config,
)
from app.core.job_agent import JobAgent
from app.jobs.job_store import JobStore
from app.outreach.outreach_pipeline import (
    OutreachResult,
)


class AgentRunner:
    """
    High-level entry point for JobAgent.

    Coordinates:

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
        Outreach
            ↓
        Tracking

    Actual application submission remains protected by
    explicit confirmation in the application layer.

    Outreach sending also requires explicit confirmation.

    Job discovery is an optional dependency. A JobAgent must
    be explicitly supplied when discovery functionality is
    required.
    """

    def __init__(
        self,
        config: Optional[
            JobAgentConfig
        ] = None,
        job_store: Optional[
            JobStore
        ] = None,
        job_agent: Optional[
            JobAgent
        ] = None,
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
                storage_path=(
                    self.config.storage.jobs_file
                )
            )
        )

        # Job discovery is an optional dependency.
        #
        # Do NOT automatically create JobAgent here.
        # This keeps AgentRunner independent and allows
        # discovery to be explicitly injected.
        self.job_agent = job_agent

    # ========================================================
    # CONFIGURATION
    # ========================================================

    def validate_config(
        self,
    ) -> None:
        """
        Validate current configuration.
        """

        self.config.validate()

    # ========================================================
    # JOB STORAGE
    # ========================================================

    def store_jobs(
        self,
        jobs: Iterable[dict],
    ) -> list[str]:
        """
        Store discovered jobs.

        Invalid/non-dictionary entries are ignored.

        Returns:
            Stable job IDs.
        """

        if jobs is None:
            return []

        job_ids: list[str] = []

        for job in jobs:
            if not isinstance(
                job,
                dict,
            ):
                continue

            job_id = self.job_store.add_job(
                job,
                status="discovered",
            )

            job_ids.append(
                job_id
            )

        return job_ids

    # ========================================================
    # JOB STATUS
    # ========================================================

    def update_job_status(
        self,
        job_id: str,
        status: str,
    ) -> bool:
        """
        Update lifecycle status.
        """

        return self.job_store.update_status(
            job_id,
            status,
        )

    # ========================================================
    # JOB RETRIEVAL
    # ========================================================

    def get_jobs(
        self,
        status: Optional[str] = None,
    ) -> list[dict]:
        """
        Return all jobs or jobs filtered by status.
        """

        if status is not None:
            return (
                self.job_store
                .get_jobs_by_status(
                    status
                )
            )

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
        """
        Discover jobs through the configured JobAgent.

        A JobAgent must be explicitly configured.

        Raises:
            RuntimeError:
                If no JobAgent is configured or if the
                configured object does not expose discover_jobs().
        """

        if self.job_agent is None:
            raise RuntimeError(
                "JobAgent is not configured. "
                "Provide a job_agent before discovering jobs."
            )

        if not hasattr(
            self.job_agent,
            "discover_jobs",
        ):
            raise RuntimeError(
                "The configured JobAgent does not "
                "provide discover_jobs()."
            )

        jobs = self.job_agent.discover_jobs(
            board_url=board_url,
            keywords=keywords,
            location=location,
        )

        if jobs is None:
            return []

        return list(jobs)

    # ========================================================
    # DISCOVER + STORE
    # ========================================================

    def discover_and_store(
        self,
        board_url: str,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[str]:
        """
        Discover jobs and persist them.
        """

        jobs = self.discover_jobs(
            board_url=board_url,
            keywords=keywords,
            location=location,
        )

        return self.store_jobs(
            jobs
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
        """
        Prepare HR/recruiter outreach.

        No email is sent.
        """

        if candidate is None:
            candidate = {}

        if not isinstance(
            candidate,
            dict,
        ):
            raise TypeError(
                "candidate must be a dictionary."
            )

        if self.job_agent is None:
            raise RuntimeError(
                "JobAgent is not configured."
            )

        return self.job_agent.prepare_outreach(
            job_id=job_id,
            contacts=contacts,
            candidate=candidate,
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
        """
        Send HR/recruiter outreach.

        Explicit confirmation is required.
        """

        if candidate is None:
            candidate = {}

        if not isinstance(
            candidate,
            dict,
        ):
            raise TypeError(
                "candidate must be a dictionary."
            )

        if self.job_agent is None:
            raise RuntimeError(
                "JobAgent is not configured."
            )

        return self.job_agent.send_outreach(
            job_id=job_id,
            contacts=contacts,
            candidate=candidate,
            resume_path=resume_path,
            confirm=confirm,
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    def summary(
        self,
    ) -> dict:
        """
        Return a compact summary of the current
        job database.
        """

        jobs = self.job_store.get_all_jobs()

        summary = {
            "total": len(jobs),

            "discovered": 0,
            "matched": 0,
            "selected": 0,

            "application_started": 0,
            "applied": 0,
            "application_failed": 0,

            "shortlisted": 0,
            "rejected": 0,
            "interview": 0,
            "assessment": 0,
            "walk_in": 0,

            "status_changed": 0,
        }

        for job in jobs:
            status = job.get(
                "status"
            )

            if status in summary:
                summary[status] += 1

        return summary