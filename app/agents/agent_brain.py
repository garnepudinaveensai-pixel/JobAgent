from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class BrainDecision:
    intent: str
    confidence: float
    target: bool
    reason: str
    matched_signals: tuple[str, ...] = ()
    negative_signals: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalAgentBrain:
    """
    Explainable local reasoning engine.

    No API keys.
    No external AI service.
    No network calls.

    Reasoning flow:

        observe
            ↓
        classify
            ↓
        detect contradictions
            ↓
        estimate confidence
            ↓
        prioritize
            ↓
        choose action
    """

    ROLE_SIGNALS = {
        "software": (
            "software engineer",
            "software developer",
            "python developer",
            "backend",
            "frontend",
            "full stack",
            "developer",
            "devops",
            "qa engineer",
            "test engineer",
        ),
        "embedded": (
            "embedded",
            "firmware",
            "microcontroller",
            "embedded c",
        ),
        "automation": (
            "automation",
            "controls engineer",
            "control engineer",
            "plc",
            "scada",
            "instrumentation",
        ),
        "electrical_core": (
            "electrical engineer",
            "electrical",
            "power engineer",
            "power systems",
            "power electronics",
            "electrical maintenance",
            "maintenance engineer",
            "reliability engineer",
            "condition based maintenance",
            "commissioning engineer",
            "testing and commissioning",
        ),
        "energy": (
            "energy engineer",
            "renewable energy",
            "solar engineer",
            "energy management",
        ),
        "data_ai": (
            "data engineer",
            "machine learning engineer",
            "ai engineer",
            "artificial intelligence",
        ),
    }

    NEGATIVE_TITLE = (
        "sales",
        "business development",
        "bd executive",
        "account executive",
        "customer success",
        "customer support",
        "inside sales",
        "field sales",
        "marketing",
        "recruiter",
        "recruitment",
        "human resources",
        "hr executive",
        "talent acquisition",
        "finance",
        "accountant",
        "accounts executive",
        "procurement",
        "purchase executive",
        "administration",
        "admin executive",
        "civil engineer",
        "mechanical engineer",
        "plumbing",
        "electrical sales",
    )

    NEGATIVE_DESCRIPTION = (
        "cold calling",
        "sales target",
        "lead generation",
        "sell products",
        "customer acquisition",
        "business development executive",
    )

    TECHNICAL_DESCRIPTION = (
        "python",
        "embedded",
        "plc",
        "scada",
        "matlab",
        "simulink",
        "power electronics",
        "electrical system",
        "microcontroller",
        "firmware",
        "software development",
        "sql",
        "automation",
        "control systems",
        "condition-based maintenance",
        "predictive maintenance",
        "thermography",
        "vibration analysis",
        "industrial equipment",
        "testing",
        "commissioning",
    )

    @staticmethod
    def text(value: Any) -> str:
        return " ".join(
            str(value or "").split()
        ).strip()

    @classmethod
    def classify_job(
        cls,
        job: Mapping[str, Any],
    ) -> BrainDecision:

        if not isinstance(job, Mapping):
            raise TypeError(
                "job must be a mapping."
            )

        title = cls.text(
            job.get("title")
            or job.get("job_title")
        ).lower()

        description = cls.text(
            job.get("description")
        ).lower()

        text = f"{title} {description}"

        negative_title = tuple(
            signal
            for signal in cls.NEGATIVE_TITLE
            if signal in title
        )

        negative_description = tuple(
            signal
            for signal in cls.NEGATIVE_DESCRIPTION
            if signal in description
        )

        role_scores: dict[str, int] = {}

        for role, signals in cls.ROLE_SIGNALS.items():
            score = 0

            for signal in signals:
                if signal in title:
                    score += 4
                elif signal in text:
                    score += 2

            if score:
                role_scores[role] = score

        technical_hits = tuple(
            signal
            for signal in cls.TECHNICAL_DESCRIPTION
            if signal in text
        )

        negative_signals = tuple(
            dict.fromkeys(
                (
                    *negative_title,
                    *negative_description,
                )
            )
        )

        # Strong title-level exclusion always wins.
        if negative_title:
            return BrainDecision(
                intent="non_target",
                confidence=0.99,
                target=False,
                reason=(
                    "title contains an excluded "
                    "non-target role signal"
                ),
                matched_signals=technical_hits,
                negative_signals=negative_signals,
            )

        # If the description clearly indicates sales/support
        # activity and there is no actual technical role signal,
        # reject it.
        if (
            negative_description
            and not role_scores
        ):
            return BrainDecision(
                intent="non_target",
                confidence=0.96,
                target=False,
                reason=(
                    "description is dominated by "
                    "non-technical sales/support activity"
                ),
                matched_signals=technical_hits,
                negative_signals=negative_signals,
            )

        # No technical evidence means the agent should not
        # automatically apply.
        if (
            not role_scores
            and not technical_hits
        ):
            return BrainDecision(
                intent="uncertain",
                confidence=0.35,
                target=False,
                reason=(
                    "insufficient technical evidence"
                ),
                matched_signals=(),
                negative_signals=negative_signals,
            )

        if role_scores:
            role, raw_score = max(
                role_scores.items(),
                key=lambda item: item[1],
            )
        else:
            role = "technical"
            raw_score = 0

        confidence = min(
            0.99,
            0.55
            + raw_score * 0.06
            + min(
                len(technical_hits),
                6,
            )
            * 0.03,
        )

        matched = tuple(
            dict.fromkeys(
                (
                    *technical_hits,
                    *role_scores.keys(),
                )
            )
        )

        return BrainDecision(
            intent=role,
            confidence=round(
                confidence,
                3,
            ),
            target=True,
            reason=(
                f"technical signals support "
                f"{role} role"
            ),
            matched_signals=matched,
            negative_signals=negative_signals,
        )

    @classmethod
    def rank_priority(
        cls,
        *,
        target: bool,
        freshness: float,
        urgency: float,
        match_score: float = 0.0,
        eligibility: float = 100.0,
    ) -> float:
        """
        Calculate application priority.

        Priority considers:

            freshness   35%
            urgency     25%
            match       25%
            eligibility 15%

        Recent/urgent jobs receive an additional boost because
        they can disappear quickly.
        """

        if not target:
            return 0.0

        freshness = max(
            0.0,
            min(
                100.0,
                float(freshness),
            ),
        )

        urgency = max(
            0.0,
            min(
                100.0,
                float(urgency),
            ),
        )

        match_score = max(
            0.0,
            min(
                100.0,
                float(match_score),
            ),
        )

        eligibility = max(
            0.0,
            min(
                100.0,
                float(eligibility),
            ),
        )

        value = (
            freshness * 0.35
            + urgency * 0.25
            + match_score * 0.25
            + eligibility * 0.15
        )

        if (
            freshness >= 80
            and urgency >= 40
        ):
            value += 12.0

        if (
            freshness >= 90
            and urgency >= 80
        ):
            value += 8.0

        return round(
            max(
                0.0,
                min(
                    100.0,
                    value,
                ),
            ),
            2,
        )

    @classmethod
    def choose_action(
        cls,
        *,
        technical_target: bool,
        eligible: bool,
        score: float | None,
        application_status: str = "",
        match_available: bool = True,
    ) -> str:
        """
        Decide the next high-level action.

        Important:
        Missing match information means REVIEW, not SKIP.

        SKIP is reserved for:
            - excluded roles
            - ineligible jobs
            - closed/expired/duplicate jobs
            - jobs with an evaluated score below threshold
        """

        status = cls.text(
            application_status
        ).lower()

        if status in {
            "closed",
            "expired",
            "withdrawn",
            "duplicate",
        }:
            return "SKIP"

        if not technical_target:
            return "SKIP"

        if not eligible:
            return "REVIEW"

        # The agent has not yet evaluated the resume against
        # this job. Do not throw away a potentially good job.
        if (
            not match_available
            or score is None
        ):
            return "REVIEW"

        try:
            score_value = float(score)
        except (
            TypeError,
            ValueError,
        ):
            return "REVIEW"

        if score_value >= 70:
            return "APPLY"

        if score_value >= 55:
            return "REVIEW"

        return "SKIP"


__all__ = [
    "BrainDecision",
    "LocalAgentBrain",
]