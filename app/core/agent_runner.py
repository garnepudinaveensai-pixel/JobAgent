from typing import Optional

from app.config import JobAgentConfig, create_default_config
from app.core.job_agent import JobAgent
from app.jobs.job_store import JobStore


class AgentRunner:
    """
    High-level entry point for JobAgent.

    Coordinates job discovery, matching, resume preparation,
    application preparation, and status tracking.

    Actual application submission remains protected by the
    confirmation mechanism in the application layer.
    """

    def __init__(
        self,
        config: Optional[JobAgentConfig] = None,
        job_store: Optional[JobStore] = None,
        job_agent: Optional[JobAgent] = None,
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

        self.job_agent = job_agent

    # ========================================================
    # CONFIGURATION
    # ========================================================

    def validate_config(self) -> None:
        """
        Validate the current configuration.
        """

        self.config.validate()

    # ========================================================
    # JOB STORAGE
    # ========================================================

    def store_jobs(
        self,
        jobs: list[dict],
    ) -> list[str]:
        """
        Store discovered jobs.

        Returns:
            List of stable job IDs.
        """

        job_ids = []

        for job in jobs:
            if not isinstance(job, dict):
                continue

            job_id = self.job_store.add_job(
                job,
                status="discovered",
            )

            job_ids.append(job_id)

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
        Update the lifecycle status of a stored job.
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
            return self.job_store.get_jobs_by_status(
                status
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
        Discover jobs through the existing JobAgent.

        This method intentionally delegates the actual browser
        work to the existing JobAgent implementation.
        """

        if self.job_agent is None:
            raise RuntimeError(
                "A JobAgent instance is required "
                "for browser-based discovery."
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

        Returns:
            Stable IDs for stored jobs.
        """

        jobs = self.discover_jobs(
            board_url=board_url,
            keywords=keywords,
            location=location,
        )

        return self.store_jobs(jobs)

    # ========================================================
    # SUMMARY
    # ========================================================

    def summary(self) -> dict:
        """
        Return a compact summary of the current job database.
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
            status = job.get("status")

            if status in summary:
                summary[status] += 1

        return summary