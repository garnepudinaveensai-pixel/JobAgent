from unittest.mock import MagicMock

import pytest

from app.browser.sites.lever import LeverSite


def test_lever_site_name():
    page = MagicMock()

    site = LeverSite(page)

    assert site.name == "Lever"


def test_lever_site_requires_keywords():
    page = MagicMock()

    site = LeverSite(page)

    with pytest.raises(
        ValueError,
        match="keywords cannot be empty",
    ):
        site.search_jobs(
            keywords=""
        )


def test_lever_site_search_uses_search_box():
    page = MagicMock()

    search_box = MagicMock()

    search_box.is_visible.return_value = True

    page.locator.return_value.first = (
        search_box
    )

    page.url = (
        "https://jobs.lever.co/example"
    )

    site = LeverSite(page)

    site.search_jobs(
        keywords="software engineer",
        location="India",
    )

    search_box.fill.assert_called_once_with(
        "software engineer"
    )

    search_box.press.assert_called_once_with(
        "Enter"
    )


def test_lever_site_get_job_details():
    page = MagicMock()

    page.url = (
        "https://jobs.lever.co/example/123"
    )

    page.locator.return_value.first.is_visible.return_value = True

    page.locator.return_value.first.inner_text.return_value = (
        "Software Engineer"
    )

    site = LeverSite(page)

    result = site.get_job_details(
        "https://jobs.lever.co/example/123"
    )

    assert result["title"] == (
        "Software Engineer"
    )

    assert "url" in result


def test_lever_site_requires_job_url():
    page = MagicMock()

    site = LeverSite(page)

    with pytest.raises(
        ValueError,
        match="job_url cannot be empty",
    ):
        site.get_job_details("")