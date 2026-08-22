from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from app.core.job_intelligence import JobIntelligence


# ============================================================
# DECISIONS
# ============================================================

APPLY = "APPLY"
OUTREACH = "OUTREACH"
REVIEW = "REVIEW"
SKIP = "SKIP"

VALID_DECISIONS = {
    APPLY,
    OUTREACH,
    REVIEW,
    SKIP,
}


# ============================================================
# CONFIGURATION
# ============================================================


@dataclass(frozen=True)
class ApplicationDecisionConfig:
    """
    Controls the final action selected by JobAgent.

    Existing application behavior is preserved:

        APPLY
            ranking score >= 85 and an application route exists

        REVIEW
            ranking score >= 70 but below APPLY threshold

        OUTREACH
            ranking score >= 50 and direct application route
            is unavailable

        SKIP
            ranking score < 50, ineligible, closed, duplicate,
            or explicitly rejected by job intelligence
    """

    apply_score: float = 85.0
    review_score: float = 70.0
    outreach_score: float = 50.0

    review_on_missing_required_skills: bool = True

    outreach_when_application_unavailable: bool = True

    skip_ineligible: bool = True

    require_technical_target: bool = True

    def __post_init__(self) -> None:
        values = (
            self.apply_score,
            self.review_score,
            self.outreach_score,
        )

        for value in values:
            if not 0 <= float(value) <= 100:
                raise ValueError(
                    "Decision scores must be between 0 and 100."
                )

        if not (
            self.apply_score
            >= self.review_score
            >= self.outreach_score
        ):
            raise ValueError(
                "Decision thresholds must satisfy: "
                "apply_score >= review_score >= outreach_score."
            )


# ============================================================
# DECISION RESULT
# ============================================================


@dataclass(frozen=True)
class ApplicationDecision:
    """
    Structured decision returned by the decision engine.
    """

    decision: str
    reason: str

    ranking_score: float
    match_score: float
    eligible: bool

    missing_required_skills: tuple[str, ...] = field(
        default_factory=tuple
    )

    application_url: str = ""

    selected_resume: Optional[dict] = None

    recommended_action: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if self.decision not in VALID_DECISIONS:
            raise ValueError(
                f"Invalid decision: {self.decision}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "ranking_score": self.ranking_score,
            "match_score": self.match_score,
            "eligible": self.eligible,
            "missing_required_skills": list(
                self.missing_required_skills
            ),
            "application_url": self.application_url,
            "selected_resume": (
                dict(self.selected_resume)
                if isinstance(
                    self.selected_resume,
                    Mapping,
                )
                else self.selected_resume
            ),
            "recommended_action": (
                self.recommended_action
            ),
            "metadata": dict(
                self.metadata
            ),
        }


# ============================================================
# DECISION ENGINE
# ============================================================


