from __future__ import annotations

from typing import Any, Optional

from app.browser.browser_manager import BrowserManager
from app.browser.job_discovery import JobDiscovery
from app.core.sources.job_source import JobSource


class GreenhouseSource(JobSource):
    """
    Greenhouse public job-board source.

    Supported source-specific option:

        board_url

    This source does not bypass authentication, CAPTCHAs,
    anti-bot controls, or other access restrictions.
    """

    name = "greenhouse"

    SUPPORTED_OPTIONS = {
        "board_url",
    }

    def __init__(
        self,
        browser: BrowserManager,
    ):
        if browser is None:
            raise ValueError(
                "GreenhouseSource requires a browser."
            )

        self.browser = browser

        self.discovery = JobDiscovery(
            browser
        )

    def supports_option(
        self,
        option: str,
    ) -> bool:
        return option in self.SUPPORTED_OPTIONS

    def get_supported_options(
        self,
    ) -> set[str]:
        return set(
            self.SUPPORTED_OPTIONS
        )

    def search(
        self,
        keywords: str,
        location: Optional[str] = None,
        **options: Any,
    ) -> list[dict]:
        """
        Search a Greenhouse public board.
        """

        if not keywords or not keywords.strip():
            raise ValueError(
                "Greenhouse keywords cannot be empty."
            )

        board_url = options.get(
            "board_url"
        )

        if not board_url or not str(
            board_url
        ).strip():
            raise ValueError(
                "Greenhouse board_url cannot be empty."
            )

        jobs = self.discovery.discover_greenhouse(
            board_url=str(
                board_url
            ).strip(),
            keywords=keywords.strip(),
            location=location,
        )

        return self._normalize_jobs(
            jobs
        )

    def _normalize_jobs(
        self,
        jobs: Any,
    ) -> list[dict]:
        """
        Normalize Greenhouse results.
        """

        if jobs is None:
            return []

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

    def is_available(self) -> bool:
        """
        Greenhouse is available when its browser is configured.
        """

        return self.browser is not None