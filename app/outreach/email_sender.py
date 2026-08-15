from __future__ import annotations

import mimetypes
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from app.outreach.email_composer import ComposedEmail


@dataclass(frozen=True)
class EmailSendResult:
    """
    Result of an email-send attempt.

    No password or other secret is ever stored here.
    """

    success: bool
    recipient: str
    subject: str
    dry_run: bool = False
    attachment: Optional[str] = None
    error: Optional[str] = None


class EmailSender:
    """
    Gmail/SMTP sender for JobAgent outreach.

    Responsibilities:
        - Validate SMTP configuration.
        - Validate the composed email.
        - Validate the resume attachment.
        - Build the email message.
        - Send through SMTP.
        - Support dry-run mode.

    Security:
        - Credentials are loaded from environment variables.
        - Passwords are never printed or returned.
        - Actual sending requires explicit invocation of send().
        - Dry-run mode never contacts the SMTP server.
    """

    DEFAULT_SMTP_HOST = "smtp.gmail.com"
    DEFAULT_SMTP_PORT = 587

    ENV_SMTP_HOST = "EMAIL_SMTP_HOST"
    ENV_SMTP_PORT = "EMAIL_SMTP_PORT"
    ENV_SENDER = "EMAIL_SENDER"
    ENV_PASSWORD = "EMAIL_PASSWORD"
    ENV_USE_TLS = "EMAIL_USE_TLS"

    def __init__(
        self,
        sender: Optional[str] = None,
        password: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        use_tls: Optional[bool] = None,
        timeout: int = 30,
        dry_run: bool = False,
    ):
        load_dotenv()

        self.sender = (
            sender
            if sender is not None
            else os.getenv(self.ENV_SENDER, "")
        ).strip()

        self.password = (
            password
            if password is not None
            else os.getenv(self.ENV_PASSWORD, "")
        )

        self.smtp_host = (
            smtp_host
            if smtp_host is not None
            else os.getenv(
                self.ENV_SMTP_HOST,
                self.DEFAULT_SMTP_HOST,
            )
        ).strip()

        port_value = (
            smtp_port
            if smtp_port is not None
            else os.getenv(
                self.ENV_SMTP_PORT,
                str(self.DEFAULT_SMTP_PORT),
            )
        )

        try:
            self.smtp_port = int(port_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "SMTP port must be an integer."
            ) from exc

        if use_tls is None:
            tls_value = os.getenv(
                self.ENV_USE_TLS,
                "true",
            ).strip().lower()

            self.use_tls = tls_value in {
                "1",
                "true",
                "yes",
                "on",
            }
        else:
            self.use_tls = bool(use_tls)

        if timeout <= 0:
            raise ValueError(
                "timeout must be greater than zero."
            )

        self.timeout = timeout
        self.dry_run = dry_run

    # ========================================================
    # CONFIGURATION
    # ========================================================

    def validate_configuration(self) -> None:
        """
        Validate SMTP configuration.

        Dry-run mode does not require SMTP credentials.
        """

        if not self.smtp_host:
            raise ValueError(
                "SMTP host is not configured."
            )

        if self.smtp_port <= 0:
            raise ValueError(
                "SMTP port must be greater than zero."
            )

        if self.dry_run:
            return

        if not self.sender:
            raise ValueError(
                "Email sender is not configured."
            )

        if not self.password:
            raise ValueError(
                "Email password is not configured."
            )

    # ========================================================
    # EMAIL VALIDATION
    # ========================================================

    @staticmethod
    def _validate_email(
        email: ComposedEmail,
    ) -> None:
        """
        Validate a ComposedEmail before sending.
        """

        if not isinstance(email, ComposedEmail):
            raise TypeError(
                "email must be a ComposedEmail."
            )

        recipient = email.recipient.strip()

        if not recipient:
            raise ValueError(
                "Email recipient cannot be empty."
            )

        if (
            recipient.count("@") != 1
            or "." not in recipient.split("@", 1)[1]
        ):
            raise ValueError(
                "Email recipient is invalid."
            )

        if not email.subject.strip():
            raise ValueError(
                "Email subject cannot be empty."
            )

        if not email.body.strip():
            raise ValueError(
                "Email body cannot be empty."
            )

    # ========================================================
    # ATTACHMENT
    # ========================================================

    @staticmethod
    def validate_attachment(
        resume_path: str,
    ) -> Path:
        """
        Validate the resume attachment.

        Returns:
            Path object for the attachment.

        Raises:
            ValueError: Empty path.
            FileNotFoundError: File does not exist.
            IsADirectoryError: Path is a directory.
        """

        path_value = str(
            resume_path or ""
        ).strip()

        if not path_value:
            raise ValueError(
                "Resume attachment path cannot be empty."
            )

        path = Path(path_value)

        if not path.exists():
            raise FileNotFoundError(
                f"Resume attachment not found: {path}"
            )

        if not path.is_file():
            raise IsADirectoryError(
                f"Resume attachment is not a file: {path}"
            )

        return path

    # ========================================================
    # MESSAGE BUILDING
    # ========================================================

    def build_message(
        self,
        email: ComposedEmail,
    ) -> EmailMessage:
        """
        Build an EmailMessage with the resume attached.

        This method does NOT send the message.
        """

        self._validate_email(email)

        attachment = self.validate_attachment(
            email.resume_path
        )

        message = EmailMessage()

        message["Subject"] = email.subject
        message["From"] = self.sender
        message["To"] = email.recipient

        message.set_content(
            email.body
        )

        mime_type, _ = mimetypes.guess_type(
            attachment.name
        )

        if mime_type:
            maintype, subtype = mime_type.split(
                "/",
                1,
            )
        else:
            maintype = "application"
            subtype = "octet-stream"

        with attachment.open(
            "rb"
        ) as file:
            file_data = file.read()

        message.add_attachment(
            file_data,
            maintype=maintype,
            subtype=subtype,
            filename=attachment.name,
        )

        return message

    # ========================================================
    # SEND
    # ========================================================

    def send(
        self,
        email: ComposedEmail,
    ) -> EmailSendResult:
        """
        Send a composed email.

        In dry-run mode, no SMTP connection is made.

        Returns:
            EmailSendResult
        """

        self._validate_email(email)

        attachment = self.validate_attachment(
            email.resume_path
        )

        self.validate_configuration()

        if self.dry_run:
            return EmailSendResult(
                success=True,
                recipient=email.recipient,
                subject=email.subject,
                dry_run=True,
                attachment=str(attachment),
            )

        try:
            message = self.build_message(
                email
            )

            with smtplib.SMTP(
                self.smtp_host,
                self.smtp_port,
                timeout=self.timeout,
            ) as smtp:

                if self.use_tls:
                    smtp.starttls()

                smtp.login(
                    self.sender,
                    self.password,
                )

                smtp.send_message(
                    message
                )

            return EmailSendResult(
                success=True,
                recipient=email.recipient,
                subject=email.subject,
                dry_run=False,
                attachment=str(attachment),
            )

        except Exception as exc:
            return EmailSendResult(
                success=False,
                recipient=email.recipient,
                subject=email.subject,
                dry_run=False,
                attachment=str(attachment),
                error=str(exc),
            )