from playwright.sync_api import sync_playwright

from app.browser.application_submitter import (
    ApplicationSubmitter,
)


def make_page(html: str):
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=True
    )
    page = browser.new_page()
    page.set_content(html)

    return (
        playwright,
        browser,
        page,
    )


def close_page(
    playwright,
    browser,
):
    browser.close()
    playwright.stop()


def test_detects_captcha():
    playwright, browser, page = make_page(
        """
        <html>
        <body>
            <h1>Verify you are human</h1>
            <div class="g-recaptcha"></div>
        </body>
        </html>
        """
    )

    try:
        submitter = ApplicationSubmitter(page)

        result = submitter.analyze_page()

        assert result["status"] == (
            "captcha_detected"
        )

        assert result["captcha_detected"] is True
        assert result["requires_human_action"] is True
        assert result["safe_for_automation"] is False

    finally:
        close_page(
            playwright,
            browser,
        )


def test_detects_login_page():
    playwright, browser, page = make_page(
        """
        <html>
        <body>
            <h1>Sign In</h1>

            <form>
                <input
                    type="email"
                    name="email"
                />

                <input
                    type="password"
                    name="password"
                />

                <button>
                    Sign In
                </button>
            </form>
        </body>
        </html>
        """
    )

    try:
        submitter = ApplicationSubmitter(page)

        result = submitter.analyze_page()

        assert result["status"] == (
            "login_required"
        )

        assert result["login_required"] is True
        assert result["requires_human_action"] is True
        assert result["safe_for_automation"] is False

    finally:
        close_page(
            playwright,
            browser,
        )


def test_detects_unavailable_job():
    playwright, browser, page = make_page(
        """
        <html>
        <body>
            <h1>Electrical Engineer</h1>

            <p>
                This job is no longer available.
            </p>
        </body>
        </html>
        """
    )

    try:
        submitter = ApplicationSubmitter(page)

        result = submitter.analyze_page()

        assert result["status"] == (
            "job_unavailable"
        )

        assert result["job_unavailable"] is True
        assert result["safe_for_automation"] is False

    finally:
        close_page(
            playwright,
            browser,
        )


def test_detects_application_form():
    playwright, browser, page = make_page(
        """
        <html>
        <body>

            <form>
                <label for="name">
                    Full Name
                </label>

                <input
                    id="name"
                    name="name"
                    required
                />

                <button type="submit">
                    Apply
                </button>
            </form>

        </body>
        </html>
        """
    )

    try:
        submitter = ApplicationSubmitter(page)

        result = submitter.analyze_page()

        assert result["status"] == (
            "form_detected"
        )

        assert result["form_found"] is True
        assert result["safe_for_automation"] is True
        assert result["requires_human_action"] is False

    finally:
        close_page(
            playwright,
            browser,
        )


def test_detects_missing_form():
    playwright, browser, page = make_page(
        """
        <html>
        <body>
            <h1>Electrical Engineer</h1>
            <p>
                Job details are available here.
            </p>
        </body>
        </html>
        """
    )

    try:
        submitter = ApplicationSubmitter(page)

        result = submitter.analyze_page()

        assert result["status"] == (
            "form_not_found"
        )

        assert result["form_found"] is False
        assert result["safe_for_automation"] is False

    finally:
        close_page(
            playwright,
            browser,
        )


def test_captcha_blocks_preparation(tmp_path):
    playwright, browser, page = make_page(
        """
        <html>
        <body>
            <h1>CAPTCHA Verification</h1>
            <div class="g-recaptcha"></div>
        </body>
        </html>
        """
    )

    try:
        resume = (
            tmp_path
            / "resume.pdf"
        )

        resume.write_bytes(
            b"%PDF-test"
        )

        submitter = ApplicationSubmitter(page)

        result = submitter.prepare_application(
            resume_path=str(resume),
            fields={
                "Name": "Naveen Sai",
            },
        )

        assert result["success"] is False
        assert result["status"] == (
            "captcha_detected"
        )

        assert result["filled_fields"] == []
        assert result["resume_uploaded"] is False

    finally:
        close_page(
            playwright,
            browser,
        )


def test_login_blocks_submission():
    playwright, browser, page = make_page(
        """
        <html>
        <body>

            <h1>Login</h1>

            <form>
                <input
                    type="email"
                    name="email"
                />

                <input
                    type="password"
                    name="password"
                />

                <button>
                    Login
                </button>
            </form>

        </body>
        </html>
        """
    )

    try:
        submitter = ApplicationSubmitter(page)

        result = submitter.submit(
            confirm=True
        )

        assert result["success"] is False
        assert result["status"] == (
            "login_required"
        )

    finally:
        close_page(
            playwright,
            browser,
        )


def test_human_action_result_for_captcha():
    playwright, browser, page = make_page(
        """
        <html>
        <body>
            <h1>Human verification</h1>
            <div class="hcaptcha"></div>
        </body>
        </html>
        """
    )

    try:
        submitter = ApplicationSubmitter(page)

        submitter.analyze_page()

        result = (
            submitter
            .human_action_required_result()
        )

        assert result["success"] is False

        assert result["status"] == (
            "human_action_required"
        )

        assert result[
            "page_analysis"
        ]["captcha_detected"] is True

    finally:
        close_page(
            playwright,
            browser,
        )


def test_normal_application_remains_automatable(
    tmp_path,
):
    playwright, browser, page = make_page(
        """
        <html>
        <body>

            <form>

                <label for="name">
                    Full Name
                </label>

                <input
                    id="name"
                    name="name"
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

    try:
        resume = (
            tmp_path
            / "resume.pdf"
        )

        resume.write_bytes(
            b"%PDF-test"
        )

        submitter = ApplicationSubmitter(page)

        analysis = (
            submitter.analyze_page()
        )

        assert analysis["status"] == (
            "form_detected"
        )

        result = (
            submitter.prepare_application(
                resume_path=str(resume),
                fields={
                    "Full Name": "Naveen Sai",
                    "Email": "test@example.com",
                },
            )
        )

        assert result["success"] is True

        assert result["status"] == (
            "ready_for_submission"
        )

        assert result[
            "validation"
        ]["ready"] is True

        # Explicit confirmation is still required.
        submit_result = (
            submitter.submit(
                confirm=False
            )
        )

        assert submit_result["success"] is False

        assert submit_result["status"] == (
            "confirmation_required"
        )

    finally:
        close_page(
            playwright,
            browser,
        )