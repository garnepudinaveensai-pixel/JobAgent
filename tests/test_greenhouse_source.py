from unittest.mock import MagicMock

import pytest

from app.browser.browser_manager import BrowserManager
from app.core.sources.greenhouse_source import (
    GreenhouseSource,
)


def test_greenhouse_source_search():

    browser = MagicMock()

    source = GreenhouseSource(
        browser
    )

    source.discovery.discover_greenhouse = (
        MagicMock(
            return_value=[
                {
                    "title": "Electrical Engineer",
                    "company": "Example Company",
                    "location": "Hyderabad",
                    "url": "https://example.com/job/1",
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
        board_url=(
            "https://boards.greenhouse.io/example"
        ),
    )

    assert len(jobs) == 1

    assert jobs[0] == {
        "title": "Electrical Engineer",
        "company": "Example Company",
        "location": "Hyderabad",
        "url": "https://example.com/job/1",
        "description": (
            "Electrical engineering role."
        ),
        "source": "greenhouse",
    }


def test_greenhouse_source_requires_board_url():

    browser = MagicMock()

    source = GreenhouseSource(
        browser
    )

    with pytest.raises(
        ValueError,
        match="Greenhouse board_url cannot be empty",
    ):
        source.search(
            keywords="engineer",
            location="Hyderabad",
            board_url="",
        )


def test_greenhouse_source_ignores_invalid_jobs():

    browser = MagicMock()

    source = GreenhouseSource(
        browser
    )

    source.discovery.discover_greenhouse = (
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
            "https://boards.greenhouse.io/example"
        ),
    )

    assert len(jobs) == 1

    assert jobs[0]["title"] == (
        "Valid Job"
    )

    assert jobs[0]["source"] == (
        "greenhouse"
    )

def test_greenhouse_supported_options():

    source = GreenhouseSource(
        browser=MagicMock()
    )

    assert source.get_supported_options() == {
        "board_url"
    }

    assert source.supports_option(
        "board_url"
    )

    assert not source.supports_option(
        "career_url"
    )
