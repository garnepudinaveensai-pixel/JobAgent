from pathlib import Path

from app.core.job_agent import JobAgent
from app.jobs.job_store import JobStore
from app.outreach.email_composer import (
    ComposedEmail,
    EmailComposer,
)
from app.outreach.email_sender import EmailSender
from app.outreach.outreach_manager import OutreachManager


# ============================================================
# TEST DATA
# ============================================================

def sample_job():
    return {
        "title": "Electrical Engineer",
        "company": "Example Energy",
        "location": "Hyderabad",
        "description": (
            "Electrical engineering role involving "
            "industrial equipment and maintenance."
        ),
        "url": (
            "https://example.com/jobs/"
            "electrical-engineer"
        ),
    }


def sample_contact():
    return {
        "name": "HR Manager",
        "email": "hr@example.com",
        "company": "Example Energy",
        "role": "HR Manager",
    }


def sample_resume_path(tmp_path):
    path = (
        tmp_path
        / "tailored"
        / "electrical_engineer.pdf"
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        b"%PDF-1.4\nJobAgent test resume\n"
    )

    return path


# ============================================================
# OUTREACH MANAGER
# ============================================================

def test_outreach_manager_prepares_message(
    tmp_path,
):
    resume_path = sample_resume_path(
        tmp_path
    )

    manager = OutreachManager(
        default_resume_path=str(
            resume_path
        )
    )

    result = manager.prepare_outreach(
        job=sample_job(),
        contacts=[
            sample_contact()
        ],
    )

    assert result is not None

    assert result.recipient == (
        "hr@example.com"
    )

    assert result.subject == (
        "Application for Electrical Engineer "
        "at Example Energy"
    )

    assert "Electrical Engineer" in (
        result.body
    )

    assert "Example Energy" in (
        result.body
    )

    assert result.resume_path == (
        str(resume_path)
    )


# ============================================================
# EMAIL COMPOSER
# ============================================================

def test_email_composer_creates_complete_email(
    tmp_path,
):
    resume_path = sample_resume_path(
        tmp_path
    )

    composer = EmailComposer(
        default_resume_path=str(
            resume_path
        )
    )

    email = composer.compose(
        job=sample_job(),
        contact=sample_contact(),
    )

    assert isinstance(
        email,
        ComposedEmail,
    )

    assert email.recipient == (
        "hr@example.com"
    )

    assert email.subject == (
        "Application for Electrical Engineer "
        "at Example Energy"
    )

    assert "Dear HR Manager" in (
        email.body
    )

    assert "Example Energy" in (
        email.body
    )

    assert email.resume_path == (
        str(resume_path)
    )


# ============================================================
# EMAIL SERIALIZATION
# ============================================================

def test_composed_email_serialization(
    tmp_path,
):
    resume_path = sample_resume_path(
        tmp_path
    )

    composer = EmailComposer(
        default_resume_path=str(
            resume_path
        )
    )

    email = composer.compose(
        job=sample_job(),
        contact=sample_contact(),
    )

    result = composer.to_dict(
        email
    )

    assert result["recipient"] == (
        "hr@example.com"
    )

    assert result["subject"] == (
        "Application for Electrical Engineer "
        "at Example Energy"
    )

    assert result["resume_path"] == (
        str(resume_path)
    )

    assert result["job"]["company"] == (
        "Example Energy"
    )

    assert result["contact"]["email"] == (
        "hr@example.com"
    )


# ============================================================
# EMAIL SENDER - DRY RUN
# ============================================================

def test_email_sender_dry_run(
    tmp_path,
):
    resume_path = sample_resume_path(
        tmp_path
    )

    composer = EmailComposer(
        default_resume_path=str(
            resume_path
        )
    )

    email = composer.compose(
        job=sample_job(),
        contact=sample_contact(),
    )

    sender = EmailSender(
        sender="test@example.com",
        password="not-used-in-dry-run",
        dry_run=True,
    )

    result = sender.send(
        email
    )

    assert result.success is True
    assert result.dry_run is True

    assert result.recipient == (
        "hr@example.com"
    )

    assert result.attachment == (
        str(resume_path)
    )


# ============================================================
# EMAIL MESSAGE WITH ATTACHMENT
# ============================================================

def test_email_sender_builds_attachment(
    tmp_path,
):
    resume_path = sample_resume_path(
        tmp_path
    )

    composer = EmailComposer(
        default_resume_path=str(
            resume_path
        )
    )

    email = composer.compose(
        job=sample_job(),
        contact=sample_contact(),
    )

    sender = EmailSender(
        sender="test@example.com",
        password="not-used",
        dry_run=True,
    )

    message = sender.build_message(
        email
    )

    assert message["To"] == (
        "hr@example.com"
    )

    assert message["Subject"] == (
        "Application for Electrical Engineer "
        "at Example Energy"
    )

    attachments = list(
        message.iter_attachments()
    )

    assert len(attachments) == 1

    assert attachments[0].get_filename() == (
        resume_path.name
    )


# ============================================================
# INVALID RESUME
# ============================================================

