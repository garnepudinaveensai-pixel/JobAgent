from unittest.mock import MagicMock

import pytest

from app.browser.sites.greenhouse import GreenhouseSite


def test_greenhouse_site_name():
    page = MagicMock()

    site = GreenhouseSite(page)

    assert site.site_name == "Greenhouse"


def test_search_jobs_rejects_empty_keyword():
    page = MagicMock()

    site = GreenhouseSite(page)

    with pytest.raises(ValueError):
        site.search_jobs("")


def test_get_job_details_rejects_empty_url():
    page = MagicMock()

    site = GreenhouseSite(page)

    with pytest.raises(ValueError):
        site.get_job_details("")


def test_get_job_listings_empty_page():
    page = MagicMock()

    links = MagicMock()
    links.count.return_value = 0

    page.locator.return_value = links

    site = GreenhouseSite(page)

    result = site.get_job_listings()

    assert result == []


def test_get_job_details_returns_normalized_structure():
    page = MagicMock()

    page.url = "https://example.com/jobs/123"

    site = GreenhouseSite(page)

    site.wait_for_page = MagicMock()
    site.get_current_url = MagicMock(
        return_value="https://example.com/jobs/123"
    )

    site._first_text = MagicMock(
        side_effect=[
            "Graduate Engineer Trainee",
            "Example Company",
            "India",
            "Job description",
        ]
    )

    result = site.get_job_details(
        "https://example.com/jobs/123"
    )

    assert result == {
        "title": "Graduate Engineer Trainee",
        "company": "Example Company",
        "location": "India",
        "url": "https://example.com/jobs/123",
        "description": "Job description",
    }


def test_get_job_listings_normalized_structure():
    page = MagicMock()

    link = MagicMock()

    link.is_visible.return_value = True
    link.inner_text.return_value = "Graduate Engineer Trainee"
    link.get_attribute.return_value = (
        "https://example.com/jobs/123"
    )

    links = MagicMock()
    links.count.return_value = 1
    links.nth.return_value = link

    page.locator.return_value = links

    site = GreenhouseSite(page)

    site._extract_company = MagicMock(
        return_value="Example Company"
    )

    site._extract_listing_location = MagicMock(
        return_value="India"
    )

    result = site.get_job_listings()

    assert len(result) == 1

    job = result[0]

    assert job["title"] == "Graduate Engineer Trainee"
    assert job["company"] == "Example Company"
    assert job["location"] == "India"
    assert job["url"] == "https://example.com/jobs/123"
    assert job["description"] == ""


def test_get_job_listings_skips_empty_titles():
    page = MagicMock()

    link = MagicMock()

    link.is_visible.return_value = True
    link.inner_text.return_value = ""
    link.get_attribute.return_value = (
        "https://example.com/jobs/123"
    )

    links = MagicMock()
    links.count.return_value = 1
    links.nth.return_value = link

    page.locator.return_value = links

    site = GreenhouseSite(page)

    result = site.get_job_listings()

    assert result == []