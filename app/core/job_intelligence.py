from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from app.agents.agent_brain import LocalAgentBrain
from app.agents.agent_learning import AgentLearning


class JobIntelligence:
    """
    Explainable AI-style job reasoning layer.

    Pipeline:

        Job
          ↓
        Role classification
          ↓
        Freshness / urgency
          ↓
        Candidate fit
          ↓
        Historical learning
          ↓
        Adaptive priority
          ↓
        APPLY / REVIEW / SKIP
    """

    EXCLUDED_TITLE_TERMS = (
        LocalAgentBrain.NEGATIVE_TITLE
    )

    TARGET_TITLE_TERMS = tuple(
        signal
        for signals in LocalAgentBrain.ROLE_SIGNALS.values()
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
        history: (
            Iterable[Mapping[str, Any]]
            | None
        ) = None,
    ) -> dict[str, Any]:
        """
        Analyze one job.

        ``history`` is optional so all existing callers remain
        backward compatible.

        When supplied, historical application outcomes are used
        as a conservative learning signal for the detected role.
        """

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

        # ========================================================
        # 1. ROLE INTELLIGENCE
        # ========================================================

        brain = (
            LocalAgentBrain.classify_job(
                job
            )
        )

        # ========================================================
        # 2. FRESHNESS / URGENCY
        # ========================================================

        freshness = (
            cls._freshness_score(
                combined,
                job,
            )
        )

        urgency = (
            cls._urgency_score(
                combined.lower()
            )
        )

        # ========================================================
        # 3. APPLICATION ROUTE
        # ========================================================

        route = (
            cls._application_route(
                url,
                job,
            )
        )

        # ========================================================
        # 4. MATCH INFORMATION
        # ========================================================

        match = job.get("match")

        if not isinstance(
            match,
            Mapping,
        ):
            match = {}

        eligible = match.get(
            "eligible"
        )

        match_score_raw = match.get(
            "match_score",
            match.get(
                "resume_score",
                None,
            ),
        )

        missing_required_skills = (
            match.get(
                "missing_required_skills",
                [],
            )
        )

        # ========================================================
        # 5. CANDIDATE FIT
        # ========================================================

        candidate_fit = (
            LocalAgentBrain.evaluate_candidate_fit(
                intent=brain.intent,
                confidence=brain.confidence,
                match_score=match_score_raw,
                eligible=eligible,
                missing_required_skills=(
                    missing_required_skills
                ),
            )
        )

        # ========================================================
        # 6. NORMALIZE MATCH
        # ========================================================

        match_available = (
            match_score_raw is not None
        )

        if match_available:
            try:
                match_score = float(
                    match_score_raw
                )
            except (
                TypeError,
                ValueError,
            ):
                match_score = 0.0
                match_available = False
        else:
            match_score = 0.0

        match_score = max(
            0.0,
            min(
                100.0,
                match_score,
            ),
        )

        # ========================================================
        # 7. ELIGIBILITY
        # ========================================================

        eligibility_score = (
            candidate_fit[
                "eligibility_score"
            ]
        )

        # ========================================================
        # 8. BASE PRIORITY
        # ========================================================

        base_priority = (
            LocalAgentBrain.rank_priority(
                target=brain.target,
                freshness=freshness,
                urgency=urgency,
                match_score=match_score,
                eligibility=eligibility_score,
            )
        )

        # ========================================================
        # 9. HISTORICAL LEARNING
        # ========================================================

        learning = (
            AgentLearning.analyze_history(
                history,
                role_class=(
                    brain.intent
                    if brain.target
                    else None
                ),
            )
        )

        learning_score = (
            learning[
                "learning_score"
            ]
        )

        learning_confidence = (
            learning[
                "confidence"
            ]
        )

        # Historical learning must never create priority for
        # a non-target job.
        if brain.target:
            learned_priority = (
                AgentLearning.adjust_priority(
                    priority_score=base_priority,
                    learning_score=learning_score,
                    confidence=learning_confidence,
                )
            )
        else:
            learned_priority = 0.0

        learning_adjustment = round(
            learned_priority
            - base_priority,
            2,
        )

        # ========================================================
        # 10. RECOMMENDED ACTION
        # ========================================================

        recommended_action = (
            LocalAgentBrain.choose_action(
                technical_target=brain.target,
                eligible=(
                    eligible is not False
                ),
                score=(
                    match_score
                    if match_available
                    else None
                ),
                application_status=cls._text(
                    job.get("status")
                ),
                match_available=(
                    match_available
                ),
            )
        )

        # ========================================================
        # 11. EXPLAINABLE REASONS
        # ========================================================

        reasons = [
            brain.reason,
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

        reasons.append(
            "candidate_fit="
            + str(
                candidate_fit[
                    "fit_level"
                ]
            )
        )

        reasons.append(
            "candidate_fit_score="
            + f"{candidate_fit['candidate_fit_score']:.1f}"
        )

        if candidate_fit[
            "missing_required_skills"
        ]:
            reasons.append(
                "required skills missing"
            )

        if learning_confidence > 0:
            reasons.append(
                "historical learning="
                + f"{learning_score:.1f}"
            )

        reasons.append(
            f"route={route}"
        )

        # ========================================================
        # 12. RESULT
        # ========================================================

        return {
            # ----------------------------------------------------
            # Role intelligence
            # ----------------------------------------------------

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

            "role_score": (
                brain.role_score
            ),

            "technical_score": (
                brain.technical_score
            ),

            "contradiction_score": (
                brain.contradiction_score
            ),

            "seniority": (
                brain.seniority
            ),

            "evidence_strength": (
                brain.evidence_strength
            ),

            # ----------------------------------------------------
            # Freshness / urgency
            # ----------------------------------------------------

            "freshness_score": freshness,

            "urgency_score": urgency,

            # ----------------------------------------------------
            # Candidate fit
            # ----------------------------------------------------

            "candidate_fit_score": (
                candidate_fit[
                    "candidate_fit_score"
                ]
            ),

            "fit_confidence": (
                candidate_fit[
                    "fit_confidence"
                ]
            ),

            "fit_level": (
                candidate_fit[
                    "fit_level"
                ]
            ),

            "missing_required_skills": list(
                candidate_fit[
                    "missing_required_skills"
                ]
            ),

            "eligibility_score": (
                candidate_fit[
                    "eligibility_score"
                ]
            ),

            "fit_reason": (
                candidate_fit[
                    "fit_reason"
                ]
            ),

            # ----------------------------------------------------
            # Historical learning
            # ----------------------------------------------------

            "learning_score": (
                learning_score
            ),

            "learning_confidence": (
                learning_confidence
            ),

            "learning_adjustment": (
                learning_adjustment
            ),

            "learning_reason": (
                learning[
                    "reason"
                ]
            ),

            "learning_history_count": (
                learning[
                    "history_count"
                ]
            ),

            "learning_successful_count": (
                learning[
                    "successful_count"
                ]
            ),

            "learning_negative_count": (
                learning[
                    "negative_count"
                ]
            ),

            "learning_success_rate": (
                learning[
                    "success_rate"
                ]
            ),

            # ----------------------------------------------------
            # Priority
            # ----------------------------------------------------

            "base_priority_score": (
                base_priority
            ),

            "priority_score": (
                learned_priority
            ),

            "priority_reason": (
                "; ".join(
                    reasons
                )
            ),

            # ----------------------------------------------------
            # Decision
            # ----------------------------------------------------

            "recommended_action": (
                recommended_action
            ),

            # ----------------------------------------------------
            # Application
            # ----------------------------------------------------

            "application_route": route,

            "company": company,
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

            except ValueError:
                continue

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

        host = urlparse(
            url
        ).netloc.lower()

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