from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from app.outreach.contact_selector import (
    ContactSelection,
    ContactSelector,
)
from app.outreach.email_composer import (
    EmailComposer,
)
from app.outreach.email_sender import (
    EmailSender,
)
from app.outreach.outreach_tracker import (
    OutreachRecord,
    OutreachTracker,
)


_MISSING = object()


# ============================================================
# RESULT
# ============================================================


@dataclass(frozen=True)
class OutreachResult:
    """
    Result of an outreach preparation or sending operation.

    tracker_id contains the persistent OutreachTracker ID when
    tracking is enabled.
    """

    success: bool
    status: str
    email: Optional[str] = None
    subject: str = ""
    message: str = ""
    attachment: Optional[str] = None
    error: Optional[str] = None
    dry_run: bool = False
    tracker_id: Optional[str] = None


# ============================================================
# PIPELINE
# ============================================================


class OutreachPipeline:
    """
    Coordinates the complete recruiter outreach workflow.

    Flow:

        contacts
            ↓
        contact selection
            ↓
        email composition
            ↓
        OutreachTracker
            ↓
        human confirmation
            ↓
        email sending
            ↓
        OutreachTracker
            ↓
        result

    Responsibilities:

        - Select the best contact.
        - Validate job/candidate input.
        - Compose outreach emails.
        - Attach/reference the selected resume.
        - Respect explicit confirmation.
        - Send only when explicitly confirmed.
        - Track prepared outreach.
        - Track successful sends.
        - Track failed sends.
        - Preserve compatibility with existing
          composer/sender interfaces.

    This class does NOT:

        - discover contacts
        - perform browser automation
        - store passwords
        - request OTPs
        - expose authentication credentials

    Safety:

        The default EmailSender remains dry-run.

        Real sending requires:
            1. An explicitly configured sender.
            2. confirm=True.
    """

    def __init__(
        self,
        contact_selector: Optional[
            ContactSelector
        ] = None,
        email_composer: Optional[
            EmailComposer
        ] = None,
        email_sender: Optional[
            EmailSender
        ] = None,
        outreach_tracker: Optional[
            OutreachTracker
        ] = None,
    ):
        self.contact_selector = (
            contact_selector
            if contact_selector is not None
            else ContactSelector()
        )

        self.email_composer = (
            email_composer
            if email_composer is not None
            else EmailComposer()
        )

        # Default sender is always dry-run.
        #
        # A real sender must be explicitly injected.
        self.email_sender = (
            email_sender
            if email_sender is not None
            else EmailSender(
                dry_run=True
            )
        )

        # Tracking is optional for backward compatibility.
        self.outreach_tracker = (
            outreach_tracker
        )

    # ========================================================
    # CONTACT SELECTION
    # ========================================================

    def select_contact(
        self,
        contacts: Iterable[dict],
        job: Optional[dict] = None,
    ) -> Optional[ContactSelection]:
        """
        Select the highest-ranked relevant contact.
        """

        return self.contact_selector.select_best_contact(
            contacts,
            job=job,
        )

    # ========================================================
    # PREPARATION
    # ========================================================

    def prepare_outreach(
        self,
        contacts: Iterable[dict],
        job: dict,
        candidate: Any = _MISSING,
        resume_path: Optional[str] = None,
    ) -> OutreachResult:
        """
        Prepare an outreach email.

        No email is sent.

        When an OutreachTracker is configured, a persistent
        record with status='prepared' is created.
        """

        self._validate_job(job)

        candidate_data = self._normalize_candidate(
            candidate
        )

        contact = self.select_contact(
            contacts,
            job=job,
        )

        if contact is None:
            return OutreachResult(
                success=False,
                status="no_suitable_contact",
            )

        try:
            composed = self._compose(
                job=job,
                candidate=candidate_data,
                contact=contact.contact,
                resume_path=resume_path,
            )

            result = self._build_prepared_result(
                composed=composed,
                selected_contact=contact,
                resume_path=resume_path,
            )

            tracker_record = (
                self._track_prepared(
                    job=job,
                    contact=contact,
                    result=result,
                )
            )

            if tracker_record is not None:
                return self._with_tracker_id(
                    result,
                    tracker_record.outreach_id,
                )

            return result

        except Exception as exc:
            return OutreachResult(
                success=False,
                status="composition_failed",
                email=contact.email,
                error=str(exc),
            )

    # ========================================================
    # COMPOSITION
    # ========================================================

    def compose_outreach(
        self,
        contacts: Iterable[dict],
        job: dict,
        candidate: Any = _MISSING,
        resume_path: Optional[str] = None,
    ) -> Any:
        """
        Return the actual result produced by the configured
        composer.

        Supports both candidate-aware and legacy composers.
        """

        self._validate_job(job)

        candidate_data = self._normalize_candidate(
            candidate
        )

        contact = self.select_contact(
            contacts,
            job=job,
        )

        if contact is None:
            raise ValueError(
                "No suitable outreach contact found."
            )

        return self._compose(
            job=job,
            candidate=candidate_data,
            contact=contact.contact,
            resume_path=resume_path,
        )

    # ========================================================
    # SEND
    # ========================================================

    def send_outreach(
        self,
        contacts: Iterable[dict],
        job: dict,
        candidate: Any = _MISSING,
        resume_path: Optional[str] = None,
        confirm: bool = False,
    ) -> OutreachResult:
        """
        Prepare and optionally send outreach.

        confirm=False:
            Nothing is sent.

        confirm=True:
            The configured sender is invoked.

        Explicit confirmation is mandatory before an actual
        sender call.
        """

        self._validate_job(job)

        candidate_data = self._normalize_candidate(
            candidate
        )

        # ----------------------------------------------------
        # CONFIRMATION GATE
        # ----------------------------------------------------

        if not confirm:
            prepared = self.prepare_outreach(
                contacts=contacts,
                job=job,
                candidate=candidate_data,
                resume_path=resume_path,
            )

            if not prepared.success:
                return prepared

            tracker_id = (
                self._mark_confirmation_required(
                    prepared
                )
            )

            confirmation_result = OutreachResult(
                success=True,
                status="confirmation_required",
                email=prepared.email,
                subject=prepared.subject,
                message=prepared.message,
                attachment=prepared.attachment,
            )

            if tracker_id is not None:
                return self._with_tracker_id(
                    confirmation_result,
                    tracker_id,
                )

            return confirmation_result

        # ----------------------------------------------------
        # COMPOSITION
        # ----------------------------------------------------

        try:
            selected_contact = self.select_contact(
                contacts,
                job=job,
            )

            if selected_contact is None:
                return OutreachResult(
                    success=False,
                    status="no_suitable_contact",
                )

            composed = self._compose(
                job=job,
                candidate=candidate_data,
                contact=selected_contact.contact,
                resume_path=resume_path,
            )

        except ValueError as exc:
            return OutreachResult(
                success=False,
                status="no_suitable_contact",
                error=str(exc),
            )

        except Exception as exc:
            return OutreachResult(
                success=False,
                status="composition_failed",
                error=str(exc),
            )

        # ----------------------------------------------------
        # ENSURE TRACKING RECORD EXISTS
        # ----------------------------------------------------

        tracker_record = (
            self._ensure_tracking_record(
                job=job,
                contact=selected_contact,
                composed=composed,
                resume_path=resume_path,
            )
        )

        # ----------------------------------------------------
        # SEND
        # ----------------------------------------------------

        try:
            sender_result = self._send(
                composed=composed,
                contact=selected_contact,
                resume_path=resume_path,
            )

        except Exception as exc:
            result = OutreachResult(
                success=False,
                status="send_failed",
                email=self._get_value(
                    composed,
                    "recipient",
                    default=selected_contact.email,
                ),
                subject=self._get_value(
                    composed,
                    "subject",
                    default="",
                ),
                message=self._get_value(
                    composed,
                    "message",
                    default=self._get_value(
                        composed,
                        "body",
                        default="",
                    ),
                ),
                attachment=self._attachment_from(
                    composed,
                    resume_path,
                ),
                error=str(exc),
                tracker_id=(
                    tracker_record.outreach_id
                    if tracker_record
                    else None
                ),
            )

            self._record_send_failure(
                tracker_record,
                error=str(exc),
            )

            return result

        # ----------------------------------------------------
        # NORMALIZE RESULT
        # ----------------------------------------------------

        result = self._build_send_result(
            composed=composed,
            sender_result=sender_result,
            selected_contact=selected_contact,
            resume_path=resume_path,
            tracker_id=(
                tracker_record.outreach_id
                if tracker_record
                else None
            ),
        )

        # ----------------------------------------------------
        # UPDATE TRACKER
        # ----------------------------------------------------

        self._record_send_result(
            tracker_record,
            result,
        )

        return result

    # ========================================================
    # COMPOSER ADAPTER
    # ========================================================

    def _compose(
        self,
        job: dict,
        candidate: dict,
        contact: dict,
        resume_path: Optional[str],
    ) -> Any:
        """
        Call the configured composer while supporting:

            compose(job, candidate, contact)

            compose(
                job,
                candidate,
                contact,
                resume_path,
            )

            compose(
                job,
                contact,
                resume_path=None,
            )

        Candidate-aware APIs are preferred.

        Unsupported concrete signatures always produce:

            Unsupported EmailComposer.compose()
            signature.
        """

        compose_method = (
            self.email_composer.compose
        )

        # ----------------------------------------------------
        # Inspect the callable.
        # ----------------------------------------------------

        try:
            signature = inspect.signature(
                compose_method
            )

            parameters = signature.parameters

        except (
            TypeError,
            ValueError,
        ):
            parameters = {}

        parameter_values = list(
            parameters.values()
        )

        parameter_names = set(
            parameters.keys()
        )

        has_varargs = any(
            parameter.kind
            == inspect.Parameter.VAR_POSITIONAL
            for parameter in parameter_values
        )

        has_varkwargs = any(
            parameter.kind
            == inspect.Parameter.VAR_KEYWORD
            for parameter in parameter_values
        )

        positional_parameters = [
            parameter
            for parameter in parameter_values
            if parameter.kind
            in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            }
        ]

        parameter_count = len(
            positional_parameters
        )

        # ----------------------------------------------------
        # Explicitly unsupported zero-argument composer.
        #
        # This is important because a concrete:
        #
        #     def compose(self):
        #
        # should NOT receive our keyword arguments and leak
        # Python's "unexpected keyword argument" message.
        # ----------------------------------------------------

        if (
            not has_varargs
            and not has_varkwargs
            and parameter_count == 0
        ):
            raise TypeError(
                "Unsupported "
                "EmailComposer.compose() "
                "signature."
            )

        # ====================================================
        # CANDIDATE-AWARE COMPOSER
        # ====================================================

        if "candidate" in parameter_names:
            kwargs = {
                "job": job,
                "candidate": candidate,
                "contact": contact,
            }

            if "resume_path" in parameter_names:
                kwargs[
                    "resume_path"
                ] = resume_path

            try:
                return compose_method(
                    **kwargs
                )

            except TypeError as exc:
                raise TypeError(
                    "Unsupported "
                    "EmailComposer.compose() "
                    "signature."
                ) from exc

        # ====================================================
        # CURRENT PRODUCTION COMPOSER
        # ====================================================

        if "contact" in parameter_names:
            kwargs = {
                "job": job,
                "contact": contact,
            }

            if "resume_path" in parameter_names:
                kwargs[
                    "resume_path"
                ] = resume_path

            try:
                return compose_method(
                    **kwargs
                )

            except TypeError as exc:
                raise TypeError(
                    "Unsupported "
                    "EmailComposer.compose() "
                    "signature."
                ) from exc

        # ====================================================
        # DYNAMIC CALLABLE / MAGICMOCK
        # ====================================================

        if (
            has_varargs
            or has_varkwargs
            or not parameters
        ):
            try:
                return compose_method(
                    job=job,
                    candidate=candidate,
                    contact=contact,
                    resume_path=resume_path,
                )

            except TypeError as first_error:
                try:
                    return compose_method(
                        job=job,
                        contact=contact,
                        resume_path=resume_path,
                    )

                except TypeError:
                    try:
                        return compose_method(
                            job,
                            candidate,
                            contact,
                        )

                    except TypeError:
                        raise TypeError(
                            "Unsupported "
                            "EmailComposer.compose() "
                            "signature."
                        ) from first_error

        # ====================================================
        # POSITIONAL CANDIDATE-AWARE COMPOSER
        # ====================================================

        if parameter_count >= 4:
            try:
                return compose_method(
                    job,
                    candidate,
                    contact,
                    resume_path,
                )

            except TypeError as exc:
                raise TypeError(
                    "Unsupported "
                    "EmailComposer.compose() "
                    "signature."
                ) from exc

        # ====================================================
        # THREE-PARAMETER COMPOSER
        # ====================================================

        if parameter_count == 3:
            try:
                return compose_method(
                    job,
                    candidate,
                    contact,
                )

            except TypeError as exc:
                raise TypeError(
                    "Unsupported "
                    "EmailComposer.compose() "
                    "signature."
                ) from exc

        # ====================================================
        # TWO-PARAMETER PRODUCTION COMPOSER
        # ====================================================

        if parameter_count == 2:
            try:
                return compose_method(
                    job,
                    contact,
                )

            except TypeError as exc:
                raise TypeError(
                    "Unsupported "
                    "EmailComposer.compose() "
                    "signature."
                ) from exc

        # ====================================================
        # EVERYTHING ELSE
        # ====================================================

        raise TypeError(
            "Unsupported "
            "EmailComposer.compose() "
            "signature."
        )

    # ========================================================
    # SENDER ADAPTER
    # ========================================================

    def _send(
        self,
        composed: Any,
        contact: ContactSelection,
        resume_path: Optional[str],
    ) -> Any:
        """
        Call either:

            EmailSender.send(ComposedEmail)

        or a compatible legacy sender interface.
        """

        send_method = (
            self.email_sender.send
        )

        try:
            signature = inspect.signature(
                send_method
            )

            parameters = signature.parameters

        except (
            TypeError,
            ValueError,
        ):
            parameters = {}

        # ----------------------------------------------------
        # CURRENT PRODUCTION SENDER
        # ----------------------------------------------------

        if len(parameters) == 1:
            return send_method(
                composed
            )

        # ----------------------------------------------------
        # LEGACY / TEST SENDER
        # ----------------------------------------------------

        recipient = self._get_value(
            composed,
            "recipient",
            default=contact.email,
        )

        subject = self._get_value(
            composed,
            "subject",
            default="",
        )

        message = self._get_value(
            composed,
            "message",
            default=self._get_value(
                composed,
                "body",
                default="",
            ),
        )

        attachment = self._attachment_from(
            composed,
            resume_path,
        )

        kwargs = {}

        if "recipient" in parameters:
            kwargs[
                "recipient"
            ] = recipient

        if "subject" in parameters:
            kwargs[
                "subject"
            ] = subject

        if "message" in parameters:
            kwargs[
                "message"
            ] = message

        elif "body" in parameters:
            kwargs[
                "body"
            ] = message

        if "attachment" in parameters:
            kwargs[
                "attachment"
            ] = attachment

        if kwargs:
            return send_method(
                **kwargs
            )

        return send_method(
            recipient,
            subject,
            message,
            attachment,
        )

    # ========================================================
    # RESULT NORMALIZATION
    # ========================================================

    def _build_prepared_result(
        self,
        composed: Any,
        selected_contact: ContactSelection,
        resume_path: Optional[str],
    ) -> OutreachResult:
        """
        Normalize composer output.
        """

        recipient = self._get_value(
            composed,
            "recipient",
            default=selected_contact.email,
        )

        subject = self._get_value(
            composed,
            "subject",
            default="",
        )

        message = self._get_value(
            composed,
            "message",
            default=self._get_value(
                composed,
                "body",
                default="",
            ),
        )

        attachment = self._attachment_from(
            composed,
            resume_path,
        )

        return OutreachResult(
            success=True,
            status="prepared",
            email=recipient,
            subject=str(
                subject or ""
            ),
            message=str(
                message or ""
            ),
            attachment=attachment,
        )

    def _build_send_result(
        self,
        composed: Any,
        sender_result: Any,
        selected_contact: ContactSelection,
        resume_path: Optional[str],
        tracker_id: Optional[str] = None,
    ) -> OutreachResult:
        """
        Normalize:

            - bool
            - dict
            - EmailSendResult
            - arbitrary result objects

        into OutreachResult.
        """

        recipient = self._get_value(
            composed,
            "recipient",
            default=selected_contact.email,
        )

        subject = self._get_value(
            composed,
            "subject",
            default="",
        )

        message = self._get_value(
            composed,
            "message",
            default=self._get_value(
                composed,
                "body",
                default="",
            ),
        )

        attachment = self._attachment_from(
            composed,
            resume_path,
        )

        success = self._send_success(
            sender_result
        )

        error = self._get_error(
            sender_result
        )

        dry_run = bool(
            self._get_value(
                sender_result,
                "dry_run",
                default=False,
            )
        )

        sender_recipient = self._get_value(
            sender_result,
            "recipient",
            default=recipient,
        )

        sender_subject = self._get_value(
            sender_result,
            "subject",
            default=subject,
        )

        sender_attachment = self._get_value(
            sender_result,
            "attachment",
            default=attachment,
        )

        if success:
            return OutreachResult(
                success=True,
                status="sent",
                email=sender_recipient,
                subject=str(
                    sender_subject or ""
                ),
                message=str(
                    message or ""
                ),
                attachment=sender_attachment,
                dry_run=dry_run,
                tracker_id=tracker_id,
            )

        return OutreachResult(
            success=False,
            status="send_failed",
            email=sender_recipient,
            subject=str(
                sender_subject or ""
            ),
            message=str(
                message or ""
            ),
            attachment=sender_attachment,
            error=error,
            dry_run=dry_run,
            tracker_id=tracker_id,
        )

    # ========================================================
    # TRACKER INTEGRATION
    # ========================================================

    def _track_prepared(
        self,
        job: dict,
        contact: ContactSelection,
        result: OutreachResult,
    ) -> Optional[OutreachRecord]:
        """
        Create a persistent tracker record for prepared
        outreach.

        Tracking failures never break email preparation.
        """

        if self.outreach_tracker is None:
            return None

        try:
            contact_data = dict(
                contact.contact
            )

            contact_data.setdefault(
                "email",
                contact.email,
            )

            contact_data.setdefault(
                "score",
                contact.score,
            )

            contact_data.setdefault(
                "reason",
                contact.reason,
            )

            return self.outreach_tracker.create(
                job=job,
                contact=contact_data,
                subject=result.subject,
                resume_path=(
                    result.attachment or ""
                ),
                status="prepared",
            )

        except Exception:
            return None

    def _ensure_tracking_record(
        self,
        job: dict,
        contact: ContactSelection,
        composed: Any,
        resume_path: Optional[str],
    ) -> Optional[OutreachRecord]:
        """
        Ensure a persistent tracker record exists before
        sending.
        """

        if self.outreach_tracker is None:
            return None

        recipient = self._get_value(
            composed,
            "recipient",
            default=contact.email,
        )

        subject = self._get_value(
            composed,
            "subject",
            default="",
        )

        attachment = self._attachment_from(
            composed,
            resume_path,
        )

        contact_data = dict(
            contact.contact
        )

        contact_data.setdefault(
            "email",
            contact.email,
        )

        contact_data.setdefault(
            "score",
            contact.score,
        )

        contact_data.setdefault(
            "reason",
            contact.reason,
        )

        try:
            existing = (
                self.outreach_tracker.find(
                    contact_email=recipient,
                )
            )

            if existing is not None:
                return existing

        except Exception:
            pass

        try:
            return self.outreach_tracker.create(
                job=job,
                contact=contact_data,
                subject=str(
                    subject or ""
                ),
                resume_path=(
                    attachment or ""
                ),
                status="confirmation_required",
            )

        except Exception:
            return None

    def _mark_confirmation_required(
        self,
        prepared: OutreachResult,
    ) -> Optional[str]:
        """
        Move an existing prepared record to
        confirmation_required.
        """

        if self.outreach_tracker is None:
            return None

        if not prepared.email:
            return None

        try:
            record = (
                self.outreach_tracker.find(
                    contact_email=prepared.email,
                )
            )

            if record is None:
                return None

            updated = (
                self.outreach_tracker.update_status(
                    record.outreach_id,
                    "confirmation_required",
                )
            )

            if updated is None:
                return None

            return updated.outreach_id

        except Exception:
            return None

    def _record_send_result(
        self,
        tracker_record: Optional[
            OutreachRecord
        ],
        result: OutreachResult,
    ) -> None:
        """
        Persist the result of a send operation.

        Tracker failures never replace the actual send result.
        """

        if (
            self.outreach_tracker is None
            or tracker_record is None
        ):
            return

        try:
            self.outreach_tracker.record_send_result(
                tracker_record.outreach_id,
                success=result.success,
                error=result.error,
                dry_run=result.dry_run,
            )

        except Exception:
            pass

    def _record_send_failure(
        self,
        tracker_record: Optional[
            OutreachRecord
        ],
        error: str,
    ) -> None:
        """
        Persist a failed send attempt.
        """

        if (
            self.outreach_tracker is None
            or tracker_record is None
        ):
            return

        try:
            self.outreach_tracker.record_send_result(
                tracker_record.outreach_id,
                success=False,
                error=error,
            )

        except Exception:
            pass

    @staticmethod
    def _with_tracker_id(
        result: OutreachResult,
        tracker_id: str,
    ) -> OutreachResult:
        """
        Return a copy of OutreachResult with tracker ID.
        """

        return OutreachResult(
            success=result.success,
            status=result.status,
            email=result.email,
            subject=result.subject,
            message=result.message,
            attachment=result.attachment,
            error=result.error,
            dry_run=result.dry_run,
            tracker_id=tracker_id,
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def _validate_job(
        job: Any,
    ) -> None:
        """
        Validate the job object.
        """

        if not isinstance(
            job,
            dict,
        ):
            raise TypeError(
                "job must be a dictionary."
            )

    @staticmethod
    def _normalize_candidate(
        candidate: Any,
    ) -> dict:
        """
        Normalize candidate information.

        Omitted candidate:
            {}

        Explicit None/non-dictionary:
            TypeError
        """

        if candidate is _MISSING:
            return {}

        if not isinstance(
            candidate,
            dict,
        ):
            raise TypeError(
                "candidate must be a dictionary."
            )

        return candidate

    # ========================================================
    # VALUE HELPERS
    # ========================================================

    @staticmethod
    def _get_value(
        source: Any,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Safely retrieve a value from:

            - dictionaries
            - objects with attributes
        """

        if source is None:
            return default

        if isinstance(
            source,
            dict,
        ):
            return source.get(
                key,
                default,
            )

        return getattr(
            source,
            key,
            default,
        )

    @staticmethod
    def _send_success(
        result: Any,
    ) -> bool:
        """
        Normalize sender success values.

        Supports:

            True
            False
            {"success": True}
            object.success
        """

        if isinstance(
            result,
            bool,
        ):
            return result

        if isinstance(
            result,
            dict,
        ):
            return bool(
                result.get(
                    "success",
                    False,
                )
            )

        return bool(
            getattr(
                result,
                "success",
                False,
            )
        )

    @staticmethod
    def _get_error(
        result: Any,
    ) -> Optional[str]:
        """
        Extract an error message from a sender result.
        """

        error = (
            OutreachPipeline._get_value(
                result,
                "error",
                default=None,
            )
        )

        if error is None:
            return None

        return str(error)

    @staticmethod
    def _attachment_from(
        composed: Any,
        explicit_resume_path: Optional[str],
    ) -> Optional[str]:
        """
        Determine the attachment path.

        Priority:

            1. Explicit resume_path
            2. Composer attachment
            3. Composer resume_path
        """

        if explicit_resume_path is not None:
            value = str(
                explicit_resume_path
            ).strip()

            if value:
                return value

        attachment = (
            OutreachPipeline._get_value(
                composed,
                "attachment",
                default=None,
            )
        )

        if attachment is None:
            attachment = (
                OutreachPipeline._get_value(
                    composed,
                    "resume_path",
                    default=None,
                )
            )

        if attachment is None:
            return None

        value = str(
            attachment
        ).strip()

        return value or None


__all__ = [
    "OutreachResult",
    "OutreachPipeline",
]