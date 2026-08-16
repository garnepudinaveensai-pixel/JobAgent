import pytest
from unittest.mock import MagicMock

from app.core.sources.indeed_source import IndeedSource


def test_indeed_source_name():
    source = IndeedSource(
        browser=MagicMock()
    )

    assert source.name == "indeed"


def test_indeed_source_requires_keywords():
    source = IndeedSource(
        browser=MagicMock()
    )

    with pytest.raises(
        ValueError,
        match="Indeed keywords cannot be empty",
    ):
        source.search(
            keywords=""
        )


def test_indeed_source_requires_browser():
    source = IndeedSource(
        browser=None
    )

    with pytest.raises(
        RuntimeError,
        match="IndeedSource requires a browser",
    ):
        source.search(
            keywords="electrical engineer"
        )


def test_indeed_source_search():
    browser = MagicMock()

    source = IndeedSource(
        browser=browser
    )

    source.discovery.discover_indeed = (
        MagicMock(
            return_value=[
                {
                    "title": "Electrical Engineer",
                    "company": "Example Company",
                    "location": "Hyderabad",
                    "url": (
                        "https://example.com/job/1"
                    ),
                    "description": (
                        "Electrical engineering role."
                    ),
                }
            ]
        )
    )

    jobs = source.search(
        keywords="electrical engineer",
        location="Hyderabad",
    )

    assert len(jobs) == 1

    assert jobs[0] == {
        "title": "Electrical Engineer",
        "company": "Example Company",
        "location": "Hyderabad",
        "url": (
            "https://example.com/job/1"
        ),
        "description": (
            "Electrical engineering role."
        ),
        "source": "indeed",
    }


def test_indeed_source_ignores_invalid_jobs():
    source = IndeedSource(
        browser=MagicMock()
    )

    source.discovery.discover_indeed = (
        MagicMock(
            return_value=[
                None,
                "invalid",
                123,
                {
                    "title": "Valid Job",
                },
            ]
        )
    )

    jobs = source.search(
        keywords="engineer"
    )

    assert len(jobs) == 1

    assert jobs[0]["title"] == "Valid Job"
    assert jobs[0]["company"] == ""
    assert jobs[0]["location"] == ""
    assert jobs[0]["url"] == ""
    assert jobs[0]["description"] == ""
    assert jobs[0]["source"] == "indeed"


def test_indeed_source_normalizes_fields():
    source = IndeedSource(
        browser=MagicMock()
    )

    source.discovery.discover_indeed = (
        MagicMock(
            return_value=[
                {
                    "title": "  Electrical Engineer  ",
                    "company": " Example Company ",
                    "location": " Hyderabad ",
                    "url": " https://example.com/job/1 ",
                    "description": " Electrical role. ",
                }
            ]
        )
    )

    jobs = source.search(
        keywords=" engineer "
    )

    assert jobs[0] == {
        "title": "Electrical Engineer",
        "company": "Example Company",
        "location": "Hyderabad",
        "url": "https://example.com/job/1",
        "description": "Electrical role.",
        "source": "indeed",
    }


def test_indeed_source_available_with_browser():
    source = IndeedSource(
        browser=MagicMock()
    )

    assert source.is_available() is True


def test_indeed_source_unavailable_without_browser():
    source = IndeedSource(
        browser=None
    )

    assert source.is_available() is False