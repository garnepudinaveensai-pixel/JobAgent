import pytest
from unittest.mock import MagicMock

from app.core.sources.naukri_source import NaukriSource


# ============================================================
# NAME
# ============================================================


def test_naukri_source_name():
    source = NaukriSource(
        browser=MagicMock()
    )

    assert source.name == "naukri"


# ============================================================
# KEYWORDS
# ============================================================


def test_naukri_source_requires_keywords():
    source = NaukriSource(
        browser=MagicMock()
    )

    with pytest.raises(
        ValueError,
        match="Naukri keywords cannot be empty",
    ):
        source.search(
            keywords=""
        )


# ============================================================
# BROWSER
# ============================================================


def test_naukri_source_requires_browser():
    source = NaukriSource(
        browser=None
    )

    with pytest.raises(
        RuntimeError,
        match="NaukriSource requires a browser",
    ):
        source.search(
            keywords="electrical engineer"
        )


# ============================================================
# SEARCH
# ============================================================


def test_naukri_source_search():
    browser = MagicMock()

    source = NaukriSource(
        browser=browser
    )

    source.discovery.discover_naukri = (
        MagicMock(
            return_value=[
                {
                    "title": "Electrical Engineer",
                    "company": "Example Company",
                    "location": "Hyderabad",
                    "url": (
                        "https://www.naukri.com/"
                        "job-listings-example"
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
            "https://www.naukri.com/"
            "job-listings-example"
        ),
        "description": (
            "Electrical engineering role."
        ),
        "source": "naukri",
    }


# ============================================================
# INVALID JOBS
# ============================================================


def test_naukri_source_ignores_invalid_jobs():
    browser = MagicMock()

    source = NaukriSource(
        browser=browser
    )

    source.discovery.discover_naukri = (
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

    assert jobs[0]["title"] == (
        "Valid Job"
    )

    assert jobs[0]["company"] == ""
    assert jobs[0]["location"] == ""
    assert jobs[0]["url"] == ""
    assert jobs[0]["description"] == ""

    assert jobs[0]["source"] == "naukri"


# ============================================================
# NORMALIZATION
# ============================================================


def test_naukri_source_normalizes_fields():
    browser = MagicMock()

    source = NaukriSource(
        browser=browser
    )

    source.discovery.discover_naukri = (
        MagicMock(
            return_value=[
                {
                    "title": "  Electrical Engineer  ",
                    "company": " Example Company ",
                    "location": " Hyderabad ",
                    "url": (
                        " https://example.com/job/1 "
                    ),
                    "description": (
                        " Electrical role. "
                    ),
                }
            ]
        )
    )

    jobs = source.search(
        keywords=" engineer ",
        location="Hyderabad",
    )

    assert jobs[0] == {
        "title": "Electrical Engineer",
        "company": "Example Company",
        "location": "Hyderabad",
        "url": (
            "https://example.com/job/1"
        ),
        "description": "Electrical role.",
        "source": "naukri",
    }


# ============================================================
# AVAILABILITY
# ============================================================


def test_naukri_source_available_with_browser():
    source = NaukriSource(
        browser=MagicMock()
    )

    assert source.is_available() is True


def test_naukri_source_unavailable_without_browser():
    source = NaukriSource(
        browser=None
    )

    assert source.is_available() is False