class ApplicationDecisionEngine:
    """
    Final reasoning layer between ranking and execution.

    Flow:

        ranked job
            ↓
        job intelligence
            ↓
        hard safety / relevance guards
            ↓
        eligibility
            ↓
        match information
            ↓
        required skills
            ↓
        score thresholds
            ↓
        APPLY / REVIEW / OUTREACH / SKIP

    Important compatibility rule:

    Existing score-based application behavior remains the
    source of truth for final routing. Job intelligence adds
    intelligence and safety guards around that behavior rather
    than overriding established score thresholds.
    """

    def __init__(
        self,
        config: Optional[
            ApplicationDecisionConfig
        ] = None,
    ):
        self.config = (
            config
            if config is not None
            else ApplicationDecisionConfig()
        )

    # ========================================================
    # SINGLE DECISION
    # ========================================================

    def decide(
        self,
        ranked_result: Mapping[str, Any],
    ) -> ApplicationDecision:

        if not isinstance(
            ranked_result,
            Mapping,
        ):
            raise TypeError(
                "ranked_result must be a mapping."
            )

        job = self._get_mapping(
            ranked_result.get("job")
        )

        match_present = isinstance(
            ranked_result.get("match"),
            Mapping,
        )

        match = self._get_mapping(
            ranked_result.get("match")
        )

        ranking_score = self._score(
            ranked_result.get(
                "ranking_score",
                0,
            )
        )

        match_score = self._extract_match_score(
            ranked_result,
            match,
        )

        eligible = self._get_eligibility(
            ranked_result,
            match,
        )

        missing_required = (
            self._extract_missing_required_skills(
                ranked_result,
                match,
            )
        )

        application_url = (
            self._extract_application_url(
                ranked_result,
                job,
            )
        )

        selected_resume = (
            self._extract_selected_resume(
                ranked_result,
                match,
            )
        )

        # ----------------------------------------------------
        # JOB INTELLIGENCE
        # ----------------------------------------------------

        intelligence = (
            ranked_result.get(
                "job_intelligence"
            )
        )

        if not isinstance(
            intelligence,
            Mapping,
        ):
            intelligence = JobIntelligence.analyze(
                job
            )

        intelligence = dict(
            intelligence
        )

        technical_target = bool(
            intelligence.get(
                "technical_target",
                False,
            )
        )

        role_class = str(
            intelligence.get(
                "role_class",
                "uncertain",
            )
        )

        confidence = self._score(
            intelligence.get(
                "confidence",
                0,
            )
        )

        priority_score = self._score(
            intelligence.get(
                "priority_score",
                ranked_result.get(
                    "priority_score",
                    0,
                ),
            )
        )

        intelligence_action = str(
            intelligence.get(
                "recommended_action",
                "",
            )
        ).strip().upper()

        metadata = {
            "job_intelligence": intelligence,
            "technical_target": technical_target,
            "role_class": role_class,
            "intelligence_confidence": confidence,
            "priority_score": priority_score,
            "intelligence_recommended_action": (
                intelligence_action
            ),
            "match_available": match_present,
        }

        # ----------------------------------------------------
        # HARD TARGET GUARD
        # ----------------------------------------------------

        if (
            self.config.require_technical_target
            and not technical_target
        ):
            return self._result(
                decision=SKIP,
                reason=(
                    "Job intelligence classified this role "
                    "as non-target or uncertain. Automatic "
                    "application is blocked."
                ),
                ranking_score=ranking_score,
                match_score=match_score,
                eligible=eligible,
                missing_required_skills=(
                    missing_required
                ),
                application_url=application_url,
                selected_resume=selected_resume,
                metadata=metadata,
            )

        # ----------------------------------------------------
        # STATUS GUARD
        # ----------------------------------------------------

        status = str(
            job.get(
                "status",
                ranked_result.get(
                    "status",
                    "",
                ),
            )
            or ""
        ).strip().lower()

        if status in {
            "closed",
            "expired",
            "withdrawn",
            "duplicate",
            "job_unavailable",
        }:
            return self._result(
                decision=SKIP,
                reason=(
                    f"Job status is '{status}' and the "
                    "application should not proceed."
                ),
                ranking_score=ranking_score,
                match_score=match_score,
                eligible=eligible,
                missing_required_skills=(
                    missing_required
                ),
                application_url=application_url,
                selected_resume=selected_resume,
                metadata=metadata,
            )

        # ----------------------------------------------------
        # ELIGIBILITY GUARD
        # ----------------------------------------------------

        if (
            self.config.skip_ineligible
            and not eligible
        ):
            return self._result(
                decision=SKIP,
                reason=(
                    "The job is marked as ineligible "
                    "for the candidate."
                ),
                ranking_score=ranking_score,
                match_score=match_score,
                eligible=eligible,
                missing_required_skills=(
                    missing_required
                ),
                application_url=application_url,
                selected_resume=selected_resume,
                metadata=metadata,
            )

        # ----------------------------------------------------
        # MISSING MATCH INFORMATION
        # ----------------------------------------------------

        if not match_present:
            return self._result(
                decision=REVIEW,
                reason=(
                    "Resume matching has not been completed "
                    "for this job. The job remains reviewable "
                    "but must not be automatically submitted."
                ),
                ranking_score=ranking_score,
                match_score=match_score,
                eligible=eligible,
                missing_required_skills=(
                    missing_required
                ),
                application_url=application_url,
                selected_resume=selected_resume,
                metadata=metadata,
            )

        # ----------------------------------------------------
        # REQUIRED SKILLS
        # ----------------------------------------------------

        if (
            missing_required
            and self.config.review_on_missing_required_skills
        ):
            metadata = dict(
                metadata
            )

            metadata[
                "missing_required_skill_count"
            ] = len(
                missing_required
            )

            return self._result(
                decision=REVIEW,
                reason=(
                    "Required skills are missing. "
                    "Human review is required before "
                    "application."
                ),
                ranking_score=ranking_score,
                match_score=match_score,
                eligible=eligible,
                missing_required_skills=(
                    missing_required
                ),
                application_url=application_url,
                selected_resume=selected_resume,
                metadata=metadata,
            )

        # ----------------------------------------------------
        # INTELLIGENCE HARD SKIP
        # ----------------------------------------------------

        # Intelligence is allowed to prevent an application.
        # It is NOT allowed to turn an already low score into
        # REVIEW or to override the established score routing.
        if intelligence_action == SKIP:
            return self._result(
                decision=SKIP,
                reason=(
                    "The job intelligence layer explicitly "
                    "recommended SKIP."
                ),
                ranking_score=ranking_score,
                match_score=match_score,
                eligible=eligible,
                missing_required_skills=(
                    missing_required
                ),
                application_url=application_url,
                selected_resume=selected_resume,
                metadata=metadata,
            )

        # ----------------------------------------------------
        # SCORE-BASED ROUTING
        # ----------------------------------------------------

        # ====================================================
        # APPLY
        # ====================================================

        if ranking_score >= self.config.apply_score:

            # A direct application route exists.
            if application_url:
                return self._result(
                    decision=APPLY,
                    reason=(
                        "Strong technical match, eligibility "
                        "confirmed, and an application route "
                        "is available."
                    ),
                    ranking_score=ranking_score,
                    match_score=match_score,
                    eligible=eligible,
                    missing_required_skills=(
                        missing_required
                    ),
                    application_url=application_url,
                    selected_resume=selected_resume,
                    metadata=metadata,
                )

            # No direct application URL.
            if (
                self.config
                .outreach_when_application_unavailable
            ):
                return self._result(
                    decision=OUTREACH,
                    reason=(
                        "Strong technical match, but no "
                        "direct application URL is available."
                    ),
                    ranking_score=ranking_score,
                    match_score=match_score,
                    eligible=eligible,
                    missing_required_skills=(
                        missing_required
                    ),
                    application_url=application_url,
                    selected_resume=selected_resume,
                    metadata=metadata,
                )

        # ====================================================
        # REVIEW
        # ====================================================

        if (
            ranking_score
            >= self.config.review_score
        ):
            return self._result(
                decision=REVIEW,
                reason=(
                    "The job is relevant but does not yet "
                    "meet the automatic application threshold."
                ),
                ranking_score=ranking_score,
                match_score=match_score,
                eligible=eligible,
                missing_required_skills=(
                    missing_required
                ),
                application_url=application_url,
                selected_resume=selected_resume,
                metadata=metadata,
            )

        # ====================================================
        # OUTREACH
        # ====================================================

        if (
            ranking_score
            >= self.config.outreach_score
        ):
            if (
                self.config
                .outreach_when_application_unavailable
                and not application_url
            ):
                return self._result(
                    decision=OUTREACH,
                    reason=(
                        "The job meets the outreach threshold "
                        "but does not expose a direct "
                        "application route."
                    ),
                    ranking_score=ranking_score,
                    match_score=match_score,
                    eligible=eligible,
                    missing_required_skills=(
                        missing_required
                    ),
                    application_url=application_url,
                    selected_resume=selected_resume,
                    metadata=metadata,
                )

            return self._result(
                decision=REVIEW,
                reason=(
                    "The job is potentially relevant but "
                    "requires manual review."
                ),
                ranking_score=ranking_score,
                match_score=match_score,
                eligible=eligible,
                missing_required_skills=(
                    missing_required
                ),
                application_url=application_url,
                selected_resume=selected_resume,
                metadata=metadata,
            )

        # ====================================================
        # SKIP
        # ====================================================

        return self._result(
            decision=SKIP,
            reason=(
                "The job does not meet the minimum "
                "threshold for further action."
            ),
            ranking_score=ranking_score,
            match_score=match_score,
            eligible=eligible,
            missing_required_skills=(
                missing_required
            ),
            application_url=application_url,
            selected_resume=selected_resume,
            metadata=metadata,
        )

    # ========================================================
    # BATCH
    # ========================================================

    def decide_many(
        self,
        ranked_results: list[
            Mapping[str, Any]
        ],
    ) -> list[ApplicationDecision]:

        if not isinstance(
            ranked_results,
            list,
        ):
            raise TypeError(
                "ranked_results must be a list."
            )

        return [
            self.decide(
                result
            )
            for result in ranked_results
        ]

    # ========================================================
    # FILTER
    # ========================================================

    def filter_by_decision(
        self,
        ranked_results: list[
            Mapping[str, Any]
        ],
        decision: str,
    ) -> list[
        Mapping[str, Any]
    ]:

        if decision not in VALID_DECISIONS:
            raise ValueError(
                f"Invalid decision: {decision}"
            )

        if not isinstance(
            ranked_results,
            list,
        ):
            raise TypeError(
                "ranked_results must be a list."
            )

        return [
            result
            for result in ranked_results
            if self.decide(
                result
            ).decision == decision
        ]

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _get_mapping(
        value: Any,
    ) -> Mapping[str, Any]:

        if isinstance(
            value,
            Mapping,
        ):
            return value

        return {}

    @staticmethod
    def _score(
        value: Any,
    ) -> float:

        try:
            score = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0.0

        return max(
            0.0,
            min(
                100.0,
                score,
            ),
        )

    @classmethod
    def _extract_match_score(
        cls,
        ranked_result: Mapping[str, Any],
        match: Mapping[str, Any],
    ) -> float:

        value = match.get(
            "match_score",
            match.get(
                "resume_score",
                ranked_result.get(
                    "match_score",
                    0,
                ),
            ),
        )

        return cls._score(
            value
        )

    @staticmethod
    def _get_eligibility(
        ranked_result: Mapping[str, Any],
        match: Mapping[str, Any],
    ) -> bool:

        value = match.get(
            "eligible",
            ranked_result.get(
                "eligible",
                True,
            ),
        )

        if isinstance(
            value,
            str,
        ):
            return (
                value.strip().lower()
                in {
                    "true",
                    "1",
                    "yes",
                    "eligible",
                }
            )

        return bool(
            value
        )

    @staticmethod
    def _extract_missing_required_skills(
        ranked_result: Mapping[str, Any],
        match: Mapping[str, Any],
    ) -> tuple[str, ...]:

        candidates = (
            match.get(
                "missing_required_skills"
            )
            or ranked_result.get(
                "missing_required_skills"
            )
            or []
        )

        if isinstance(
            candidates,
            str,
        ):
            candidates = [
                candidates
            ]

        if not isinstance(
            candidates,
            (
                list,
                tuple,
                set,
            ),
        ):
            return ()

        result: list[str] = []

        for item in candidates:
            value = str(
                item
            ).strip()

            if (
                value
                and value not in result
            ):
                result.append(
                    value
                )

        return tuple(
            result
        )

    @staticmethod
    def _extract_application_url(
        ranked_result: Mapping[str, Any],
        job: Mapping[str, Any],
    ) -> str:

        candidates = (
            ranked_result.get(
                "application_url"
            ),
            job.get(
                "application_url"
            ),
            job.get(
                "apply_url"
            ),
            job.get(
                "url"
            ),
        )

        for value in candidates:
            if value is None:
                continue

            result = str(
                value
            ).strip()

            if result:
                return result

        return ""

    @staticmethod
    def _extract_selected_resume(
        ranked_result: Mapping[str, Any],
        match: Mapping[str, Any],
    ) -> Optional[dict]:

        candidates = (
            match.get(
                "selected_resume"
            ),
            ranked_result.get(
                "selected_resume"
            ),
            ranked_result.get(
                "resume"
            ),
        )

        for value in candidates:
            if isinstance(
                value,
                Mapping,
            ):
                return dict(
                    value
                )

        return None

    @staticmethod
    def _result(
        *,
        decision: str,
        reason: str,
        ranking_score: float,
        match_score: float,
        eligible: bool,
        missing_required_skills: tuple[str, ...],
        application_url: str,
        selected_resume: Optional[dict],
        metadata: Optional[
            dict[str, Any]
        ] = None,
    ) -> ApplicationDecision:

        recommended_action = {
            APPLY: "application",
            OUTREACH: "outreach",
            REVIEW: "manual_review",
            SKIP: "none",
        }[decision]

        return ApplicationDecision(
            decision=decision,
            reason=reason,
            ranking_score=ranking_score,
            match_score=match_score,
            eligible=eligible,
            missing_required_skills=(
                missing_required_skills
            ),
            application_url=(
                application_url
            ),
            selected_resume=(
                selected_resume
            ),
            recommended_action=(
                recommended_action
            ),
            metadata=dict(
                metadata or {}
            ),
        )


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================


def decide_application_action(
    ranked_result: Mapping[str, Any],
    config: Optional[
        ApplicationDecisionConfig
    ] = None,
) -> dict[str, Any]:

    engine = ApplicationDecisionEngine(
        config=config
    )

    return engine.decide(
        ranked_result
    ).to_dict()


__all__ = [
    "APPLY",
    "OUTREACH",
    "REVIEW",
    "SKIP",
    "VALID_DECISIONS",
    "ApplicationDecisionConfig",
    "ApplicationDecision",
    "ApplicationDecisionEngine",
    "decide_application_action",
]