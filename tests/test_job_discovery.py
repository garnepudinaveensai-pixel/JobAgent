from unittest.mock import MagicMock, patch

import pytest

from app.browser.job_discovery import JobDiscovery


def test_job_discovery_can_be_created():
    browser = MagicMock()

    discovery = JobDiscovery(browser)

    assert discovery.browser is browser


def test_discover_greenhouse_rejects_empty_board_url():
    browser = MagicMock()

    discovery = JobDiscovery(browser)

    with pytest.raises(ValueError):
        discovery.discover_greenhouse(
            board_url="",
            keywords="Python",
        )


def test_discover_greenhouse_rejects_empty_keywords():
    browser = MagicMock()

    discovery = JobDiscovery(browser)

    with pytest.raises(ValueError):
        discovery.discover_greenhouse(
            board_url="https://example.com",
            keywords="",
        )


@patch("app.browser.job_discovery.GreenhouseSite")
def test_discover_greenhouse(
    mock_greenhouse,
):
    browser = MagicMock()
    page = MagicMock()

    browser.open.return_value = page

    mock_site = mock_greenhouse.return_value

    mock_site.get_job_listings.return_value = [
        {
            "title": "Graduate Engineer Trainee",
            "company": "Example Company",
            "location": "India",
            "url": "https://example.com/jobs/1",
            "description": "",
        }
    ]

    discovery = JobDiscovery(browser)

    result = discovery.discover_greenhouse(
        board_url="https://example.com/jobs",
        keywords="Electrical Engineer",
        location="India",
    )

    browser.open.assert_called_once_with(
        "https://example.com/jobs"
    )

    mock_site.search_jobs.assert_called_once_with(
        keywords="Electrical Engineer",
        location="India",
    )

    mock_site.get_job_listings.assert_called_once()

    assert len(result) == 1
    assert result[0]["title"] == "Graduate Engineer Trainee"


def test_get_greenhouse_job_details_rejects_empty_url():
    browser = MagicMock()

    discovery = JobDiscovery(browser)

    with pytest.raises(ValueError):
        discovery.get_greenhouse_job_details("")


@patch("app.browser.job_discovery.GreenhouseSite")
def test_get_greenhouse_job_details(
    mock_greenhouse,
):
    browser = MagicMock()
    page = MagicMock()

    browser.open.return_value = page

    mock_site = mock_greenhouse.return_value

    mock_site.get_job_details.return_value = {
        "title": "Electrical Engineer",
        "company": "Example Company",
        "location": "India",
        "url": "https://example.com/jobs/2",
        "description": "Electrical engineering role",
    }

    discovery = JobDiscovery(browser)

    result = discovery.get_greenhouse_job_details(
        "https://example.com/jobs/2"
    )

    browser.open.assert_called_once_with(
        "https://example.com/jobs/2"
    )

    mock_site.get_job_details.assert_called_once_with(
        "https://example.com/jobs/2"
    )

    assert result["title"] == "Electrical Engineer"
    assert result["company"] == "Example Company"
    assert result["location"] == "India"
    assert result["url"] == "https://example.com/jobs/2"
    assert result["description"] == "Electrical engineering role"