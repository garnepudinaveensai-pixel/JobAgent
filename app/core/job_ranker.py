from __future__ import annotations

from typing import Any, Optional


class JobRanker:
    """
    Rank matched jobs using a transparent scoring model.

    This class does NOT discover jobs.
    This class does NOT select resumes.
    This class does NOT apply to jobs.

    It operates on the output produced by JobMatchPipeline.

    Expected input format:

        {
            "job": {...},
            "resume": {...},
            "match": {...},
        }

    Ranking considers:

        1. Resume match score
        2. Required-skill coverage
        3. Preferred-skill coverage
        4. Job-title relevance
        5. Experience suitability
        6. Location relevance

    The final ranking score is normalized to 0-100.
    """

    # ========================================================
    # WEIGHTS
    # ========================================================

    RESUME_WEIGHT = 40.0
    REQUIRED_SKILLS_WEIGHT = 25.0
    PREFERRED_SKILLS_WEIGHT = 10.0
    TITLE_WEIGHT = 10.0
    EXPERIENCE_WEIGHT = 10.0
    LOCATION_WEIGHT = 5.0

    TOTAL_WEIGHT = (
        RESUME_WEIGHT
        + REQUIRED_SKILLS_WEIGHT
        + PREFERRED_SKILLS_WEIGHT
        + TITLE_WEIGHT
        + EXPERIENCE_WEIGHT
        + LOCATION_WEIGHT
    )

    # ========================================================
    # PUBLIC API
    # ========================================================

    @classmethod
    def rank(
        cls,
        results: Optional[list[dict]],
    ) -> list[dict]:
        """
        Rank matched job results from highest to lowest.

        Invalid entries are ignored.

        Each returned result receives:

            ranking_score
            ranking_breakdown

        Existing fields are preserved.
        """

        if not results:
            return []

        ranked: list[dict] = []

        for result in results:
            if not isinstance(result, dict):
                continue

            job = result.get("job")

            if not isinstance(job, dict):
                continue

            match = result.get("match")

            if not isinstance(match, dict):
                match = {}

            ranked_result = dict(result)

            breakdown = cls._calculate_breakdown(
                job=job,
                match=match,
            )

            ranked_result["ranking_score"] = (
                breakdown["total"]
            )

            ranked_result["ranking_breakdown"] = (
                breakdown
            )

            ranked.append(
                ranked_result
            )

        return sorted(
            ranked,
            key=cls._sort_key,
            reverse=True,
        )

    @classmethod
    def filter_and_rank(
        cls,
        results: Optional[list[dict]],
        *,
        min_score: float = 0.0,
        eligible_only: bool = False,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """
        Filter and rank matched jobs.

        Args:
            results:
                Results from JobMatchPipeline.

            min_score:
                Minimum ranking score from 0-100.

            eligible_only:
                When True, only results explicitly marked
                eligible=True are returned.

            limit:
                Optional maximum number of results.

        Returns:
            Ranked and filtered results.
        """

        if min_score < 0:
            raise ValueError(
                "min_score cannot be negative."
            )

        if min_score > 100:
            raise ValueError(
                "min_score cannot exceed 100."
            )

        ranked = cls.rank(results)

        filtered: list[dict] = []

        for result in ranked:

            score = result.get(
                "ranking_score",
                0.0,
            )

            if score < min_score:
                continue

            if eligible_only:
                match = result.get(
                    "match",
                    {},
                )

                if not isinstance(
                    match,
                    dict,
                ):
                    continue

                if match.get(
                    "eligible"
                ) is not True:
                    continue

            filtered.append(result)

        if limit is not None:
            if limit < 0:
                raise ValueError(
                    "limit cannot be negative."
                )

            filtered = filtered[:limit]

        return filtered

    # ========================================================
    # SCORE CALCULATION
    # ========================================================

    @classmethod
    def _calculate_breakdown(
        cls,
        job: dict,
        match: dict,
    ) -> dict:
        """
        Calculate all ranking components.
        """

        resume_score = cls._normalized_resume_score(
            match
        )

        required_score = (
            cls._required_skill_score(
                job,
                match,
            )
        )

        preferred_score = (
            cls._preferred_skill_score(
                job,
                match,
            )
        )

        title_score = cls._title_score(
            job
        )

        experience_score = (
            cls._experience_score(
                job,
                match,
            )
        )

        location_score = cls._location_score(
            job
        )

        total = (
            resume_score * cls.RESUME_WEIGHT
            + required_score
            * cls.REQUIRED_SKILLS_WEIGHT
            + preferred_score
            * cls.PREFERRED_SKILLS_WEIGHT
            + title_score
            * cls.TITLE_WEIGHT
            + experience_score
            * cls.EXPERIENCE_WEIGHT
            + location_score
            * cls.LOCATION_WEIGHT
        ) / cls.TOTAL_WEIGHT

        return {
            "resume": round(
                resume_score,
                2,
            ),
            "required_skills": round(
                required_score,
                2,
            ),
            "preferred_skills": round(
                preferred_score,
                2,
            ),
            "title": round(
                title_score,
                2,
            ),
            "experience": round(
                experience_score,
                2,
            ),
            "location": round(
                location_score,
                2,
            ),
            "total": round(
                max(
                    0.0,
                    min(
                        100.0,
                        total,
                    ),
                ),
                2,
            ),
        }

    # ========================================================
    # RESUME SCORE
    # ========================================================

    @staticmethod
    def _normalized_resume_score(
        match: dict,
    ) -> float:
        """
        Convert the selector's raw score into 0-100.

        The selector's score is intentionally treated as
        an internal weighted score.

        If the selector already provides a normalized
        resume_match_percentage, that value is preferred.
        """

        percentage = match.get(
            "resume_match_percentage"
        )

        if isinstance(
            percentage,
            (int, float),
        ):
            return max(
                0.0,
                min(
                    100.0,
                    float(
                        percentage
                    ),
                ),
            )

        score = match.get(
            "resume_score",
            match.get(
                "match_score",
                0,
            ),
        )

        if not isinstance(
            score,
            (int, float),
        ):
            return 0.0

        score = float(score)

        if score <= 0:
            return 0.0

        # Existing selector scores are raw weighted
        # values. Convert them using a smooth saturation
        # curve rather than assuming they are percentages.
        normalized = (
            100.0
            * score
            / (
                score
                + 100.0
            )
        )

        return max(
            0.0,
            min(
                100.0,
                normalized,
            ),
        )

    # ========================================================
    # REQUIRED SKILLS
    # ========================================================

    @classmethod
    def _required_skill_score(
        cls,
        job: dict,
        match: dict,
    ) -> float:
        """
        Estimate required-skill coverage.
        """

        required = cls._as_string_list(
            job.get(
                "required_skills",
                [],
            )
        )

        if not required:
            return 100.0

        matched = cls._extract_matched_skills(
            match,
            "required",
        )

        if matched:
            return cls._coverage(
                required,
                matched,
            )

        return cls._resume_skill_coverage(
            job,
            match,
            required,
        )

    # ========================================================
    # PREFERRED SKILLS
    # ========================================================

    @classmethod
    def _preferred_skill_score(
        cls,
        job: dict,
        match: dict,
    ) -> float:
        """
        Estimate preferred-skill coverage.
        """

        preferred = cls._as_string_list(
            job.get(
                "preferred_skills",
                [],
            )
        )

        if not preferred:
            return 100.0

        matched = cls._extract_matched_skills(
            match,
            "preferred",
        )

        if matched:
            return cls._coverage(
                preferred,
                matched,
            )

        return cls._resume_skill_coverage(
            job,
            match,
            preferred,
        )

    # ========================================================
    # TITLE
    # ========================================================

    @staticmethod
    def _title_score(
        job: dict,
    ) -> float:
        """
        Estimate relevance between the job title and
        parsed keywords.
        """

        title = str(
            job.get(
                "job_title",
                job.get(
                    "title",
                    "",
                ),
            )
            or ""
        ).strip().lower()

        if not title:
            return 0.0

        keywords = JobRanker._as_string_list(
            job.get(
                "all_keywords",
                [],
            )
        )

        if not keywords:
            return 50.0

        title_words = set(
            title.replace(
                "/",
                " ",
            ).split()
        )

        keyword_words = set()

        for keyword in keywords:
            keyword_words.update(
                str(keyword)
                .lower()
                .replace(
                    "/",
                    " ",
                )
                .split()
            )

        if not keyword_words:
            return 50.0

        overlap = (
            len(
                title_words
                & keyword_words
            )
            / len(keyword_words)
        )

        return max(
            0.0,
            min(
                100.0,
                overlap * 100.0,
            ),
        )

    # ========================================================
    # EXPERIENCE
    # ========================================================

    @staticmethod
    def _experience_score(
        job: dict,
        match: dict,
    ) -> float:
        """
        Estimate experience suitability.

        Fresher / entry-level jobs receive a strong score
        because the matching system targets early-career
        opportunities.

        Explicit incompatibility lowers the score.
        """

        requirement = str(
            job.get(
                "experience_requirements",
                "",
            )
            or ""
        ).strip().lower()

        if not requirement:
            return 75.0

        if any(
            phrase in requirement
            for phrase in (
                "fresher",
                "fresh graduate",
                "graduate",
                "entry level",
                "entry-level",
                "0 year",
                "0-1 year",
            )
        ):
            return 100.0

        if any(
            phrase in requirement
            for phrase in (
                "intern",
                "internship",
                "trainee",
            )
        ):
            return 95.0

        # If the matcher has explicitly marked the job
        # eligible, treat that as useful evidence.
        if match.get(
            "eligible"
        ) is True:
            return 80.0

        return 60.0

    # ========================================================
    # LOCATION
    # ========================================================

    @staticmethod
    def _location_score(
        job: dict,
    ) -> float:
        """
        Estimate location quality.

        Without a configured user-location preference,
        location cannot be judged precisely.

        Therefore:
            non-empty location = 100
            unknown location    = 50
        """

        location = str(
            job.get(
                "location",
                "",
            )
            or ""
        ).strip()

        if not location:
            return 50.0

        return 100.0

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _sort_key(
        result: dict,
    ) -> tuple:
        score = result.get(
            "ranking_score",
            0.0,
        )

        if not isinstance(
            score,
            (int, float),
        ):
            score = 0.0

        match = result.get(
            "match",
            {},
        )

        if not isinstance(
            match,
            dict,
        ):
            match = {}

        resume_score = match.get(
            "resume_score",
            match.get(
                "match_score",
                0,
            ),
        )

        if not isinstance(
            resume_score,
            (int, float),
        ):
            resume_score = 0

        return (
            float(score),
            float(resume_score),
        )

    @staticmethod
    def _as_string_list(
        value: Any,
    ) -> list[str]:
        if not isinstance(
            value,
            (list, tuple, set),
        ):
            return []

        result: list[str] = []

        for item in value:
            text = str(
                item or ""
            ).strip()

            if text:
                result.append(text)

        return result

    @staticmethod
    def _extract_matched_skills(
        match: dict,
        category: str,
    ) -> list[str]:
        """
        Support several possible selector result names.
        """

        candidates = [
            f"matched_{category}_skills",
            f"{category}_skills_matched",
        ]

        for key in candidates:
            value = match.get(key)

            if isinstance(
                value,
                (list, tuple, set),
            ):
                return JobRanker._as_string_list(
                    value
                )

        return []

    @classmethod
    def _resume_skill_coverage(
        cls,
        job: dict,
        match: dict,
        skills: list[str],
    ) -> float:
        """
        Estimate skill coverage using the selected resume
        when explicit matched-skill information is unavailable.
        """

        resume = match.get(
            "selected_resume"
        )

        if not isinstance(
            resume,
            dict,
        ):
            return 0.0

        resume_skills = cls._as_string_list(
            resume.get(
                "skills",
                [],
            )
        )

        if not resume_skills:
            return 0.0

        return cls._coverage(
            skills,
            resume_skills,
        )

    @staticmethod
    def _coverage(
        required: list[str],
        available: list[str],
    ) -> float:
        if not required:
            return 100.0

        available_normalized = {
            str(item).strip().lower()
            for item in available
        }

        matched = 0

        for requirement in required:
            normalized = (
                str(requirement)
                .strip()
                .lower()
            )

            if not normalized:
                continue

            if normalized in available_normalized:
                matched += 1
                continue

            # Allow simple substring matching for
            # related skill labels.
            if any(
                normalized in item
                or item in normalized
                for item in available_normalized
            ):
                matched += 1

        return (
            matched
            / len(required)
            * 100.0
        )


__all__ = [
    "JobRanker",
]