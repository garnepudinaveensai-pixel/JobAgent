from pathlib import Path

from playwright.sync_api import sync_playwright

from app.browser.application_submitter import ApplicationSubmitter


def test_direct_apply_control_is_detected_without_form():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.set_content(
                """
                <html>
                <body>
                    <h1>Electrical Engineer</h1>
                    <a id="apply" href="#">Apply Now</a>
                </body>
                </html>
                """
            )

            submitter = ApplicationSubmitter(page)
            analysis = submitter.analyze_page()

            assert (
                analysis["status"]
                == submitter.STATUS_APPLY_CONTROL_DETECTED
            )
            assert analysis["safe_for_automation"] is True
            assert analysis["form_found"] is False

        finally:
            browser.close()


def test_apply_filters_is_not_treated_as_application():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.set_content(
                """
                <html>
                <body>
                    <button>Apply filters</button>
                </body>
                </html>
                """
            )

            submitter = ApplicationSubmitter(page)
            analysis = submitter.analyze_page()

            assert (
                analysis["status"]
                == submitter.STATUS_FORM_NOT_FOUND
            )

        finally:
            browser.close()


def test_direct_apply_is_deferred_until_confirmed_submission():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.set_content(
                """
                <html>
                <body>
                    <a id="apply" href="#">Apply Now</a>
                </body>
                </html>
                """
            )

            resume = Path("test-direct-apply-resume.pdf")
            resume.write_bytes(b"%PDF-test")

            try:
                submitter = ApplicationSubmitter(page)

                prepared = submitter.prepare_application(
                    resume_path=str(resume),
                    fields={},
                )

                assert prepared["success"] is True
                assert (
                    prepared["status"]
                    == submitter.STATUS_APPLY_CONTROL_DETECTED
                )

                result = submitter.submit(confirm=True)

                assert result["success"] is True
                assert result["submitted"] is False
                assert (
                    result["status"]
                    == submitter.STATUS_APPLICATION_HANDOFF
                )

            finally:
                resume.unlink(missing_ok=True)

        finally:
            browser.close()
