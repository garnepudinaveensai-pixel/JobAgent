from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from app.browser.application_submitter import ApplicationSubmitter


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        yield page

        browser.close()


def make_form(page):
    page.set_content(
        """
        <html>
        <body>

            <form id="application-form">

                <label for="first_name">
                    First Name
                </label>
                <input
                    id="first_name"
                    name="first_name"
                    required
                />

                <label for="email">
                    Email
                </label>
                <input
                    id="email"
                    name="email"
                    type="email"
                    required
                />

                <label for="resume">
                    Resume
                </label>
                <input
                    id="resume"
                    name="resume"
                    type="file"
                    required
                />

                <button type="submit">
                    Submit Application
                </button>

            </form>

        </body>
        </html>
        """
    )


def test_submitter_initialization(page):
    submitter = ApplicationSubmitter(page)

    assert submitter.page == page
    assert submitter.form is not None


def test_open(page):
    submitter = ApplicationSubmitter(page)

    result = submitter.open(
        "data:text/html,<h1>Application</h1>"
    )

    assert result is True
    assert page.locator("h1").inner_text() == "Application"


def test_discover_fields(page):
    make_form(page)

    submitter = ApplicationSubmitter(page)

    fields = submitter.discover()

    assert len(fields) == 3


def test_fill_field(page):
    make_form(page)

    submitter = ApplicationSubmitter(page)
    submitter.discover()

    assert submitter.fill_field(
        "First Name",
        "Naveen",
    )

    assert (
        page.locator("#first_name").input_value()
        == "Naveen"
    )


def test_validation_fails_when_required_fields_missing(page):
    make_form(page)

    submitter = ApplicationSubmitter(page)
    submitter.discover()

    result = submitter.validate()

    assert result["ready"] is False
    assert "First Name" in result["missing_required_fields"]


def test_submit_requires_confirmation(page):
    make_form(page)

    submitter = ApplicationSubmitter(page)
    submitter.discover()

    submitter.fill_field(
        "First Name",
        "Naveen",
    )

    result = submitter.submit()

    assert result["success"] is False
    assert result["status"] == "confirmation_required"


def test_submit_fails_without_resume(page):
    make_form(page)

    submitter = ApplicationSubmitter(page)
    submitter.discover()

    submitter.fill_field(
        "First Name",
        "Naveen",
    )

    submitter.fill_field(
        "Email",
        "test@example.com",
    )

    result = submitter.submit(
        confirm=True
    )

    assert result["success"] is False
    assert result["status"] == "validation_failed"


def test_prepare_application(page, tmp_path):
    make_form(page)

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF-test")

    submitter = ApplicationSubmitter(page)

    result = submitter.prepare_application(
        resume_path=str(resume),
        fields={
            "First Name": "Naveen",
            "Email": "test@example.com",
        },
    )

    assert result["filled_fields"] == [
        "First Name",
        "Email",
    ]

    assert result["resume_uploaded"] is True
    assert result["validation"]["ready"] is True
    assert result["status"] == "ready_for_submission"


def test_submit_success(page, tmp_path):
    make_form(page)

    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF-test")

    submitter = ApplicationSubmitter(page)

    result = submitter.prepare_application(
        resume_path=str(resume),
        fields={
            "First Name": "Naveen",
            "Email": "test@example.com",
        },
    )

    assert result["success"] is True

    result = submitter.submit(
        confirm=True
    )

    assert result["success"] is True
    assert result["status"] == "submitted"


def test_missing_resume_raises_error(page):
    make_form(page)

    submitter = ApplicationSubmitter(page)

    with pytest.raises(FileNotFoundError):
        submitter.upload_resume(
            "does-not-exist.pdf"
        )