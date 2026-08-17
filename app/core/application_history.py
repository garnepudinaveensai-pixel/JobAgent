from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from app.core.job_deduplicator import JobDeduplicator


HISTORY_STATUSES = {
    "discovered",
    "review",
    "skipped",
    "prepared",
    "confirmation_required",
    "applied",
    "outreach_sent",
    "captcha_detected",
    "login_required",
    "human_action_required",
    "job_unavailable",
    "form_not_found",
    "navigation_failed",
    "validation_failed",
    "application_prepare_failed",
    "submission_timeout",
    "submission_failed",
    "send_failed",
    "error",
}


@dataclass(frozen=True)
class ApplicationHistoryRecord:
    """Persistent record of one job/application lifecycle."""

    history_id: str
    identity: str
    job_id: str
    job_title: str
    company: str
    location: str
    job_url: str
    decision: str
    status: str
    attempts: int
    created_at: str
    updated_at: str
    last_attempt_at: Optional[str] = None
    applied_at: Optional[str] = None
    human_action_required: bool = False
    submitted: bool = False
    sent: bool = False
    error: Optional[str] = None
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ApplicationHistory:
    """
    Persistent application history and duplicate-prevention store.

    Identity priority:
        1. canonical job URL
        2. explicit job_id/id
        3. company + title + location
        4. company + title

    A record is updated rather than duplicated when the same job
    is encountered again. Storage is JSON and writes are atomic.
    """

    def __init__(
        self,
        storage_path: str = "data/application_history.json",
    ) -> None:
        value = str(storage_path or "").strip()
        if not value:
            raise ValueError("storage_path cannot be empty.")

        self.storage_path = Path(value)
        self._records: dict[str, ApplicationHistoryRecord] = {}
        self._load()

    # --------------------------------------------------------
    # TIME / NORMALIZATION
    # --------------------------------------------------------

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_status(status: str) -> str:
        value = str(status or "").strip().lower()
        if value not in HISTORY_STATUSES:
            raise ValueError(f"Invalid application history status: {value}")
        return value

    @classmethod
    def identity_for(cls, job: Mapping[str, Any]) -> str:
        if not isinstance(job, Mapping):
            raise TypeError("job must be a mapping.")

        url = JobDeduplicator.canonicalize_url(
            cls._clean(job.get("url"))
        )
        if url:
            return f"url:{url}"

        job_id = cls._clean(job.get("job_id") or job.get("id"))
        if job_id:
            return f"id:{job_id.lower()}"

        company = " ".join(cls._clean(job.get("company")).lower().split())
        title = " ".join(
            cls._clean(job.get("title") or job.get("job_title")).lower().split()
        )
        location = " ".join(cls._clean(job.get("location")).lower().split())

        if company and title and location:
            return f"detail:{company}|{title}|{location}"

        if company and title:
            return f"basic:{company}|{title}"

        raise ValueError(
            "job must contain a url, job_id/id, or company and title."
        )

    # --------------------------------------------------------
    # PERSISTENCE
    # --------------------------------------------------------

    def _load(self) -> None:
        if not self.storage_path.exists():
            return

        try:
            with self.storage_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(data, list):
            return

        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                record = ApplicationHistoryRecord(**item)
                if record.history_id and record.identity:
                    self._records[record.identity] = record
            except (TypeError, ValueError):
                continue

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = [asdict(record) for record in self._records.values()]
        fd, temp_name = tempfile.mkstemp(
            prefix="application_history_",
            suffix=".tmp",
            dir=str(self.storage_path.parent),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            Path(temp_name).replace(self.storage_path)
        except Exception:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass
            raise

    # --------------------------------------------------------
    # QUERY
    # --------------------------------------------------------

    def get(self, job: Mapping[str, Any]) -> Optional[ApplicationHistoryRecord]:
        return self._records.get(self.identity_for(job))

    def get_by_identity(self, identity: str) -> Optional[ApplicationHistoryRecord]:
        return self._records.get(self._clean(identity))

    def has(self, job: Mapping[str, Any]) -> bool:
        return self.get(job) is not None

    def is_processed(
        self,
        job: Mapping[str, Any],
        *,
        include_skipped: bool = True,
    ) -> bool:
        record = self.get(job)
        if record is None:
            return False
        if include_skipped:
            return True
        return record.status != "skipped"

    def list_records(
        self,
        *,
        status: Optional[str] = None,
    ) -> list[ApplicationHistoryRecord]:
        if status is None:
            return list(self._records.values())
        normalized = self._normalize_status(status)
        return [
            record
            for record in self._records.values()
            if record.status == normalized
        ]

    def count(self, status: Optional[str] = None) -> int:
        return len(self.list_records(status=status))

    # --------------------------------------------------------
    # WRITE / UPDATE
    # --------------------------------------------------------

    def record(
        self,
        job: Mapping[str, Any],
        *,
        decision: str = "",
        status: str = "discovered",
        attempts: Optional[int] = None,
        human_action_required: bool = False,
        submitted: bool = False,
        sent: bool = False,
        error: Optional[str] = None,
        notes: str = "",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ApplicationHistoryRecord:
        if not isinstance(job, Mapping):
            raise TypeError("job must be a mapping.")

        identity = self.identity_for(job)
        normalized_status = self._normalize_status(status)
        now = self._now()
        existing = self._records.get(identity)

        if existing is None:
            record = ApplicationHistoryRecord(
                history_id=str(uuid.uuid4()),
                identity=identity,
                job_id=self._clean(job.get("job_id") or job.get("id") or identity),
                job_title=self._clean(job.get("title") or job.get("job_title")),
                company=self._clean(job.get("company")),
                location=self._clean(job.get("location")),
                job_url=self._clean(job.get("url")),
                decision=self._clean(decision).lower(),
                status=normalized_status,
                attempts=max(0, int(attempts or 0)),
                created_at=now,
                updated_at=now,
                last_attempt_at=now if attempts else None,
                applied_at=now if submitted and normalized_status == "applied" else None,
                human_action_required=bool(human_action_required),
                submitted=bool(submitted),
                sent=bool(sent),
                error=self._clean(error) if error else None,
                notes=self._clean(notes),
                metadata=dict(metadata or {}),
            )
        else:
            next_attempts = (
                existing.attempts
                if attempts is None
                else max(0, int(attempts))
            )
            if normalized_status in {
                "prepared",
                "confirmation_required",
                "applied",
                "submission_timeout",
                "submission_failed",
                "application_prepare_failed",
            } and attempts is None:
                next_attempts = existing.attempts + 1

            merged_metadata = dict(existing.metadata)
            if metadata:
                merged_metadata.update(dict(metadata))

            applied_at = existing.applied_at
            if submitted and applied_at is None:
                applied_at = now

            record = ApplicationHistoryRecord(
                history_id=existing.history_id,
                identity=identity,
                job_id=self._clean(job.get("job_id") or job.get("id")) or existing.job_id,
                job_title=self._clean(job.get("title") or job.get("job_title")) or existing.job_title,
                company=self._clean(job.get("company")) or existing.company,
                location=self._clean(job.get("location")) or existing.location,
                job_url=self._clean(job.get("url")) or existing.job_url,
                decision=self._clean(decision).lower() or existing.decision,
                status=normalized_status,
                attempts=next_attempts,
                created_at=existing.created_at,
                updated_at=now,
                last_attempt_at=now if attempts is not None or next_attempts != existing.attempts else existing.last_attempt_at,
                applied_at=applied_at,
                human_action_required=bool(human_action_required),
                submitted=bool(submitted),
                sent=bool(sent),
                error=self._clean(error) if error else None,
                notes=self._clean(notes) or existing.notes,
                metadata=merged_metadata,
            )

        self._records[identity] = record
        self._save()
        return record

    def update(
        self,
        job: Mapping[str, Any],
        *,
        decision: Optional[str] = None,
        status: Optional[str] = None,
        human_action_required: Optional[bool] = None,
        submitted: Optional[bool] = None,
        sent: Optional[bool] = None,
        error: Optional[str] = None,
        notes: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ApplicationHistoryRecord:
        existing = self.get(job)
        if existing is None:
            return self.record(
                job,
                decision=decision or "",
                status=status or "discovered",
                human_action_required=bool(human_action_required),
                submitted=bool(submitted),
                sent=bool(sent),
                error=error,
                notes=notes or "",
                metadata=metadata,
            )

        return self.record(
            job,
            decision=decision if decision is not None else existing.decision,
            status=status if status is not None else existing.status,
            attempts=existing.attempts,
            human_action_required=(
                existing.human_action_required
                if human_action_required is None
                else human_action_required
            ),
            submitted=existing.submitted if submitted is None else submitted,
            sent=existing.sent if sent is None else sent,
            error=error if error is not None else existing.error,
            notes=notes if notes is not None else existing.notes,
            metadata=metadata,
        )

    def remove(self, job: Mapping[str, Any]) -> bool:
        identity = self.identity_for(job)
        if identity not in self._records:
            return False
        del self._records[identity]
        self._save()
        return True


__all__ = [
    "ApplicationHistory",
    "ApplicationHistoryRecord",
    "HISTORY_STATUSES",
]
