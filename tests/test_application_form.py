from pathlib import Path

from playwright.sync_api import sync_playwright

from app.browser.application_form import ApplicationForm


HTML = """
<html>
<body>

<form>

<label for="first_name">First Name</label>
<input
    id="first_name"
    name="first_name"
    type="text"
    required
/>

<label for="email">Email</label>
<input
    id="email"
    name="email"
    type="email"
    required
/>

<label for="phone">Phone</label>
<input
    id="phone"
    name="phone"
    type="tel"
/>

<label for="cover_letter">Cover Letter</label>
<textarea
    id="cover_letter"
    name="cover_letter"
></textarea>

<label for="experience">Experience</label>
<select id="experience" name="experience">
    <option value="0">0 years</option>
    <option value="1">1 year</option>
</select>

<input
    id="resume"
    name="resume"
    type="file"
/>

</form>

</body>
</html>
"""


def make_page():
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=True
    )
    page = browser.new_page()

    page.set_content(HTML)

    return playwright, browser, page


def test_discover_fields():
    playwright, browser, page = make_page()

    try:
        form = ApplicationForm(page)

        fields = form.discover_fields()

        assert len(fields) == 6

        assert form.find("First Name") is not None
        assert form.find("Email") is not None
        assert form.find("Phone") is not None

    finally:
        browser.close()
        playwright.stop()


def test_required_fields():
    playwright, browser, page = make_page()

    try:
        form = ApplicationForm(page)

        form.discover_fields()

        required = form.get_required_fields()

        assert len(required) == 2

    finally:
        browser.close()
        playwright.stop()


def test_fill_field():
    playwright, browser, page = make_page()

    try:
        form = ApplicationForm(page)

        form.discover_fields()

        assert form.fill(
            "First Name",
            "Naveen Sai",
        )

        assert (
            page.locator("#first_name").input_value()
            == "Naveen Sai"
        )

    finally:
        browser.close()
        playwright.stop()


def test_select_field():
    playwright, browser, page = make_page()

    try:
        form = ApplicationForm(page)

        form.discover_fields()

        assert form.select(
            "Experience",
            "1 year",
        )

        assert (
            page.locator("#experience").input_value()
            == "1"
        )

    finally:
        browser.close()
        playwright.stop()


def test_upload_resume(tmp_path):
    playwright, browser, page = make_page()

    resume = tmp_path / "resume.pdf"

    resume.write_bytes(
        b"fake pdf content"
    )

    try:
        form = ApplicationForm(page)

        form.discover_fields()

        assert form.upload_resume(
            str(resume)
        )

    finally:
        browser.close()
        playwright.stop()


def test_missing_required_fields():
    playwright, browser, page = make_page()

    try:
        form = ApplicationForm(page)

        form.discover_fields()

        result = (
            form.validate_before_submission()
        )

        assert result["ready"] is False

        assert (
            "First Name"
            in result["missing_required_fields"]
        )

        assert (
            "Email"
            in result["missing_required_fields"]
        )

    finally:
        browser.close()
        playwright.stop()


def test_validation_after_filling():
    playwright, browser, page = make_page()

    try:
        form = ApplicationForm(page)

        form.discover_fields()

        form.fill(
            "First Name",
            "Naveen Sai",
        )

        form.fill(
            "Email",
            "test@example.com",
        )

        result = (
            form.validate_before_submission()
        )

        assert result["ready"] is True
        assert result["missing_required_fields"] == []

    finally:
        browser.close()
        playwright.stop()


def test_unknown_field_returns_false():
    playwright, browser, page = make_page()

    try:
        form = ApplicationForm(page)

        form.discover_fields()

        assert form.fill(
            "Does Not Exist",
            "test",
        ) is False

    finally:
        browser.close()
        playwright.stop()