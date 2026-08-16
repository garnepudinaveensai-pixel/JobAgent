from __future__ import annotations

from typing import Optional

from app.browser.browser_manager import BrowserManager
from app.browser.sites.greenhouse import GreenhouseSite
from app.browser.sites.indeed import IndeedSite
from app.browser.sites.lever import LeverSite
from app.browser.sites.naukri import NaukriSite
from app.browser.sites.workday import WorkdaySite


class JobDiscovery:
    """
    Coordinates browser-based job discovery across supported
    public job-board sites.

    Supported:
        - Greenhouse
        - Lever
        - Workday
        - Naukri
        - Indeed

    Uses only permitted/public access methods.

    Does NOT:
        - bypass authentication
        - bypass anti-bot systems
        - bypass CAPTCHAs
        - bypass access restrictions
        - submit applications
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
        self._validate_search_inputs(
            board_url,
            keywords,
        )

        page = self.browser.open(
            board_url.strip()
        )

        site = GreenhouseSite(page)

        site.search_jobs(
            keywords=keywords.strip(),
            location=location,
        )

        return self._normalize_discovered_jobs(
            site.get_job_listings()
        )

    def get_greenhouse_job_details(
        self,
        job_url: str,
    ) -> dict:
        self._validate_job_url(job_url)

        page = self.browser.open(
            job_url.strip()
        )

        site = GreenhouseSite(page)

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
        self._validate_search_inputs(
            board_url,
            keywords,
        )

        page = self.browser.open(
            board_url.strip()
        )

        site = LeverSite(page)

        site.search_jobs(
            keywords=keywords.strip(),
            location=location,
        )

        jobs = self._normalize_discovered_jobs(
            site.get_job_listings()
        )

        return self._filter_location(
            jobs,
            location,
        )

    def get_lever_job_details(
        self,
        job_url: str,
    ) -> dict:
        self._validate_job_url(job_url)

        page = self.browser.open(
            job_url.strip()
        )

        site = LeverSite(page)

        return site.get_job_details(
            job_url.strip()
        )

    # ========================================================
    # WORKDAY
    # ========================================================

    def discover_workday(
        self,
        board_url: str,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:
        self._validate_search_inputs(
            board_url,
            keywords,
        )

        page = self.browser.open(
            board_url.strip()
        )

        site = WorkdaySite(page)

        site.search_jobs(
            keywords=keywords.strip(),
            location=location,
        )

        jobs = self._normalize_discovered_jobs(
            site.get_job_listings()
        )

        return self._filter_location(
            jobs,
            location,
        )

    def get_workday_job_details(
        self,
        job_url: str,
    ) -> dict:
        self._validate_job_url(job_url)

        page = self.browser.open(
            job_url.strip()
        )

        site = WorkdaySite(page)

        return site.get_job_details(
            job_url.strip()
        )

    # ========================================================
    # NAUKRI
    # ========================================================

    def discover_naukri(
        self,
        board_url: Optional[str],
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:
        if not keywords or not keywords.strip():
            raise ValueError(
                "keywords cannot be empty."
            )

        page = self.browser.open(
            (
                board_url.strip()
                if board_url
                else "https://www.naukri.com/"
            )
        )

        site = NaukriSite(page)

        site.search_jobs(
            keywords=keywords.strip(),
            location=location,
        )

        jobs = self._normalize_discovered_jobs(
            site.get_job_listings()
        )

        return self._filter_location(
            jobs,
            location,
        )

    def get_naukri_job_details(
        self,
        job_url: str,
    ) -> dict:
        self._validate_job_url(job_url)

        page = self.browser.open(
            job_url.strip()
        )

        site = NaukriSite(page)

        return site.get_job_details(
            job_url.strip()
        )

    # ========================================================
    # INDEED
    # ========================================================

    def discover_indeed(
        self,
        board_url: Optional[str],
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:
        """
        Discover jobs from publicly accessible Indeed.

        board_url is optional. If supplied, it is used as the
        starting page; otherwise Indeed's public search URL
        is used by the site adapter.
        """

        if not keywords or not keywords.strip():
            raise ValueError(
                "keywords cannot be empty."
            )

        start_url = (
            board_url.strip()
            if board_url
            else "https://www.indeed.com/"
        )

        page = self.browser.open(
            start_url
        )

        site = IndeedSite(page)

        site.search_jobs(
            keywords=keywords.strip(),
            location=location,
        )

        jobs = self._normalize_discovered_jobs(
            site.get_job_listings()
        )

        return self._filter_location(
            jobs,
            location,
        )

    def get_indeed_job_details(
        self,
        job_url: str,
    ) -> dict:
        self._validate_job_url(job_url)

        page = self.browser.open(
            job_url.strip()
        )

        site = IndeedSite(page)

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
        if not board_url or not board_url.strip():
            raise ValueError(
                "board_url cannot be empty."
            )

        if not keywords or not keywords.strip():
            raise ValueError(
                "keywords cannot be empty."
            )

    @staticmethod
    def _validate_job_url(
        job_url: str,
    ) -> None:
        if not job_url or not job_url.strip():
            raise ValueError(
                "job_url cannot be empty."
            )

    # ========================================================
    # NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_discovered_jobs(
        jobs: Optional[list[dict]],
    ) -> list[dict]:
        normalized: list[dict] = []

        if jobs is None:
            return normalized

        for job in jobs:
            if not isinstance(job, dict):
                continue

            normalized.append(
                {
                    "title": str(
                        job.get("title", "")
                        or ""
                    ).strip(),
                    "company": str(
                        job.get("company", "")
                        or ""
                    ).strip(),
                    "location": str(
                        job.get("location", "")
                        or ""
                    ).strip(),
                    "url": str(
                        job.get("url", "")
                        or ""
                    ).strip(),
                    "description": str(
                        job.get("description", "")
                        or ""
                    ).strip(),
                }
            )

        return normalized

    @staticmethod
    def _filter_location(
        jobs: list[dict],
        location: Optional[str],
    ) -> list[dict]:
        if not location or not location.strip():
            return jobs

        requested = location.strip().lower()

        return [
            job
            for job in jobs
            if (
                not job.get("location")
                or requested
                in str(
                    job.get("location", "")
                ).lower()
            )
        ]