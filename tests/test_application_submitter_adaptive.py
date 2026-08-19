
from playwright.sync_api import sync_playwright

from app.browser.application_submitter import ApplicationSubmitter


def test_submit_control_outside_form_is_found_and_activated(tmp_path):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.set_content(
                """
                <html>
                <body>
                  <form id="application-form">
                    <label for="name">Full Name</label>
                    <input id="name" name="name" required>
                    <label for="email">Email</label>
                    <input id="email" name="email" required>
                    <label for="resume">Upload CV/Resume</label>
                    <input id="resume" type="file" required>
                  </form>
                  <button id="submit" type="button"
                          onclick="document.body.innerHTML='<h1>Thank you for applying</h1>'">
                    Submit Application
                  </button>
                </body>
                </html>
                """
            )
            resume = tmp_path / "resume.pdf"
            resume.write_bytes(b"%PDF-test")

            submitter = ApplicationSubmitter(page)
            prepared = submitter.prepare_application(
                resume_path=str(resume),
                fields={"Full Name": "Test User", "Email": "test@example.com"},
            )
            assert prepared["success"] is True

            result = submitter.submit(confirm=True)

            assert result["success"] is True
            assert result["submitted"] is True
            assert result["status"] == submitter.STATUS_SUBMITTED
        finally:
            browser.close()
