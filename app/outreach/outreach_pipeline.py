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


_MISSING = object()


@dataclass(frozen=True)
class OutreachResult:
    """
    Result of an outreach preparation or sending operation.

    This object is intentionally independent of the concrete
    EmailComposer and EmailSender implementations.
    """

    success: bool
    status: str
    email: Optional[str] = None
    subject: str = ""
    message: str = ""
    attachment: Optional[str] = None
    error: Optional[str] = None
    dry_run: bool = False


class OutreachPipeline:
    """
    Coordinates the complete outreach workflow.

    Flow:

        contacts
            ↓
        contact selection
            ↓
        email composition
            ↓
        human confirmation
            ↓
        email sending
            ↓
        result

    Responsibilities:

        - Select the best contact.
        - Validate job/candidate input.
        - Compose the outreach email.
        - Respect explicit confirmation.
        - Adapt to supported composer/sender interfaces.
        - Normalize sender results.
        - Never send when confirmation is False.

    This class does not:

        - discover contacts
        - perform browser automation
        - store passwords
        - request OTPs
        - expose authentication credentials
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

        # IMPORTANT:
        #
        # The default sender is ALWAYS dry-run.
        #
        # Real sending must be explicitly configured.
        # This prevents accidental external email sending.
        self.email_sender = (
            email_sender
            if email_sender is not None
            else EmailSender(
                dry_run=True
            )
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

        candidate is optional.

        If omitted:
            candidate = {}

        If explicitly supplied as None:
            TypeError is raised.
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

            return self._build_prepared_result(
                composed=composed,
                selected_contact=contact,
                resume_path=resume_path,
            )

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

        Supports:

            compose(
                job,
                contact,
                resume_path=None,
            )

        and:

            compose(
                job,
                candidate,
                contact,
            )

        and:

            compose(
                job,
                candidate,
                contact,
                resume_path,
            )
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

        Explicit confirmation is therefore mandatory before
        any actual sender call occurs.
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

            return OutreachResult(
                success=True,
                status="confirmation_required",
                email=prepared.email,
                subject=prepared.subject,
                message=prepared.message,
                attachment=prepared.attachment,
            )

        # ----------------------------------------------------
        # CONTACT + COMPOSITION
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
        # SEND
        # ----------------------------------------------------

        try:
            sender_result = self._send(
                composed=composed,
                contact=selected_contact,
                resume_path=resume_path,
            )

        except Exception as exc:
            return OutreachResult(
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
            )

        # ----------------------------------------------------
        # RESULT NORMALIZATION
        # ----------------------------------------------------

        return self._build_send_result(
            composed=composed,
            sender_result=sender_result,
            selected_contact=selected_contact,
            resume_path=resume_path,
        )

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
        Call the configured composer while supporting multiple
        composer APIs.
        """

        compose_method = self.email_composer.compose

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

        # ====================================================
        # CANDIDATE-AWARE COMPOSER
        # ====================================================

        if "candidate" in parameters:
            kwargs = {
                "job": job,
                "candidate": candidate,
                "contact": contact,
            }

            if "resume_path" in parameters:
                kwargs["resume_path"] = resume_path

            return compose_method(
                **kwargs
            )

        # ====================================================
        # CURRENT PRODUCTION COMPOSER
        # ====================================================

        if "contact" in parameters:
            kwargs = {
                "job": job,
                "contact": contact,
            }

            if "resume_path" in parameters:
                kwargs["resume_path"] = resume_path

            return compose_method(
                **kwargs
            )

        # ====================================================
        # POSITIONAL FALLBACK
        # ====================================================

        positional_parameters = [
            parameter
            for parameter in parameters.values()
            if parameter.kind
            in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            }
        ]

        parameter_count = len(
            positional_parameters
        )

        if parameter_count >= 4:
            return compose_method(
                job,
                candidate,
                contact,
                resume_path,
            )

        if parameter_count == 3:
            return compose_method(
                job,
                candidate,
                contact,
            )

        if parameter_count == 2:
            return compose_method(
                job,
                contact,
            )

        raise TypeError(
            "Unsupported EmailComposer.compose() "
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

        send_method = self.email_sender.send

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
        # CURRENT PRODUCTION EmailSender
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
            kwargs["recipient"] = recipient

        if "subject" in parameters:
            kwargs["subject"] = subject

        if "message" in parameters:
            kwargs["message"] = message

        elif "body" in parameters:
            kwargs["body"] = message

        if "attachment" in parameters:
            kwargs["attachment"] = attachment

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
        Convert different composer result formats into
        OutreachResult.
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
            subject=str(subject or ""),
            message=str(message or ""),
            attachment=attachment,
        )

    def _build_send_result(
        self,
        composed: Any,
        sender_result: Any,
        selected_contact: ContactSelection,
        resume_path: Optional[str],
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

        An omitted candidate becomes {}.

        Explicit None or another non-dictionary value is
        rejected.
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

        error = OutreachPipeline._get_value(
            result,
            "error",
            default=None,
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

            1. Explicit resume_path argument.
            2. Composer attachment.
            3. Composer resume_path.
        """

        if explicit_resume_path is not None:
            value = str(
                explicit_resume_path
            ).strip()

            if value:
                return value

        attachment = OutreachPipeline._get_value(
            composed,
            "attachment",
            default=None,
        )

        if attachment is None:
            attachment = OutreachPipeline._get_value(
                composed,
                "resume_path",
                default=None,
            )

        if attachment is None:
            return None

        return str(
            attachment
        )


__all__ = [
    "OutreachResult",
    "OutreachPipeline",
]