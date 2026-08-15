import json

import pytest

from app.outreach.contact_finder import (
    Contact,
    ContactFinder,
)


# ============================================================
# DOMAIN EXTRACTION
# ============================================================


def test_extract_domain_from_url():

    result = ContactFinder.extract_domain(
        "https://www.example.com/jobs/123"
    )

    assert result == "example.com"


def test_extract_domain_from_email():

    result = ContactFinder.extract_domain(
        "hr@example.com"
    )

    assert result == "example.com"


def test_extract_domain_from_plain_domain():

    result = ContactFinder.extract_domain(
        "example.com"
    )

    assert result == "example.com"


def test_extract_domain_empty():

    result = ContactFinder.extract_domain("")

    assert result == ""


# ============================================================
# JOB DOMAIN
# ============================================================


def test_get_job_domain_from_company_domain():

    finder = ContactFinder()

    job = {
        "title": "Electrical Engineer",
        "company": "Example",
        "company_domain": "example.com",
    }

    assert (
        finder.get_job_domain(job)
        == "example.com"
    )


def test_get_job_domain_from_job_url():

    finder = ContactFinder()

    job = {
        "title": "Electrical Engineer",
        "company": "Example",
        "url": (
            "https://example.com/jobs/123"
        ),
    }

    assert (
        finder.get_job_domain(job)
        == "example.com"
    )


def test_get_job_domain_without_domain():

    finder = ContactFinder()

    job = {
        "title": "Electrical Engineer",
        "company": "Example",
    }

    assert (
        finder.get_job_domain(job)
        == ""
    )


# ============================================================
# CONTACT MODEL
# ============================================================


def test_contact_to_dict():

    contact = Contact(
        email="hr@example.com",
        first_name="Jane",
        last_name="Doe",
        full_name="Jane Doe",
        position="HR Manager",
        department="Human Resources",
        company="Example",
        confidence=95,
        source="hunter",
        verification_status="valid",
    )

    result = contact.to_dict()

    assert result["email"] == (
        "hr@example.com"
    )

    assert result["position"] == (
        "HR Manager"
    )

    assert result["confidence"] == 95


# ============================================================
# EMAIL VALIDATION
# ============================================================


def test_valid_email():

    assert ContactFinder._valid_email(
        "hr@example.com"
    )


def test_invalid_email():

    assert not ContactFinder._valid_email(
        "not-an-email"
    )


# ============================================================
# HUNTER RESPONSE PARSING
# ============================================================


def test_parse_hunter_response():

    finder = ContactFinder(
        hunter_api_key="test-key"
    )

    payload = {
        "data": {
            "domain": "example.com",
            "organization": "Example Corp",
            "emails": [
                {
                    "value": "hr@example.com",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "full_name": "Jane Doe",
                    "position": "HR Manager",
                    "department": "Human Resources",
                    "confidence": 95,
                    "verification": {
                        "status": "valid"
                    },
                }
            ],
        }
    }

    contacts = (
        finder._parse_hunter_response(
            payload
        )
    )

    assert len(contacts) == 1

    contact = contacts[0]

    assert contact.email == (
        "hr@example.com"
    )

    assert contact.full_name == (
        "Jane Doe"
    )

    assert contact.position == (
        "HR Manager"
    )

    assert contact.department == (
        "Human Resources"
    )

    assert contact.confidence == 95

    assert contact.source == "hunter"

    assert (
        contact.verification_status
        == "valid"
    )


def test_parse_hunter_ignores_invalid_email():

    finder = ContactFinder(
        hunter_api_key="test-key"
    )

    payload = {
        "data": {
            "domain": "example.com",
            "emails": [
                {
                    "value": "invalid-email",
                    "position": "HR Manager",
                }
            ],
        }
    }

    contacts = (
        finder._parse_hunter_response(
            payload
        )
    )

    assert contacts == []


# ============================================================
# RELEVANCE
# ============================================================


