from typing import Optional

from app.browser.browser_manager import BrowserManager
from app.core.job_pipeline import JobPipeline
from app.core.matcher import match_job
from app.resume.resume_manager import ResumeManager


class JobMatchPipeline:
    """
    Complete discovery + resume matching pipeline.

    Flow:

        Greenhouse
            ↓
        Job Discovery
            ↓
        Normalize jobs
            ↓
        Match against resumes
            ↓
        Ranked results

    Does NOT apply to jobs.
    """

    def __init__(
        self,
        browser: BrowserManager,
        resume_manager: ResumeManager,
    ):
        self.browser = browser
        self.resume_manager = resume_manager
        self.job_pipeline = JobPipeline(browser)

    # ========================================================
    # DISCOVER + MATCH
    # ========================================================

    def discover_and_match_greenhouse(
        self,
        board_url: str,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:
        """
        Discover Greenhouse jobs and match every job
        against every available resume.
        """

        jobs = self.job_pipeline.discover_greenhouse_jobs(
            board_url=board_url,
            keywords=keywords,
            location=location,
        )

        resumes = self.resume_manager.load_all_resumes()

        results = []

        for job in jobs:

            parsed_job = self._prepare_job_for_matching(
                job
            )

            best_match = None

            for resume in resumes:

                match_result = match_job(
                    resume=resume,
                    job=parsed_job,
                )

                result = {
                    "job": job,
                    "resume": {
                        "filename": resume.get(
                            "_filename",
                            "",
                        ),
                        "name": resume.get(
                            "name",
                            "",
                        ),
                    },
                    "match": match_result,
                }

                if (
                    best_match is None
                    or match_result["match_score"]
                    > best_match["match"]["match_score"]
                ):
                    best_match = result

            if best_match is not None:
                results.append(best_match)

        return self._sort_results(results)

    # ========================================================
    # JOB PREPARATION
    # ========================================================

    @staticmethod
    def _prepare_job_for_matching(
        job: dict,
    ) -> dict:
        """
        Convert a discovered job into the structure expected
        by the existing matcher.

        The current matcher expects:
        - required_skills
        - preferred_skills
        - experience_requirements
        """

        return {
            "title": job.get(
                "title",
                "",
            ),
            "company": job.get(
                "company",
                "",
            ),
            "location": job.get(
                "location",
                "",
            ),
            "url": job.get(
                "url",
                "",
            ),
            "description": job.get(
                "description",
                "",
            ),

            # These will be populated when the job parser
            # is connected to this pipeline.
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

    # ========================================================
    # SORT
    # ========================================================

    @staticmethod
    def _sort_results(
        results: list[dict],
    ) -> list[dict]:
        """
        Put the strongest job/resume matches first.
        """

        return sorted(
            results,
            key=lambda item: item["match"]["match_score"],
            reverse=True,
        )