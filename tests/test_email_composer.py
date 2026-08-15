import pytest

from app.outreach.email_composer import (
    ComposedEmail,
    EmailComposer,
)


def test_composer_creation():

    composer = EmailComposer()

    assert composer is not None
    assert composer.default_resume_path


def test_custom_resume_path():

    composer = EmailComposer(
        default_resume_path="resume.pdf"
    )

    assert (
        composer.default_resume_path
        == "resume.pdf"
    )


def test_compose_returns_structured_email():

    composer = EmailComposer()

    result = composer.compose(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contact={
            "email": "recruiter@abc.com",
            "role": "Recruiter",
        },
    )

    assert isinstance(
        result,
        ComposedEmail,
    )


def test_recipient_is_normalized():

    composer = EmailComposer()

    result = composer.compose(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contact={
            "email": " Recruiter@ABC.COM ",
        },
    )

    assert (
        result.recipient
        == "recruiter@abc.com"
    )


def test_invalid_recipient_is_rejected():

    composer = EmailComposer()

    with pytest.raises(ValueError):

        composer.compose(
            job={
                "title": "Electrical Engineer",
            },
            contact={
                "email": "not-an-email",
            },
        )


def test_missing_recipient_is_rejected():

    composer = EmailComposer()

    with pytest.raises(ValueError):

        composer.compose(
            job={
                "title": "Electrical Engineer",
            },
            contact={},
        )


def test_invalid_job_type():

    composer = EmailComposer()

    with pytest.raises(TypeError):

        composer.compose(
            job="invalid",
            contact={
                "email": "hr@abc.com",
            },
        )


def test_invalid_contact_type():

    composer = EmailComposer()

    with pytest.raises(TypeError):

        composer.compose(
            job={
                "title": "Electrical Engineer",
            },
            contact="invalid",
        )


def test_subject_contains_title():

    composer = EmailComposer()

    subject = composer.build_subject(
        {
            "title": "Electrical Engineer",
            "company": "ABC",
        }
    )

    assert (
        "Electrical Engineer"
        in subject
    )


def test_subject_contains_company():

    composer = EmailComposer()

    subject = composer.build_subject(
        {
            "title": "Electrical Engineer",
            "company": "ABC",
        }
    )

    assert "ABC" in subject


def test_subject_without_company():

    composer = EmailComposer()

    subject = composer.build_subject(
        {
            "title": "Electrical Engineer",
        }
    )

    assert (
        subject
        == "Application for Electrical Engineer"
    )


def test_subject_without_title():

    composer = EmailComposer()

    subject = composer.build_subject(
        {
            "company": "ABC",
        }
    )

    assert (
        subject
        == "Job Application – ABC"
    )


def test_default_subject():

    composer = EmailComposer()

    subject = composer.build_subject({})

    assert (
        subject
        == "Job Application – Electrical Engineer"
    )


def test_named_contact_gets_personalized_greeting():

    composer = EmailComposer()

    body = composer.build_body(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contact={
            "name": "John",
        },
    )

    assert "Dear John," in body


def test_missing_contact_name_uses_hiring_team():

    composer = EmailComposer()

    body = composer.build_body(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contact={},
    )

    assert "Dear Hiring Team," in body


def test_body_contains_job_title():

    composer = EmailComposer()

    body = composer.build_body(
        job={
            "title": "Automation Engineer",
            "company": "ABC",
        }
    )

    assert (
        "Automation Engineer"
        in body
    )


def test_body_contains_company():

    composer = EmailComposer()

    body = composer.build_body(
        job={
            "title": "Automation Engineer",
            "company": "ABC",
        }
    )

    assert "ABC" in body


def test_body_contains_location():

    composer = EmailComposer()

    body = composer.build_body(
        job={
            "title": "Automation Engineer",
            "company": "ABC",
            "location": "Hyderabad",
        }
    )

    assert "Hyderabad" in body


def test_body_contains_engineering_background():

    composer = EmailComposer()

    body = composer.build_body(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        }
    )

    assert (
        "Electrical & Electronics Engineering"
        in body
    )


def test_body_contains_relevant_experience():

    composer = EmailComposer()

    body = composer.build_body(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        }
    )

    assert (
        "condition-based maintenance"
        in body
    )

    assert (
        "TI C2000"
        in body
    )


def test_resume_path_is_preserved():

    composer = EmailComposer()

    result = composer.compose(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contact={
            "email": "hr@abc.com",
        },
        resume_path="tailored/abc.pdf",
    )

    assert (
        result.resume_path
        == "tailored/abc.pdf"
    )


def test_default_resume_path_is_used():

    composer = EmailComposer(
        default_resume_path="master.pdf"
    )

    result = composer.compose(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contact={
            "email": "hr@abc.com",
        },
    )

    assert result.resume_path == "master.pdf"


def test_empty_resume_path_is_rejected():

    composer = EmailComposer()

    with pytest.raises(ValueError):

        composer.compose(
            job={
                "title": "Electrical Engineer",
            },
            contact={
                "email": "hr@abc.com",
            },
            resume_path="",
        )


def test_to_dict():

    composer = EmailComposer()

    result = composer.compose(
        job={
            "title": "Electrical Engineer",
            "company": "ABC",
        },
        contact={
            "email": "hr@abc.com",
        },
    )

    data = composer.to_dict(result)

    assert isinstance(data, dict)
    assert (
        data["recipient"]
        == "hr@abc.com"
    )
    assert "subject" in data
    assert "body" in data
    assert "resume_path" in data
    assert "job" in data
    assert "contact" in data


def test_to_dict_rejects_invalid_object():

    composer = EmailComposer()

    with pytest.raises(TypeError):

        composer.to_dict(
            {
                "recipient": "hr@abc.com",
            }
        )


def test_composer_does_not_send_email():

    composer = EmailComposer()

    assert not hasattr(
        composer,
        "send",
    )


def test_full_composition():

    composer = EmailComposer()

    result = composer.compose(
        job={
            "title": "Graduate Engineer Trainee",
            "company": "ABC Industries",
            "location": "Hyderabad",
        },
        contact={
            "email": "recruiter@abc.com",
            "name": "Recruitment Team",
            "role": "Recruiter",
        },
        resume_path=(
            "data/resumes/tailored/abc.pdf"
        ),
    )

    assert (
        result.recipient
        == "recruiter@abc.com"
    )

    assert (
        "Graduate Engineer Trainee"
        in result.subject
    )

    assert (
        "ABC Industries"
        in result.subject
    )

    assert (
        "Recruitment Team"
        in result.body
    )

    assert (
        "Hyderabad"
        in result.body
    )

    assert (
        result.resume_path
        == "data/resumes/tailored/abc.pdf"
    )