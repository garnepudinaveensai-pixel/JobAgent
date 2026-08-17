from app.outreach.contact_discovery import (
    ContactDiscovery,
    DiscoveredContact,
    StaticContactProvider,
)


def test_discovered_contact_to_dict():
    contact = DiscoveredContact(
        email="recruiter@example.com",
        name="Recruiter",
        role="Talent Acquisition",
        company="Example",
        source="test",
        confidence=0.9,
        verification_status="verified",
    )

    data = contact.to_dict()

    assert data["email"] == (
        "recruiter@example.com"
    )

    assert data["role"] == (
        "Talent Acquisition"
    )

    assert data["confidence"] == 0.9


def test_static_provider():
    provider = StaticContactProvider(
        [
            {
                "email": "hr@example.com",
                "name": "HR",
            }
        ]
    )

    results = provider.search(
        company="Example"
    )

    assert len(results) == 1
    assert (
        results[0]["email"]
        == "hr@example.com"
    )


def test_discovery_normalizes_contacts():
    provider = StaticContactProvider(
        [
            {
                "email": " HR@Example.COM ",
                "name": " HR ",
                "role": " Recruiter ",
            }
        ]
    )

    discovery = ContactDiscovery(
        providers=[provider]
    )

    results = discovery.discover(
        company="Example Company"
    )

    assert len(results) == 1

    assert (
        results[0]["email"]
        == "hr@example.com"
    )

    assert results[0]["name"] == "HR"
    assert results[0]["role"] == "Recruiter"
    assert (
        results[0]["company"]
        == "Example Company"
    )


def test_invalid_email_is_ignored():
    provider = StaticContactProvider(
        [
            {
                "email": "not-an-email",
            },
            {
                "email": "valid@example.com",
            },
        ]
    )

    discovery = ContactDiscovery(
        providers=[provider]
    )

    results = discovery.discover(
        company="Example"
    )

    assert len(results) == 1
    assert (
        results[0]["email"]
        == "valid@example.com"
    )


def test_duplicate_emails_are_removed():
    provider = StaticContactProvider(
        [
            {
                "email": "hr@example.com",
                "confidence": 0.5,
            },
            {
                "email": "HR@example.com",
                "confidence": 0.9,
                "name": "Example HR",
                "role": "Recruiter",
            },
        ]
    )

    discovery = ContactDiscovery(
        providers=[provider]
    )

    results = discovery.discover(
        company="Example"
    )

    assert len(results) == 1

    assert (
        results[0]["email"]
        == "hr@example.com"
    )

    assert (
        results[0]["confidence"]
        == 0.9
    )


def test_domain_is_extracted_from_url():
    assert (
        ContactDiscovery.extract_domain(
            "https://www.example.com/jobs/123"
        )
        == "example.com"
    )


def test_domain_is_extracted_without_scheme():
    assert (
        ContactDiscovery.extract_domain(
            "www.example.com"
        )
        == "example.com"
    )


def test_domain_can_come_from_job():
    provider = StaticContactProvider(
        [
            {
                "email": "recruiter@example.com",
            }
        ]
    )

    discovery = ContactDiscovery(
        providers=[provider]
    )

    results = discovery.discover(
        company="Example",
        job={
            "company_domain": (
                "https://example.com"
            )
        },
    )

    assert len(results) == 1
    assert (
        results[0]["domain"]
        == "example.com"
    )


def test_quality_prefers_verified_contact():
    low = {
        "email": "a@example.com",
        "confidence": 0.5,
        "verification_status": "unknown",
    }

    high = {
        "email": "a@example.com",
        "confidence": 0.8,
        "verification_status": "verified",
        "name": "Recruiter",
        "role": "Recruiter",
    }

    assert (
        ContactDiscovery.contact_quality(
            high
        )
        > ContactDiscovery.contact_quality(
            low
        )
    )


def test_no_company_raises():
    discovery = ContactDiscovery()

    try:
        discovery.discover(
            company=""
        )
    except ValueError as exc:
        assert "company" in str(exc)
    else:
        raise AssertionError(
            "Expected ValueError"
        )


def test_provider_failure_does_not_break_discovery():

    class BrokenProvider:
        name = "broken"

        def is_available(self):
            return True

        def search(
            self,
            company,
            domain=None,
            job=None,
            **options,
        ):
            raise RuntimeError(
                "provider failure"
            )

    good = StaticContactProvider(
        [
            {
                "email": "hr@example.com",
            }
        ]
    )

    discovery = ContactDiscovery(
        providers=[
            BrokenProvider(),
            good,
        ]
    )

    results = discovery.discover(
        company="Example"
    )

    assert len(results) == 1
    assert (
        results[0]["email"]
        == "hr@example.com"
    )