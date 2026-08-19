from __future__ import annotations

from pathlib import Path

from app.browser.application_navigator import ApplicationNavigator
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
    STATUS_APPLY_CONTROL_FOUND = "apply_control_found"
    # Backward-compatible name used by the application-control tests and
    # older workflow/router code. Both constants intentionally represent
    # the same detected Apply control state.
    STATUS_APPLY_CONTROL_DETECTED = STATUS_APPLY_CONTROL_FOUND
    STATUS_READY_TO_APPLY = "ready_to_apply"
    STATUS_APPLICATION_HANDOFF = "application_handoff"
    STATUS_APPLICATION_ROUTE_NOT_FOUND = "application_route_not_found"

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
        self._job_context: dict[str, Any] = {}
        self._apply_control_label = ""
        self._direct_apply_control = None
        self._application_completed = False
        self._prepared_resume_path = ""
        self._prepared_fields: dict[str, Any] = {}

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

    def set_job_context(self, job: Optional[dict[str, Any]] = None) -> None:
        self._job_context = dict(job or {}) if isinstance(job, dict) else {}

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
        # APPLY CONTROL / APPLICATION ROUTE
        # ----------------------------------------------------

        apply_control = self._find_apply_control()
        if apply_control is not None:
            self._apply_control_label = self._control_label(apply_control)
            self._direct_apply_control = apply_control
            self._set_page_analysis(
                status=self.STATUS_APPLY_CONTROL_FOUND,
                safe_for_automation=True,
                requires_human_action=False,
                captcha_detected=False,
                login_required=False,
                job_unavailable=False,
                form_found=False,
                reason=f"Application control detected: {self._apply_control_label}",
                signals=["application_control_found"],
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
                "No application form or usable application control "
                "was detected on the current page."
            ),
            signals=["application_form_not_found", "application_control_not_found"],
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
    # APPLY CONTROL / ROUTING
    # ========================================================

    @staticmethod
    def _control_label(element: Locator) -> str:
        for attr in ("aria-label", "title", "value", "name"):
            try:
                value = (element.get_attribute(attr) or "").strip()
                if value:
                    return value
            except Exception:
                pass
        try:
            return " ".join((element.inner_text() or "").split()).strip()
        except Exception:
            return ""

    def _find_apply_control(self) -> Optional[Locator]:
        try:
            candidates = self.page.locator('a,button,input[type="submit"],input[type="button"]')
            for index in range(candidates.count()):
                element = candidates.nth(index)
                label = self._control_label(element).lower().strip()
                if label in {
                    "apply", "apply now", "apply on company site",
                    "apply on employer site", "apply on company website",
                    "apply at company", "apply externally",
                }:
                    try:
                        if element.is_visible(timeout=500):
                            return element
                    except Exception:
                        continue
        except Exception:
            return None
        return None

    def _is_external_apply_control(self) -> bool:
        label = self._apply_control_label.lower()
        return any(token in label for token in (
            "company site", "employer site", "company website", "extern"
        ))

    def _follow_application_route(self) -> dict:
        navigator = ApplicationNavigator(self.page, timeout=self.timeout)
        result = navigator.navigate(self._job_context)
        status = result.get("status")
        if status == "form_detected":
            self.form = self.page.locator(self.form_selector).first
            self.analyze_page()
        elif status == "submitted":
            self._application_completed = True
            self._page_status = self.STATUS_SUBMITTED
        return result

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

        if analysis["status"] == self.STATUS_APPLY_CONTROL_FOUND:
            if self._is_external_apply_control():
                route = self._follow_application_route()
                route_status = route.get("status")
                if route_status == "form_detected":
                    analysis = self.analyze_page()
                elif route_status == "ready_to_apply":
                    self._prepared = True
                    self._prepared_resume_path = str(resume_path)
                    self._prepared_fields = dict(fields or {})
                    return {
                        "success": True,
                        "status": self.STATUS_READY_TO_APPLY,
                        "message": "Employer site reached its final Apply control; final click is deferred until live submission.",
                        "page_analysis": self.get_page_analysis(),
                        "navigation": route,
                        "filled_fields": [],
                        "failed_fields": [],
                        "resume_uploaded": False,
                        "validation": {"ready": True, "missing_required_fields": [], "resume_uploaded": False},
                    }
                elif route_status == "submitted":
                    return {
                        "success": True,
                        "status": self.STATUS_SUBMITTED,
                        "submitted": True,
                        "filled_fields": [],
                        "failed_fields": [],
                        "resume_uploaded": False,
                        "validation": {"ready": True, "missing_required_fields": [], "resume_uploaded": False},
                        "page_analysis": self.get_page_analysis(),
                        "navigation": route,
                    }
                else:
                    return {
                        "success": False,
                        "status": route_status or self.STATUS_APPLICATION_ROUTE_NOT_FOUND,
                        "message": "The employer application route could not be completed automatically.",
                        "page_analysis": self.get_page_analysis(),
                        "navigation": route,
                        "filled_fields": [],
                        "failed_fields": [],
                        "resume_uploaded": False,
                        "validation": {"ready": False, "missing_required_fields": [], "resume_uploaded": False},
                    }
            else:
                self._prepared = True
                self._prepared_resume_path = str(resume_path)
                self._prepared_fields = dict(fields or {})
                return {
                    "success": True,
                    "status": self.STATUS_APPLY_CONTROL_DETECTED,
                    "message": "Direct Apply control detected; final click is deferred until live submission.",
                    "page_analysis": analysis,
                    "filled_fields": [],
                    "failed_fields": [],
                    "resume_uploaded": False,
                    "validation": {"ready": True, "missing_required_fields": [], "resume_uploaded": False},
                }

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

        self._prepared_resume_path = str(resume_path)
        self._prepared_fields = dict(fields)

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

        if analysis["status"] == self.STATUS_SUBMITTED and self._application_completed:
            if not confirm:
                return {
                    "success": False,
                    "status": self.STATUS_CONFIRMATION_REQUIRED,
                    "submitted": False,
                    "page_analysis": analysis,
                }
            return {
                "success": True,
                "status": self.STATUS_SUBMITTED,
                "submitted": True,
                "page_analysis": analysis,
            }

        if analysis["status"] == self.STATUS_APPLY_CONTROL_FOUND:
            # A direct Apply control and an employer-site Apply control use
            # the same state machine.  The distinction matters for
            # navigation during preparation, but once the user has explicitly
            # authorized live execution we must follow the control and inspect
            # the resulting page instead of treating it as a failed form.
            if not confirm:
                return {
                    "success": False,
                    "status": self.STATUS_CONFIRMATION_REQUIRED,
                    "submitted": False,
                    "page_analysis": analysis,
                }

            control = self._find_apply_control()
            if control is None:
                return {
                    "success": False,
                    "status": self.STATUS_APPLICATION_ROUTE_NOT_FOUND,
                    "page_analysis": analysis,
                }

            before_url = self._safe_page_url()

            try:
                control.scroll_into_view_if_needed(timeout=self.timeout)
                control.click(timeout=self.timeout)
                try:
                    self.page.wait_for_load_state(
                        "domcontentloaded",
                        timeout=self.timeout,
                    )
                except Exception:
                    pass
                try:
                    self.page.wait_for_timeout(1000)
                except Exception:
                    pass
            except Exception as exc:
                return {
                    "success": False,
                    "status": self.STATUS_SUBMISSION_FAILED,
                    "message": str(exc),
                    "page_analysis": analysis,
                }

            # Re-analyze after every transition.  A real application may
            # expose another Apply step, an application form, a login/CAPTCHA
            # barrier, or a confirmation page.
            next_analysis = self.analyze_page()

            if next_analysis["status"] == self.STATUS_FORM_DETECTED:
                prepared = self.prepare_application(
                    resume_path=self._prepared_resume_path,
                    fields=self._prepared_fields,
                )
                if prepared.get("success"):
                    return self.submit(confirm=True)
                return prepared

            if self._success_visible():
                self._application_completed = True
                self._page_status = self.STATUS_SUBMITTED
                return {
                    "success": True,
                    "status": self.STATUS_SUBMITTED,
                    "submitted": True,
                    "page_analysis": next_analysis,
                }

            if next_analysis["status"] == self.STATUS_APPLY_CONTROL_FOUND:
                return {
                    "success": True,
                    "status": self.STATUS_APPLICATION_HANDOFF,
                    "submitted": False,
                    "message": (
                        "The Apply control was activated, but the resulting "
                        "page still requires another application step. "
                        "Submission was not claimed."
                    ),
                    "page_analysis": next_analysis,
                }

            if next_analysis["status"] in {
                self.STATUS_LOGIN_REQUIRED,
                self.STATUS_CAPTCHA_DETECTED,
            }:
                return {
                    "success": False,
                    "status": next_analysis["status"],
                    "submitted": False,
                    "requires_human_action": True,
                    "message": next_analysis["reason"],
                    "page_analysis": next_analysis,
                }

            # If the URL changed but the new page is not yet classifiable,
            # report a handoff rather than falsely claiming failure or
            # submission.  This is particularly useful for employer ATS
            # redirects that finish rendering asynchronously.
            if self._safe_page_url() != before_url:
                return {
                    "success": True,
                    "status": self.STATUS_APPLICATION_HANDOFF,
                    "submitted": False,
                    "message": (
                        "The application route advanced to a new page, "
                        "but submission has not yet been confirmed."
                    ),
                    "page_analysis": next_analysis,
                }

            return {
                "success": False,
                "status": next_analysis.get(
                    "status",
                    self.STATUS_APPLICATION_ROUTE_NOT_FOUND,
                ),
                "page_analysis": next_analysis,
            }

        if analysis["status"] == self.STATUS_FORM_NOT_FOUND:
            return {
                "success": False,
                "status": self.STATUS_FORM_NOT_FOUND,
                "message": analysis["reason"],
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
        # Find the actual submission control
        # ----------------------------------------------------
        #
        # Some employer forms place the submit control outside the <form>
        # element (common with JS/React form builders).  Looking only inside
        # ``form`` therefore produces the misleading ``submit_button_not_found``
        # result even though a real Submit/Apply control is present on the
        # page.  Prefer controls inside the form, then fall back to the page.
        submit_button = self._find_submission_control(form)

        if submit_button is None:

            return {
                "success": False,
                "status": "submit_button_not_found",
                "message": (
                    "The application page was prepared, but no reliable "
                    "Submit/Apply control could be identified."
                ),
                "page_analysis": self.get_page_analysis(),
            }

        # ----------------------------------------------------
        # Submit
        # ----------------------------------------------------

        try:

            before_url = self._safe_page_url()

            submit_button.scroll_into_view_if_needed(
                timeout=self.timeout
            )
            submit_button.click(
                timeout=self.timeout
            )

            try:
                self.page.wait_for_load_state(
                    "domcontentloaded",
                    timeout=self.timeout,
                )
            except Exception:
                pass

            try:
                self.page.wait_for_timeout(1000)
            except Exception:
                pass

            # Never equate a successful click with a successful application.
            # Re-analyze the resulting page and only report ``submitted`` when
            # a confirmation signal is visible OR when this was a real native/
            # server form submission that navigated away and the application
            # form disappeared. The latter is important for simple/ATS forms
            # that redirect to a URL without rendering a "Thank you" message.
            after_analysis = self.analyze_page()

            after_url = self._safe_page_url()
            form_still_present = self._form_exists()

            if self._success_visible():
                self._application_completed = True
                self._page_status = self.STATUS_SUBMITTED
                return {
                    "success": True,
                    "status": self.STATUS_SUBMITTED,
                    "submitted": True,
                    "page_analysis": after_analysis,
                }

            if (
                after_url != before_url
                and not form_still_present
                and after_analysis["status"] == self.STATUS_FORM_NOT_FOUND
            ):
                self._application_completed = True
                self._page_status = self.STATUS_SUBMITTED
                return {
                    "success": True,
                    "status": self.STATUS_SUBMITTED,
                    "submitted": True,
                    "message": (
                        "The application form was submitted and the page "
                        "navigated away from the form without exposing a "
                        "separate confirmation message."
                    ),
                    "page_analysis": after_analysis,
                }

            if after_analysis["status"] in {
                self.STATUS_LOGIN_REQUIRED,
                self.STATUS_CAPTCHA_DETECTED,
            }:
                return {
                    "success": False,
                    "status": after_analysis["status"],
                    "submitted": False,
                    "requires_human_action": True,
                    "page_analysis": after_analysis,
                }

            # A successful click may leave the browser on a pending/ATS
            # transition page.  Treat that as a handoff rather than claiming
            # submission.
            if after_analysis["status"] == self.STATUS_APPLY_CONTROL_FOUND:
                return {
                    "success": True,
                    "status": self.STATUS_APPLICATION_HANDOFF,
                    "submitted": False,
                    "page_analysis": after_analysis,
                }

            return {
                "success": True,
                "status": self.STATUS_APPLICATION_HANDOFF,
                "submitted": False,
                "message": (
                    "The submission control was activated, but the page "
                    "did not expose a confirmation signal."
                ),
                "page_analysis": after_analysis,
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

    def _find_submission_control(self, form: Locator) -> Optional[Locator]:
        """
        Find a likely final application-submit control.

        Employer ATS pages are inconsistent: the final control may be inside
        the form, outside it, a <button type="button"> driven by JavaScript,
        or an ARIA button.  We therefore inspect the form first and then the
        whole document.

        Deliberately conservative: navigation/filter controls are rejected so
        that "Apply filters" is never mistaken for a job application.
        """
        reject_tokens = {
            "apply filters",
            "filter",
            "search",
            "save",
            "cancel",
            "close",
            "back",
            "previous",
            "sign in",
            "login",
            "register",
            "create account",
        }

        strong = (
            "submit application",
            "submit your application",
            "submit application form",
            "send application",
            "send your application",
            "complete application",
            "finish application",
            "submit",
        )
        medium = (
            "apply now",
            "apply",
            "finish",
            "complete",
        )

        def label(element: Locator) -> str:
            return self._control_label(element).strip()

        def score(element: Locator) -> int:
            text = label(element).lower()
            if not text or any(token in text for token in reject_tokens):
                return -1

            score_value = 0
            if any(token == text for token in strong):
                score_value = 100
            elif any(token in text for token in strong):
                score_value = 90
            elif any(token == text for token in medium):
                score_value = 80
            elif any(token in text for token in medium):
                score_value = 70

            # A submit-type control is useful even when its visible label is
            # empty, but only after stronger text-labelled controls.
            try:
                control_type = (
                    element.get_attribute("type") or ""
                ).lower()
            except Exception:
                control_type = ""

            if control_type == "submit":
                score_value = max(score_value, 75)

            return score_value

        selectors = (
            'button, input[type="submit"], input[type="button"], '
            '[role="button"]'
        )

        best: Optional[Locator] = None
        best_score = -1

        # Search the actual form first.
        containers = [form]
        try:
            if form.count() == 0:
                containers = []
        except Exception:
            containers = []

        # Then search the entire document because some JS form builders put
        # the final action outside <form>.
        containers.append(self.page.locator("body"))

        seen = set()
        for container in containers:
            try:
                candidates = container.locator(selectors)
                count = candidates.count()
            except Exception:
                continue

            for index in range(count):
                element = candidates.nth(index)
                try:
                    element_id = element.get_attribute("id") or ""
                    element_name = element.get_attribute("name") or ""
                    key = (element_id, element_name, label(element))
                    if key in seen:
                        continue
                    seen.add(key)

                    if not element.is_visible(timeout=500):
                        continue

                    current_score = score(element)
                    if current_score > best_score:
                        best = element
                        best_score = current_score
                except Exception:
                    continue

        return best if best_score >= 70 else None

    def _success_visible(self) -> bool:
        try:
            text = self.page.locator("body").inner_text(timeout=1000)
        except Exception:
            return False
        lowered = (text or "").lower()
        return any(phrase in lowered for phrase in (
            "application submitted", "application received",
            "thank you for applying", "successfully applied",
            "application complete",
        ))

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
        self._apply_control_label = ""
        self._direct_apply_control = None
        self._application_completed = False
        self._prepared_resume_path = ""
        self._prepared_fields = {}

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