from __future__ import annotations

from typing import Optional

from app.browser.browser_manager import BrowserManager
from app.browser.job_discovery import JobDiscovery
from app.core.sources.job_source import JobSource


class IndeedSource(JobSource):
    """
    Indeed public job source.

    Uses permitted public browser access only.

    Does NOT bypass:
        - authentication
        - CAPTCHA
        - anti-bot protections
        - access restrictions
    """

    name = "indeed"

    def __init__(
        self,
        browser: Optional[BrowserManager] = None,
    ):
        self.browser = browser

        self.discovery = (
            JobDiscovery(browser)
            if browser is not None
            else None
        )
        self.last_diagnostic: dict = {}

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
        Search Indeed.

        board_url is optional for compatibility with the
        common JobSource interface.
        """

        if not keywords or not keywords.strip():
            raise ValueError(
                "Indeed keywords cannot be empty."
            )

        if self.browser is None:
            raise RuntimeError(
                "IndeedSource requires a browser."
            )

        if self.discovery is None:
            raise RuntimeError(
                "IndeedSource requires a browser."
            )

        jobs = self.discovery.discover_indeed(
            board_url=board_url,
            keywords=keywords.strip(),
            location=location,
        )

        self.last_diagnostic = dict(
            getattr(self.discovery, "last_diagnostic", {})
        )
        return self._normalize_jobs(jobs)

    # ========================================================
    # NORMALIZATION
    # ========================================================

    def _normalize_jobs(
        self,
        jobs: Optional[list[dict]],
    ) -> list[dict]:
        """
        Normalize Indeed job results.
        """

        normalized: list[dict] = []

        if jobs is None:
            return normalized

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
                        or ""
                    ).strip(),

                    "company": str(
                        job.get(
                            "company",
                            "",
                        )
                        or ""
                    ).strip(),

                    "location": str(
                        job.get(
                            "location",
                            "",
                        )
                        or ""
                    ).strip(),

                    "url": str(
                        job.get(
                            "url",
                            "",
                        )
                        or ""
                    ).strip(),

                    "description": str(
                        job.get(
                            "description",
                            "",
                        )
                        or ""
                    ).strip(),

                    "source": self.name,
                }
            )

        return normalized

    # ========================================================
    # OPTIONS
    # ========================================================

    def get_supported_options(self) -> set[str]:
        return {"board_url"}

    # ========================================================
    # AVAILABILITY
    # ========================================================

    def is_available(
        self,
    ) -> bool:
        """
        Return whether the source has a browser available.
        """

        return self.browser is not None