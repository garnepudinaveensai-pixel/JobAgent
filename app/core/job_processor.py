from typing import Optional

from app.core.job_match_pipeline import match_job
from app.core.job_pipeline import JobPipeline
from app.browser.browser_manager import BrowserManager


class JobProcessor:
    """
    Connects job discovery with resume/job matching.

    Flow:
        Greenhouse
            ↓
        JobPipeline
            ↓
        Discovered jobs
            ↓
        match_job()
            ↓
        Match results
    """

    def __init__(
        self,
        browser: BrowserManager,
        resume: dict,
    ):
        self.browser = browser
        self.resume = resume
        self.pipeline = JobPipeline(browser)

    # ========================================================
    # PROCESS GREENHOUSE JOBS
    # ========================================================

    def process_greenhouse_jobs(
        self,
        board_url: str,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:
        """
        Discover Greenhouse jobs and calculate their
        compatibility with the selected resume.
        """

        jobs = self.pipeline.discover_greenhouse_jobs(
            board_url=board_url,
            keywords=keywords,
            location=location,
        )

        results = []

        for job in jobs:

            # ------------------------------------------------
            # Build job text for matching
            # ------------------------------------------------

            job_text = " ".join(
                [
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    job.get("description", ""),
                ]
            )

            # ------------------------------------------------
            # Create matching input
            # ------------------------------------------------

            matching_job = {
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "url": job.get("url", ""),
                "description": job.get(
                    "description",
                    "",
                ),
                "required_skills": job.get(
                    "required_skills",
                    [],
                ),
                "preferred_skills": job.get(
                    "preferred_skills",
                    [],
                ),
                "experience_requirements": job.get(
                    "experience_requirements",
                    "",
                ),
            }

            # ------------------------------------------------
            # If structured skills aren't available,
            # preserve the complete description.
            # ------------------------------------------------

            if not matching_job["description"]:
                matching_job["description"] = job_text

            # ------------------------------------------------
            # Match resume against job
            # ------------------------------------------------

            match_result = match_job(
                self.resume,
                matching_job,
            )

            # ------------------------------------------------
            # Combine discovery + matching
            # ------------------------------------------------

            results.append(
                {
                    **job,
                    "match": match_result,
                }
            )

        return results

    # ========================================================
    # FILTER
    # ========================================================

    @staticmethod
    def filter_jobs(
        results: list[dict],
        recommendation: Optional[str] = None,
        minimum_score: Optional[float] = None,
    ) -> list[dict]:
        """
        Filter processed jobs by recommendation and/or
        minimum match score.
        """

        filtered = []

        for result in results:

            if not isinstance(result, dict):
                continue

            match = result.get("match", {})

            if not isinstance(match, dict):
                continue

            if (
                recommendation is not None
                and match.get("recommendation")
                != recommendation
            ):
                continue

            if minimum_score is not None:

                score = match.get(
                    "match_score",
                    0,
                )

                if score < minimum_score:
                    continue

            filtered.append(result)

        return filtered

    # ========================================================
    # SORT
    # ========================================================

    @staticmethod
    def sort_by_match_score(
        results: list[dict],
    ) -> list[dict]:
        """
        Return jobs sorted from highest to lowest
        match score.
        """

        return sorted(
            results,
            key=lambda result: result.get(
                "match",
                {},
            ).get(
                "match_score",
                0,
            ),
            reverse=True,
        )