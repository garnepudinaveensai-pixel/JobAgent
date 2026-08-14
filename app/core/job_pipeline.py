from typing import Optional

from app.browser.browser_manager import BrowserManager
from app.browser.job_discovery import JobDiscovery


class JobPipeline:
    """
    Connects browser-based job discovery with the existing
    JobAgent processing pipeline.

    Current responsibility:
    - Discover jobs from Greenhouse.
    - Normalize the discovered jobs.
    - Keep the result ready for the existing matching layer.

    Does NOT apply to jobs.
    """

    def __init__(
        self,
        browser: BrowserManager,
    ):
        self.browser = browser
        self.discovery = JobDiscovery(browser)

    def discover_greenhouse_jobs(
        self,
        board_url: str,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:
        """
        Discover jobs from a Greenhouse board.
        """

        jobs = self.discovery.discover_greenhouse(
            board_url=board_url,
            keywords=keywords,
            location=location,
        )

        return self._normalize_jobs(jobs)

    @staticmethod
    def _normalize_jobs(
        jobs: list[dict],
    ) -> list[dict]:
        """
        Ensure every discovered job has the normalized
        fields expected by the rest of JobAgent.
        """

        normalized = []

        for job in jobs:
            if not isinstance(job, dict):
                continue

            normalized.append(
                {
                    "title": str(
                        job.get("title", "")
                    ).strip(),

                    "company": str(
                        job.get("company", "")
                    ).strip(),

                    "location": str(
                        job.get("location", "")
                    ).strip(),

                    "url": str(
                        job.get("url", "")
                    ).strip(),

                    "description": str(
                        job.get("description", "")
                    ).strip(),
                }
            )

        return normalized