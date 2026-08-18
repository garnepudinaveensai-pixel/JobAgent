from __future__ import annotations

from typing import Any, Optional

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
        self.last_diagnostic: dict[str, Any] = {}

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

        jobs = self._normalize_discovered_jobs(
            site.get_job_listings()
        )

        jobs = self._filter_location(
            jobs,
            location,
        )

        self.last_diagnostic = {
            "source": "greenhouse",
            "status": "ok" if jobs else "no_results",
            "jobs": len(jobs),
            "error": (
                None
                if jobs
                else "No usable Greenhouse listings were extracted."
            ),
            "code": (
                "ok"
                if jobs
                else "no_results"
            ),
            "requires_human_action": False,
        }

        return jobs

    def get_greenhouse_job_details(
        self,
        job_url: str,
    ) -> dict:
        self._validate_job_url(
            job_url
        )

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

        jobs = self._filter_location(
            jobs,
            location,
        )

        self.last_diagnostic = {
            "source": "lever",
            "status": "ok" if jobs else "no_results",
            "jobs": len(jobs),
            "error": (
                None
                if jobs
                else "No usable Lever listings were extracted."
            ),
            "code": (
                "ok"
                if jobs
                else "no_results"
            ),
            "requires_human_action": False,
        }

        return jobs

    def get_lever_job_details(
        self,
        job_url: str,
    ) -> dict:
        self._validate_job_url(
            job_url
        )

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

        jobs = self._filter_location(
            jobs,
            location,
        )

        self.last_diagnostic = {
            "source": "workday",
            "status": "ok" if jobs else "no_results",
            "jobs": len(jobs),
            "error": (
                None
                if jobs
                else "No usable Workday listings were extracted."
            ),
            "code": (
                "ok"
                if jobs
                else "no_results"
            ),
            "requires_human_action": False,
        }

        return jobs

    def get_workday_job_details(
        self,
        job_url: str,
    ) -> dict:
        self._validate_job_url(
            job_url
        )

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

        # IMPORTANT:
        # Import lazily to avoid circular import during
        # app.core.sources package initialization.
        from app.core.sources.job_source import (
            SourceAccessError,
        )

        start_url = (
            board_url.strip()
            if board_url
            else "https://www.naukri.com/"
        )

        page = self.browser.open(
            start_url
        )

        site = NaukriSite(page)

        site.search_jobs(
            keywords=keywords.strip(),
            location=location,
        )

        state = site.get_access_state()

        if state["blocked"]:
            self.last_diagnostic = {
                "source": "naukri",
                "status": "blocked",
                "jobs": 0,
                "error": state["message"],
                "code": state["code"],
                "requires_human_action": (
                    state[
                        "requires_human_action"
                    ]
                ),
                "url": site.get_current_url(),
            }

            raise SourceAccessError(
                state["message"],
                code=state["code"],
                requires_human_action=(
                    state[
                        "requires_human_action"
                    ]
                ),
            )

        jobs = self._normalize_discovered_jobs(
            site.get_job_listings()
        )

        jobs = self._filter_location(
            jobs,
            location,
        )

        self.last_diagnostic = {
            "source": "naukri",
            "status": (
                "ok"
                if jobs
                else "no_results"
            ),
            "jobs": len(jobs),
            "error": (
                None
                if jobs
                else (
                    "No publicly accessible "
                    "Naukri listings were extracted."
                )
            ),
            "code": (
                "ok"
                if jobs
                else "no_results"
            ),
            "requires_human_action": False,
            "url": site.get_current_url(),
        }

        return jobs

    def get_naukri_job_details(
        self,
        job_url: str,
    ) -> dict:
        self._validate_job_url(
            job_url
        )

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
        Discover publicly accessible Indeed listings.

        If Indeed presents a verification or anti-bot page,
        report it as blocked instead of incorrectly returning
        an empty job list.
        """

        if not keywords or not keywords.strip():
            raise ValueError(
                "keywords cannot be empty."
            )

        # IMPORTANT:
        # Import lazily to avoid circular import during
        # app.core.sources package initialization.
        from app.core.sources.job_source import (
            SourceAccessError,
        )

        start_url = (
            board_url.strip()
            if board_url
            else "https://in.indeed.com/"
        )

        page = self.browser.open(
            start_url
        )

        site = IndeedSite(page)

        site.search_jobs(
            keywords=keywords.strip(),
            location=location,
        )

        state = site.get_access_state()

        if state["blocked"]:
            self.last_diagnostic = {
                "source": "indeed",
                "status": "blocked",
                "jobs": 0,
                "error": state["message"],
                "code": state["code"],
                "requires_human_action": (
                    state[
                        "requires_human_action"
                    ]
                ),
                "url": site.get_current_url(),
            }

            raise SourceAccessError(
                state["message"],
                code=state["code"],
                requires_human_action=(
                    state[
                        "requires_human_action"
                    ]
                ),
            )

        jobs = self._normalize_discovered_jobs(
            site.get_job_listings()
        )

        jobs = self._filter_location(
            jobs,
            location,
        )

        self.last_diagnostic = {
            "source": "indeed",
            "status": (
                "ok"
                if jobs
                else "no_results"
            ),
            "jobs": len(jobs),
            "error": (
                None
                if jobs
                else (
                    "No publicly accessible "
                    "Indeed listings were extracted."
                )
            ),
            "code": (
                "ok"
                if jobs
                else "no_results"
            ),
            "requires_human_action": False,
            "url": site.get_current_url(),
        }

        return jobs

    def get_indeed_job_details(
        self,
        job_url: str,
    ) -> dict:
        self._validate_job_url(
            job_url
        )

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
                }
            )

        return normalized

    # ========================================================
    # LOCATION FILTER
    # ========================================================

    @staticmethod
    def _filter_location(
        jobs: list[dict],
        location: Optional[str],
    ) -> list[dict]:
        if not location or not location.strip():
            return jobs

        requested = location.strip().lower()

        filtered: list[dict] = []

        for job in jobs:
            job_location = str(
                job.get(
                    "location",
                    "",
                )
                or ""
            ).strip().lower()

            # Preserve jobs where the source did not provide
            # a location. This avoids throwing away potentially
            # useful public listings with incomplete metadata.
            if not job_location:
                filtered.append(job)
                continue

            if requested in job_location:
                filtered.append(job)

        return filtered