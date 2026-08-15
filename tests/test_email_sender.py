from email.message import EmailMessage

import pytest

from app.outreach.email_composer import (
    ComposedEmail,
)
from app.outreach.email_sender import (
    EmailSendResult,
    EmailSender,
)


def make_email(
    resume_path: str,
) -> ComposedEmail:

    return ComposedEmail(
        recipient="recruiter@example.com",
        subject="Application for Electrical Engineer",
        body="Please find my resume attached.",
        resume_path=resume_path,
        job={
            "title": "Electrical Engineer",
            "company": "Example",
        },
        contact={
            "email": "recruiter@example.com",
            "role": "Recruiter",
        },
    )


def test_sender_creation():

    sender = EmailSender(
        sender="sender@example.com",
        password="test-password",
    )

    assert sender.sender == "sender@example.com"
    assert sender.smtp_host == "smtp.gmail.com"
    assert sender.smtp_port == 587


def test_custom_smtp_configuration():

    sender = EmailSender(
        sender="sender@example.com",
        password="secret",
        smtp_host="smtp.example.com",
        smtp_port=465,
        use_tls=False,
    )

    assert sender.smtp_host == "smtp.example.com"
    assert sender.smtp_port == 465
    assert sender.use_tls is False


def test_invalid_smtp_port():

    with pytest.raises(ValueError):

        EmailSender(
            smtp_port="invalid",
        )


def test_invalid_timeout():

    with pytest.raises(ValueError):

        EmailSender(
            timeout=0,
        )


def test_dry_run_does_not_require_credentials(
    tmp_path,
):

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(
        b"test resume"
    )

    sender = EmailSender(
        dry_run=True,
    )

    result = sender.send(
        make_email(
            str(resume)
        )
    )

    assert isinstance(
        result,
        EmailSendResult,
    )

    assert result.success is True
    assert result.dry_run is True
    assert (
        result.recipient
        == "recruiter@example.com"
    )


def test_missing_attachment_is_rejected(
    tmp_path,
):

    sender = EmailSender(
        sender="sender@example.com",
        password="secret",
        dry_run=True,
    )

    email = make_email(
        str(
            tmp_path / "missing.pdf"
        )
    )

    with pytest.raises(
        FileNotFoundError
    ):
        sender.send(email)


def test_empty_attachment_path_is_rejected():

    sender = EmailSender(
        sender="sender@example.com",
        password="secret",
        dry_run=True,
    )

    email = make_email("")

    with pytest.raises(ValueError):
        sender.send(email)


def test_directory_attachment_is_rejected(
    tmp_path,
):

    sender = EmailSender(
        sender="sender@example.com",
        password="secret",
        dry_run=True,
    )

    email = make_email(
        str(tmp_path)
    )

    with pytest.raises(
        IsADirectoryError
    ):
        sender.send(email)


def test_missing_sender_configuration():

    sender = EmailSender(
        password="secret",
    )

    with pytest.raises(ValueError):

        sender.validate_configuration()


def test_missing_password_configuration():

    sender = EmailSender(
        sender="sender@example.com",
    )

    with pytest.raises(ValueError):

        sender.validate_configuration()


def test_dry_run_configuration_allows_missing_credentials():

    sender = EmailSender(
        dry_run=True,
    )

    sender.validate_configuration()


def test_invalid_email_object():

    sender = EmailSender(
        dry_run=True,
    )

    with pytest.raises(TypeError):

        sender.send(
            "not-an-email"
        )


def test_empty_recipient_is_rejected(
    tmp_path,
):

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(
        b"resume"
    )

    sender = EmailSender(
        dry_run=True,
    )

    email = ComposedEmail(
        recipient="",
        subject="Test",
        body="Body",
        resume_path=str(resume),
        job={},
        contact={},
    )

    with pytest.raises(ValueError):
        sender.send(email)


def test_invalid_recipient_is_rejected(
    tmp_path,
):

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(
        b"resume"
    )

    sender = EmailSender(
        dry_run=True,
    )

    email = ComposedEmail(
        recipient="invalid-email",
        subject="Test",
        body="Body",
        resume_path=str(resume),
        job={},
        contact={},
    )

    with pytest.raises(ValueError):
        sender.send(email)


def test_empty_subject_is_rejected(
    tmp_path,
):

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(
        b"resume"
    )

    sender = EmailSender(
        dry_run=True,
    )

    email = ComposedEmail(
        recipient="hr@example.com",
        subject="",
        body="Body",
        resume_path=str(resume),
        job={},
        contact={},
    )

    with pytest.raises(ValueError):
        sender.send(email)


def test_empty_body_is_rejected(
    tmp_path,
):

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(
        b"resume"
    )

    sender = EmailSender(
        dry_run=True,
    )

    email = ComposedEmail(
        recipient="hr@example.com",
        subject="Test",
        body="",
        resume_path=str(resume),
        job={},
        contact={},
    )

    with pytest.raises(ValueError):
        sender.send(email)


def test_validate_attachment_returns_path(
    tmp_path,
):

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(
        b"resume"
    )

    path = EmailSender.validate_attachment(
        str(resume)
    )

    assert path == resume


