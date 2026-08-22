from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


class AgentMemory:
    """
    Persistent, deterministic memory for JobAgent.

    Stores application/job outcomes as JSON and provides
    filtered history for AgentLearning.

    The memory layer intentionally does not contain scoring logic.
    """

    DEFAULT_FILENAME = "agent_memory.json"

    def __init__(
        self,
        path: str | Path | None = None,
    ) -> None:
        if path is None:
            path = (
                Path("data")
                / self.DEFAULT_FILENAME
            )

        self.path = Path(path)
        self._records: list[dict[str, Any]] = []

        self.load()

    # ============================================================
    # STORAGE
    # ============================================================

    def load(self) -> list[dict[str, Any]]:
        """
        Load memory from disk.

        Missing or malformed files are treated as empty memory.
        """

        if not self.path.exists():
            self._records = []
            return self.records()

        try:
            raw = self.path.read_text(
                encoding="utf-8"
            )

            data = json.loads(raw)

        except (
            OSError,
            json.JSONDecodeError,
        ):
            self._records = []
            return self.records()

        if not isinstance(data, list):
            self._records = []
            return self.records()

        self._records = [
            dict(item)
            for item in data
            if isinstance(
                item,
                Mapping,
            )
        ]

        return self.records()

    def save(self) -> None:
        """
        Persist memory to disk.
        """

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = json.dumps(
            self._records,
            indent=2,
            ensure_ascii=False,
        )

        self.path.write_text(
            payload,
            encoding="utf-8",
        )

    # ============================================================
    # RECORDING
    # ============================================================

    def record(
        self,
        event: str,
        *,
        job_id: str | None = None,
        role_class: str | None = None,
        outcome: str | None = None,
        application_route: str | None = None,
        priority_score: float | None = None,
        match_score: float | None = None,
        metadata: Mapping[str, Any] | None = None,
        save: bool = True,
        **extra: Any,
    ) -> dict[str, Any]:
        """
        Record one agent event.

        The method is intentionally flexible so existing pipeline
        objects can provide additional fields without requiring
        changes to the memory schema.
        """

        normalized_event = self._text(
            event
        )

        if not normalized_event:
            raise ValueError(
                "event must not be empty."
            )

        record: dict[str, Any] = {
            "event": normalized_event,
        }

        self._add_if_present(
            record,
            "job_id",
            job_id,
        )

        self._add_if_present(
            record,
            "role_class",
            role_class,
        )

        self._add_if_present(
            record,
            "outcome",
            outcome,
        )

        self._add_if_present(
            record,
            "application_route",
            application_route,
        )

        if priority_score is not None:
            record[
                "priority_score"
            ] = self._number(
                priority_score
            )

        if match_score is not None:
            record[
                "match_score"
            ] = self._number(
                match_score
            )

        if metadata is not None:
            record[
                "metadata"
            ] = dict(metadata)

        for key, value in extra.items():
            if value is not None:
                record[key] = value

        self._records.append(record)

        if save:
            self.save()

        return dict(record)

    # ============================================================
    # APPLICATION OUTCOME
    # ============================================================

    def record_application_outcome(
        self,
        *,
        outcome: str,
        job_id: str | None = None,
        role_class: str | None = None,
        application_route: str | None = None,
        priority_score: float | None = None,
        match_score: float | None = None,
        metadata: Mapping[str, Any] | None = None,
        save: bool = True,
        **extra: Any,
    ) -> dict[str, Any]:
        """
        Record an application outcome in the format consumed by
        AgentLearning.
        """

        normalized_outcome = self._text(
            outcome
        )

        if not normalized_outcome:
            raise ValueError(
                "outcome must not be empty."
            )

        return self.record(
            "application_outcome",
            job_id=job_id,
            role_class=role_class,
            outcome=normalized_outcome,
            application_route=application_route,
            priority_score=priority_score,
            match_score=match_score,
            metadata=metadata,
            save=save,
            **extra,
        )

    # ============================================================
    # QUERY
    # ============================================================

    def records(self) -> list[dict[str, Any]]:
        """
        Return a defensive copy of all records.
        """

        return [
            dict(record)
            for record in self._records
        ]

    def history(
        self,
        *,
        role_class: str | None = None,
        event: str | None = None,
        outcome: str | None = None,
        job_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return filtered memory records.
        """

        role = self._normalize(
            role_class
        )

        event_value = self._normalize(
            event
        )

        outcome_value = self._normalize(
            outcome
        )

        job_value = self._normalize(
            job_id
        )

        result: list[
            dict[str, Any]
        ] = []

        for record in self._records:
            if role and (
                self._normalize(
                    record.get(
                        "role_class"
                    )
                )
                != role
            ):
                continue

            if event_value and (
                self._normalize(
                    record.get(
                        "event"
                    )
                )
                != event_value
            ):
                continue

            if outcome_value and (
                self._normalize(
                    record.get(
                        "outcome"
                    )
                )
                != outcome_value
            ):
                continue

            if job_value and (
                self._normalize(
                    record.get(
                        "job_id"
                    )
                )
                != job_value
            ):
                continue

            result.append(
                dict(record)
            )

        return result

    def application_history(
        self,
        *,
        role_class: str | None = None,
        job_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return only application outcome records.

        This is the primary interface for AgentLearning.
        """

        return self.history(
            role_class=role_class,
            event="application_outcome",
            job_id=job_id,
        )

    # ============================================================
    # STATISTICS
    # ============================================================

    def count(
        self,
        *,
        role_class: str | None = None,
        event: str | None = None,
        outcome: str | None = None,
    ) -> int:
        return len(
            self.history(
                role_class=role_class,
                event=event,
                outcome=outcome,
            )
        )

    def clear(
        self,
        *,
        save: bool = True,
    ) -> None:
        """
        Clear all in-memory records.
        """

        self._records = []

        if save:
            self.save()

    # ============================================================
    # HELPERS
    # ============================================================

    @staticmethod
    def _text(
        value: Any,
    ) -> str:
        return " ".join(
            str(value or "")
            .strip()
            .split()
        )

    @classmethod
    def _normalize(
        cls,
        value: Any,
    ) -> str:
        return cls._text(
            value
        ).lower()

    @staticmethod
    def _number(
        value: Any,
    ) -> float:
        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    @staticmethod
    def _add_if_present(
        target: dict[str, Any],
        key: str,
        value: Any,
    ) -> None:
        if value is not None:
            target[key] = value


__all__ = [
    "AgentMemory",
]