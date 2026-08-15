from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional


@dataclass(frozen=True)
class EmailMessage:
    sender: str
    subject: str
    body: str
    received_at: Optional[str] = None
    message_id: Optional[str] = None


@dataclass(frozen=True)
class StatusDetection:
    status: Optional[str]
    confidence: float
    reason: str


class EmailStatusReader:
    """
    Detect application status from emails and connect emails
    to jobs stored in JobStore.

    Responsibilities:
        Email
          ↓
        Status detection
          ↓
        Job matching
          ↓
        Application status update

    No external email service is accessed here.
    """

    # --------------------------------------------------------
    # STATUS PATTERNS
    # --------------------------------------------------------

    STATUS_PATTERNS = {
        "walk_in": (
            r"\bwalk[\s-]?in\b",
            r"\bwalk[\s-]?in\s+interview\b",
            r"\bwalk[\s-]?in\s+drive\b",
            r"\bwalk[\s-]?in\s+recruitment\b",
        ),

        "rejected": (
            r"\brejected\b",
            r"\bnot selected\b",
            r"\bnot been selected\b",
            r"\bunsuccessful\b",
            r"\bnot successful\b",
            r"\bwill not be moving forward\b",
            r"\bwill not move forward\b",
            r"\bregret to inform\b",
        ),

        "interview": (
            r"\binterview invitation\b",
            r"\binterview invite\b",
            r"\binvited to interview\b",
            r"\bschedule an interview\b",
            r"\bscheduled interview\b",
            r"\btechnical interview\b",
            r"\bhr interview\b",
            r"\binterview\b",
        ),

        "assessment": (
            r"\bonline assessment\b",
            r"\bassessment invitation\b",
            r"\bassessment test\b",
            r"\bcoding assessment\b",
            r"\btechnical assessment\b",
            r"\btest invitation\b",
            r"\bassessment\b",
        ),

        "shortlisted": (
            r"\bshortlisted\b",
            r"\bshortlisted for\b",
            r"\byou have been shortlisted\b",
            r"\bselected for the next round\b",
            r"\bselected for next round\b",
            r"\bselected to proceed\b",
            r"\bproceed to the next round\b",
            r"\bproceed to next round\b",
        ),
    }

    # More specific statuses must be checked first.
    STATUS_PRIORITY = (
        "walk_in",
        "rejected",
        "interview",
        "assessment",
        "shortlisted",
    )

    TRACKABLE_STATUSES = {
        "shortlisted",
        "rejected",
        "interview",
        "assessment",
        "walk_in",
    }

    # --------------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------------

    def __init__(self, monitor):
        if monitor is None:
            raise ValueError(
                "monitor cannot be None."
            )

        self.monitor = monitor

    # --------------------------------------------------------
    # NORMALIZATION
    # --------------------------------------------------------

    @staticmethod
    def normalize_text(
        value: Optional[str],
    ) -> str:
        if value is None:
            return ""

        text = str(value)

        text = text.replace(
            "\r\n",
            "\n",
        )

        text = text.replace(
            "\r",
            "\n",
        )

        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        return text.strip().lower()

    @staticmethod
    def _compact(
        value: Optional[str],
    ) -> str:
        if not value:
            return ""

        return re.sub(
            r"[^a-z0-9]+",
            "",
            str(value).lower(),
        )

    @staticmethod
    def _words(
        value: Optional[str],
    ) -> set[str]:
        if not value:
            return set()

        return {
            word
            for word in re.findall(
                r"[a-z0-9]+",
                str(value).lower(),
            )
            if len(word) >= 2
        }

    # --------------------------------------------------------
    # EMAIL VALIDATION
    # --------------------------------------------------------

    @staticmethod
    def validate_email(
        email: EmailMessage,
    ) -> None:

        if not isinstance(
            email,
            EmailMessage,
        ):
            raise TypeError(
                "email must be an EmailMessage."
            )

        if not email.sender.strip():
            raise ValueError(
                "Email sender cannot be empty."
            )

        if not email.subject.strip():
            raise ValueError(
                "Email subject cannot be empty."
            )

        if not email.body.strip():
            raise ValueError(
                "Email body cannot be empty."
            )

    # --------------------------------------------------------
    # STATUS DETECTION
    # --------------------------------------------------------

    def detect_status(
        self,
        email: EmailMessage,
    ) -> StatusDetection:

        self.validate_email(
            email
        )

        subject = self.normalize_text(
            email.subject
        )

        body = self.normalize_text(
            email.body
        )

        text = (
            f"{subject}\n{body}"
        )

        for status in self.STATUS_PRIORITY:

            patterns = self.STATUS_PATTERNS.get(
                status,
                (),
            )

            matched = []

            for pattern in patterns:

                if re.search(
                    pattern,
                    text,
                    flags=re.IGNORECASE,
                ):
                    matched.append(
                        pattern
                    )

            if matched:

                confidence = min(
                    1.0,
                    0.6
                    + (
                        0.1
                        * (
                            len(matched)
                            - 1
                        )
                    ),
                )

                return StatusDetection(
                    status=status,
                    confidence=confidence,
                    reason=(
                        f"Detected application "
                        f"status '{status}'."
                    ),
                )

        return StatusDetection(
            status=None,
            confidence=0.0,
            reason=(
                "No supported application "
                "status pattern detected."
            ),
        )

    # --------------------------------------------------------
    # JOB FIELD EXTRACTION
    # --------------------------------------------------------

    @staticmethod
    def _get_job_id(
        job: dict,
    ) -> Optional[str]:

        if not isinstance(
            job,
            dict,
        ):
            return None

        for key in (
            "job_id",
            "id",
            "url",
            "job_url",
            "application_id",
            "application_url",
        ):

            value = job.get(
                key
            )

            if value is not None:

                value = str(
                    value
                ).strip()

                if value:
                    return value

        return None

    @staticmethod
    def _get_job_title(
        job: dict,
    ) -> str:

        if not isinstance(
            job,
            dict,
        ):
            return ""

        for key in (
            "title",
            "job_title",
            "role",
            "position",
        ):

            value = job.get(
                key
            )

            if value:
                return str(
                    value
                ).strip()

        return ""

    @staticmethod
    def _get_job_company(
        job: dict,
    ) -> str:

        if not isinstance(
            job,
            dict,
        ):
            return ""

        for key in (
            "company",
            "company_name",
            "employer",
            "organization",
        ):

            value = job.get(
                key
            )

            if value:
                return str(
                    value
                ).strip()

        return ""

    # --------------------------------------------------------
    # NORMALIZE STORED JOB
    # --------------------------------------------------------

    @classmethod
    def _normalize_job(
        cls,
        job,
        inherited_id=None,
    ) -> Optional[dict]:

        if not isinstance(
            job,
            dict,
        ):
            return None

        # Direct job.
        result = dict(
            job
        )

        # Nested job representation.
        nested = result.get(
            "job"
        )

        if isinstance(
            nested,
            dict,
        ):

            result = dict(
                nested
            )

            for key in (
                "status",
                "application_status",
                "match_score",
                "selected",
                "applied_at",
                "updated_at",
            ):

                if key in job:
                    result.setdefault(
                        key,
                        job[key],
                    )

            inherited_id = (
                job.get("job_id")
                or job.get("id")
                or job.get("url")
                or inherited_id
            )

        # If the dictionary itself has no identifying
        # job fields, it may be a mapping record.
        if not cls._get_job_title(
            result
        ) and not cls._get_job_company(
            result
        ):

            return None

        # Preserve outer/mapping ID.
        if (
            cls._get_job_id(result)
            is None
            and inherited_id is not None
        ):

            result["job_id"] = str(
                inherited_id
            ).strip()

        # IMPORTANT:
        # JobStore.add_job() returns the job's stable ID.
        # In this project the job URL is also a valid ID.
        if not cls._get_job_id(
            result
        ):

            for key in (
                "url",
                "job_url",
                "application_url",
            ):

                value = result.get(
                    key
                )

                if value:

                    result["job_id"] = str(
                        value
                    ).strip()

                    break

        return result

    # --------------------------------------------------------
    # NORMALIZE JOB COLLECTION
    # --------------------------------------------------------

    @classmethod
    def _normalise_job_collection(
        cls,
        jobs,
    ) -> list[dict]:
        """
        Convert every supported JobStore representation
        into a list of job dictionaries.

        Handles:

            list[dict]

            dict[str, dict]

            {"jobs": [...]}

            {"data": [...]}

            {"applications": [...]}

            {"job": {...}}

            generators/iterables
        """

        if jobs is None:
            return []

        wrapper_keys = (
            "jobs",
            "data",
            "applications",
            "items",
            "records",
            "results",
            "tracked_applications",
        )

        output = []

        def visit(
            value,
            inherited_id=None,
        ):

            if value is None:
                return

            # --------------------------------------------
            # Dictionary
            # --------------------------------------------

            if isinstance(
                value,
                dict,
            ):

                # Direct job.
                direct = cls._normalize_job(
                    value,
                    inherited_id=inherited_id,
                )

                if direct is not None:

                    output.append(
                        direct
                    )

                    return

                # Known wrapper.
                for key in wrapper_keys:

                    if key in value:

                        visit(
                            value[key],
                            inherited_id=(
                                inherited_id
                            ),
                        )

                # Mapping:
                #
                # {
                #   "job-id": {...},
                #   "job-id-2": {...}
                # }
                for key, item in value.items():

                    if key in wrapper_keys:
                        continue

                    if isinstance(
                        item,
                        dict,
                    ):

                        visit(
                            item,
                            inherited_id=key,
                        )

                return

            # --------------------------------------------
            # List / tuple / set
            # --------------------------------------------

            if isinstance(
                value,
                (list, tuple, set),
            ):

                for item in value:

                    visit(
                        item
                    )

                return

            # --------------------------------------------
            # Generic iterable
            # --------------------------------------------

            if isinstance(
                value,
                (str, bytes),
            ):
                return

            try:

                for item in value:

                    visit(
                        item
                    )

            except TypeError:
                return

        visit(
            jobs
        )

        return output

    # --------------------------------------------------------
    # COMPANY MATCH
    # --------------------------------------------------------

    def _company_matches(
        self,
        email: EmailMessage,
        company: str,
    ) -> bool:

        if not company:
            return False

        company_compact = self._compact(
            company
        )

        if not company_compact:
            return False

        combined = (
            f"{email.sender} "
            f"{email.subject} "
            f"{email.body}"
        )

        combined_compact = self._compact(
            combined
        )

        # Exact company match.
        if company_compact in combined_compact:
            return True

        # Company word match.
        company_words = self._words(
            company
        )

        text_words = self._words(
            combined
        )

        if (
            company_words
            and company_words.issubset(
                text_words
            )
        ):
            return True

        # Sender domain match.
        sender = (
            email.sender
            or ""
        ).strip().lower()

        if "@" in sender:

            domain = sender.split(
                "@",
                1,
            )[1]

            domain_compact = self._compact(
                domain
            )

            if (
                company_compact
                in domain_compact
            ):
                return True

        return False

    # --------------------------------------------------------
    # TITLE MATCH
    # --------------------------------------------------------

    def _title_matches(
        self,
        email: EmailMessage,
        title: str,
    ) -> bool:

        if not title:
            return False

        text = (
            f"{email.subject} "
            f"{email.body}"
        )

        title_compact = self._compact(
            title
        )

        text_compact = self._compact(
            text
        )

        if (
            title_compact
            and title_compact
            in text_compact
        ):
            return True

        title_words = self._words(
            title
        )

        text_words = self._words(
            text
        )

        return bool(
            title_words
            and title_words.issubset(
                text_words
            )
        )

    # --------------------------------------------------------
    # MATCH JOB
    # --------------------------------------------------------

    def email_matches_job(
        self,
        email: EmailMessage,
        job: dict,
    ) -> bool:

        if not isinstance(
            job,
            dict,
        ):
            return False

        return (
            self._company_matches(
                email,
                self._get_job_company(
                    job
                ),
            )
            or self._title_matches(
                email,
                self._get_job_title(
                    job
                ),
            )
        )

    # --------------------------------------------------------
    # GET ALL STORED JOBS
    # --------------------------------------------------------

    def _get_stored_jobs(
        self,
    ) -> list[dict]:
        """
        Obtain jobs directly from the same JobStore used
        by ApplicationStatusMonitor.

        Multiple APIs are supported so the email reader is
        not tightly coupled to one storage implementation.
        """

        store = getattr(
            self.monitor,
            "job_store",
            None,
        )

        if store is None:
            return []

        # Preferred.
        getter = getattr(
            store,
            "get_all_jobs",
            None,
        )

        if callable(
            getter
        ):

            try:

                jobs = getter()

                normalized = (
                    self._normalise_job_collection(
                        jobs
                    )
                )

                if normalized:
                    return normalized

            except Exception:
                pass

        # Other store APIs.
        for method_name in (
            "get_all_applications",
            "get_applications",
            "get_applied_jobs",
            "list_jobs",
        ):

            getter = getattr(
                store,
                method_name,
                None,
            )

            if not callable(
                getter
            ):
                continue

            try:

                jobs = getter()

                normalized = (
                    self._normalise_job_collection(
                        jobs
                    )
                )

                if normalized:
                    return normalized

            except Exception:
                continue

        # Final monitor fallback.
        getter = getattr(
            self.monitor,
            "get_tracked_applications",
            None,
        )

        if callable(
            getter
        ):

            try:

                jobs = getter()

                return (
                    self._normalise_job_collection(
                        jobs
                    )
                )

            except Exception:
                pass

        return []

    # --------------------------------------------------------
    # FIND MATCHING JOB
    # --------------------------------------------------------

    def find_matching_job(
        self,
        email: EmailMessage,
        jobs: Optional[Iterable[dict]] = None,
    ) -> Optional[dict]:
        """
        Match email to the strongest stored job.

        Scoring:

            company match = +10
            title match   = +10
            both          = +10 bonus

        Therefore a full company + title match scores 30.
        """

        if jobs is None:

            candidates = (
                self._get_stored_jobs()
            )

        else:

            candidates = (
                self._normalise_job_collection(
                    jobs
                )
            )

        best_job = None
        best_score = 0

        for candidate in candidates:

            if not isinstance(
                candidate,
                dict,
            ):
                continue

            company = (
                self._get_job_company(
                    candidate
                )
            )

            title = (
                self._get_job_title(
                    candidate
                )
            )

            company_match = (
                self._company_matches(
                    email,
                    company,
                )
            )

            title_match = (
                self._title_matches(
                    email,
                    title,
                )
            )

            score = 0

            if company_match:
                score += 10

            if title_match:
                score += 10

            if (
                company_match
                and title_match
            ):
                score += 10

            if score > best_score:

                best_score = score

                best_job = dict(
                    candidate
                )

        if best_job is None:
            return None

        # ----------------------------------------------------
        # Guarantee job ID propagation.
        # ----------------------------------------------------

        job_id = self._get_job_id(
            best_job
        )

        if not job_id:

            job_id = (
                best_job.get("url")
                or best_job.get("job_url")
                or best_job.get(
                    "application_id"
                )
                or best_job.get(
                    "application_url"
                )
            )

        if job_id:

            best_job["job_id"] = str(
                job_id
            ).strip()

        return best_job

    # --------------------------------------------------------
    # PROCESS ONE EMAIL
    # --------------------------------------------------------

    def process_email(
        self,
        email: EmailMessage,
        jobs: Optional[Iterable[dict]] = None,
    ) -> dict:

        self.validate_email(
            email
        )

        detection = self.detect_status(
            email
        )

        # No status.
        if detection.status is None:

            return {
                "success": True,
                "status_detected": False,
                "status": None,
                "confidence": 0.0,
                "reason": detection.reason,
                "job_id": None,
                "job": None,
                "email": email,
            }

        # Find job.
        job = self.find_matching_job(
            email=email,
            jobs=jobs,
        )

        # No job.
        if job is None:

            return {
                "success": True,
                "status_detected": True,
                "status": detection.status,
                "confidence": detection.confidence,
                "reason": (
                    f"{detection.reason} "
                    "No matching stored job found."
                ),
                "job_id": None,
                "job": None,
                "email": email,
            }

        # Get ID.
        job_id = self._get_job_id(
            job
        )

        if not job_id:

            job_id = (
                job.get("url")
                or job.get("job_url")
                or job.get(
                    "application_id"
                )
                or job.get(
                    "application_url"
                )
            )

        if not job_id:

            return {
                "success": False,
                "status_detected": True,
                "status": detection.status,
                "confidence": detection.confidence,
                "reason": (
                    "Matching job was found "
                    "but no usable job ID exists."
                ),
                "job_id": None,
                "job": job,
                "email": email,
            }

        job_id = str(
            job_id
        ).strip()

        job["job_id"] = job_id

        return {
            "success": True,
            "status_detected": True,
            "status": detection.status,
            "confidence": detection.confidence,
            "reason": detection.reason,
            "job_id": job_id,
            "job": job,
            "email": email,
        }

    # --------------------------------------------------------
    # UPDATE APPLICATION
    # --------------------------------------------------------

    def update_application_from_email(
        self,
        email: EmailMessage,
        jobs: Optional[Iterable[dict]] = None,
    ) -> dict:

        result = self.process_email(
            email=email,
            jobs=jobs,
        )

        if not result["success"]:
            return result

        if not result["status_detected"]:
            return {
                **result,
                "changed": False,
                "notification_required": False,
            }

        job_id = result.get(
            "job_id"
        )

        status = result.get(
            "status"
        )

        if not job_id:
            return {
                **result,
                "changed": False,
                "notification_required": False,
            }

        if (
            status
            not in self.TRACKABLE_STATUSES
        ):
            return {
                **result,
                "changed": False,
                "notification_required": False,
            }

        try:

            monitor_result = (
                self.monitor.detect_status(
                    job_id=job_id,
                    detected_status=status,
                )
            )

        except Exception as exc:

            return {
                **result,
                "success": False,
                "changed": False,
                "notification_required": False,
                "error": str(exc),
            }

        return {
            **result,
            "monitor_result": monitor_result,
            "changed": monitor_result.get(
                "changed",
                False,
            ),
            "notification_required": (
                monitor_result.get(
                    "notification_required",
                    False,
                )
            ),
        }

    # --------------------------------------------------------
    # PROCESS MULTIPLE EMAILS
    # --------------------------------------------------------

    def process_emails(
        self,
        emails: Iterable[EmailMessage],
        jobs: Optional[Iterable[dict]] = None,
    ) -> list[dict]:

        if emails is None:
            return []

        # Explicit jobs are frozen once.
        #
        # If jobs=None, every email queries the current
        # JobStore independently.
        jobs_list = (
            list(jobs)
            if jobs is not None
            else None
        )

        results = []

        for email in emails:

            try:

                result = (
                    self.update_application_from_email(
                        email=email,
                        jobs=jobs_list,
                    )
                )

            except Exception as exc:

                result = {
                    "success": False,
                    "status_detected": False,
                    "status": None,
                    "confidence": 0.0,
                    "reason": str(exc),
                    "job_id": None,
                    "job": None,
                    "email": email,
                    "changed": False,
                    "notification_required": False,
                }

            results.append(
                result
            )

        return results

    # --------------------------------------------------------
    # STATUS HELPERS
    # --------------------------------------------------------

    @classmethod
    def supported_statuses(
        cls,
    ) -> list[str]:

        return [
            "shortlisted",
            "rejected",
            "interview",
            "assessment",
            "walk_in",
        ]

    @classmethod
    def is_trackable_status(
        cls,
        status: Optional[str],
    ) -> bool:

        return (
            status
            in cls.TRACKABLE_STATUSES
        )