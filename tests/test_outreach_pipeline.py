import pytest

from app.outreach.outreach_pipeline import (
    OutreachPipeline,
    OutreachResult,
)


# ============================================================
# TEST DOUBLES
# ============================================================


class FakeSelector:
    def __init__(self, result=None):
        self.result = result

    def select_best_contact(self, contacts, job=None):
        return self.result


class FakeComposer:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def compose(self, job, candidate, contact):
        if self.error:
            raise self.error

        return self.result


class FakeSender:
    def __init__(self, result=True, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def send(
        self,
        recipient,
        subject,
        message,
        attachment=None,
    ):
        self.calls.append(
            {
                "recipient": recipient,
                "subject": subject,
                "message": message,
                "attachment": attachment,
            }
        )

        if self.error:
            raise self.error

        return self.result


# ============================================================
# FIXTURES / HELPERS
# ============================================================


def make_contact():
    """
    Create a representative selected contact.
    """

    from app.outreach.contact_selector import (
        ContactSelection,
    )

    contact = {
        "email": "recruiter@company.com",
        "role": "Recruiter",
        "name": "Hiring Recruiter",
    }

    return ContactSelection(
        email="recruiter@company.com",
        score=190,
        reason="recruiting/HR role",
        contact=contact,
    )


def make_job():
    return {
        "title": "Graduate Engineer Trainee",
        "company": "Example Company",
        "location": "India",
        "url": "https://example.com/jobs/123",
        "description": "Electrical engineering role.",
    }


def make_candidate():
    return {
        "name": "Naveen Sai",
        "email": "naveen@example.com",
        "phone": "9876543210",
        "skills": [
            "Electrical Engineering",
            "Automation",
            "Python",
        ],
    }


def make_composed_email():
    return {
        "subject": "Application for Graduate Engineer Trainee",
        "message": "Dear Hiring Team,\n\nI am interested in this opportunity.",
        "attachment": "data/resumes/master_resume.pdf",
    }


# ============================================================
# CREATION
# ============================================================


def test_pipeline_creation():

    pipeline = OutreachPipeline()

    assert pipeline is not None
    assert pipeline.contact_selector is not None
    assert pipeline.email_composer is not None
    assert pipeline.email_sender is not None


# ============================================================
# CONTACT SELECTION
# ============================================================


def test_select_contact():

    selected = make_contact()

    selector = FakeSelector(
        result=selected
    )

    pipeline = OutreachPipeline(
        contact_selector=selector
    )

    contacts = [
        selected.contact
    ]

    result = pipeline.select_contact(
        contacts,
        job=make_job(),
    )

    assert result is selected


def test_select_contact_returns_none():

    selector = FakeSelector(
        result=None
    )

    pipeline = OutreachPipeline(
        contact_selector=selector
    )

    result = pipeline.select_contact(
        [],
        job=make_job(),
    )

    assert result is None


# ============================================================
# PREPARATION
# ============================================================


def test_prepare_outreach_success():

    selected = make_contact()

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=selected
        ),
        email_composer=FakeComposer(
            result=make_composed_email()
        ),
        email_sender=FakeSender(),
    )

    result = pipeline.prepare_outreach(
        contacts=[selected.contact],
        job=make_job(),
        candidate=make_candidate(),
    )

    assert isinstance(
        result,
        OutreachResult,
    )

    assert result.success is True
    assert result.status == "prepared"
    assert result.email == "recruiter@company.com"
    assert (
        result.subject
        == "Application for Graduate Engineer Trainee"
    )
    assert result.message
    assert (
        result.attachment
        == "data/resumes/master_resume.pdf"
    )


def test_prepare_outreach_uses_explicit_resume():

    selected = make_contact()

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=selected
        ),
        email_composer=FakeComposer(
            result={
                "subject": "Subject",
                "message": "Message",
                "attachment": "old.pdf",
            }
        ),
    )

    result = pipeline.prepare_outreach(
        contacts=[selected.contact],
        job=make_job(),
        candidate=make_candidate(),
        resume_path="data/resumes/tailored/resume.pdf",
    )

    assert result.success is True
    assert (
        result.attachment
        == "data/resumes/tailored/resume.pdf"
    )


def test_prepare_outreach_no_contact():

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=None
        ),
        email_composer=FakeComposer(
            result=make_composed_email()
        ),
    )

    result = pipeline.prepare_outreach(
        contacts=[],
        job=make_job(),
        candidate=make_candidate(),
    )

    assert result.success is False
    assert result.status == "no_suitable_contact"


def test_prepare_outreach_invalid_job():

    pipeline = OutreachPipeline()

    try:
        pipeline.prepare_outreach(
            contacts=[],
            job=None,
            candidate=make_candidate(),
        )
    except TypeError as exc:
        assert "job" in str(exc)
    else:
        assert False


