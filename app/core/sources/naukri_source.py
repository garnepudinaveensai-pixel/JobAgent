from __future__ import annotations

from typing import Optional

from app.browser.browser_manager import BrowserManager
from app.browser.job_discovery import JobDiscovery
from app.core.sources.job_source import JobSource


class NaukriSource(JobSource):
    """
    Naukri job source.

    Uses publicly accessible browser functionality.

    Does NOT bypass:
        - authentication
        - CAPTCHA
        - anti-bot protections
        - access restrictions
    """

    name = "naukri"

    def __init__(
        self,
        browser: Optional[BrowserManager] = None,
    ):
        """
        Create a Naukri source.

        A browser is validated when search() is called rather
        than during construction. This keeps the source easy
        to instantiate in tests and configuration code.
        """

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
        Search publicly accessible Naukri jobs.

        board_url is optional because Naukri can construct a
        public search URL from the keywords and location.
        """

        if not keywords or not keywords.strip():
            raise ValueError(
                "Naukri keywords cannot be empty."
            )

        if self.browser is None:
            raise RuntimeError(
                "NaukriSource requires a browser."
            )

        if self.discovery is None:
            raise RuntimeError(
                "NaukriSource requires a browser."
            )

        jobs = self.discovery.discover_naukri(
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

    @staticmethod
    def _normalize_jobs(
        jobs: Optional[list[dict]],
    ) -> list[dict]:
        """
        Normalize jobs returned by Naukri discovery.

        Invalid non-dictionary results are ignored.
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

                    "source": "naukri",
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

    def is_available(self) -> bool:
        """
        Return whether a browser is configured.
        """

        return self.browser is not None