def test_build_message_returns_email_message(
    tmp_path,
):

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(
        b"PDF DATA"
    )

    sender = EmailSender(
        sender="sender@example.com",
        password="secret",
    )

    message = sender.build_message(
        make_email(
            str(resume)
        )
    )

    assert isinstance(
        message,
        EmailMessage,
    )

    assert (
        message["To"]
        == "recruiter@example.com"
    )

    assert (
        message["Subject"]
        == "Application for Electrical Engineer"
    )


def test_build_message_contains_attachment(
    tmp_path,
):

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(
        b"PDF DATA"
    )

    sender = EmailSender(
        sender="sender@example.com",
        password="secret",
    )

    message = sender.build_message(
        make_email(
            str(resume)
        )
    )

    attachments = list(
        message.iter_attachments()
    )

    assert len(attachments) == 1

    assert (
        attachments[0].get_filename()
        == "resume.pdf"
    )


def test_build_message_does_not_send(
    tmp_path,
    monkeypatch,
):

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(
        b"PDF DATA"
    )

    called = {
        "smtp": False,
    }

    def fake_smtp(*args, **kwargs):
        called["smtp"] = True
        raise AssertionError(
            "SMTP must not be called by build_message."
        )

    monkeypatch.setattr(
        "app.outreach.email_sender.smtplib.SMTP",
        fake_smtp,
    )

    sender = EmailSender(
        sender="sender@example.com",
        password="secret",
    )

    sender.build_message(
        make_email(
            str(resume)
        )
    )

    assert called["smtp"] is False


def test_dry_run_does_not_connect_to_smtp(
    tmp_path,
    monkeypatch,
):

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(
        b"PDF DATA"
    )

    called = {
        "smtp": False,
    }

    def fake_smtp(*args, **kwargs):
        called["smtp"] = True
        raise AssertionError(
            "SMTP must not be called in dry-run mode."
        )

    monkeypatch.setattr(
        "app.outreach.email_sender.smtplib.SMTP",
        fake_smtp,
    )

    sender = EmailSender(
        dry_run=True,
    )

    result = sender.send(
        make_email(
            str(resume)
        )
    )

    assert result.success is True
    assert result.dry_run is True
    assert called["smtp"] is False


def test_successful_send(
    tmp_path,
    monkeypatch,
):

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(
        b"PDF DATA"
    )

    class FakeSMTP:

        def __init__(
            self,
            host,
            port,
            timeout,
        ):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.logged_in = False
            self.sent = False

        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            return False

        def starttls(self):
            pass

        def login(
            self,
            sender,
            password,
        ):
            assert sender == "sender@example.com"
            assert password == "secret"
            self.logged_in = True

        def send_message(
            self,
            message,
        ):
            assert (
                message["To"]
                == "recruiter@example.com"
            )
            self.sent = True

    smtp_instance = None

    def fake_smtp(
        host,
        port,
        timeout,
    ):

        nonlocal smtp_instance

        smtp_instance = FakeSMTP(
            host,
            port,
            timeout,
        )

        return smtp_instance

    monkeypatch.setattr(
        "app.outreach.email_sender.smtplib.SMTP",
        fake_smtp,
    )

    sender = EmailSender(
        sender="sender@example.com",
        password="secret",
    )

    result = sender.send(
        make_email(
            str(resume)
        )
    )

    assert result.success is True
    assert result.dry_run is False
    assert smtp_instance is not None
    assert smtp_instance.logged_in is True
    assert smtp_instance.sent is True


def test_send_failure_returns_result(
    tmp_path,
    monkeypatch,
):

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(
        b"PDF DATA"
    )

    class FakeSMTP:

        def __init__(
            self,
            *args,
            **kwargs,
        ):
            pass

        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            return False

        def starttls(self):
            pass

        def login(
            self,
            sender,
            password,
        ):
            raise RuntimeError(
                "SMTP authentication failed"
            )

    monkeypatch.setattr(
        "app.outreach.email_sender.smtplib.SMTP",
        FakeSMTP,
    )

    sender = EmailSender(
        sender="sender@example.com",
        password="secret",
    )

    result = sender.send(
        make_email(
            str(resume)
        )
    )

    assert result.success is False
    assert result.error is not None
    assert (
        "authentication failed"
        in result.error
    )


def test_password_is_not_in_result(
    tmp_path,
    monkeypatch,
):

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(
        b"PDF DATA"
    )

    secret = "SUPER_SECRET_PASSWORD"

    class FakeSMTP:

        def __init__(
            self,
            *args,
            **kwargs,
        ):
            pass

        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            return False

        def starttls(self):
            pass

        def login(
            self,
            sender,
            password,
        ):
            raise RuntimeError(
                "authentication failed"
            )

    monkeypatch.setattr(
        "app.outreach.email_sender.smtplib.SMTP",
        FakeSMTP,
    )

    sender = EmailSender(
        sender="sender@example.com",
        password=secret,
    )

    result = sender.send(
        make_email(
            str(resume)
        )
    )

    assert secret not in str(result)