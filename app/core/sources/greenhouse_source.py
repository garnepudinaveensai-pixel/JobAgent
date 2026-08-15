from __future__ import annotations

from typing import Optional

from app.browser.browser_manager import BrowserManager
from app.browser.job_discovery import JobDiscovery
from app.core.sources.job_source import JobSource


class GreenhouseSource(JobSource):
    """
    Greenhouse job-board source.

    Uses the existing JobDiscovery implementation rather
    than duplicating Greenhouse browser logic.
    """

    name = "greenhouse"

    def __init__(
        self,
        browser: BrowserManager,
    ):
        self.browser = browser
        self.discovery = JobDiscovery(
            browser
        )

    def search(
        self,
        keywords: str,
        location: Optional[str] = None,
        board_url: Optional[str] = None,
    ) -> list[dict]:
        """
        Search a Greenhouse board.

        A board URL is required because Greenhouse hosts
        separate public boards for companies.
        """

        if not board_url or not board_url.strip():
            raise ValueError(
                "Greenhouse board_url cannot be empty."
            )

        jobs = self.discovery.discover_greenhouse(
            board_url=board_url,
            keywords=keywords,
            location=location,
        )

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

                    "source": self.name,
                }
            )

        return normalized