def test_email_sender_rejects_missing_resume():
    composer = EmailComposer(
        default_resume_path=(
            "does-not-exist.pdf"
        )
    )

    email = composer.compose(
        job=sample_job(),
        contact=sample_contact(),
    )

    sender = EmailSender(
        sender="test@example.com",
        password="test",
        dry_run=True,
    )

    try:
        sender.send(email)
        assert False, (
            "Expected FileNotFoundError."
        )
    except FileNotFoundError:
        pass


# ============================================================
# JOB AGENT + OUTREACH PREPARATION
# ============================================================

def test_job_agent_prepares_outreach_for_job(
    tmp_path,
):
    store = JobStore(
        storage_path=str(
            tmp_path / "jobs.json"
        )
    )

    agent = JobAgent(
        job_store=store,
    )

    job_id = agent.add_job(
        sample_job(),
        status="applied",
    )

    resume_path = sample_resume_path(
        tmp_path
    )

    result = agent.prepare_outreach(
        job_id=job_id,
        contacts=[
            sample_contact()
        ],
        candidate={
            "name": "Naveen Sai"
        },
        resume_path=str(
            resume_path
        ),
    )

    assert result is not None
    assert result.success is True
    assert result.status == "prepared"

    # OutreachResult uses `email`, not `recipient`.
    assert result.email == (
        "hr@example.com"
    )

    assert result.subject == (
        "Application for Electrical Engineer "
        "at Example Energy"
    )

    assert "Electrical Engineer" in (
        result.message
    )

    assert "Example Energy" in (
        result.message
    )

    # OutreachResult uses `attachment`.
    assert result.attachment == (
        str(resume_path)
    )


# ============================================================
# JOB AGENT + OUTREACH SENDING
# ============================================================

def test_job_agent_send_outreach_requires_confirmation(
    tmp_path,
):
    store = JobStore(
        storage_path=str(
            tmp_path / "jobs.json"
        )
    )

    agent = JobAgent(
        job_store=store,
    )

    job_id = agent.add_job(
        sample_job(),
        status="applied",
    )

    resume_path = sample_resume_path(
        tmp_path
    )

    result = agent.send_outreach(
        job_id=job_id,
        contacts=[
            sample_contact()
        ],
        candidate={
            "name": "Naveen Sai"
        },
        resume_path=str(
            resume_path
        ),
        confirm=False,
    )

    assert result is not None
    assert result.success is True
    assert result.status == (
        "confirmation_required"
    )

    assert result.email == (
        "hr@example.com"
    )

    assert result.attachment == (
        str(resume_path)
    )


# ============================================================
# COMPLETE OUTREACH PREPARATION FLOW
# ============================================================

def test_complete_outreach_preparation_flow(
    tmp_path,
):
    """
    Integration checkpoint:

        Applied Job
            ↓
        HR Contact
            ↓
        Contact Selection
            ↓
        Personalized Email
            ↓
        Tailored Resume Attachment
            ↓
        Email Ready To Send

    No real email is sent.
    """

    store = JobStore(
        storage_path=str(
            tmp_path / "jobs.json"
        )
    )

    agent = JobAgent(
        job_store=store,
    )

    job = sample_job()

    job_id = agent.add_job(
        job,
        status="applied",
    )

    resume_path = sample_resume_path(
        tmp_path
    )

    contact = sample_contact()

    outreach = agent.prepare_outreach(
        job_id=job_id,
        contacts=[contact],
        candidate={
            "name": "Naveen Sai",
            "degree": (
                "B.Tech Electrical & "
                "Electronics Engineering"
            ),
        },
        resume_path=str(
            resume_path
        ),
    )

    assert outreach is not None
    assert outreach.success is True
    assert outreach.status == "prepared"

    assert outreach.email == (
        contact["email"]
    )

    assert outreach.subject == (
        "Application for Electrical Engineer "
        "at Example Energy"
    )

    assert "Example Energy" in (
        outreach.message
    )

    assert "Electrical Engineer" in (
        outreach.message
    )

    assert outreach.attachment == (
        str(resume_path)
    )

    assert Path(
        outreach.attachment
    ).exists()


# ============================================================
# MULTIPLE CONTACTS
# ============================================================

def test_outreach_selects_best_contact(
    tmp_path,
):
    resume_path = sample_resume_path(
        tmp_path
    )

    contacts = [
        {
            "name": "General Employee",
            "email": "employee@example.com",
            "company": "Example Energy",
            "role": "Engineer",
        },
        {
            "name": "HR Manager",
            "email": "hr@example.com",
            "company": "Example Energy",
            "role": "HR Manager",
        },
    ]

    manager = OutreachManager(
        default_resume_path=str(
            resume_path
        )
    )

    result = manager.prepare_outreach(
        job=sample_job(),
        contacts=contacts,
    )

    assert result is not None

    assert result.recipient == (
        "hr@example.com"
    )


# ============================================================
# NO CONTACT
# ============================================================

def test_outreach_returns_none_without_contacts(
    tmp_path,
):
    resume_path = sample_resume_path(
        tmp_path
    )

    manager = OutreachManager(
        default_resume_path=str(
            resume_path
        )
    )

    result = manager.prepare_outreach(
        job=sample_job(),
        contacts=[],
    )

    assert result is None