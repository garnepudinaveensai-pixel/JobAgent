from __future__ import annotations

from typing import Any, Optional

from app.browser.browser_manager import BrowserManager
from app.browser.job_discovery import JobDiscovery
from app.core.sources.job_source import JobSource


class LeverSource(JobSource):
    """
    Lever public job-board source.

    Supported source-specific option:

        board_url

    This source does not bypass authentication, CAPTCHAs,
    anti-bot controls, or other access restrictions.
    """

    name = "lever"

    SUPPORTED_OPTIONS = {
        "board_url",
    }

    def __init__(
        self,
        browser: Optional[BrowserManager] = None,
    ):
        self.browser = browser

        self.discovery = None

        if browser is not None:
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
        Search a public Lever job board.
        """

        if not keywords or not keywords.strip():
            raise ValueError(
                "Lever keywords cannot be empty."
            )

        board_url = options.get(
            "board_url"
        )

        if not board_url or not str(
            board_url
        ).strip():
            raise ValueError(
                "Lever board_url cannot be empty."
            )

        if self.browser is None:
            raise RuntimeError(
                "LeverSource requires a browser."
            )

        if self.discovery is None:
            self.discovery = JobDiscovery(
                self.browser
            )

        jobs = self.discovery.discover_lever(
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
        Normalize Lever results.
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
        Lever is available when a browser is configured.
        """

        return self.browser is not None