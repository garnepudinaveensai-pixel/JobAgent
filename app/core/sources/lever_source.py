from __future__ import annotations

from typing import Optional

from app.browser.browser_manager import BrowserManager
from app.browser.job_discovery import JobDiscovery
from app.core.sources.job_source import JobSource


class LeverSource(JobSource):
    """
    Lever job source.

    Uses publicly accessible Lever job-board functionality
    through the existing browser discovery layer.

    This source does NOT:
    - bypass authentication
    - bypass anti-bot controls
    - bypass access restrictions
    - bypass CAPTCHAs
    - submit applications

    Application submission remains a separate pipeline.
    """

    name = "lever"

    def __init__(
        self,
        browser: Optional[BrowserManager] = None,
    ):
        """
        Create a Lever source.

        The browser is optional during construction so that
        configuration and validation can be performed before
        an actual browser is required.
        """

        self.browser = browser

        self.discovery: Optional[
            JobDiscovery
        ] = None

        if browser is not None:
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
        Search a publicly accessible Lever job board.

        Args:
            keywords:
                Job search keywords.

            location:
                Optional location filter.

            board_url:
                Public Lever job-board URL.

        Returns:
            Normalized job dictionaries.

        Raises:
            ValueError:
                If keywords or board_url are empty.

            RuntimeError:
                If no browser has been configured.
        """

        # ----------------------------------------------------
        # Validate keywords
        # ----------------------------------------------------

        if not keywords or not keywords.strip():
            raise ValueError(
                "Lever keywords cannot be empty."
            )

        # ----------------------------------------------------
        # Validate board URL
        # ----------------------------------------------------

        if not board_url or not board_url.strip():
            raise ValueError(
                "Lever board_url cannot be empty."
            )

        # ----------------------------------------------------
        # Validate browser
        # ----------------------------------------------------

        if self.browser is None:
            raise RuntimeError(
                "LeverSource requires a browser."
            )

        # ----------------------------------------------------
        # Ensure discovery exists
        # ----------------------------------------------------

        if self.discovery is None:
            self.discovery = JobDiscovery(
                self.browser
            )

        # ----------------------------------------------------
        # Discover jobs
        # ----------------------------------------------------

        jobs = self.discovery.discover_lever(
            board_url=board_url.strip(),
            keywords=keywords.strip(),
            location=location,
        )

        # ----------------------------------------------------
        # Normalize results
        # ----------------------------------------------------

        return self._normalize_jobs(
            jobs
        )

    # ========================================================
    # NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_jobs(
        jobs: list[dict],
    ) -> list[dict]:
        """
        Normalize jobs returned by Lever discovery.

        Every valid job receives the common JobAgent schema.
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

                    "source": "lever",
                }
            )

        return normalized

    # ========================================================
    # AVAILABILITY
    # ========================================================

    def is_available(self) -> bool:
        """
        Return whether the Lever source has a browser
        configured.

        This does not claim that the remote Lever site is
        reachable. Actual site availability is determined
        during discovery.
        """

        return self.browser is not None