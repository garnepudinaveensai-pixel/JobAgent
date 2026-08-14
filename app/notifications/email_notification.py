import os
import smtplib
from email.message import EmailMessage
from typing import Any, Optional

from dotenv import load_dotenv

from app.notifications.notification import Notification, NotificationResult


class EmailNotification(Notification):
    """
    Email notification channel for JobAgent.

    The sender, SMTP configuration, credentials, and recipient
    can be supplied directly or loaded from environment variables.

    Environment variables:

        EMAIL_SMTP_HOST
        EMAIL_SMTP_PORT
        EMAIL_SENDER
        EMAIL_PASSWORD
        EMAIL_RECIPIENT
        EMAIL_USE_TLS
    """

    name = "Email"

    def __init__(
        self,
        sender: Optional[str] = None,
        password: Optional[str] = None,
        recipient: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        use_tls: Optional[bool] = None,
        enabled: bool = True,
    ):
        super().__init__(enabled=enabled)

        # Load .env if available.
        load_dotenv()

        self.sender = (
            sender
            or os.getenv("EMAIL_SENDER", "")
        ).strip()

        self.password = (
            password
            or os.getenv("EMAIL_PASSWORD", "")
        )

        self.recipient = (
            recipient
            or os.getenv("EMAIL_RECIPIENT", "")
        ).strip()

        self.smtp_host = (
            smtp_host
            or os.getenv(
                "EMAIL_SMTP_HOST",
                "smtp.gmail.com",
            )
        ).strip()

        port_value = (
            smtp_port
            if smtp_port is not None
            else os.getenv(
                "EMAIL_SMTP_PORT",
                "587",
            )
        )

        self.smtp_port = int(port_value)

        if use_tls is None:
            tls_value = os.getenv(
                "EMAIL_USE_TLS",
                "true",
            ).strip().lower()

            self.use_tls = tls_value in {
                "1",
                "true",
                "yes",
                "on",
            }
        else:
            self.use_tls = use_tls

    # ========================================================
    # CONFIGURATION
    # ========================================================

    def validate_configuration(self) -> None:
        """
        Validate the email configuration before sending.
        """

        if not self.sender:
            raise ValueError(
                "Email sender is not configured."
            )

        if not self.password:
            raise ValueError(
                "Email password is not configured."
            )

        if not self.recipient:
            raise ValueError(
                "Email recipient is not configured."
            )

        if not self.smtp_host:
            raise ValueError(
                "SMTP host is not configured."
            )

        if not self.smtp_port:
            raise ValueError(
                "SMTP port is not configured."
            )

    # ========================================================
    # SEND
    # ========================================================

    def send(
        self,
        title: str,
        message: str,
        recipient: Optional[str] = None,
        **kwargs: Any,
    ) -> bool:
        """
        Send an email notification.

        If recipient is provided, it overrides the configured
        default recipient for this message.

        Returns:
            True if successfully sent.
            False if disabled.
        """

        self.validate(title, message)

        if not self.enabled:
            return False

        target = (
            recipient
            or self.recipient
        ).strip()

        if not target:
            raise ValueError(
                "Email recipient is not configured."
            )

        self.validate_configuration()

        email = EmailMessage()

        email["Subject"] = title
        email["From"] = self.sender
        email["To"] = target

        email.set_content(message)

        with smtplib.SMTP(
            self.smtp_host,
            self.smtp_port,
            timeout=30,
        ) as smtp:

            if self.use_tls:
                smtp.starttls()

            smtp.login(
                self.sender,
                self.password,
            )

            smtp.send_message(email)

        return True

    # ========================================================
    # STRUCTURED SEND
    # ========================================================

    def send_result(
        self,
        title: str,
        message: str,
        recipient: Optional[str] = None,
    ) -> NotificationResult:
        """
        Send an email and return a structured result.

        Errors are captured rather than raised so the
        application-status pipeline can continue running.
        """

        try:

            success = self.send(
                title=title,
                message=message,
                recipient=recipient,
            )

            return NotificationResult(
                success=success,
                channel=self.channel_name,
                title=title,
                message=message,
            )

        except Exception as exc:

            return NotificationResult(
                success=False,
                channel=self.channel_name,
                title=title,
                message=message,
                error=str(exc),
            )