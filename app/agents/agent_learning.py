from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


class AgentLearning:
    """
    Deterministic application-outcome learning layer.

    Converts historical application outcomes into an explainable
    learning signal that can later be consumed by JobIntelligence.

    No external services or LLM calls are used.
    """

    SUCCESS_WEIGHTS = {
        "offer": 1.00,
        "hired": 1.00,
        "accepted": 1.00,
        "shortlisted": 0.85,
        "interview": 0.75,
        "screening": 0.60,
        "assessment": 0.45,
        "applied": 0.20,
    }

    NEGATIVE_WEIGHTS = {
        "rejected": 0.00,
        "failed": 0.00,
        "declined": 0.00,
        "withdrawn": 0.10,
        "expired": 0.10,
    }

    IGNORED_OUTCOMES = {
        "",
        "unknown",
        "pending",
        "review",
        "reviewing",
        "not_started",
    }

    @classmethod
    def analyze_history(
        cls,
        history: Iterable[Mapping[str, Any]] | None,
        role_class: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyze historical application outcomes.

        Only records matching role_class are considered when a role
        is supplied.

        Returns an explainable, bounded learning signal.
        """

        if history is None:
            records: list[Mapping[str, Any]] = []
        else:
            records = [
                item
                for item in history
                if isinstance(item, Mapping)
            ]

        requested_role = cls._normalize(
            role_class
        )

        relevant: list[Mapping[str, Any]] = []

        for record in records:
            record_role = cls._normalize(
                record.get(
                    "role_class",
                    record.get(
                        "role",
                        record.get(
                            "intent",
                            "",
                        ),
                    ),
                )
            )

            if requested_role:
                if record_role != requested_role:
                    continue

            outcome = cls._normalize(
                record.get("outcome")
            )

            if outcome in cls.IGNORED_OUTCOMES:
                continue

            if (
                outcome not in cls.SUCCESS_WEIGHTS
                and outcome not in cls.NEGATIVE_WEIGHTS
            ):
                continue

            relevant.append(record)

        history_count = len(relevant)

        if history_count == 0:
            return {
                "history_count": 0,
                "successful_count": 0,
                "negative_count": 0,
                "learning_score": 50.0,
                "confidence": 0.0,
                "success_rate": 0.0,
                "reason": (
                    "No usable application history"
                    + (
                        f" for role={requested_role}"
                        if requested_role
                        else ""
                    )
                ),
                "outcomes": {},
            }

        weighted_values: list[float] = []
        successful_count = 0
        negative_count = 0
        outcome_counter: Counter[str] = Counter()

        for record in relevant:
            outcome = cls._normalize(
                record.get("outcome")
            )

            outcome_counter[outcome] += 1

            if outcome in cls.SUCCESS_WEIGHTS:
                value = cls.SUCCESS_WEIGHTS[
                    outcome
                ]

                if value >= 0.45:
                    successful_count += 1
            else:
                value = cls.NEGATIVE_WEIGHTS[
                    outcome
                ]

                if value <= 0.10:
                    negative_count += 1

            weighted_values.append(
                value
            )

        average = (
            sum(weighted_values)
            / len(weighted_values)
        )

        learning_score = (
            50.0
            + (average - 0.5) * 100.0
        )

        learning_score = max(
            0.0,
            min(
                100.0,
                learning_score,
            ),
        )

        # Confidence increases with usable history,
        # but deliberately saturates rather than pretending
        # that a small sample is highly reliable.
        confidence = min(
            1.0,
            history_count / 10.0,
        )

        success_rate = (
            successful_count
            / history_count
            * 100.0
        )

        outcomes = dict(
            outcome_counter
        )

        role_text = (
            requested_role
            or "all roles"
        )

        reason = (
            f"role={role_text}; "
            f"history={history_count}; "
            f"successful={successful_count}; "
            f"negative={negative_count}; "
            f"learning_score="
            f"{learning_score:.1f}"
        )

        return {
            "history_count": history_count,
            "successful_count": successful_count,
            "negative_count": negative_count,
            "learning_score": round(
                learning_score,
                2,
            ),
            "confidence": round(
                confidence,
                3,
            ),
            "success_rate": round(
                success_rate,
                2,
            ),
            "reason": reason,
            "outcomes": outcomes,
        }

    @classmethod
    def adjust_priority(
        cls,
        priority_score: float,
        learning_score: float,
        confidence: float,
    ) -> float:
        """
        Apply a conservative historical-learning adjustment.

        Learning can influence priority, but never dominates the
        current job's actual evidence.
        """

        try:
            priority = float(
                priority_score
            )
        except (
            TypeError,
            ValueError,
        ):
            priority = 0.0

        try:
            learning = float(
                learning_score
            )
        except (
            TypeError,
            ValueError,
        ):
            learning = 50.0

        try:
            confidence_value = float(
                confidence
            )
        except (
            TypeError,
            ValueError,
        ):
            confidence_value = 0.0

        priority = max(
            0.0,
            min(
                100.0,
                priority,
            ),
        )

        learning = max(
            0.0,
            min(
                100.0,
                learning,
            ),
        )

        confidence_value = max(
            0.0,
            min(
                1.0,
                confidence_value,
            ),
        )

        # Difference from neutral learning.
        signal = (
            learning - 50.0
        )

        # Conservative maximum influence:
        # ±10 points at full confidence.
        adjustment = (
            signal
            * 0.20
            * confidence_value
        )

        adjusted = (
            priority
            + adjustment
        )

        return round(
            max(
                0.0,
                min(
                    100.0,
                    adjusted,
                ),
            ),
            2,
        )

    @staticmethod
    def _normalize(
        value: Any,
    ) -> str:
        return " ".join(
            str(value or "")
            .strip()
            .lower()
            .split()
        )


__all__ = [
    "AgentLearning",
]