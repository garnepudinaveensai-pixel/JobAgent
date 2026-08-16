from __future__ import annotations

from typing import Optional

from app.browser.browser_manager import BrowserManager
from app.browser.job_discovery import JobDiscovery
from app.core.sources.job_source import JobSource


class WorkdaySource(JobSource):
    """
    Public Workday external-career-site source.

    Uses the existing JobDiscovery layer and does not
    duplicate browser logic.

    This source does NOT:
        - bypass authentication
        - bypass CAPTCHA
        - bypass anti-bot controls
        - bypass access restrictions
        - submit applications
    """

    name = "workday"

    def __init__(
        self,
        browser: BrowserManager,
    ):
        if browser is None:
            raise ValueError(
                "WorkdaySource requires a browser."
            )

        self.browser = browser

        self.discovery = JobDiscovery(
            browser
        )

    # ========================================================
    # SEARCH
    # ========================================================

    def search(
        self,
        keywords: str,
        location: Optional[str] = None,
        board_url: Optional[str] = None,
    ) -> list[dict]:
        """
        Search a public Workday external career site.
        """

        if not keywords or not keywords.strip():
            raise ValueError(
                "Workday keywords cannot be empty."
            )

        if not board_url or not board_url.strip():
            raise ValueError(
                "Workday board_url cannot be empty."
            )

        jobs = self.discovery.discover_workday(
            board_url=board_url.strip(),
            keywords=keywords.strip(),
            location=location,
        )

        return self._normalize_jobs(
            jobs
        )

    # ========================================================
    # NORMALIZATION
    # ========================================================

    def _normalize_jobs(
        self,
        jobs: list[dict],
    ) -> list[dict]:
        """
        Normalize Workday discovery results.
        """

        normalized: list[dict] = []

        for job in jobs:

            if not isinstance(
                job,
                dict,
            ):
                continue

            normalized.append(
                {
                    "title": str(
                        job.get(
                            "title",
                            "",
                        )
                    ).strip(),

                    "company": str(
                        job.get(
                            "company",
                            "",
                        )
                    ).strip(),

                    "location": str(
                        job.get(
                            "location",
                            "",
                        )
                    ).strip(),

                    "url": str(
                        job.get(
                            "url",
                            "",
                        )
                    ).strip(),

                    "description": str(
                        job.get(
                            "description",
                            "",
                        )
                    ).strip(),

                    "source": self.name,
                }
            )

        return normalized

    # ========================================================
    # AVAILABILITY
    # ========================================================

    def is_available(self) -> bool:
        """
        Workday is considered configured when a browser
        instance exists.

        Actual availability is determined when a public
        career site is accessed.
        """

        return self.browser is not None