def test_prepare_outreach_invalid_candidate():

    pipeline = OutreachPipeline()

    try:
        pipeline.prepare_outreach(
            contacts=[],
            job=make_job(),
            candidate=None,
        )
    except TypeError as exc:
        assert "candidate" in str(exc)
    else:
        assert False


def test_prepare_outreach_composition_failure():

    selected = make_contact()

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=selected
        ),
        email_composer=FakeComposer(
            error=RuntimeError(
                "composition failed"
            )
        ),
    )

    result = pipeline.prepare_outreach(
        contacts=[selected.contact],
        job=make_job(),
        candidate=make_candidate(),
    )

    assert result.success is False
    assert result.status == "composition_failed"
    assert (
        result.email
        == "recruiter@company.com"
    )
    assert (
        "composition failed"
        in result.error
    )


# ============================================================
# COMPOSER API COMPATIBILITY
# ============================================================

def test_compose_supports_candidate_aware_composer():
    selected = make_contact()

    class CandidateAwareComposer:
        def __init__(self):
            self.calls = []

        def compose(
            self,
            job,
            candidate,
            contact,
        ):
            self.calls.append(
                {
                    "job": job,
                    "candidate": candidate,
                    "contact": contact,
                }
            )

            return make_composed_email()

    composer = CandidateAwareComposer()

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=selected
        ),
        email_composer=composer,
    )

    candidate = make_candidate()
    job = make_job()

    result = pipeline.compose_outreach(
        contacts=[selected.contact],
        job=job,
        candidate=candidate,
    )

    assert result == make_composed_email()
    assert len(composer.calls) == 1
    assert composer.calls[0]["job"] == job
    assert composer.calls[0]["candidate"] == candidate
    assert composer.calls[0]["contact"] == selected.contact


def test_compose_supports_candidate_aware_composer_with_resume():
    selected = make_contact()

    class CandidateAwareComposer:
        def __init__(self):
            self.calls = []

        def compose(
            self,
            job,
            candidate,
            contact,
            resume_path,
        ):
            self.calls.append(
                {
                    "job": job,
                    "candidate": candidate,
                    "contact": contact,
                    "resume_path": resume_path,
                }
            )

            return make_composed_email()

    composer = CandidateAwareComposer()

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=selected
        ),
        email_composer=composer,
    )

    candidate = make_candidate()
    job = make_job()
    resume_path = "data/resumes/tailored/resume.pdf"

    result = pipeline.compose_outreach(
        contacts=[selected.contact],
        job=job,
        candidate=candidate,
        resume_path=resume_path,
    )

    assert result == make_composed_email()
    assert len(composer.calls) == 1
    assert composer.calls[0]["job"] == job
    assert composer.calls[0]["candidate"] == candidate
    assert composer.calls[0]["contact"] == selected.contact
    assert composer.calls[0]["resume_path"] == resume_path


def test_compose_supports_production_composer():
    selected = make_contact()

    class ProductionComposer:
        def __init__(self):
            self.calls = []

        def compose(
            self,
            job,
            contact,
            resume_path=None,
        ):
            self.calls.append(
                {
                    "job": job,
                    "contact": contact,
                    "resume_path": resume_path,
                }
            )

            return make_composed_email()

    composer = ProductionComposer()

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=selected
        ),
        email_composer=composer,
    )

    job = make_job()

    result = pipeline.compose_outreach(
        contacts=[selected.contact],
        job=job,
    )

    assert result == make_composed_email()
    assert len(composer.calls) == 1
    assert composer.calls[0]["job"] == job
    assert composer.calls[0]["contact"] == selected.contact
    assert composer.calls[0]["resume_path"] is None


def test_compose_production_composer_receives_resume():
    selected = make_contact()

    class ProductionComposer:
        def __init__(self):
            self.calls = []

        def compose(
            self,
            job,
            contact,
            resume_path=None,
        ):
            self.calls.append(
                {
                    "job": job,
                    "contact": contact,
                    "resume_path": resume_path,
                }
            )

            return make_composed_email()

    composer = ProductionComposer()

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=selected
        ),
        email_composer=composer,
    )

    resume_path = "data/resumes/tailored/resume.pdf"

    pipeline.compose_outreach(
        contacts=[selected.contact],
        job=make_job(),
        resume_path=resume_path,
    )

    assert len(composer.calls) == 1
    assert composer.calls[0]["resume_path"] == resume_path


def test_compose_rejects_unsupported_composer_signature():
    selected = make_contact()

    class UnsupportedComposer:
        def compose(self):
            return make_composed_email()

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=selected
        ),
        email_composer=UnsupportedComposer(),
    )

    with pytest.raises(TypeError) as exc_info:
        pipeline.compose_outreach(
            contacts=[selected.contact],
            job=make_job(),
            candidate=make_candidate(),
        )

    assert "Unsupported EmailComposer.compose()" in str(
        exc_info.value
    )


