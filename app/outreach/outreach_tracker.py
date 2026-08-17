from __future__ import annotations

import json
import tempfile
import uuid

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


# ============================================================
# STATUS DEFINITIONS
# ============================================================

OUTREACH_STATUSES = {
    "prepared",
    "confirmation_required",
    "sent",
    "send_failed",
    "follow_up_due",
    "replied",
    "interview",
    "closed",
    "cancelled",
}


# ============================================================
# DATA MODEL
# ============================================================


@dataclass
class OutreachRecord:
    """
    Persistent record of one recruiter/company outreach.

    The record is intentionally independent of the email sender.
    It represents the lifecycle of the outreach itself.
    """

    outreach_id: str

    job_id: str
    job_title: str
    company: str
    job_url: str

    contact_name: str
    contact_email: str
    contact_role: str
    contact_source: str

    subject: str
    resume_path: str

    status: str

    created_at: str
    updated_at: str

    sent_at: Optional[str] = None
    follow_up_at: Optional[str] = None
    replied_at: Optional[str] = None
    closed_at: Optional[str] = None

    response_status: str = ""

    error: Optional[str] = None

    notes: str = ""

    # Number of times the outreach was sent.
    send_attempts: int = 0

    # Whether the last send was performed as a dry run.
    dry_run: bool = False


# ============================================================
# TRACKER
# ============================================================


