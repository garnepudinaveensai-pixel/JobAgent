from __future__ import annotations

from typing import Optional

from app.browser.browser_manager import BrowserManager
from app.browser.sites.greenhouse import GreenhouseSite
from app.browser.sites.lever import LeverSite


class JobDiscovery:
    """
    Coordinates browser-based job discovery across supported
    public job-board sites.

    Current supported sites:
        - Greenhouse
        - Lever

    Responsible for:
        - opening job boards
        - searching jobs
        - collecting listings
        - collecting job details

    Does NOT:
        - match jobs to resumes
        - tailor resumes
        - submit applications
        - bypass authentication
        - bypass anti-bot systems
        - bypass CAPTCHAs
        - bypass access restrictions
    """

    def __init__(
        self,
        browser: BrowserManager,
    ):
        if browser is None:
            raise ValueError(
                "JobDiscovery requires a browser."
            )

        self.browser = browser

    # ========================================================
    # GREENHOUSE
    # ========================================================

    def discover_greenhouse(
        self,
        board_url: str,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:
        """
        Discover jobs from a publicly accessible
        Greenhouse job board.
        """

        self._validate_search_inputs(
            board_url=board_url,
            keywords=keywords,
        )

        page = self.browser.open(
            board_url.strip()
        )

        site = GreenhouseSite(
            page
        )

        site.search_jobs(
            keywords=keywords.strip(),
            location=location,
        )

        jobs = site.get_job_listings()

        return self._normalize_discovered_jobs(
            jobs
        )

    def get_greenhouse_job_details(
        self,
        job_url: str,
    ) -> dict:
        """
        Get complete details for one Greenhouse job.
        """

        self._validate_job_url(
            job_url
        )

        page = self.browser.open(
            job_url.strip()
        )

        site = GreenhouseSite(
            page
        )

        return site.get_job_details(
            job_url.strip()
        )

    # ========================================================
    # LEVER
    # ========================================================

    def discover_lever(
        self,
        board_url: str,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:
        """
        Discover jobs from a publicly accessible
        Lever job board.

        Only normal publicly permitted access is used.
        """

        self._validate_search_inputs(
            board_url=board_url,
            keywords=keywords,
        )

        page = self.browser.open(
            board_url.strip()
        )

        site = LeverSite(
            page
        )

        site.search_jobs(
            keywords=keywords.strip(),
            location=location,
        )

        jobs = site.get_job_listings()

        jobs = self._normalize_discovered_jobs(
            jobs
        )

        if location and location.strip():

            requested_location = (
                location.strip().lower()
            )

            filtered: list[dict] = []

            for job in jobs:

                job_location = str(
                    job.get(
                        "location",
                        "",
                    )
                ).lower()

                # Keep jobs with unknown location.
                #
                # This avoids accidentally throwing away
                # valid jobs when the website does not expose
                # location information in the listing.
                if (
                    not job_location
                    or requested_location
                    in job_location
                ):
                    filtered.append(
                        job
                    )

            return filtered

        return jobs

    def get_lever_job_details(
        self,
        job_url: str,
    ) -> dict:
        """
        Get complete details for one publicly accessible
        Lever job.
        """

        self._validate_job_url(
            job_url
        )

        page = self.browser.open(
            job_url.strip()
        )

        site = LeverSite(
            page
        )

        return site.get_job_details(
            job_url.strip()
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def _validate_search_inputs(
        board_url: str,
        keywords: str,
    ) -> None:
        """
        Validate common job-search inputs.
        """

        if (
            not board_url
            or not board_url.strip()
        ):
            raise ValueError(
                "board_url cannot be empty."
            )

        if (
            not keywords
            or not keywords.strip()
        ):
            raise ValueError(
                "keywords cannot be empty."
            )

    @staticmethod
    def _validate_job_url(
        job_url: str,
    ) -> None:
        """
        Validate a job URL.
        """

        if (
            not job_url
            or not job_url.strip()
        ):
            raise ValueError(
                "job_url cannot be empty."
            )

    # ========================================================
    # NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_discovered_jobs(
        jobs: list[dict],
    ) -> list[dict]:
        """
        Normalize raw site results.

        This keeps the browser/site layer consistent while
        allowing source-specific adapters to provide additional
        information later.
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
                }
            )

        return normalized