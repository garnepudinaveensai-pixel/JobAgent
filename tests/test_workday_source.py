import pytest
from unittest.mock import MagicMock

from app.core.sources.workday_source import WorkdaySource


def test_workday_source_name():
    source = WorkdaySource(
        browser=MagicMock()
    )

    assert source.name == "workday"


def test_workday_source_requires_keywords():
    source = WorkdaySource(
        browser=MagicMock()
    )

    with pytest.raises(
        ValueError,
        match="Workday keywords cannot be empty",
    ):
        source.search(
            keywords="",
            board_url=(
                "https://example.wd1.myworkdayjobs.com/"
                "External_Career_Site"
            ),
        )


def test_workday_source_requires_board_url():
    source = WorkdaySource(
        browser=MagicMock()
    )

    with pytest.raises(
        ValueError,
        match="Workday board_url cannot be empty",
    ):
        source.search(
            keywords="software engineer",
            board_url="",
        )


def test_workday_source_requires_browser():
    with pytest.raises(
        ValueError,
        match="WorkdaySource requires a browser",
    ):
        WorkdaySource(
            browser=None
        )


def test_workday_source_search():
    browser = MagicMock()

    source = WorkdaySource(
        browser=browser
    )

    source.discovery.discover_workday = (
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
            "https://example.wd1.myworkdayjobs.com/"
            "External_Career_Site"
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
        "source": "workday",
    }


def test_workday_source_ignores_invalid_jobs():
    browser = MagicMock()

    source = WorkdaySource(
        browser=browser
    )

    source.discovery.discover_workday = (
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
            "https://example.wd1.myworkdayjobs.com/"
            "External_Career_Site"
        ),
    )

    assert len(jobs) == 1

    assert jobs[0]["title"] == "Valid Job"
    assert jobs[0]["company"] == ""
    assert jobs[0]["location"] == ""
    assert jobs[0]["url"] == ""
    assert jobs[0]["description"] == ""
    assert jobs[0]["source"] == "workday"