from __future__ import annotations

from typing import Optional

from app.browser.browser_manager import BrowserManager
from app.browser.job_discovery import JobDiscovery
from app.core.job_parser import parse_job


class JobPipeline:
    """
    Connects browser-based job discovery with the
    JobAgent parsing and matching pipeline.

    Flow:

        Job Discovery
            ↓
        Normalize
            ↓
        Parse Job
            ↓
        Required / Preferred Skills
            ↓
        Resume Selection

    Does NOT apply to jobs.
    """

    def __init__(
        self,
        browser: BrowserManager,
    ):
        if browser is None:
            raise ValueError(
                "JobPipeline requires a browser."
            )

        self.browser = browser
        self.discovery = JobDiscovery(
            browser
        )

    # ========================================================
    # GREENHOUSE DISCOVERY
    # ========================================================

    def discover_greenhouse_jobs(
        self,
        board_url: str,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:
        """
        Discover, normalize and parse Greenhouse jobs.
        """

        if not board_url or not board_url.strip():
            raise ValueError(
                "Greenhouse board URL cannot be empty."
            )

        if not keywords or not keywords.strip():
            raise ValueError(
                "Greenhouse keywords cannot be empty."
            )

        jobs = self.discovery.discover_greenhouse(
            board_url=board_url.strip(),
            keywords=keywords.strip(),
            location=location,
        )

        return self._normalize_jobs(
            jobs
        )

    # ========================================================
    # NORMALIZATION + PARSING
    # ========================================================

    @staticmethod
    def _normalize_jobs(
        jobs: Optional[list[dict]],
    ) -> list[dict]:
        """
        Normalize discovered jobs and enrich them
        using the job parser.

        The pipeline guarantees the common fields required
        by downstream matching and resume selection.
        """

        if not jobs:
            return []

        normalized: list[dict] = []

        for job in jobs:
            if not isinstance(
                job,
                dict,
            ):
                continue

            # ------------------------------------------------
            # Basic normalized fields
            # ------------------------------------------------

            title = str(
                job.get(
                    "title",
                    "",
                )
                or ""
            ).strip()

            company = str(
                job.get(
                    "company",
                    "",
                )
                or ""
            ).strip()

            location = str(
                job.get(
                    "location",
                    "",
                )
                or ""
            ).strip()

            url = str(
                job.get(
                    "url",
                    "",
                )
                or ""
            ).strip()

            description = str(
                job.get(
                    "description",
                    "",
                )
                or ""
            ).strip()

            normalized_job = {
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "description": description,
            }

            # ------------------------------------------------
            # Preserve source/parser fields
            # ------------------------------------------------

            if "job_title" in job:
                normalized_job["job_title"] = (
                    str(
                        job.get(
                            "job_title",
                            "",
                        )
                        or ""
                    ).strip()
                )

            if "summary" in job:
                normalized_job["summary"] = (
                    str(
                        job.get(
                            "summary",
                            "",
                        )
                        or ""
                    ).strip()
                )

            if "required_skills" in job:
                normalized_job[
                    "required_skills"
                ] = job.get(
                    "required_skills"
                )

            if "preferred_skills" in job:
                normalized_job[
                    "preferred_skills"
                ] = job.get(
                    "preferred_skills"
                )

            if "all_keywords" in job:
                normalized_job[
                    "all_keywords"
                ] = job.get(
                    "all_keywords"
                )

            if "experience_requirements" in job:
                normalized_job[
                    "experience_requirements"
                ] = job.get(
                    "experience_requirements"
                )

            # ------------------------------------------------
            # Parse job
            # ------------------------------------------------

            parsed_job = parse_job(
                normalized_job
            )

            if not isinstance(
                parsed_job,
                dict,
            ):
                parsed_job = {}

            # ------------------------------------------------
            # Merge parser result
            # ------------------------------------------------

            result = {
                **normalized_job,
                **parsed_job,
            }

            # ------------------------------------------------
            # Guaranteed compatibility fields
            # ------------------------------------------------

            result["title"] = title
            result["company"] = company
            result["location"] = location
            result["url"] = url
            result["description"] = description

            # job_title must always exist.
            result["job_title"] = (
                str(
                    result.get(
                        "job_title",
                        "",
                    )
                    or title
                ).strip()
                or title
            )

            # summary must always exist.
            result["summary"] = (
                str(
                    result.get(
                        "summary",
                        "",
                    )
                    or description
                ).strip()
            )

            # These fields are required by the
            # resume-selection/matching layer.
            required_skills = result.get(
                "required_skills",
                [],
            )

            preferred_skills = result.get(
                "preferred_skills",
                [],
            )

            all_keywords = result.get(
                "all_keywords",
                [],
            )

            experience_requirements = (
                result.get(
                    "experience_requirements",
                    "",
                )
            )

            if not isinstance(
                required_skills,
                list,
            ):
                if required_skills:
                    required_skills = [
                        str(
                            required_skills
                        ).strip()
                    ]
                else:
                    required_skills = []

            if not isinstance(
                preferred_skills,
                list,
            ):
                if preferred_skills:
                    preferred_skills = [
                        str(
                            preferred_skills
                        ).strip()
                    ]
                else:
                    preferred_skills = []

            if not isinstance(
                all_keywords,
                list,
            ):
                if all_keywords:
                    all_keywords = [
                        str(
                            all_keywords
                        ).strip()
                    ]
                else:
                    all_keywords = []

            result["required_skills"] = (
                required_skills
            )

            result["preferred_skills"] = (
                preferred_skills
            )

            result["all_keywords"] = (
                all_keywords
            )

            result["experience_requirements"] = (
                str(
                    experience_requirements
                    or ""
                ).strip()
            )

            normalized.append(
                result
            )

        return normalized


__all__ = [
    "JobPipeline",
]