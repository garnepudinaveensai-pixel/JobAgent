from unittest.mock import MagicMock, patch

import pytest

from app.notifications.email_notification import (
    EmailNotification,
)


# ============================================================
# INITIALIZATION
# ============================================================


def test_initialization_with_explicit_configuration():

    notification = EmailNotification(
        sender="sender@example.com",
        password="app-password",
        recipient="receiver@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        use_tls=True,
    )

    assert (
        notification.sender
        == "sender@example.com"
    )

    assert (
        notification.recipient
        == "receiver@example.com"
    )

    assert (
        notification.smtp_host
        == "smtp.example.com"
    )

    assert notification.smtp_port == 587
    assert notification.use_tls is True


# ============================================================
# ENVIRONMENT CONFIGURATION
# ============================================================


@patch.dict(
    "os.environ",
    {
        "EMAIL_SENDER": "envsender@example.com",
        "EMAIL_PASSWORD": "env-password",
        "EMAIL_RECIPIENT": "envreceiver@example.com",
        "EMAIL_SMTP_HOST": "smtp.example.com",
        "EMAIL_SMTP_PORT": "2525",
        "EMAIL_USE_TLS": "false",
    },
    clear=False,
)
def test_load_configuration_from_environment():

    notification = EmailNotification()

    assert (
        notification.sender
        == "envsender@example.com"
    )

    assert (
        notification.password
        == "env-password"
    )

    assert (
        notification.recipient
        == "envreceiver@example.com"
    )

    assert (
        notification.smtp_host
        == "smtp.example.com"
    )

    assert notification.smtp_port == 2525
    assert notification.use_tls is False


# ============================================================
# VALIDATION
# ============================================================


def test_missing_sender_fails():

    notification = EmailNotification(
        sender="",
        password="password",
        recipient="receiver@example.com",
    )

    with pytest.raises(ValueError):

        notification.validate_configuration()


def test_missing_password_fails():

    notification = EmailNotification(
        sender="sender@example.com",
        password="",
        recipient="receiver@example.com",
    )

    with pytest.raises(ValueError):

        notification.validate_configuration()


def test_missing_recipient_fails():

    notification = EmailNotification(
        sender="sender@example.com",
        password="password",
        recipient="",
    )

    with pytest.raises(ValueError):

        notification.validate_configuration()


# ============================================================
# DISABLED
# ============================================================


def test_disabled_email_does_not_send():

    notification = EmailNotification(
        sender="sender@example.com",
        password="password",
        recipient="receiver@example.com",
        enabled=False,
    )

    result = notification.send(
        "Test",
        "Test message",
    )

    assert result is False


# ============================================================
# SMTP SEND
# ============================================================


@patch(
    "app.notifications.email_notification.smtplib.SMTP"
)
def test_send_email(mock_smtp):

    smtp = MagicMock()

    mock_smtp.return_value.__enter__.return_value = smtp

    notification = EmailNotification(
        sender="sender@example.com",
        password="password",
        recipient="receiver@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        use_tls=True,
    )

    result = notification.send(
        "Application Update",
        "You have been shortlisted.",
    )

    assert result is True

    mock_smtp.assert_called_once_with(
        "smtp.example.com",
        587,
        timeout=30,
    )

    smtp.starttls.assert_called_once()

    smtp.login.assert_called_once_with(
        "sender@example.com",
        "password",
    )

    smtp.send_message.assert_called_once()


# ============================================================
# CUSTOM RECIPIENT
# ============================================================


@patch(
    "app.notifications.email_notification.smtplib.SMTP"
)
def test_custom_recipient(mock_smtp):

    smtp = MagicMock()

    mock_smtp.return_value.__enter__.return_value = smtp

    notification = EmailNotification(
        sender="sender@example.com",
        password="password",
        recipient="default@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
    )

    result = notification.send(
        "Job Update",
        "Application status changed.",
        recipient="custom@example.com",
    )

    assert result is True

    message = smtp.send_message.call_args[0][0]

    assert (
        message["To"]
        == "custom@example.com"
    )


# ============================================================
# STRUCTURED RESULT
# ============================================================


@patch(
    "app.notifications.email_notification.smtplib.SMTP"
)
def test_send_result_success(mock_smtp):

    smtp = MagicMock()

    mock_smtp.return_value.__enter__.return_value = smtp

    notification = EmailNotification(
        sender="sender@example.com",
        password="password",
        recipient="receiver@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
    )

    result = notification.send_result(
        "Application Update",
        "You have been shortlisted.",
    )

    data = result.to_dict()

    assert data["success"] is True
    assert data["channel"] == "Email"
    assert (
        data["title"]
        == "Application Update"
    )
    assert (
        data["message"]
        == "You have been shortlisted."
    )
    assert data["error"] is None


# ============================================================
# STRUCTURED ERROR RESULT
# ============================================================


@patch(
    "app.notifications.email_notification.smtplib.SMTP"
)
def test_send_result_error(mock_smtp):

    mock_smtp.side_effect = Exception(
        "SMTP connection failed"
    )

    notification = EmailNotification(
        sender="sender@example.com",
        password="password",
        recipient="receiver@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
    )

    result = notification.send_result(
        "Application Update",
        "Application status changed.",
    )

    data = result.to_dict()

    assert data["success"] is False
    assert data["channel"] == "Email"
    assert (
        data["error"]
        == "SMTP connection failed"
    )