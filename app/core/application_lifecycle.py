from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.application_history import ApplicationHistory


@dataclass(frozen=True)
class LifecycleAction:
    """
    Describes the next safe action for an application.
    """

    action: str
    status: str
    reason: str
    eligible: bool
    requires_human_action: bool = False
    due_at: Optional[str] = None
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


class ApplicationLifecycle:
    """
    Determines what should happen next based on application history.

    This class does not submit applications or send outreach.
    It only evaluates lifecycle state and returns a safe action.
    """

    RETRYABLE_STATUSES = frozenset(
        {
            "submission_failed",
            "send_failed",
            "navigation_failed",
            "application_prepare_failed",
            "validation_failed",
        }
    )

    HUMAN_ACTION_STATUSES = frozenset(
        {
            "captcha_detected",
            "login_required",
            "human_action_required",
            "confirmation_required",
        }
    )

    CLOSED_STATUSES = frozenset(
        {
            "rejected",
            "withdrawn",
            "closed",
            "job_unavailable",
        }
    )

    COMPLETED_STATUSES = frozenset(
        {
            "applied",
            "submitted",
            "outreach_sent",
        }
    )

    def __init__(
        self,
        history: ApplicationHistory,
        *,
        retry_delay_minutes: int = 60,
        follow_up_delay_days: int = 7,
        max_retries: int = 3,
    ):
        if history is None:
            raise ValueError(
                "history is required."
            )

        if retry_delay_minutes < 0:
            raise ValueError(
                "retry_delay_minutes must be non-negative."
            )

        if follow_up_delay_days < 0:
            raise ValueError(
                "follow_up_delay_days must be non-negative."
            )

        if max_retries < 0:
            raise ValueError(
                "max_retries must be non-negative."
            )

        self.history = history
        self.retry_delay_minutes = (
            retry_delay_minutes
        )
        self.follow_up_delay_days = (
            follow_up_delay_days
        )
        self.max_retries = max_retries

    # ========================================================
    # TIME / VALUE HELPERS
    # ========================================================

    @staticmethod
    def _now() -> datetime:
        return datetime.now(
            timezone.utc
        )

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> Optional[datetime]:
        if not value:
            return None

        if isinstance(value, datetime):
            result = value
        else:
            try:
                result = datetime.fromisoformat(
                    str(value)
                )
            except (
                TypeError,
                ValueError,
            ):
                return None

        if result.tzinfo is None:
            result = result.replace(
                tzinfo=timezone.utc
            )

        return result

    @staticmethod
    def _record_value(
        record: Any,
        name: str,
        default: Any = None,
    ) -> Any:
        if isinstance(record, dict):
            return record.get(
                name,
                default,
            )

        return getattr(
            record,
            name,
            default,
        )

    def _retry_count(
        self,
        record: Any,
    ) -> int:
        value = self._record_value(
            record,
            "attempts",
            0,
        )

        try:
            return max(
                0,
                int(value),
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0

    # ========================================================
    # HISTORY
    # ========================================================

    def get_history(
        self,
        job: Dict[str, Any],
    ) -> Any:
        if not isinstance(
            job,
            dict,
        ):
            raise TypeError(
                "job must be a dictionary."
            )

        return self.history.get(job)

    # ========================================================
    # EVALUATE
    # ========================================================

    def evaluate(
        self,
        job: Dict[str, Any],
    ) -> LifecycleAction:
        if not isinstance(
            job,
            dict,
        ):
            raise TypeError(
                "job must be a dictionary."
            )

        record = self.get_history(
            job
        )

        if record is None:
            return LifecycleAction(
                action="apply",
                status="new",
                reason=(
                    "No application history exists."
                ),
                eligible=True,
            )

        status = str(
            self._record_value(
                record,
                "status",
                "",
            )
        ).strip().lower()

        attempts = self._retry_count(
            record
        )

        # ----------------------------------------------------
        # COMPLETED
        # ----------------------------------------------------

        if status in self.COMPLETED_STATUSES:
            return LifecycleAction(
                action="follow_up",
                status=status,
                reason=(
                    "Application has already been "
                    "completed and is eligible for "
                    "follow-up."
                ),
                eligible=True,
                metadata={
                    "attempts": attempts,
                },
            )

        # ----------------------------------------------------
        # HUMAN ACTION
        # ----------------------------------------------------

        if status in self.HUMAN_ACTION_STATUSES:
            return LifecycleAction(
                action="human_action",
                status=status,
                reason=(
                    "Human intervention is required "
                    "before JobAgent can continue."
                ),
                eligible=False,
                requires_human_action=True,
                metadata={
                    "attempts": attempts,
                },
            )

        # ----------------------------------------------------
        # CLOSED
        # ----------------------------------------------------

        if status in self.CLOSED_STATUSES:
            return LifecycleAction(
                action="closed",
                status=status,
                reason=(
                    "The application or job lifecycle "
                    "is closed."
                ),
                eligible=False,
                metadata={
                    "attempts": attempts,
                },
            )

        # ----------------------------------------------------
        # RETRY
        # ----------------------------------------------------

        if status in self.RETRYABLE_STATUSES:
            if attempts >= self.max_retries:
                return LifecycleAction(
                    action="retry_exhausted",
                    status=status,
                    reason=(
                        "Maximum retry attempts "
                        "have been reached."
                    ),
                    eligible=False,
                    metadata={
                        "attempts": attempts,
                        "max_retries": self.max_retries,
                    },
                )

            updated_at = self._parse_datetime(
                self._record_value(
                    record,
                    "updated_at",
                )
            )

            due_at = None

            if updated_at is not None:
                due = (
                    updated_at
                    + timedelta(
                        minutes=(
                            self.retry_delay_minutes
                        )
                    )
                )

                due_at = due.isoformat()

                if self._now() < due:
                    return LifecycleAction(
                        action="wait_retry",
                        status=status,
                        reason=(
                            "Retry is allowed but "
                            "the retry delay has "
                            "not elapsed."
                        ),
                        eligible=False,
                        due_at=due_at,
                        metadata={
                            "attempts": attempts,
                            "max_retries": (
                                self.max_retries
                            ),
                        },
                    )

            return LifecycleAction(
                action="retry",
                status=status,
                reason=(
                    "The previous attempt failed "
                    "and the application remains "
                    "retryable."
                ),
                eligible=True,
                due_at=due_at,
                metadata={
                    "attempts": attempts,
                    "max_retries": self.max_retries,
                },
            )

        # ----------------------------------------------------
        # UNKNOWN
        # ----------------------------------------------------

        return LifecycleAction(
            action="review",
            status=status or "unknown",
            reason=(
                "The historical state is not "
                "explicitly classified and requires "
                "human review."
            ),
            eligible=False,
            requires_human_action=True,
            metadata={
                "attempts": attempts,
            },
        )

    # ========================================================
    # FOLLOW-UP
    # ========================================================

    def follow_up_due(
        self,
        job: Dict[str, Any],
    ) -> LifecycleAction:
        if not isinstance(
            job,
            dict,
        ):
            raise TypeError(
                "job must be a dictionary."
            )

        record = self.get_history(
            job
        )

        if record is None:
            return LifecycleAction(
                action="none",
                status="new",
                reason=(
                    "No application exists."
                ),
                eligible=False,
            )

        status = str(
            self._record_value(
                record,
                "status",
                "",
            )
        ).strip().lower()

        if status not in self.COMPLETED_STATUSES:
            return LifecycleAction(
                action="none",
                status=status,
                reason=(
                    "Application is not in a "
                    "completed state eligible "
                    "for follow-up."
                ),
                eligible=False,
            )

        updated_at = self._parse_datetime(
            self._record_value(
                record,
                "updated_at",
            )
        )

        if updated_at is None:
            return LifecycleAction(
                action="follow_up",
                status=status,
                reason=(
                    "Application is completed but "
                    "no timestamp is available."
                ),
                eligible=True,
            )

        due = (
            updated_at
            + timedelta(
                days=self.follow_up_delay_days
            )
        )

        if self._now() < due:
            return LifecycleAction(
                action="wait_follow_up",
                status=status,
                reason=(
                    "Follow-up is not due yet."
                ),
                eligible=False,
                due_at=due.isoformat(),
            )

        return LifecycleAction(
            action="follow_up",
            status=status,
            reason=(
                "Follow-up delay has elapsed."
            ),
            eligible=True,
            due_at=due.isoformat(),
        )

    # ========================================================
    # BATCH
    # ========================================================

    def evaluate_many(
        self,
        jobs: List[Dict[str, Any]],
    ) -> List[LifecycleAction]:
        if not isinstance(
            jobs,
            list,
        ):
            raise TypeError(
                "jobs must be a list."
            )

        return [
            self.evaluate(job)
            for job in jobs
        ]

    def follow_ups_due(
        self,
        jobs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not isinstance(
            jobs,
            list,
        ):
            raise TypeError(
                "jobs must be a list."
            )

        results = []

        for job in jobs:
            action = self.follow_up_due(
                job
            )

            if action.eligible:
                results.append(
                    {
                        "job": job,
                        "action": action,
                    }
                )

        return results