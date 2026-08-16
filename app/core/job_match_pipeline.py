from __future__ import annotations

from typing import Any, Optional

from app.browser.browser_manager import BrowserManager
from app.core.job_pipeline import JobPipeline
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
        Job Normalization / Parsing
            ↓
        Resume Selection Engine
            ↓
        Best Resume + Match Diagnostics

    Does NOT apply to jobs.

    The pipeline also preserves compatibility with the
    legacy matcher API through the module-level match_job()
    function defined below.
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
        self.job_pipeline = JobPipeline(
            browser
        )

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

        Discovers Greenhouse jobs and selects the best resume
        for each discovered job.
        """

        jobs = (
            self.job_pipeline
            .discover_greenhouse_jobs(
                board_url=board_url,
                keywords=keywords,
                location=location,
            )
        )

        return self.match_jobs(
            jobs
        )

    # ========================================================
    # MATCH JOBS
    # ========================================================

    def match_jobs(
        self,
        jobs: Optional[list[dict]],
    ) -> list[dict]:
        """
        Match a collection of discovered jobs against all
        available resumes.

        Returns one result per job containing:

            job
            resume
            match

        Jobs without available resumes are skipped.
        """

        if not jobs:
            return []

        resumes = (
            self.resume_manager
            .load_all_resumes()
        )

        if not resumes:
            return []

        results: list[dict] = []

        for job in jobs:

            if not isinstance(
                job,
                dict,
            ):
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

            if not isinstance(
                selection,
                dict,
            ):
                continue

            selected_resume = (
                selection.get(
                    "selected_resume"
                )
            )

            if not isinstance(
                selected_resume,
                dict,
            ):
                continue

            # ------------------------------------------------
            # Normalize the selector output so the rest of
            # JobAgent has a stable match-result structure.
            # ------------------------------------------------

            match_result = (
                self._ensure_match_compatibility(
                    selection
                )
            )

            results.append(
                {
                    "job": job,
                    "resume": {
                        "filename": selection.get(
                            "selected_filename",
                            selected_resume.get(
                                "_filename",
                                "",
                            ),
                        ),
                        "name": selected_resume.get(
                            "name",
                            "",
                        ),
                    },
                    "match": match_result,
                }
            )

        return self._sort_results(
            results
        )

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
    # MATCH RESULT COMPATIBILITY
    # ========================================================

    @staticmethod
    def _ensure_match_compatibility(
        selection: dict,
    ) -> dict:
        """
        Normalize the newer resume-selector result so that it
        remains compatible with the older JobAgent matcher API.

        Important compatibility fields:

            match_score
            resume_score
            eligible
            recommendation

        The resume selector may return a raw weighted score
        rather than a 0-100 percentage. We preserve that score
        exactly instead of artificially converting it.
        """

        result = dict(
            selection
        )

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        resume_score = result.get(
            "resume_score"
        )

        match_score = result.get(
            "match_score"
        )

        # The selector normally provides resume_score.
        # If match_score is missing, use resume_score.
        if (
            isinstance(
                resume_score,
                (int, float),
            )
            and not isinstance(
                resume_score,
                bool,
            )
        ):
            normalized_score = resume_score

        elif (
            isinstance(
                match_score,
                (int, float),
            )
            and not isinstance(
                match_score,
                bool,
            )
        ):
            normalized_score = match_score

        else:
            normalized_score = 0.0

        result["resume_score"] = (
            normalized_score
        )

        result["match_score"] = (
            normalized_score
        )

        # ----------------------------------------------------
        # REQUIRED SKILL INFORMATION
        # ----------------------------------------------------

        missing_required = result.get(
            "missing_required_skills",
            [],
        )

        matched_required = result.get(
            "matched_required_skills",
            [],
        )

        if not isinstance(
            missing_required,
            list,
        ):
            missing_required = []

        if not isinstance(
            matched_required,
            list,
        ):
            matched_required = []

        result[
            "missing_required_skills"
        ] = missing_required

        result[
            "matched_required_skills"
        ] = matched_required

        # ----------------------------------------------------
        # ELIGIBILITY
        # ----------------------------------------------------

        if "eligible" in result:
            eligible = bool(
                result["eligible"]
            )
        else:
            # A job is eligible when there are no explicitly
            # missing required skills.
            eligible = (
                len(missing_required)
                == 0
            )

        result["eligible"] = (
            eligible
        )

        # ----------------------------------------------------
        # PREFERRED SKILLS
        # ----------------------------------------------------

        matched_preferred = result.get(
            "matched_preferred_skills",
            [],
        )

        missing_preferred = result.get(
            "missing_preferred_skills",
            [],
        )

        if not isinstance(
            matched_preferred,
            list,
        ):
            matched_preferred = []

        if not isinstance(
            missing_preferred,
            list,
        ):
            missing_preferred = []

        result[
            "matched_preferred_skills"
        ] = matched_preferred

        result[
            "missing_preferred_skills"
        ] = missing_preferred

        # ----------------------------------------------------
        # RECOMMENDATION
        # ----------------------------------------------------

        if eligible:
            recommendation = "APPLY"

        elif normalized_score >= 60:
            recommendation = "CONSIDER"

        else:
            recommendation = "SKIP"

        result[
            "recommendation"
        ] = recommendation

        # ----------------------------------------------------
        # EXPERIENCE
        # ----------------------------------------------------

        result.setdefault(
            "experience_requirements",
            "",
        )

        # ----------------------------------------------------
        # RESUME KEYWORDS
        # ----------------------------------------------------

        resume_keywords = result.get(
            "resume_keywords",
            [],
        )

        if not isinstance(
            resume_keywords,
            list,
        ):
            resume_keywords = []

        result[
            "resume_keywords"
        ] = resume_keywords

        return result

    # ========================================================
    # SORT
    # ========================================================

    @staticmethod
    def _sort_results(
        results: list[dict],
    ) -> list[dict]:
        """
        Sort jobs by resume-selection score.

        The selector uses resume_score as its primary score.
        match_score is maintained as a compatibility alias.
        """

        def score(
            item: dict,
        ) -> float:

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
                "resume_score",
                match.get(
                    "match_score",
                    0,
                ),
            )

            if isinstance(
                value,
                (int, float),
            ) and not isinstance(
                value,
                bool,
            ):
                return float(
                    value
                )

            return 0.0

        return sorted(
            results,
            key=score,
            reverse=True,
        )


# ============================================================
# LEGACY MATCHER COMPATIBILITY API
# ============================================================

def match_job(
    resume: dict,
    job: dict,
) -> dict:
    """
    Backward-compatible single-resume matcher.

    Older parts of JobAgent, including JobProcessor, import
    match_job directly from this module.

    The current implementation delegates to the same
    resume-selection engine used by JobMatchPipeline.

    Args:
        resume:
            A single resume dictionary.

        job:
            A normalized or parsed job dictionary.

    Returns:
        A match-result dictionary containing the legacy
        compatibility fields.
    """

    if not isinstance(
        resume,
        dict,
    ):
        raise TypeError(
            "resume must be a dictionary."
        )

    if not isinstance(
        job,
        dict,
    ):
        raise TypeError(
            "job must be a dictionary."
        )

    if not job:
        raise ValueError(
            "job cannot be empty."
        )

    prepared_job = (
        JobMatchPipeline
        ._prepare_job_for_matching(
            job
        )
    )

    try:
        selection = select_best_resume(
            resumes=[resume],
            job=prepared_job,
        )

    except (
        ValueError,
        TypeError,
        KeyError,
    ):
        # Preserve a predictable legacy result instead
        # of leaking selector-specific exceptions.
        return {
            "match_score": 0.0,
            "resume_score": 0.0,
            "eligible": False,
            "recommendation": "SKIP",
            "matched_required_skills": [],
            "missing_required_skills": [],
            "matched_preferred_skills": [],
            "missing_preferred_skills": [],
            "experience_requirements": prepared_job.get(
                "experience_requirements",
                "",
            ),
            "resume_keywords": [],
        }

    if not isinstance(
        selection,
        dict,
    ):
        return {
            "match_score": 0.0,
            "resume_score": 0.0,
            "eligible": False,
            "recommendation": "SKIP",
            "matched_required_skills": [],
            "missing_required_skills": [],
            "matched_preferred_skills": [],
            "missing_preferred_skills": [],
            "experience_requirements": prepared_job.get(
                "experience_requirements",
                "",
            ),
            "resume_keywords": [],
        }

    return (
        JobMatchPipeline
        ._ensure_match_compatibility(
            selection
        )
    )


# ============================================================
# PUBLIC API
# ============================================================

__all__ = [
    "JobMatchPipeline",
    "match_job",
]