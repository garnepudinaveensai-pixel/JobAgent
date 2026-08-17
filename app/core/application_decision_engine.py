from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


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
    Configuration controlling automatic application decisions.

    Default thresholds:

        >= 85 -> APPLY
        >= 70 -> REVIEW
        >= 50 -> OUTREACH when no application URL exists
        <  50 -> SKIP
    """

    apply_score: float = 85.0
    review_score: float = 70.0
    outreach_score: float = 50.0

    review_on_missing_required_skills: bool = True

    outreach_when_application_unavailable: bool = True

    skip_ineligible: bool = True

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
    Structured result returned by ApplicationDecisionEngine.
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
        """
        Convert the decision into a plain dictionary.
        """

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
                    dict,
                )
                else self.selected_resume
            ),
            "recommended_action": self.recommended_action,
            "metadata": dict(self.metadata),
        }


# ============================================================
# APPLICATION DECISION ENGINE
# ============================================================


class ApplicationDecisionEngine:
    """
    Decide what JobAgent should do with a ranked job.

    Possible decisions:

        APPLY
        OUTREACH
        REVIEW
        SKIP

    This class does not:

        - discover jobs
        - rank jobs
        - match resumes
        - send emails
        - submit applications

    It only determines the recommended next action.
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
        """
        Decide the next action for one ranked job result.
        """

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

        match = self._get_mapping(
            ranked_result.get("match")
        )

        ranking_score = self._score(
            ranked_result.get(
                "ranking_score",
                0,
            )
        )

        match_score = self._score(
            match.get(
                "match_score",
                ranked_result.get(
                    "match_score",
                    0,
                ),
            )
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
        # INELIGIBLE
        # ----------------------------------------------------

        if (
            self.config.skip_ineligible
            and not eligible
        ):
            return self._result(
                decision=SKIP,
                reason=(
                    "The job is marked as ineligible "
                    "for the selected candidate."
                ),
                ranking_score=ranking_score,
                match_score=match_score,
                eligible=eligible,
                missing_required_skills=(
                    missing_required
                ),
                application_url=application_url,
                selected_resume=selected_resume,
            )

        # ----------------------------------------------------
        # MISSING REQUIRED SKILLS
        # ----------------------------------------------------

        if (
            missing_required
            and self.config.review_on_missing_required_skills
        ):
            return self._result(
                decision=REVIEW,
                reason=(
                    "The job has missing required skills "
                    "and should be reviewed before applying."
                ),
                ranking_score=ranking_score,
                match_score=match_score,
                eligible=eligible,
                missing_required_skills=(
                    missing_required
                ),
                application_url=application_url,
                selected_resume=selected_resume,
            )

        # ----------------------------------------------------
        # HIGH SCORE
        # ----------------------------------------------------

        if ranking_score >= self.config.apply_score:

            if application_url:
                return self._result(
                    decision=APPLY,
                    reason=(
                        "Strong ranked match with an "
                        "application URL available."
                    ),
                    ranking_score=ranking_score,
                    match_score=match_score,
                    eligible=eligible,
                    missing_required_skills=(
                        missing_required
                    ),
                    application_url=application_url,
                    selected_resume=selected_resume,
                )

            if (
                self.config
                .outreach_when_application_unavailable
            ):
                return self._result(
                    decision=OUTREACH,
                    reason=(
                        "Strong ranked match, but no direct "
                        "application URL is available."
                    ),
                    ranking_score=ranking_score,
                    match_score=match_score,
                    eligible=eligible,
                    missing_required_skills=(
                        missing_required
                    ),
                    application_url=application_url,
                    selected_resume=selected_resume,
                )

            return self._result(
                decision=REVIEW,
                reason=(
                    "Strong ranked match, but the "
                    "application route is unavailable."
                ),
                ranking_score=ranking_score,
                match_score=match_score,
                eligible=eligible,
                missing_required_skills=(
                    missing_required
                ),
                application_url=application_url,
                selected_resume=selected_resume,
            )

        # ----------------------------------------------------
        # MEDIUM SCORE
        # ----------------------------------------------------

        if ranking_score >= self.config.review_score:
            return self._result(
                decision=REVIEW,
                reason=(
                    "The job is a potentially suitable "
                    "match but does not meet the automatic "
                    "application threshold."
                ),
                ranking_score=ranking_score,
                match_score=match_score,
                eligible=eligible,
                missing_required_skills=(
                    missing_required
                ),
                application_url=application_url,
                selected_resume=selected_resume,
            )

        # ----------------------------------------------------
        # OUTREACH RANGE
        # ----------------------------------------------------

        if ranking_score >= self.config.outreach_score:

            if (
                self.config
                .outreach_when_application_unavailable
                and not application_url
            ):
                return self._result(
                    decision=OUTREACH,
                    reason=(
                        "The job meets the minimum outreach "
                        "threshold and has no direct "
                        "application URL."
                    ),
                    ranking_score=ranking_score,
                    match_score=match_score,
                    eligible=eligible,
                    missing_required_skills=(
                        missing_required
                    ),
                    application_url=application_url,
                    selected_resume=selected_resume,
                )

            return self._result(
                decision=REVIEW,
                reason=(
                    "The job is above the minimum threshold "
                    "but requires manual review before action."
                ),
                ranking_score=ranking_score,
                match_score=match_score,
                eligible=eligible,
                missing_required_skills=(
                    missing_required
                ),
                application_url=application_url,
                selected_resume=selected_resume,
            )

        # ----------------------------------------------------
        # LOW SCORE
        # ----------------------------------------------------

        return self._result(
            decision=SKIP,
            reason=(
                "The ranking score is below the minimum "
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
        )

    # ========================================================
    # BATCH DECISIONS
    # ========================================================

    def decide_many(
        self,
        ranked_results: list[
            Mapping[str, Any]
        ],
    ) -> list[ApplicationDecision]:
        """
        Decide actions for multiple ranked results.

        ranked_results MUST be a list.

        None and other types are rejected deliberately so that
        invalid pipeline data is detected immediately instead
        of silently producing an empty result.
        """

        if not isinstance(
            ranked_results,
            list,
        ):
            raise TypeError(
                "ranked_results must be a list."
            )

        return [
            self.decide(result)
            for result in ranked_results
        ]

    # ========================================================
    # FILTERING
    # ========================================================

    def filter_by_decision(
        self,
        ranked_results: list[
            Mapping[str, Any]
        ],
        decision: str,
    ) -> list[Mapping[str, Any]]:
        """
        Return original ranked results matching a decision.
        """

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

        results: list[
            Mapping[str, Any]
        ] = []

        for result in ranked_results:
            result_decision = self.decide(
                result
            )

            if (
                result_decision.decision
                == decision
            ):
                results.append(result)

        return results

    # ========================================================
    # INTERNAL HELPERS
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
            score = float(value)
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
            return value.strip().lower() in {
                "true",
                "1",
                "yes",
                "eligible",
            }

        return bool(value)

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

            if value and value not in result:
                result.append(value)

        return tuple(result)

    @staticmethod
    def _extract_application_url(
        ranked_result: Mapping[str, Any],
        job: Mapping[str, Any],
    ) -> str:
        """
        Resolve the best available application URL.
        """

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
                return dict(value)

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
            application_url=application_url,
            selected_resume=selected_resume,
            recommended_action=recommended_action,
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
    """
    Convenience wrapper returning a dictionary.
    """

    engine = ApplicationDecisionEngine(
        config=config
    )

    return engine.decide(
        ranked_result
    ).to_dict()


# ============================================================
# PUBLIC API
# ============================================================


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