def test_hr_contact_ranked_first():

    finder = ContactFinder()

    contacts = [
        Contact(
            email="engineer@example.com",
            full_name="John Engineer",
            position="Software Engineer",
            confidence=95,
        ),
        Contact(
            email="recruiter@example.com",
            full_name="Jane Recruiter",
            position="Technical Recruiter",
            department="Recruiting",
            confidence=90,
        ),
    ]

    result = (
        finder.find_relevant_contacts(
            contacts
        )
    )

    assert result[0].email == (
        "recruiter@example.com"
    )


def test_hr_department_is_prioritized():

    finder = ContactFinder()

    contact = Contact(
        email="hr@example.com",
        position="Manager",
        department="Human Resources",
        confidence=80,
    )

    result = (
        finder.find_relevant_contacts(
            [contact]
        )
    )

    assert len(result) == 1

    assert result[0].email == (
        "hr@example.com"
    )


def test_minimum_confidence_filter():

    finder = ContactFinder()

    contacts = [
        Contact(
            email="low@example.com",
            position="Recruiter",
            confidence=40,
        ),
        Contact(
            email="high@example.com",
            position="Recruiter",
            confidence=90,
        ),
    ]

    result = (
        finder.find_relevant_contacts(
            contacts,
            minimum_confidence=70,
        )
    )

    assert len(result) == 1

    assert result[0].email == (
        "high@example.com"
    )


# ============================================================
# API KEY VALIDATION
# ============================================================


def test_hunter_requires_api_key():

    finder = ContactFinder(
        hunter_api_key=""
    )

    with pytest.raises(ValueError):

        finder.search_hunter(
            "example.com"
        )


def test_hunter_requires_domain():

    finder = ContactFinder(
        hunter_api_key="test-key"
    )

    with pytest.raises(ValueError):

        finder.search_hunter(
            ""
        )


# ============================================================
# API REQUEST TEST
# ============================================================


def test_search_hunter_parses_api_response(
    monkeypatch,
):

    finder = ContactFinder(
        hunter_api_key="test-key"
    )

    class FakeResponse:

        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            return False

        def read(self):
            return json.dumps(
                {
                    "data": {
                        "domain": "example.com",
                        "organization": (
                            "Example Corp"
                        ),
                        "emails": [
                            {
                                "value": (
                                    "recruiter@example.com"
                                ),
                                "full_name": (
                                    "Jane Recruiter"
                                ),
                                "position": (
                                    "Talent Acquisition"
                                ),
                                "department": (
                                    "Human Resources"
                                ),
                                "confidence": 95,
                                "verification": {
                                    "status": "valid"
                                },
                            }
                        ],
                    }
                }
            ).encode("utf-8")

    def fake_urlopen(
        request,
        timeout,
    ):
        assert (
            "api.hunter.io"
            in request.full_url
        )

        assert (
            "domain=example.com"
            in request.full_url
        )

        return FakeResponse()

    monkeypatch.setattr(
        "app.outreach.contact_finder.urlopen",
        fake_urlopen,
    )

    contacts = finder.search_hunter(
        "example.com"
    )

    assert len(contacts) == 1

    assert contacts[0].email == (
        "recruiter@example.com"
    )

    assert contacts[0].position == (
        "Talent Acquisition"
    )


# ============================================================
# JOB CONTACT SEARCH
# ============================================================


def test_find_for_job(
    monkeypatch,
):

    finder = ContactFinder(
        hunter_api_key="test-key"
    )

    monkeypatch.setattr(
        finder,
        "search_hunter",
        lambda domain: [
            Contact(
                email="hr@example.com",
                full_name="Jane HR",
                position="HR Manager",
                department="Human Resources",
                confidence=95,
                source="hunter",
            )
        ],
    )

    job = {
        "title": "Electrical Engineer",
        "company": "Example Corp",
        "company_domain": "example.com",
    }

    contacts = finder.find_for_job(
        job
    )

    assert len(contacts) == 1

    assert contacts[0].email == (
        "hr@example.com"
    )


def test_find_for_job_without_domain():

    finder = ContactFinder(
        hunter_api_key="test-key"
    )

    job = {
        "title": "Electrical Engineer",
        "company": "Example Corp",
    }

    assert (
        finder.find_for_job(job)
        == []
    )