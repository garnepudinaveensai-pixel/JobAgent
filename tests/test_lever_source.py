import pytest
from unittest.mock import MagicMock

from app.core.sources.lever_source import LeverSource


# ============================================================
# NAME
# ============================================================


def test_lever_source_name():
    source = LeverSource()

    assert source.name == "lever"


# ============================================================
# KEYWORDS
# ============================================================


def test_lever_source_requires_keywords():
    source = LeverSource(
        browser=MagicMock()
    )

    with pytest.raises(
        ValueError,
        match="Lever keywords cannot be empty",
    ):
        source.search(
            keywords="",
            board_url=(
                "https://jobs.lever.co/example"
            ),
        )


# ============================================================
# BOARD URL
# ============================================================


def test_lever_source_requires_board_url():
    source = LeverSource(
        browser=MagicMock()
    )

    with pytest.raises(
        ValueError,
        match="Lever board_url cannot be empty",
    ):
        source.search(
            keywords="software engineer",
            board_url="",
        )


# ============================================================
# BROWSER
# ============================================================


def test_lever_source_requires_browser():
    source = LeverSource(
        browser=None
    )

    with pytest.raises(
        RuntimeError,
        match="LeverSource requires a browser",
    ):
        source.search(
            keywords="software engineer",
            board_url=(
                "https://jobs.lever.co/example"
            ),
        )


# ============================================================
# SEARCH
# ============================================================


def test_lever_source_search():
    browser = MagicMock()

    source = LeverSource(
        browser=browser
    )

    source.discovery.discover_lever = (
        MagicMock(
            return_value=[
                {
                    "title": "Software Engineer",
                    "company": "Example Company",
                    "location": "India",
                    "url": (
                        "https://example.com/job/1"
                    ),
                    "description": (
                        "Software engineering role."
                    ),
                }
            ]
        )
    )

    jobs = source.search(
        keywords="software engineer",
        location="India",
        board_url=(
            "https://jobs.lever.co/example"
        ),
    )

    assert len(jobs) == 1

    assert jobs[0] == {
        "title": "Software Engineer",
        "company": "Example Company",
        "location": "India",
        "url": (
            "https://example.com/job/1"
        ),
        "description": (
            "Software engineering role."
        ),
        "source": "lever",
    }


# ============================================================
# INVALID JOBS
# ============================================================


def test_lever_source_ignores_invalid_jobs():
    browser = MagicMock()

    source = LeverSource(
        browser=browser
    )

    source.discovery.discover_lever = (
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
        keywords="engineer",
        board_url=(
            "https://jobs.lever.co/example"
        ),
    )

    assert len(jobs) == 1

    assert jobs[0]["title"] == (
        "Valid Job"
    )

    assert jobs[0]["company"] == ""

    assert jobs[0]["location"] == ""

    assert jobs[0]["url"] == ""

    assert jobs[0]["description"] == ""

    assert jobs[0]["source"] == "lever"


# ============================================================
# WHITESPACE NORMALIZATION
# ============================================================


def test_lever_source_normalizes_job_fields():
    browser = MagicMock()

    source = LeverSource(
        browser=browser
    )

    source.discovery.discover_lever = (
        MagicMock(
            return_value=[
                {
                    "title": "  Software Engineer  ",
                    "company": " Example Company ",
                    "location": " India ",
                    "url": (
                        " https://example.com/job/1 "
                    ),
                    "description": (
                        " Software engineering role. "
                    ),
                }
            ]
        )
    )

    jobs = source.search(
        keywords=" software engineer ",
        location="India",
        board_url=(
            " https://jobs.lever.co/example "
        ),
    )

    assert len(jobs) == 1

    assert jobs[0] == {
        "title": "Software Engineer",
        "company": "Example Company",
        "location": "India",
        "url": (
            "https://example.com/job/1"
        ),
        "description": (
            "Software engineering role."
        ),
        "source": "lever",
    }


# ============================================================
# AVAILABILITY
# ============================================================


def test_lever_source_available_with_browser():
    source = LeverSource(
        browser=MagicMock()
    )

    assert source.is_available() is True


def test_lever_source_unavailable_without_browser():
    source = LeverSource()

    assert source.is_available() is False