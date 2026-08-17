from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import (
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)


class ApplicationSubmitter:
    """
    Handles preparation and controlled submission of job applications.

    The submitter now has an explicit page-safety layer.

    Possible page/application states include:

        not_analyzed
        page_loaded
        navigation_failed
        login_required
        captcha_detected
        job_unavailable
        form_not_found
        form_detected
        ready_for_submission
        confirmation_required
        validation_failed
        submitted
        submission_timeout
        submission_failed
        human_action_required

    Important safety rules:

    - CAPTCHA is detected, never bypassed.
    - Authentication/login requirements are detected and
      surfaced as human-action-required.
    - Final submission requires explicit confirmation.
    - Unknown/unsafe pages are not submitted automatically.
    """

    # ========================================================
    # STATUS CONSTANTS
    # ========================================================

    STATUS_NOT_ANALYZED = "not_analyzed"
    STATUS_PAGE_LOADED = "page_loaded"
    STATUS_NAVIGATION_FAILED = "navigation_failed"

    STATUS_LOGIN_REQUIRED = "login_required"
    STATUS_CAPTCHA_DETECTED = "captcha_detected"
    STATUS_JOB_UNAVAILABLE = "job_unavailable"
    STATUS_FORM_NOT_FOUND = "form_not_found"
    STATUS_FORM_DETECTED = "form_detected"

    STATUS_READY = "ready_for_submission"
    STATUS_CONFIRMATION_REQUIRED = "confirmation_required"
    STATUS_VALIDATION_FAILED = "validation_failed"

    STATUS_HUMAN_ACTION_REQUIRED = (
        "human_action_required"
    )

    STATUS_SUBMITTED = "submitted"
    STATUS_SUBMISSION_TIMEOUT = (
        "submission_timeout"
    )
    STATUS_SUBMISSION_FAILED = (
        "submission_failed"
    )

    # ========================================================
    # DETECTION TEXT
    # ========================================================

    CAPTCHA_TEXT_PATTERNS = (
        "captcha",
        "recaptcha",
        "hcaptcha",
        "verify you are human",
        "verify you're human",
        "human verification",
        "bot verification",
        "security verification",
        "checking your browser",
        "checking if the site connection is secure",
        "press and hold",
    )

    LOGIN_TEXT_PATTERNS = (
        "sign in",
        "signin",
        "log in",
        "login",
        "sign into your account",
        "log into your account",
        "create an account",
        "authentication required",
    )

    UNAVAILABLE_TEXT_PATTERNS = (
        "job is no longer available",
        "job is no longer accepting applications",
        "no longer accepting applications",
        "position has been filled",
        "position is no longer available",
        "this job has expired",
        "job has expired",
        "job is closed",
        "position is closed",
        "applications are closed",
        "this position has been closed",
        "opening is no longer available",
        "page not found",
        "job not found",
        "position not found",
        "404 not found",
    )

    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        page: Page,
        form_selector: str = "form",
        timeout: int = 5000,
    ):
        if page is None:
            raise ValueError(
                "page cannot be None."
            )

        if not form_selector:
            raise ValueError(
                "form_selector cannot be empty."
            )

        if timeout <= 0:
            raise ValueError(
                "timeout must be greater than zero."
            )

        self.page = page
        self.form_selector = form_selector
        self.timeout = timeout

        self.form: Locator = self.page.locator(
            self.form_selector
        ).first

        self._discovered_fields: list[
            dict
        ] = []

        self._resume_input: Optional[
            Locator
        ] = None

        self._resume_uploaded = False
        self._prepared = False

        self._page_status = (
            self.STATUS_NOT_ANALYZED
        )

        self._page_analysis: dict[
            str, Any
        ] = {
            "status": self.STATUS_NOT_ANALYZED,
            "safe_for_automation": False,
            "requires_human_action": False,
            "captcha_detected": False,
            "login_required": False,
            "job_unavailable": False,
            "form_found": False,
            "url": "",
            "title": "",
            "reason": "",
            "signals": [],
        }

    # ========================================================
    # OPEN
    # ========================================================

    def open(
        self,
        url: str,
    ) -> bool:
        """
        Open an application URL.

        Returns:
            True when navigation succeeds.

        The method remains backward-compatible with the
        previous boolean API.

        Detailed information is available through:

            analyze_page()
            get_page_analysis()
        """

        if not isinstance(
            url,
            str,
        ):
            raise TypeError(
                "URL must be a string."
            )

        url = url.strip()

        if not url:
            raise ValueError(
                "URL cannot be empty."
            )

        self.reset()

        try:
            self.page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout,
            )

            self.analyze_page()

            return True

        except PlaywrightTimeoutError as exc:

            self._set_page_analysis(
                status=self.STATUS_NAVIGATION_FAILED,
                reason=(
                    "Page navigation timed out."
                ),
                signals=[
                    "navigation_timeout"
                ],
            )

            self._page_analysis[
                "error"
            ] = str(exc)

            return False

        except Exception as exc:

            self._set_page_analysis(
                status=self.STATUS_NAVIGATION_FAILED,
                reason=(
                    "Page navigation failed."
                ),
                signals=[
                    "navigation_failed"
                ],
            )

            self._page_analysis[
                "error"
            ] = str(exc)

            return False

    # ========================================================
    # PAGE ANALYSIS
    # ========================================================

    def analyze_page(self) -> dict:
        """
        Analyze the current page for application safety.

        Detection order:

            CAPTCHA
                ↓
            Login
                ↓
            Job unavailable
                ↓
            Application form
                ↓
            Unknown page

        CAPTCHA and login take priority because the agent
        should never continue automation through an
        authentication or bot-verification barrier.

        Returns:
            Structured analysis dictionary.
        """

        signals: list[str] = []

        url = self._safe_page_url()
        title = self._safe_page_title()
        text = self._safe_page_text()

        lowered_text = text.lower()
        lowered_url = url.lower()
        lowered_title = title.lower()

        # ----------------------------------------------------
        # CAPTCHA / BOT DETECTION
        # ----------------------------------------------------

        captcha_signals = (
            self._detect_captcha(
                lowered_text,
                lowered_url,
                lowered_title,
            )
        )

        if captcha_signals:
            signals.extend(
                captcha_signals
            )

            self._set_page_analysis(
                status=self.STATUS_CAPTCHA_DETECTED,
                safe_for_automation=False,
                requires_human_action=True,
                captcha_detected=True,
                login_required=False,
                job_unavailable=False,
                form_found=False,
                reason=(
                    "A CAPTCHA or bot-verification "
                    "challenge was detected. "
                    "Human intervention is required."
                ),
                signals=signals,
            )

            return self.get_page_analysis()

        # ----------------------------------------------------
        # LOGIN / AUTHENTICATION
        # ----------------------------------------------------

        login_signals = (
            self._detect_login(
                lowered_text,
                lowered_url,
                lowered_title,
            )
        )

        if login_signals:
            signals.extend(
                login_signals
            )

            self._set_page_analysis(
                status=self.STATUS_LOGIN_REQUIRED,
                safe_for_automation=False,
                requires_human_action=True,
                captcha_detected=False,
                login_required=True,
                job_unavailable=False,
                form_found=False,
                reason=(
                    "Authentication appears to be "
                    "required before continuing. "
                    "Human intervention is required."
                ),
                signals=signals,
            )

            return self.get_page_analysis()

        # ----------------------------------------------------
        # JOB UNAVAILABLE
        # ----------------------------------------------------

        unavailable_signals = (
            self._detect_unavailable(
                lowered_text,
                lowered_url,
                lowered_title,
            )
        )

        if unavailable_signals:
            signals.extend(
                unavailable_signals
            )

            self._set_page_analysis(
                status=self.STATUS_JOB_UNAVAILABLE,
                safe_for_automation=False,
                requires_human_action=False,
                captcha_detected=False,
                login_required=False,
                job_unavailable=True,
                form_found=False,
                reason=(
                    "The job or application appears "
                    "to be unavailable or closed."
                ),
                signals=signals,
            )

            return self.get_page_analysis()

        # ----------------------------------------------------
        # FORM
        # ----------------------------------------------------

        form_found = self._form_exists()

        if form_found:

            signals.append(
                "application_form_found"
            )

            self._set_page_analysis(
                status=self.STATUS_FORM_DETECTED,
                safe_for_automation=True,
                requires_human_action=False,
                captcha_detected=False,
                login_required=False,
                job_unavailable=False,
                form_found=True,
                reason=(
                    "An application form was detected "
                    "and no blocking condition was found."
                ),
                signals=signals,
            )

            return self.get_page_analysis()

        # ----------------------------------------------------
        # UNKNOWN / FORM NOT FOUND
        # ----------------------------------------------------

        self._set_page_analysis(
            status=self.STATUS_FORM_NOT_FOUND,
            safe_for_automation=False,
            requires_human_action=False,
            captcha_detected=False,
            login_required=False,
            job_unavailable=False,
            form_found=False,
            reason=(
                "No application form was detected "
                "on the current page."
            ),
            signals=[
                "application_form_not_found"
            ],
        )

        return self.get_page_analysis()

    # ========================================================
    # PAGE ANALYSIS HELPERS
    # ========================================================

    def get_page_analysis(self) -> dict:
        """
        Return a copy of the latest page analysis.
        """

        return dict(
            self._page_analysis
        )

    @property
    def page_status(self) -> str:
        """
        Current page/application status.
        """

        return self._page_status

    @property
    def requires_human_action(self) -> bool:
        """
        Whether human intervention is required.
        """

        return bool(
            self._page_analysis.get(
                "requires_human_action",
                False,
            )
        )

    @property
    def is_safe_for_automation(self) -> bool:
        """
        Whether the current page is considered safe for
        automated application interaction.
        """

        return bool(
            self._page_analysis.get(
                "safe_for_automation",
                False,
            )
        )

    def _set_page_analysis(
        self,
        *,
        status: str,
        reason: str = "",
        signals: Optional[
            list[str]
        ] = None,
        safe_for_automation: bool = False,
        requires_human_action: bool = False,
        captcha_detected: bool = False,
        login_required: bool = False,
        job_unavailable: bool = False,
        form_found: bool = False,
    ) -> None:

        self._page_status = status

        self._page_analysis = {
            "status": status,
            "safe_for_automation": (
                safe_for_automation
            ),
            "requires_human_action": (
                requires_human_action
            ),
            "captcha_detected": (
                captcha_detected
            ),
            "login_required": (
                login_required
            ),
            "job_unavailable": (
                job_unavailable
            ),
            "form_found": form_found,
            "url": self._safe_page_url(),
            "title": self._safe_page_title(),
            "reason": reason,
            "signals": list(
                signals or []
            ),
        }

    def _safe_page_url(self) -> str:
        try:
            return str(
                self.page.url or ""
            ).strip()
        except Exception:
            return ""

    def _safe_page_title(self) -> str:
        try:
            return str(
                self.page.title() or ""
            ).strip()
        except Exception:
            return ""

    def _safe_page_text(self) -> str:
        try:
            return str(
                self.page.locator(
                    "body"
                ).inner_text(
                    timeout=self.timeout
                )
                or ""
            )
        except Exception:
            return ""

    def _form_exists(self) -> bool:
        try:
            return self.form.count() > 0
        except Exception:
            return False

    # ========================================================
    # CAPTCHA DETECTION
    # ========================================================

    def _detect_captcha(
        self,
        text: str,
        url: str,
        title: str,
    ) -> list[str]:

        signals = []

        for pattern in self.CAPTCHA_TEXT_PATTERNS:

            if pattern in text:
                signals.append(
                    f"text:{pattern}"
                )

        for pattern in (
            "captcha",
            "recaptcha",
            "hcaptcha",
            "challenge",
        ):
            if pattern in url:
                signals.append(
                    f"url:{pattern}"
                )

            if pattern in title:
                signals.append(
                    f"title:{pattern}"
                )

        # ----------------------------------------------------
        # Common CAPTCHA iframe/container detection
        # ----------------------------------------------------

        selectors = [
            'iframe[src*="recaptcha"]',
            'iframe[src*="hcaptcha"]',
            '[class*="recaptcha"]',
            '[class*="hcaptcha"]',
            '[id*="recaptcha"]',
            '[id*="hcaptcha"]',
        ]

        for selector in selectors:

            try:

                if (
                    self.page.locator(
                        selector
                    ).count()
                    > 0
                ):
                    signals.append(
                        f"selector:{selector}"
                    )

            except Exception:
                continue

        # Preserve order and remove duplicates.
        return list(
            dict.fromkeys(
                signals
            )
        )

    # ========================================================
    # LOGIN DETECTION
    # ========================================================

    def _detect_login(
        self,
        text: str,
        url: str,
        title: str,
    ) -> list[str]:

        signals = []

        # URL is a strong signal.
        login_url_tokens = (
            "/login",
            "/signin",
            "/sign-in",
            "/authenticate",
            "/auth/login",
        )

        for token in login_url_tokens:

            if token in url:
                signals.append(
                    f"url:{token}"
                )

        # Password field is a strong signal.
        try:

            password_fields = self.page.locator(
                'input[type="password"]'
            )

            if password_fields.count() > 0:
                signals.append(
                    "password_input"
                )

        except Exception:
            pass

        # Text detection.
        for pattern in self.LOGIN_TEXT_PATTERNS:

            if pattern in text:
                signals.append(
                    f"text:{pattern}"
                )

        # Title detection.
        for pattern in (
            "login",
            "sign in",
            "signin",
            "authentication",
        ):

            if pattern in title:
                signals.append(
                    f"title:{pattern}"
                )

        return list(
            dict.fromkeys(
                signals
            )
        )

    # ========================================================
    # JOB AVAILABILITY
    # ========================================================

    def _detect_unavailable(
        self,
        text: str,
        url: str,
        title: str,
    ) -> list[str]:

        signals = []

        for pattern in (
            *self.UNAVAILABLE_TEXT_PATTERNS,
        ):

            if pattern in text:
                signals.append(
                    f"text:{pattern}"
                )

        for pattern in (
            "404",
            "not-found",
            "job-not-found",
            "position-not-found",
        ):

            if pattern in url:
                signals.append(
                    f"url:{pattern}"
                )

            if pattern in title:
                signals.append(
                    f"title:{pattern}"
                )

        return list(
            dict.fromkeys(
                signals
            )
        )

    # ========================================================
    # FORM
    # ========================================================

    def _ensure_form(self) -> Locator:
        """
        Return the current form.

        Raises:
            RuntimeError if no form exists.
        """

        try:
            count = self.form.count()
        except Exception as exc:
            raise RuntimeError(
                "Unable to inspect the application form."
            ) from exc

        if count == 0:
            raise RuntimeError(
                "No application form was found on the page."
            )

        return self.form

    # ========================================================
    # DISCOVERY
    # ========================================================

    def discover(self) -> list:
        """
        Discover fields in the application form.

        Returns:
            A list containing normal inputs, textarea,
            select and resume-upload fields.
        """

        form = self._ensure_form()

        discovered = []

        # ----------------------------------------------------
        # INPUTS
        # ----------------------------------------------------

        inputs = form.locator("input")

        for index in range(
            inputs.count()
        ):

            element = inputs.nth(index)

            input_type = (
                element.get_attribute(
                    "type"
                )
                or "text"
            ).lower()

            name = self._field_name(
                element
            )

            if input_type == "file":

                self._resume_input = element

                discovered.append(
                    {
                        "name": (
                            name
                            or "Resume"
                        ),
                        "type": "file",
                        "required": (
                            self._is_required(
                                element
                            )
                        ),
                    }
                )

                continue

            if input_type in {
                "submit",
                "button",
                "reset",
                "hidden",
            }:
                continue

            discovered.append(
                {
                    "name": name,
                    "type": input_type,
                    "required": (
                        self._is_required(
                            element
                        )
                    ),
                }
            )

        # ----------------------------------------------------
        # TEXTAREAS
        # ----------------------------------------------------

        textareas = form.locator(
            "textarea"
        )

        for index in range(
            textareas.count()
        ):

            element = textareas.nth(index)

            discovered.append(
                {
                    "name": self._field_name(
                        element
                    ),
                    "type": "textarea",
                    "required": (
                        self._is_required(
                            element
                        )
                    ),
                }
            )

        # ----------------------------------------------------
        # SELECTS
        # ----------------------------------------------------

        selects = form.locator(
            "select"
        )

        for index in range(
            selects.count()
        ):

            element = selects.nth(index)

            discovered.append(
                {
                    "name": self._field_name(
                        element
                    ),
                    "type": "select",
                    "required": (
                        self._is_required(
                            element
                        )
                    ),
                }
            )

        self._discovered_fields = (
            discovered
        )

        return discovered

    # ========================================================
    # FIELD NAME
    # ========================================================

    def _field_name(
        self,
        element: Locator,
    ) -> str:
        """
        Determine the most useful human-readable field name.

        Priority:

        1. Associated label
        2. Wrapping label
        3. aria-label
        4. name
        5. placeholder
        6. id
        """

        element_id = (
            element.get_attribute(
                "id"
            )
        )

        if element_id:

            label = self.page.locator(
                f'label[for="{element_id}"]'
            ).first

            if label.count() > 0:

                text = (
                    label.inner_text()
                    .strip()
                )

                if text:
                    return text

        parent_label = element.locator(
            "xpath=ancestor::label[1]"
        )

        if parent_label.count() > 0:

            text = (
                parent_label.inner_text()
                .strip()
            )

            if text:
                return text

        aria_label = (
            element.get_attribute(
                "aria-label"
            )
        )

        if aria_label:
            return aria_label.strip()

        name = element.get_attribute(
            "name"
        )

        if name:
            return name.strip()

        placeholder = (
            element.get_attribute(
                "placeholder"
            )
        )

        if placeholder:
            return placeholder.strip()

        if element_id:
            return element_id.strip()

        return ""

    # ========================================================
    # REQUIRED
    # ========================================================

    @staticmethod
    def _is_required(
        element: Locator,
    ) -> bool:

        return (
            element.get_attribute(
                "required"
            )
            is not None
        )

    # ========================================================
    # FIND FIELD
    # ========================================================

    def _find_field(
        self,
        field_name: str,
    ) -> Optional[Locator]:

        form = self._ensure_form()

        target = (
            str(field_name)
            .strip()
            .lower()
        )

        if not target:
            return None

        # ----------------------------------------------------
        # Exact selectors
        # ----------------------------------------------------

        escaped = (
            str(field_name)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
        )

        selectors = [
            f'[name="{escaped}"]',
            f'#{escaped}',
            f'[aria-label="{escaped}"]',
            f'[placeholder="{escaped}"]',
        ]

        for selector in selectors:

            try:

                locator = (
                    form.locator(
                        selector
                    ).first
                )

                if locator.count() > 0:
                    return locator

            except Exception:
                continue

        # ----------------------------------------------------
        # Label match
        # ----------------------------------------------------

        labels = form.locator(
            "label"
        )

        for index in range(
            labels.count()
        ):

            label = labels.nth(index)

            try:
                text = (
                    label.inner_text()
                    .strip()
                    .lower()
                )
            except Exception:
                continue

            if text != target:
                continue

            label_for = (
                label.get_attribute(
                    "for"
                )
            )

            if label_for:

                locator = form.locator(
                    f'#{label_for}'
                ).first

                if locator.count() > 0:
                    return locator

            wrapped = label.locator(
                "input, textarea, select"
            ).first

            if wrapped.count() > 0:
                return wrapped

        # ----------------------------------------------------
        # Human-readable field-name match
        # ----------------------------------------------------

        fields = form.locator(
            "input, textarea, select"
        )

        for index in range(
            fields.count()
        ):

            element = fields.nth(index)

            name = (
                self._field_name(
                    element
                )
                .strip()
                .lower()
            )

            if name == target:
                return element

        return None

    # ========================================================
    # FILL FIELD
    # ========================================================

    def fill_field(
        self,
        field_name: str,
        value: Any,
    ) -> bool:

        field = self._find_field(
            field_name
        )

        if field is None:
            return False

        input_type = (
            field.get_attribute(
                "type"
            )
            or ""
        ).lower()

        try:

            if input_type == "checkbox":

                desired = (
                    str(value)
                    .strip()
                    .lower()
                    in {
                        "true",
                        "yes",
                        "1",
                        "on",
                    }
                )

                if desired:
                    field.check()
                else:
                    field.uncheck()

                return True

            if input_type == "radio":

                field.check()

                return True

            tag_name = field.evaluate(
                "(element) => "
                "element.tagName.toLowerCase()"
            )

            if tag_name == "select":

                field.select_option(
                    label=str(value)
                )

                return True

            field.fill(
                str(value)
            )

            return True

        except Exception:
            return False

    # ========================================================
    # UPLOAD RESUME
    # ========================================================

    def upload_resume(
        self,
        resume_path: str,
    ) -> bool:

        path = Path(
            str(resume_path)
            .strip()
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Resume not found: {path}"
            )

        if not path.is_file():
            raise FileNotFoundError(
                f"Resume path is not a file: {path}"
            )

        if self._resume_input is None:
            self.discover()

        if self._resume_input is None:
            raise RuntimeError(
                "No resume upload field was found."
            )

        self._resume_input.set_input_files(
            str(path.resolve())
        )

        self._resume_uploaded = True

        return True

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate(self) -> dict:
        """
        Validate required application fields.

        Returns a structured validation result.
        """

        if not self._discovered_fields:
            self.discover()

        missing_required = []

        for field in self._discovered_fields:

            if not field.get(
                "required"
            ):
                continue

            name = field.get(
                "name",
                "",
            )

            locator = self._find_field(
                name
            )

            if locator is None:
                missing_required.append(
                    name
                )
                continue

            input_type = (
                locator.get_attribute(
                    "type"
                )
                or ""
            ).lower()

            # ------------------------------------------------
            # FILE
            # ------------------------------------------------

            if input_type == "file":

                if not self._resume_uploaded:

                    try:
                        files = (
                            locator.input_value()
                        )
                    except Exception:
                        files = ""

                    if not files:
                        missing_required.append(
                            name or "Resume"
                        )

                continue

            # ------------------------------------------------
            # CHECKBOX
            # ------------------------------------------------

            if input_type == "checkbox":

                try:
                    checked = (
                        locator.is_checked()
                    )
                except Exception:
                    checked = False

                if not checked:
                    missing_required.append(
                        name
                    )

                continue

            # ------------------------------------------------
            # NORMAL FIELD
            # ------------------------------------------------

            try:
                value = (
                    locator.input_value()
                    .strip()
                )
            except Exception:
                value = ""

            if not value:
                missing_required.append(
                    name
                )

        ready = (
            len(missing_required) == 0
        )

        return {
            "ready": ready,
            "missing_required_fields": (
                missing_required
            ),
            "resume_uploaded": (
                self._resume_uploaded
            ),
        }

    # ========================================================
    # PREPARE APPLICATION
    # ========================================================

    def prepare_application(
        self,
        resume_path: str,
        fields: dict,
    ) -> dict:
        """
        Prepare an application without submitting it.

        Safety checks happen before any form interaction.
        """

        # ----------------------------------------------------
        # Analyze page before automation
        # ----------------------------------------------------

        analysis = self.analyze_page()

        blocking_statuses = {
            self.STATUS_LOGIN_REQUIRED,
            self.STATUS_CAPTCHA_DETECTED,
            self.STATUS_JOB_UNAVAILABLE,
            self.STATUS_FORM_NOT_FOUND,
        }

        if (
            analysis["status"]
            in blocking_statuses
        ):

            return {
                "success": False,
                "status": analysis[
                    "status"
                ],
                "message": analysis[
                    "reason"
                ],
                "page_analysis": analysis,
                "filled_fields": [],
                "failed_fields": [],
                "resume_uploaded": False,
                "validation": {
                    "ready": False,
                    "missing_required_fields": [],
                    "resume_uploaded": False,
                },
            }

        # ----------------------------------------------------
        # Discover
        # ----------------------------------------------------

        if not self._discovered_fields:
            self.discover()

        filled_fields = []
        failed_fields = []

        # ----------------------------------------------------
        # Fill fields
        # ----------------------------------------------------

        if fields is None:
            fields = {}

        if not isinstance(
            fields,
            dict,
        ):
            raise TypeError(
                "fields must be a dictionary."
            )

        for field_name, value in (
            fields.items()
        ):

            success = self.fill_field(
                field_name,
                value,
            )

            if success:
                filled_fields.append(
                    field_name
                )
            else:
                failed_fields.append(
                    field_name
                )

        # ----------------------------------------------------
        # Upload resume
        # ----------------------------------------------------

        resume_uploaded = False

        try:

            resume_uploaded = (
                self.upload_resume(
                    resume_path
                )
            )

        except FileNotFoundError:
            raise

        except RuntimeError:
            resume_uploaded = False

        # ----------------------------------------------------
        # Validate
        # ----------------------------------------------------

        validation = self.validate()

        ready = bool(
            validation["ready"]
        )

        self._prepared = ready

        self._page_status = (
            self.STATUS_READY
            if ready
            else self.STATUS_VALIDATION_FAILED
        )

        return {
            "success": ready,
            "status": (
                self.STATUS_READY
                if ready
                else self.STATUS_VALIDATION_FAILED
            ),
            "filled_fields": filled_fields,
            "failed_fields": failed_fields,
            "resume_uploaded": (
                resume_uploaded
            ),
            "validation": validation,
            "page_analysis": (
                self.get_page_analysis()
            ),
        }

    # ========================================================
    # SUBMIT
    # ========================================================

    def submit(
        self,
        confirm: bool = False,
    ) -> dict:
        """
        Submit the application.

        Explicit confirmation is always required.

        No CAPTCHA/login bypass is attempted.
        """

        # ----------------------------------------------------
        # Analyze page before submission
        # ----------------------------------------------------

        analysis = self.analyze_page()

        if (
            analysis["status"]
            == self.STATUS_CAPTCHA_DETECTED
        ):

            return {
                "success": False,
                "status": self.STATUS_CAPTCHA_DETECTED,
                "message": analysis[
                    "reason"
                ],
                "page_analysis": analysis,
            }

        if (
            analysis["status"]
            == self.STATUS_LOGIN_REQUIRED
        ):

            return {
                "success": False,
                "status": self.STATUS_LOGIN_REQUIRED,
                "message": analysis[
                    "reason"
                ],
                "page_analysis": analysis,
            }

        if (
            analysis["status"]
            == self.STATUS_JOB_UNAVAILABLE
        ):

            return {
                "success": False,
                "status": self.STATUS_JOB_UNAVAILABLE,
                "message": analysis[
                    "reason"
                ],
                "page_analysis": analysis,
            }

        if (
            analysis["status"]
            == self.STATUS_FORM_NOT_FOUND
        ):

            return {
                "success": False,
                "status": self.STATUS_FORM_NOT_FOUND,
                "message": analysis[
                    "reason"
                ],
                "page_analysis": analysis,
            }

        # ----------------------------------------------------
        # Explicit confirmation
        # ----------------------------------------------------

        if not confirm:

            return {
                "success": False,
                "status": (
                    self.STATUS_CONFIRMATION_REQUIRED
                ),
                "message": (
                    "Application is ready, but final "
                    "submission requires explicit "
                    "confirmation."
                ),
                "page_analysis": analysis,
            }

        # ----------------------------------------------------
        # Validate before submitting
        # ----------------------------------------------------

        validation = self.validate()

        if not validation["ready"]:

            self._page_status = (
                self.STATUS_VALIDATION_FAILED
            )

            return {
                "success": False,
                "status": (
                    self.STATUS_VALIDATION_FAILED
                ),
                "validation": validation,
                "page_analysis": (
                    self.get_page_analysis()
                ),
            }

        # ----------------------------------------------------
        # Make sure form exists
        # ----------------------------------------------------

        try:
            form = self._ensure_form()

        except RuntimeError as exc:

            return {
                "success": False,
                "status": (
                    self.STATUS_FORM_NOT_FOUND
                ),
                "message": str(exc),
                "page_analysis": (
                    self.get_page_analysis()
                ),
            }

        # ----------------------------------------------------
        # Find submit button
        # ----------------------------------------------------

        submit_button = form.locator(
            'button[type="submit"], '
            'input[type="submit"], '
            'button:has-text("Submit"), '
            'button:has-text("Apply")'
        ).first

        if submit_button.count() == 0:

            return {
                "success": False,
                "status": (
                    "submit_button_not_found"
                ),
                "page_analysis": (
                    self.get_page_analysis()
                ),
            }

        # ----------------------------------------------------
        # Submit
        # ----------------------------------------------------

        try:

            submit_button.click(
                timeout=self.timeout
            )

            self._page_status = (
                self.STATUS_SUBMITTED
            )

            return {
                "success": True,
                "status": (
                    self.STATUS_SUBMITTED
                ),
                "page_analysis": (
                    self.get_page_analysis()
                ),
            }

        except PlaywrightTimeoutError:

            self._page_status = (
                self.STATUS_SUBMISSION_TIMEOUT
            )

            return {
                "success": False,
                "status": (
                    self.STATUS_SUBMISSION_TIMEOUT
                ),
                "page_analysis": (
                    self.get_page_analysis()
                ),
            }

        except Exception as exc:

            self._page_status = (
                self.STATUS_SUBMISSION_FAILED
            )

            return {
                "success": False,
                "status": (
                    self.STATUS_SUBMISSION_FAILED
                ),
                "message": str(exc),
                "page_analysis": (
                    self.get_page_analysis()
                ),
            }

    # ========================================================
    # HUMAN ACTION
    # ========================================================

    def human_action_required_result(
        self,
    ) -> dict:
        """
        Convert the current blocking page state into a
        standard human-action-required result.
        """

        analysis = (
            self.get_page_analysis()
        )

        if not analysis.get(
            "requires_human_action"
        ):
            return {
                "success": False,
                "status": (
                    "human_action_not_required"
                ),
                "page_analysis": analysis,
            }

        return {
            "success": False,
            "status": (
                self.STATUS_HUMAN_ACTION_REQUIRED
            ),
            "message": analysis.get(
                "reason",
                "Human intervention is required.",
            ),
            "page_analysis": analysis,
        }

    # ========================================================
    # RESET
    # ========================================================

    def reset(self) -> None:
        """
        Reset internal application state.
        """

        self._discovered_fields = []
        self._resume_input = None
        self._resume_uploaded = False
        self._prepared = False

        self._page_status = (
            self.STATUS_NOT_ANALYZED
        )

        self._page_analysis = {
            "status": self.STATUS_NOT_ANALYZED,
            "safe_for_automation": False,
            "requires_human_action": False,
            "captcha_detected": False,
            "login_required": False,
            "job_unavailable": False,
            "form_found": False,
            "url": "",
            "title": "",
            "reason": "",
            "signals": [],
        }