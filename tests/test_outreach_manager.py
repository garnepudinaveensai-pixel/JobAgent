from pathlib import Path

from app.outreach.outreach_manager import (
    OutreachManager,
    OutreachMessage,
)


def test_manager_creation():

    manager = OutreachManager()

    assert manager is not None
    assert manager.default_resume_path


def test_custom_resume_path():

    manager = OutreachManager(
        default_resume_path="resume.pdf"
    )

    assert (
        manager.default_resume_path
        == "resume.pdf"
    )


def test_no_contacts_returns_none():

    manager = OutreachManager()

    result = manager.prepare_outreach(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contacts=[],
    )

    assert result is None


def test_invalid_contacts_returns_none():

    manager = OutreachManager()

    result = manager.prepare_outreach(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contacts=[
            None,
            "invalid",
            {"email": "not-an-email"},
        ],
    )

    assert result is None


def test_recruiter_is_selected():

    manager = OutreachManager()

    result = manager.prepare_outreach(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contacts=[
            {
                "email": "info@abc.com",
            },
            {
                "email": "recruiter@abc.com",
                "role": "Recruiter",
            },
        ],
    )

    assert result is not None

    assert (
        result.recipient
        == "recruiter@abc.com"
    )


def test_talent_acquisition_is_selected():

    manager = OutreachManager()

    result = manager.prepare_outreach(
        job={
            "title": "Automation Engineer",
            "company": "ABC",
        },
        contacts=[
            {
                "email": "info@abc.com",
            },
            {
                "email": "talent@abc.com",
                "role": "Talent Acquisition",
            },
        ],
    )

    assert result is not None

    assert (
        result.recipient
        == "talent@abc.com"
    )


def test_subject_contains_job_title():

    manager = OutreachManager()

    subject = manager.build_subject(
        {
            "title": "Electrical Engineer",
            "company": "ABC",
        }
    )

    assert "Electrical Engineer" in subject
    assert "ABC" in subject


def test_subject_without_company():

    manager = OutreachManager()

    subject = manager.build_subject(
        {
            "title": "Electrical Engineer",
        }
    )

    assert (
        subject
        == "Application for Electrical Engineer"
    )


def test_body_contains_job_information():

    manager = OutreachManager()

    body = manager.build_body(
        job={
            "title": "Automation Engineer",
            "company": "ABC",
            "location": "Hyderabad",
        }
    )

    assert "Automation Engineer" in body
    assert "ABC" in body
    assert "Hyderabad" in body


def test_body_contains_engineering_background():

    manager = OutreachManager()

    body = manager.build_body(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        }
    )

    assert (
        "Electrical & Electronics Engineering"
        in body
    )

    assert (
        "condition-based maintenance"
        in body
    )


def test_named_contact_gets_personalized_greeting():

    manager = OutreachManager()

    body = manager.build_body(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contact={
            "email": "recruiter@abc.com",
            "name": "Hiring Manager",
            "role": "Recruiter",
        },
    )

    assert "Dear Hiring Manager," in body


def test_generic_contact_gets_hiring_team_greeting():

    manager = OutreachManager()

    body = manager.build_body(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        }
    )

    assert "Dear Hiring Team," in body


def test_resume_path_is_preserved():

    manager = OutreachManager()

    result = manager.prepare_outreach(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contacts=[
            {
                "email": "recruiter@abc.com",
                "role": "Recruiter",
            }
        ],
        resume_path="data/resumes/tailored/abc.pdf",
    )

    assert result is not None

    assert (
        result.resume_path
        == "data/resumes/tailored/abc.pdf"
    )


def test_default_resume_path_is_used():

    manager = OutreachManager(
        default_resume_path="master.pdf"
    )

    result = manager.prepare_outreach(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contacts=[
            {
                "email": "recruiter@abc.com",
                "role": "Recruiter",
            }
        ],
    )

    assert result is not None

    assert result.resume_path == "master.pdf"


def test_result_is_structured():

    manager = OutreachManager()

    result = manager.prepare_outreach(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contacts=[
            {
                "email": "recruiter@abc.com",
                "role": "Recruiter",
            }
        ],
    )

    assert isinstance(
        result,
        OutreachMessage,
    )


def test_contact_score_is_preserved():

    manager = OutreachManager()

    result = manager.prepare_outreach(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contacts=[
            {
                "email": "recruiter@abc.com",
                "role": "Recruiter",
            }
        ],
    )

    assert result is not None
    assert result.contact_score > 0


def test_original_contact_is_preserved():

    manager = OutreachManager()

    contact = {
        "email": "recruiter@abc.com",
        "role": "Recruiter",
        "name": "John",
    }

    result = manager.prepare_outreach(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contacts=[contact],
    )

    assert result is not None
    assert result.contact is contact


def test_to_dict():

    manager = OutreachManager()

    result = manager.prepare_outreach(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contacts=[
            {
                "email": "recruiter@abc.com",
                "role": "Recruiter",
            }
        ],
    )

    assert result is not None

    data = manager.to_dict(result)

    assert isinstance(data, dict)
    assert (
        data["recipient"]
        == "recruiter@abc.com"
    )
    assert "subject" in data
    assert "body" in data
    assert "resume_path" in data


def test_resume_validation_existing_file(
    tmp_path,
):

    resume = tmp_path / "resume.pdf"
    resume.write_text(
        "test resume",
        encoding="utf-8",
    )

    assert (
        OutreachManager.validate_resume_path(
            str(resume)
        )
        is True
    )


def test_resume_validation_missing_file(
    tmp_path,
):

    resume = tmp_path / "missing.pdf"

    assert (
        OutreachManager.validate_resume_path(
            str(resume)
        )
        is False
    )


def test_no_email_sending_method_exists():

    manager = OutreachManager()

    assert not hasattr(
        manager,
        "send",
    )