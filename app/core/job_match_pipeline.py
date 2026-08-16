from __future__ import annotations

from typing import Optional

from app.browser.browser_manager import BrowserManager
from app.core.job_pipeline import JobPipeline
from app.core.matcher import match_job
from app.core.resume_selector import select_best_resume
from app.resume.resume_manager import ResumeManager


class JobMatchPipeline:
    """
    Complete job discovery + resume selection pipeline.

    Flow:

        Job Source
            ↓
        Job Discovery
            ↓
        Normalize
            ↓
        Resume Selection Engine
            ↓
        Best Resume + Match Diagnostics

    Does NOT apply to jobs.
    """

    def __init__(
        self,
        browser: BrowserManager,
        resume_manager: ResumeManager,
    ):
        if browser is None:
            raise ValueError(
                "JobMatchPipeline requires a browser."
            )

        if resume_manager is None:
            raise ValueError(
                "JobMatchPipeline requires a resume manager."
            )

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
        Backward-compatible Greenhouse discovery + matching.
        """

        jobs = self.job_pipeline.discover_greenhouse_jobs(
            board_url=board_url,
            keywords=keywords,
            location=location,
        )

        return self.match_jobs(jobs)

    # ========================================================
    # MATCH JOBS
    # ========================================================

    def match_jobs(
        self,
        jobs: Optional[list[dict]],
    ) -> list[dict]:
        """
        Match discovered jobs against all available resumes.

        Uses the resume selection engine and preserves the
        legacy match_score/eligible/recommendation fields.
        """

        if not jobs:
            return []

        resumes = self.resume_manager.load_all_resumes()

        if not resumes:
            return []

        results: list[dict] = []

        for job in jobs:

            if not isinstance(job, dict):
                continue

            prepared_job = (
                self._prepare_job_for_matching(
                    job
                )
            )

            try:
                selection = select_best_resume(
                    resumes=resumes,
                    job=prepared_job,
                )
            except (
                ValueError,
                TypeError,
                KeyError,
            ):
                continue

            if not isinstance(selection, dict):
                continue

            selected_resume = selection.get(
                "selected_resume"
            )

            if not isinstance(
                selected_resume,
                dict,
            ):
                continue

            match = self._build_compatible_match_result(
                selection
            )

            results.append(
                {
                    "job": job,

                    "resume": {
                        "filename": selection.get(
                            "selected_filename",
                            "",
                        ),
                        "name": selected_resume.get(
                            "name",
                            "",
                        ),
                    },

                    "match": match,
                }
            )

        return self._sort_results(results)

    # ========================================================
    # COMPATIBILITY MATCH RESULT
    # ========================================================

    @staticmethod
    def _build_compatible_match_result(
        selection: dict,
    ) -> dict:
        """
        Convert the resume-selector result into the existing
        JobMatchPipeline match-result format.
        """

        # ----------------------------------------------------
        # If the selector already provides the legacy fields,
        # preserve them.
        # ----------------------------------------------------

        result = dict(selection)

        if (
            "match_score" in result
            and "eligible" in result
            and "recommendation" in result
        ):
            return result

        # ----------------------------------------------------
        # Extract skill counts from the selector.
        # ----------------------------------------------------

        required_count = int(
            result.get(
                "required_skill_count",
                0,
            )
            or 0
        )

        matched_required_count = int(
            result.get(
                "matched_required_count",
                0,
            )
            or 0
        )

        preferred_count = int(
            result.get(
                "preferred_skill_count",
                0,
            )
            or 0
        )

        matched_preferred_count = int(
            result.get(
                "matched_preferred_count",
                0,
            )
            or 0
        )

        # ----------------------------------------------------
        # Calculate compatible match score.
        # ----------------------------------------------------

        if required_count:
            required_score = (
                matched_required_count
                / required_count
            )
        else:
            required_score = 1.0

        if preferred_count:
            preferred_score = (
                matched_preferred_count
                / preferred_count
            )
        else:
            preferred_score = 1.0

        if required_count and preferred_count:
            score = (
                required_score * 0.75
                + preferred_score * 0.25
            ) * 100

        elif required_count:
            score = required_score * 100

        elif preferred_count:
            score = preferred_score * 100

        else:
            score = 0.0

        score = round(
            score,
            2,
        )

        # ----------------------------------------------------
        # Eligibility.
        # ----------------------------------------------------

        eligible = (
            matched_required_count
            == required_count
            if required_count
            else True
        )

        # ----------------------------------------------------
        # Recommendation.
        # ----------------------------------------------------

        if eligible:
            recommendation = "APPLY"
        elif score >= 60:
            recommendation = "CONSIDER"
        else:
            recommendation = "SKIP"

        result.update(
            {
                "match_score": score,
                "eligible": eligible,
                "recommendation": recommendation,
            }
        )

        return result

    # ========================================================
    # JOB PREPARATION
    # ========================================================

    @staticmethod
    def _prepare_job_for_matching(
        job: dict,
    ) -> dict:
        """
        Convert a discovered job into the structure expected
        by the resume selection engine.
        """

        if not isinstance(
            job,
            dict,
        ):
            return {}

        return {
            "title": str(
                job.get(
                    "title",
                    "",
                )
                or ""
            ).strip(),

            "job_title": str(
                job.get(
                    "job_title",
                    job.get(
                        "title",
                        "",
                    ),
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

            "summary": str(
                job.get(
                    "summary",
                    "",
                )
                or ""
            ).strip(),

            "required_skills": job.get(
                "required_skills",
                [],
            ),

            "preferred_skills": job.get(
                "preferred_skills",
                [],
            ),

            "all_keywords": job.get(
                "all_keywords",
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
        Sort strongest matches first.

        Supports both the legacy match_score and the newer
        resume_score fields.
        """

        def score(item: dict) -> float:
            match = item.get(
                "match",
                {},
            )

            if not isinstance(
                match,
                dict,
            ):
                return 0.0

            value = match.get(
                "match_score"
            )

            if value is None:
                value = match.get(
                    "resume_score",
                    0,
                )

            try:
                return float(
                    value
                )
            except (
                TypeError,
                ValueError,
            ):
                return 0.0

        return sorted(
            results,
            key=score,
            reverse=True,
        )


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

__all__ = [
    "JobMatchPipeline",
    "match_job",
]