class OutreachTracker:
    """
    Persistent outreach lifecycle tracker.

    Responsibilities:

        Prepare
            ↓
        Confirmation
            ↓
        Sent
            ↓
        Follow-up
            ↓
        Replied / Interview / Closed

    The tracker:

        - stores outreach records
        - updates outreach status
        - prevents accidental duplicate records
        - tracks send attempts
        - tracks follow-up dates
        - provides filtering and summaries

    The tracker NEVER:

        - sends email
        - discovers contacts
        - opens browsers
        - stores passwords
        - stores SMTP credentials
    """

    DEFAULT_STORAGE_PATH = (
        "data/outreach/outreach.json"
    )

    def __init__(
        self,
        storage_path: str = DEFAULT_STORAGE_PATH,
    ):
        if not storage_path or not str(
            storage_path
        ).strip():
            raise ValueError(
                "storage_path cannot be empty."
            )

        self.storage_path = Path(
            str(storage_path).strip()
        )

        self._records: dict[
            str,
            OutreachRecord,
        ] = {}

        self._load()

    # ========================================================
    # STORAGE
    # ========================================================

    def _load(self) -> None:
        """
        Load existing records.

        Missing files are treated as an empty tracker.
        Invalid records are ignored rather than crashing
        the entire application.
        """

        if not self.storage_path.exists():
            self._records = {}
            return

        try:
            with self.storage_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

        except (
            OSError,
            json.JSONDecodeError,
        ):
            self._records = {}
            return

        if not isinstance(
            data,
            list,
        ):
            self._records = {}
            return

        records: dict[
            str,
            OutreachRecord,
        ] = {}

        for item in data:
            if not isinstance(
                item,
                dict,
            ):
                continue

            try:
                record = OutreachRecord(
                    **item
                )
            except TypeError:
                continue

            if not record.outreach_id:
                continue

            if (
                record.status
                not in OUTREACH_STATUSES
            ):
                continue

            records[
                record.outreach_id
            ] = record

        self._records = records

    def _save(self) -> None:
        """
        Persist records atomically.

        A temporary file is written first and then replaced
        over the target file.
        """

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = [
            asdict(record)
            for record in self._records.values()
        ]

        fd, temp_name = tempfile.mkstemp(
            prefix="outreach_",
            suffix=".tmp",
            dir=str(
                self.storage_path.parent
            ),
            text=True,
        )

        try:
            with open(
                fd,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    data,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

            Path(temp_name).replace(
                self.storage_path
            )

        except Exception:
            try:
                Path(temp_name).unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            raise

    # ========================================================
    # TIME
    # ========================================================

    @staticmethod
    def _now() -> str:
        """
        Return a UTC ISO-8601 timestamp.
        """

        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _parse_datetime(
        value: Optional[str],
    ) -> Optional[datetime]:
        """
        Parse an ISO timestamp.

        Naive timestamps are interpreted as UTC.
        """

        if not value:
            return None

        try:
            result = datetime.fromisoformat(
                str(value)
            )
        except ValueError:
            return None

        if result.tzinfo is None:
            result = result.replace(
                tzinfo=timezone.utc
            )

        return result

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def _validate_status(
        status: str,
    ) -> str:
        status = str(
            status or ""
        ).strip().lower()

        if status not in OUTREACH_STATUSES:
            raise ValueError(
                f"Invalid outreach status: {status}"
            )

        return status

    @staticmethod
    def _clean(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        return str(value).strip()

    # ========================================================
    # CREATE
    # ========================================================

    def create(
        self,
        job: dict,
        contact: dict,
        subject: str = "",
        resume_path: str = "",
        status: str = "prepared",
        follow_up_days: Optional[int] = None,
        error: Optional[str] = None,
        notes: str = "",
        dry_run: bool = False,
    ) -> OutreachRecord:
        """
        Create a persistent outreach record.

        Duplicate detection uses:

            job_id + contact_email

        If an outreach already exists for the same job/contact,
        the existing record is returned instead of creating a
        duplicate.
        """

        if not isinstance(
            job,
            dict,
        ):
            raise TypeError(
                "job must be a dictionary."
            )

        if not isinstance(
            contact,
            dict,
        ):
            raise TypeError(
                "contact must be a dictionary."
            )

        normalized_status = self._validate_status(
            status
        )

        job_id = self._clean(
            job.get("job_id")
            or job.get("id")
            or job.get("url")
        )

        job_title = self._clean(
            job.get("title")
            or job.get("job_title")
        )

        company = self._clean(
            job.get("company")
        )

        job_url = self._clean(
            job.get("url")
        )

        contact_email = self._clean(
            contact.get("email")
        ).lower()

        contact_name = self._clean(
            contact.get("name")
        )

        contact_role = self._clean(
            contact.get("role")
            or contact.get("title")
            or contact.get("position")
        )

        contact_source = self._clean(
            contact.get("source")
        )

        if not job_id:
            raise ValueError(
                "job must contain job_id, id, or url."
            )

        if not contact_email:
            raise ValueError(
                "contact must contain an email."
            )

        existing = self.find(
            job_id=job_id,
            contact_email=contact_email,
        )

        if existing is not None:
            return existing

        now = self._now()

        follow_up_at = None

        if follow_up_days is not None:
            if follow_up_days < 0:
                raise ValueError(
                    "follow_up_days cannot be negative."
                )

            follow_up_at = (
                datetime.now(
                    timezone.utc
                )
                + timedelta(
                    days=follow_up_days
                )
            ).isoformat()

        record = OutreachRecord(
            outreach_id=str(
                uuid.uuid4()
            ),
            job_id=job_id,
            job_title=job_title,
            company=company,
            job_url=job_url,
            contact_name=contact_name,
            contact_email=contact_email,
            contact_role=contact_role,
            contact_source=contact_source,
            subject=self._clean(
                subject
            ),
            resume_path=self._clean(
                resume_path
            ),
            status=normalized_status,
            created_at=now,
            updated_at=now,
            follow_up_at=follow_up_at,
            error=(
                self._clean(error)
                if error is not None
                else None
            ),
            notes=self._clean(
                notes
            ),
            dry_run=bool(
                dry_run
            ),
        )

        self._records[
            record.outreach_id
        ] = record

        self._save()

        return record

    # ========================================================
    # GET
    # ========================================================

    def get(
        self,
        outreach_id: str,
    ) -> Optional[OutreachRecord]:
        """
        Return one outreach record.
        """

        return self._records.get(
            str(outreach_id)
        )

    def get_all(self) -> list[OutreachRecord]:
        """
        Return all outreach records.
        """

        return list(
            self._records.values()
        )

    # ========================================================
    # FIND
    # ========================================================

    def find(
        self,
        job_id: Optional[str] = None,
        contact_email: Optional[str] = None,
    ) -> Optional[OutreachRecord]:
        """
        Find an outreach record by job and/or contact.
        """

        normalized_job_id = (
            self._clean(job_id)
            if job_id is not None
            else None
        )

        normalized_email = (
            self._clean(
                contact_email
            ).lower()
            if contact_email is not None
            else None
        )

        for record in self._records.values():

            if (
                normalized_job_id is not None
                and record.job_id
                != normalized_job_id
            ):
                continue

            if (
                normalized_email is not None
                and record.contact_email
                != normalized_email
            ):
                continue

            return record

        return None

    # ========================================================
    # FILTER
    # ========================================================

    def list(
        self,
        status: Optional[str] = None,
        company: Optional[str] = None,
        contact_email: Optional[str] = None,
    ) -> list[OutreachRecord]:
        """
        Return records matching the supplied filters.
        """

        normalized_status = None

        if status is not None:
            normalized_status = (
                self._validate_status(
                    status
                )
            )

        normalized_company = (
            self._clean(company).lower()
            if company is not None
            else None
        )

        normalized_email = (
            self._clean(
                contact_email
            ).lower()
            if contact_email is not None
            else None
        )

        results: list[
            OutreachRecord
        ] = []

        for record in self._records.values():

            if (
                normalized_status is not None
                and record.status
                != normalized_status
            ):
                continue

            if (
                normalized_company is not None
                and record.company.lower()
                != normalized_company
            ):
                continue

            if (
                normalized_email is not None
                and record.contact_email
                != normalized_email
            ):
                continue

            results.append(record)

        return results

    # ========================================================
    # UPDATE STATUS
    # ========================================================

    def update_status(
        self,
        outreach_id: str,
        status: str,
        error: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[OutreachRecord]:
        """
        Update the lifecycle status of an outreach.
        """

        record = self.get(
            outreach_id
        )

        if record is None:
            return None

        normalized_status = self._validate_status(
            status
        )

        now = self._now()

        record.status = normalized_status
        record.updated_at = now

        if error is not None:
            record.error = self._clean(
                error
            )

        if notes is not None:
            record.notes = self._clean(
                notes
            )

        if normalized_status == "sent":
            record.sent_at = (
                record.sent_at
                or now
            )
            record.error = None

        elif normalized_status == "replied":
            record.replied_at = (
                record.replied_at
                or now
            )

        elif normalized_status == "closed":
            record.closed_at = (
                record.closed_at
                or now
            )

        self._save()

        return record

    # ========================================================
    # SEND RESULT
    # ========================================================

    def record_send_result(
        self,
        outreach_id: str,
        success: bool,
        error: Optional[str] = None,
        dry_run: bool = False,
    ) -> Optional[OutreachRecord]:
        """
        Record the result of an email-send attempt.
        """

        record = self.get(
            outreach_id
        )

        if record is None:
            return None

        record.send_attempts += 1
        record.updated_at = self._now()
        record.dry_run = bool(
            dry_run
        )

        if success:
            record.status = "sent"
            record.sent_at = (
                record.sent_at
                or record.updated_at
            )
            record.error = None

        else:
            record.status = "send_failed"

            if error is not None:
                record.error = self._clean(
                    error
                )

        self._save()

        return record

    # ========================================================
    # FOLLOW-UP
    # ========================================================

    def schedule_follow_up(
        self,
        outreach_id: str,
        follow_up_days: int = 7,
    ) -> Optional[OutreachRecord]:
        """
        Schedule a future follow-up.

        Scheduling a follow-up does not automatically send
        anything.
        """

        if follow_up_days < 0:
            raise ValueError(
                "follow_up_days cannot be negative."
            )

        record = self.get(
            outreach_id
        )

        if record is None:
            return None

        record.follow_up_at = (
            datetime.now(
                timezone.utc
            )
            + timedelta(
                days=follow_up_days
            )
        ).isoformat()

        record.updated_at = self._now()

        self._save()

        return record

    def get_due_follow_ups(
        self,
        now: Optional[datetime] = None,
    ) -> list[OutreachRecord]:
        """
        Return sent outreach records whose follow-up date
        has arrived.

        Only records in active outreach states are returned.
        """

        if now is None:
            now = datetime.now(
                timezone.utc
            )

        if now.tzinfo is None:
            now = now.replace(
                tzinfo=timezone.utc
            )

        due: list[
            OutreachRecord
        ] = []

        for record in self._records.values():

            if record.status not in {
                "sent",
                "follow_up_due",
            }:
                continue

            follow_up = self._parse_datetime(
                record.follow_up_at
            )

            if follow_up is None:
                continue

            if follow_up <= now:
                due.append(record)

        return due

    def mark_follow_up_due(
        self,
        now: Optional[datetime] = None,
    ) -> list[OutreachRecord]:
        """
        Mark all due follow-ups as follow_up_due.

        No email is sent.
        """

        due = self.get_due_follow_ups(
            now=now
        )

        changed: list[
            OutreachRecord
        ] = []

        for record in due:

            if record.status != "follow_up_due":
                record.status = (
                    "follow_up_due"
                )
                record.updated_at = self._now()
                changed.append(record)

        if changed:
            self._save()

        return changed

    # ========================================================
    # RESPONSE
    # ========================================================

    def record_reply(
        self,
        outreach_id: str,
        response_status: str = "replied",
        notes: Optional[str] = None,
    ) -> Optional[OutreachRecord]:
        """
        Record that a recruiter/company responded.
        """

        normalized = self._validate_status(
            response_status
        )

        if normalized not in {
            "replied",
            "interview",
            "closed",
        }:
            raise ValueError(
                "response_status must be "
                "'replied', 'interview', or 'closed'."
            )

        record = self.get(
            outreach_id
        )

        if record is None:
            return None

        now = self._now()

        record.status = normalized
        record.response_status = normalized
        record.replied_at = (
            record.replied_at
            or now
        )
        record.updated_at = now

        if normalized == "closed":
            record.closed_at = (
                record.closed_at
                or now
            )

        if notes is not None:
            record.notes = self._clean(
                notes
            )

        self._save()

        return record

    # ========================================================
    # NOTES
    # ========================================================

    def add_note(
        self,
        outreach_id: str,
        note: str,
    ) -> Optional[OutreachRecord]:
        """
        Append a note to an outreach record.
        """

        record = self.get(
            outreach_id
        )

        if record is None:
            return None

        clean_note = self._clean(
            note
        )

        if not clean_note:
            raise ValueError(
                "note cannot be empty."
            )

        timestamp = self._now()

        if record.notes:
            record.notes += (
                "\n"
                f"[{timestamp}] "
                f"{clean_note}"
            )
        else:
            record.notes = (
                f"[{timestamp}] "
                f"{clean_note}"
            )

        record.updated_at = timestamp

        self._save()

        return record

    # ========================================================
    # DELETE
    # ========================================================

    def delete(
        self,
        outreach_id: str,
    ) -> bool:
        """
        Delete an outreach record.
        """

        outreach_id = str(
            outreach_id
        )

        if outreach_id not in self._records:
            return False

        del self._records[
            outreach_id
        ]

        self._save()

        return True

    # ========================================================
    # SUMMARY
    # ========================================================

    def summary(self) -> dict:
        """
        Return counts for every supported outreach status.
        """

        summary = {
            "total": len(
                self._records
            )
        }

        for status in sorted(
            OUTREACH_STATUSES
        ):
            summary[status] = sum(
                1
                for record
                in self._records.values()
                if record.status
                == status
            )

        summary[
            "send_attempts"
        ] = sum(
            record.send_attempts
            for record
            in self._records.values()
        )

        summary[
            "replied"
        ] = sum(
            1
            for record
            in self._records.values()
            if record.replied_at
        )

        summary[
            "follow_ups_scheduled"
        ] = sum(
            1
            for record
            in self._records.values()
            if record.follow_up_at
        )

        return summary

    # ========================================================
    # SERIALIZATION
    # ========================================================

    @staticmethod
    def to_dict(
        record: OutreachRecord,
    ) -> dict:
        """
        Convert an OutreachRecord into a plain dictionary.
        """

        return asdict(
            record
        )

    def to_list(self) -> list[dict]:
        """
        Return all records as dictionaries.
        """

        return [
            self.to_dict(record)
            for record in self._records.values()
        ]


__all__ = [
    "OUTREACH_STATUSES",
    "OutreachRecord",
    "OutreachTracker",
]