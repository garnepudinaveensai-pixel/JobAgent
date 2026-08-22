from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from urllib.parse import urlparse

from app.agents.agent_brain import LocalAgentBrain


class JobIntelligence:
    """
    Explainable AI-style job reasoning layer.

    Responsibilities:

        job observation
            ↓
        role classification
            ↓
        contradiction detection
            ↓
        freshness analysis
            ↓
        urgency analysis
            ↓
        application-route detection
            ↓
        match/eligibility analysis
            ↓
        priority calculation
            ↓
        APPLY / REVIEW / SKIP
    """

    EXCLUDED_TITLE_TERMS = (
        LocalAgentBrain.NEGATIVE_TITLE
    )

    TARGET_TITLE_TERMS = tuple(
        signal
        for signals in (
            LocalAgentBrain.ROLE_SIGNALS.values()
        )
        for signal in signals
    )

    URGENCY_TERMS = (
        "urgent hiring",
        "urgent requirement",
        "urgently hiring",
        "immediate hiring",
        "immediate joiner",
        "immediate joining",
        "join immediately",
        "walk-in",
        "walk in",
        "actively hiring",
        "hiring now",
        "join asap",
        "asap",
    )

    FRESHNESS_PATTERNS = (
        (
            re.compile(
                r"\btoday\b|"
                r"\bjust posted\b|"
                r"\bjust now\b",
                re.I,
            ),
            100,
        ),
        (
            re.compile(
                r"\b1\s*day\s*ago\b|"
                r"\byesterday\b",
                re.I,
            ),
            90,
        ),
        (
            re.compile(
                r"\b[2-3]\s*days?\s*ago\b",
                re.I,
            ),
            80,
        ),
        (
            re.compile(
                r"\b[4-7]\s*days?\s*ago\b",
                re.I,
            ),
            65,
        ),
        (
            re.compile(
                r"\b[1-2]\s*weeks?\s*ago\b",
                re.I,
            ),
            45,
        ),
        (
            re.compile(
                r"\b[3-4]\s*weeks?\s*ago\b",
                re.I,
            ),
            25,
        ),
        (
            re.compile(
                r"\b\d+\s*months?\s*ago\b",
                re.I,
            ),
            5,
        ),
    )

    @classmethod
    def analyze(
        cls,
        job: Mapping[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(
            job,
            Mapping,
        ):
            raise TypeError(
                "job must be a mapping."
            )

        title = cls._text(
            job.get("title")
            or job.get("job_title")
        )

        description = cls._text(
            job.get("description")
        )

        company = cls._text(
            job.get("company")
        )

        url = cls._text(
            job.get("url")
        )

        combined = (
            f"{title} {description}"
        )

        brain = (
            LocalAgentBrain.classify_job(
                job
            )
        )

        freshness = cls._freshness_score(
            combined,
            job,
        )

        urgency = cls._urgency_score(
            combined.lower()
        )

        route = cls._application_route(
            url,
            job,
        )

        # --------------------------------------------------------
        # Match information
        # --------------------------------------------------------

        match = job.get("match")

        match_available = isinstance(
            match,
            Mapping,
        )

        if not match_available:
            match = {}

        eligible_value = match.get(
            "eligible"
        )

        if eligible_value is True:
            eligibility_score = 100.0
        elif eligible_value is None:
            # Unknown eligibility is not the same as
            # ineligible. Keep it reviewable.
            eligibility_score = 55.0
        else:
            eligibility_score = 0.0

        raw_match_score = match.get(
            "match_score",
            match.get(
                "resume_score",
                None,
            ),
        )

        match_score: float | None

        if raw_match_score is None:
            match_score = None
        else:
            try:
                match_score = float(
                    raw_match_score
                )
            except (
                TypeError,
                ValueError,
            ):
                match_score = None

        # Priority calculation requires a numeric value.
        # Missing matching data contributes zero, but it does
        # NOT cause the job to be rejected.
        priority_match_score = (
            match_score
            if match_score is not None
            else 0.0
        )

        priority = (
            LocalAgentBrain.rank_priority(
                target=brain.target,
                freshness=freshness,
                urgency=urgency,
                match_score=priority_match_score,
                eligibility=eligibility_score,
            )
        )

        # --------------------------------------------------------
        # Reasoning
        # --------------------------------------------------------

        reasons = [
            brain.reason
        ]

        if freshness >= 80:
            reasons.append(
                "very recent"
            )
        elif freshness >= 45:
            reasons.append(
                "recent"
            )

        if urgency >= 40:
            reasons.append(
                "active/urgent hiring signal"
            )

        if match_available:
            if match_score is None:
                reasons.append(
                    "match data present but score unavailable"
                )
            else:
                reasons.append(
                    f"resume match={match_score:.1f}"
                )
        else:
            reasons.append(
                "resume match not evaluated yet"
            )

        if eligible_value is True:
            reasons.append(
                "eligibility confirmed"
            )
        elif eligible_value is None:
            reasons.append(
                "eligibility not yet confirmed"
            )
        else:
            reasons.append(
                "eligibility failed"
            )

        reasons.append(
            f"route={route}"
        )

        # --------------------------------------------------------
        # Action decision
        # --------------------------------------------------------

        # Closed/expired/duplicate jobs are always skipped.
        # Non-target roles are always skipped.
        # Missing match data goes to REVIEW.
        recommended_action = (
            LocalAgentBrain.choose_action(
                technical_target=brain.target,
                eligible=(
                    eligible_value is not False
                ),
                score=match_score,
                application_status=cls._text(
                    job.get("status")
                ),
                match_available=match_available,
            )
        )

        # --------------------------------------------------------
        # Result
        # --------------------------------------------------------

        return {
            "technical_target": (
                brain.target
            ),

            "role_class": (
                brain.intent
                if brain.target
                else (
                    "non_target"
                    if brain.intent
                    == "non_target"
                    else "uncertain"
                )
            ),

            "confidence": (
                brain.confidence
            ),

            "excluded_terms": list(
                brain.negative_signals
            ),

            "matched_target_terms": list(
                brain.matched_signals
            ),

            "freshness_score": (
                freshness
            ),

            "urgency_score": (
                urgency
            ),

            "priority_score": (
                priority
            ),

            "application_route": (
                route
            ),

            "match_available": (
                match_available
            ),

            "match_score": (
                match_score
            ),

            "eligibility": (
                eligible_value
            ),

            "priority_reason": (
                "; ".join(reasons)
            ),

            "recommended_action": (
                recommended_action
            ),

            "company": (
                company
            ),
        }

    # ============================================================
    # FRESHNESS
    # ============================================================

    @classmethod
    def _freshness_score(
        cls,
        text: str,
        job: Mapping[str, Any],
    ) -> int:

        explicit = cls._text(
            job.get("posted_date")
            or job.get("date_posted")
        )

        source_text = (
            f"{explicit} {text}"
        ).strip()

        for pattern, score in (
            cls.FRESHNESS_PATTERNS
        ):
            if pattern.search(
                source_text
            ):
                return score

        for key in (
            "posted_at",
            "published_at",
            "date_posted",
        ):
            value = cls._text(
                job.get(key)
            )

            if not value:
                continue

            try:
                parsed = datetime.fromisoformat(
                    value.replace(
                        "Z",
                        "+00:00",
                    )
                )

                if parsed.tzinfo is None:
                    parsed = (
                        parsed.replace(
                            tzinfo=timezone.utc
                        )
                    )

                age = (
                    datetime.now(
                        timezone.utc
                    )
                    - parsed
                )

                if age <= timedelta(
                    days=1
                ):
                    return 90

                if age <= timedelta(
                    days=3
                ):
                    return 80

                if age <= timedelta(
                    days=7
                ):
                    return 65

                if age <= timedelta(
                    days=14
                ):
                    return 45

                if age <= timedelta(
                    days=30
                ):
                    return 25

                return 5

            except (
                TypeError,
                ValueError,
            ):
                continue

        # Unknown posting date should not be treated as
        # extremely old. Give it a neutral baseline.
        return 40

    # ============================================================
    # URGENCY
    # ============================================================

    @classmethod
    def _urgency_score(
        cls,
        text: str,
    ) -> int:

        hits = sum(
            1
            for term in cls.URGENCY_TERMS
            if term in text
        )

        return min(
            100,
            hits * 40,
        )

    # ============================================================
    # APPLICATION ROUTE
    # ============================================================

    @classmethod
    def _application_route(
        cls,
        url: str,
        job: Mapping[str, Any],
    ) -> str:

        explicit = cls._text(
            job.get(
                "application_url"
            )
            or job.get(
                "apply_url"
            )
        )

        if explicit:
            return "application_url"

        source = cls._text(
            job.get("source")
        ).lower()

        if source == "naukri":
            return (
                "job_board_or_company_site"
            )

        if source == "indeed":
            return (
                "job_board_or_external_site"
            )

        if source in {
            "greenhouse",
            "lever",
            "workday",
        }:
            return "employer_ats"

        host = (
            urlparse(url)
            .netloc
            .lower()
        )

        if host:
            return "job_page"

        return "unknown"

    # ============================================================
    # TEXT
    # ============================================================

    @staticmethod
    def _text(
        value: Any,
    ) -> str:

        return " ".join(
            str(value or "").split()
        ).strip()


__all__ = [
    "JobIntelligence",
]