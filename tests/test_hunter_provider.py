import json

from app.outreach.hunter_provider import (
    HunterProvider,
)


def test_hunter_provider_without_key_is_unavailable():
    provider = HunterProvider(
        api_key=""
    )

    assert (
        provider.is_available()
        is False
    )


def test_hunter_provider_with_key_is_available():
    provider = HunterProvider(
        api_key="test-key"
    )

    assert (
        provider.is_available()
        is True
    )


def test_hunter_provider_normalizes_response():
    payload = {
        "data": {
            "emails": [
                {
                    "value": (
                        "recruiter@example.com"
                    ),
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "position": (
                        "Talent Acquisition"
                    ),
                    "confidence": 95,
                    "verification": {
                        "status": "valid"
                    },
                }
            ]
        }
    }

    results = (
        HunterProvider._normalize_response(
            payload,
            company="Example Company",
            domain="example.com",
        )
    )

    assert len(results) == 1

    contact = results[0]

    assert (
        contact["email"]
        == "recruiter@example.com"
    )

    assert (
        contact["name"]
        == "Jane Doe"
    )

    assert (
        contact["role"]
        == "Talent Acquisition"
    )

    assert (
        contact["company"]
        == "Example Company"
    )

    assert (
        contact["domain"]
        == "example.com"
    )

    assert (
        contact["confidence"]
        == 95
    )


def test_hunter_empty_response():
    results = (
        HunterProvider._normalize_response(
            {},
            company="Example",
            domain="example.com",
        )
    )

    assert results == []


def test_hunter_malformed_response():
    results = (
        HunterProvider._normalize_response(
            {
                "data": {
                    "emails": None
                }
            },
            company="Example",
            domain="example.com",
        )
    )

    assert results == []