# ============================================================
# SEND — CONFIRMATION
# ============================================================


def test_send_outreach_requires_confirmation():

    selected = make_contact()

    sender = FakeSender(
        result=True
    )

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=selected
        ),
        email_composer=FakeComposer(
            result=make_composed_email()
        ),
        email_sender=sender,
    )

    result = pipeline.send_outreach(
        contacts=[selected.contact],
        job=make_job(),
        candidate=make_candidate(),
        confirm=False,
    )

    assert result.success is True
    assert (
        result.status
        == "confirmation_required"
    )

    assert sender.calls == []


# ============================================================
# SEND — SUCCESS
# ============================================================


def test_send_outreach_success():

    selected = make_contact()

    sender = FakeSender(
        result=True
    )

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=selected
        ),
        email_composer=FakeComposer(
            result=make_composed_email()
        ),
        email_sender=sender,
    )

    result = pipeline.send_outreach(
        contacts=[selected.contact],
        job=make_job(),
        candidate=make_candidate(),
        confirm=True,
    )

    assert result.success is True
    assert result.status == "sent"
    assert (
        result.email
        == "recruiter@company.com"
    )

    assert len(sender.calls) == 1

    assert (
        sender.calls[0]["recipient"]
        == "recruiter@company.com"
    )

    assert (
        sender.calls[0]["subject"]
        == "Application for Graduate Engineer Trainee"
    )

    assert (
        sender.calls[0]["attachment"]
        == "data/resumes/master_resume.pdf"
    )


# ============================================================
# SEND — FAILURE
# ============================================================


def test_send_outreach_sender_returns_false():

    selected = make_contact()

    sender = FakeSender(
        result=False
    )

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=selected
        ),
        email_composer=FakeComposer(
            result=make_composed_email()
        ),
        email_sender=sender,
    )

    result = pipeline.send_outreach(
        contacts=[selected.contact],
        job=make_job(),
        candidate=make_candidate(),
        confirm=True,
    )

    assert result.success is False
    assert result.status == "send_failed"


def test_send_outreach_sender_returns_failure_dict():

    selected = make_contact()

    sender = FakeSender(
        result={
            "success": False,
            "error": "SMTP failed",
        }
    )

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=selected
        ),
        email_composer=FakeComposer(
            result=make_composed_email()
        ),
        email_sender=sender,
    )

    result = pipeline.send_outreach(
        contacts=[selected.contact],
        job=make_job(),
        candidate=make_candidate(),
        confirm=True,
    )

    assert result.success is False
    assert result.status == "send_failed"
    assert result.error == "SMTP failed"


def test_send_outreach_sender_exception():

    selected = make_contact()

    sender = FakeSender(
        error=RuntimeError(
            "SMTP connection failed"
        )
    )

    pipeline = OutreachPipeline(
        contact_selector=FakeSelector(
            result=selected
        ),
        email_composer=FakeComposer(
            result=make_composed_email()
        ),
        email_sender=sender,
    )

    result = pipeline.send_outreach(
        contacts=[selected.contact],
        job=make_job(),
        candidate=make_candidate(),
        confirm=True,
    )

    assert result.success is False
    assert result.status == "send_failed"
    assert (
        "SMTP connection failed"
        in result.error
    )


# ============================================================
# RESULT HELPERS
# ============================================================


def test_get_value_from_dict():

    result = OutreachPipeline._get_value(
        {
            "subject": "Test",
        },
        "subject",
    )

    assert result == "Test"


def test_get_value_missing_dict_value():

    result = OutreachPipeline._get_value(
        {},
        "subject",
        default="fallback",
    )

    assert result == "fallback"


def test_get_value_from_object():

    class Result:
        subject = "Object Subject"

    result = OutreachPipeline._get_value(
        Result(),
        "subject",
    )

    assert result == "Object Subject"


def test_send_success_boolean():

    assert (
        OutreachPipeline._send_success(True)
        is True
    )

    assert (
        OutreachPipeline._send_success(False)
        is False
    )


def test_send_success_dict():

    assert (
        OutreachPipeline._send_success(
            {"success": True}
        )
        is True
    )

    assert (
        OutreachPipeline._send_success(
            {"success": False}
        )
        is False
    )


def test_send_success_object():

    class Result:
        success = True

    assert (
        OutreachPipeline._send_success(
            Result()
        )
        is True
    )


def test_get_error_from_dict():

    result = OutreachPipeline._get_error(
        {
            "error": "SMTP error"
        }
    )

    assert result == "SMTP error"


def test_get_error_from_object():

    class Result:
        error = "Object error"

    result = OutreachPipeline._get_error(
        Result()
    )

    assert result == "Object error"


def test_get_error_without_error():

    assert (
        OutreachPipeline._get_error(
            {"success": False}
        )
        is None
    )