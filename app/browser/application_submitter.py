from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError


class ApplicationSubmitter:
    """
    Handles preparation and controlled submission of job applications.

    Responsibilities:
    - Open application pages
    - Discover form fields
    - Fill application fields
    - Upload resumes
    - Validate required fields
    - Prepare an application
    - Submit only after explicit confirmation

    Important:
    Final submission requires:

        submit(confirm=True)

    This prevents accidental job applications.
    """

    def __init__(
        self,
        page: Page,
        form_selector: str = "form",
        timeout: int = 5000,
    ):
        self.page = page
        self.form_selector = form_selector
        self.timeout = timeout

        self.form: Locator = self.page.locator(
            self.form_selector
        ).first

        self._discovered_fields: list[dict] = []
        self._resume_input: Optional[Locator] = None
        self._resume_uploaded: bool = False
        self._prepared: bool = False

    # ========================================================
    # OPEN
    # ========================================================

    def open(self, url: str) -> bool:
        """
        Open an application URL.

        Returns:
            True when the page opens successfully.
        """

        if not url or not url.strip():
            raise ValueError("URL cannot be empty.")

        try:
            self.page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout,
            )

            return True

        except Exception:
            return False

    # ========================================================
    # FORM
    # ========================================================

    def _ensure_form(self) -> Locator:
        """
        Return the current form.

        Raises:
            RuntimeError if no form exists.
        """

        if self.form.count() == 0:
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

        Returns a list containing:
        - normal input fields
        - textarea fields
        - select fields
        - resume upload fields
        """

        form = self._ensure_form()

        discovered = []

        # ----------------------------------------------------
        # INPUTS
        # ----------------------------------------------------

        inputs = form.locator("input")

        for index in range(inputs.count()):

            element = inputs.nth(index)

            input_type = (
                element.get_attribute("type")
                or "text"
            ).lower()

            name = self._field_name(element)

            if input_type == "file":
                self._resume_input = element

                discovered.append(
                    {
                        "name": name or "Resume",
                        "type": "file",
                        "required": self._is_required(element),
                    }
                )

                continue

            # Skip submit/button/reset/hidden controls.
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
                    "required": self._is_required(element),
                }
            )

        # ----------------------------------------------------
        # TEXTAREAS
        # ----------------------------------------------------

        textareas = form.locator("textarea")

        for index in range(textareas.count()):

            element = textareas.nth(index)

            discovered.append(
                {
                    "name": self._field_name(element),
                    "type": "textarea",
                    "required": self._is_required(element),
                }
            )

        # ----------------------------------------------------
        # SELECTS
        # ----------------------------------------------------

        selects = form.locator("select")

        for index in range(selects.count()):

            element = selects.nth(index)

            discovered.append(
                {
                    "name": self._field_name(element),
                    "type": "select",
                    "required": self._is_required(element),
                }
            )

        self._discovered_fields = discovered

        return discovered

    # ========================================================
    # FIELD NAME
    # ========================================================

    def _field_name(self, element: Locator) -> str:
        """
        Determine the most useful human-readable field name.

        Priority:
        1. Associated label
        2. aria-label
        3. name
        4. placeholder
        5. id
        """

        element_id = element.get_attribute("id")

        # ----------------------------------------------------
        # Associated <label for="...">
        # ----------------------------------------------------

        if element_id:

            label = self.page.locator(
                f'label[for="{element_id}"]'
            ).first

            if label.count() > 0:

                text = label.inner_text().strip()

                if text:
                    return text

        # ----------------------------------------------------
        # Wrapping label
        # ----------------------------------------------------

        parent_label = element.locator(
            "xpath=ancestor::label[1]"
        )

        if parent_label.count() > 0:

            text = parent_label.inner_text().strip()

            if text:
                return text

        # ----------------------------------------------------
        # aria-label
        # ----------------------------------------------------

        aria_label = element.get_attribute(
            "aria-label"
        )

        if aria_label:
            return aria_label.strip()

        # ----------------------------------------------------
        # name
        # ----------------------------------------------------

        name = element.get_attribute("name")

        if name:
            return name.strip()

        # ----------------------------------------------------
        # placeholder
        # ----------------------------------------------------

        placeholder = element.get_attribute(
            "placeholder"
        )

        if placeholder:
            return placeholder.strip()

        # ----------------------------------------------------
        # id
        # ----------------------------------------------------

        if element_id:
            return element_id.strip()

        return ""

    # ========================================================
    # REQUIRED
    # ========================================================

    @staticmethod
    def _is_required(element: Locator) -> bool:
        """
        Determine whether an element is required.
        """

        return (
            element.get_attribute("required")
            is not None
        )

    # ========================================================
    # FIND FIELD
    # ========================================================

    def _find_field(
        self,
        field_name: str,
    ) -> Optional[Locator]:
        """
        Find a form field using several strategies.
        """

        form = self._ensure_form()

        target = field_name.strip().lower()

        if not target:
            return None

        # ----------------------------------------------------
        # Search discovered fields first
        # ----------------------------------------------------

        selectors = [
            f'[name="{field_name}"]',
            f'#{field_name}',
            f'[aria-label="{field_name}"]',
            f'[placeholder="{field_name}"]',
        ]

        for selector in selectors:

            try:

                locator = form.locator(selector).first

                if locator.count() > 0:
                    return locator

            except Exception:
                continue

        # ----------------------------------------------------
        # Match by label
        # ----------------------------------------------------

        labels = form.locator("label")

        for index in range(labels.count()):

            label = labels.nth(index)

            try:
                text = label.inner_text().strip().lower()
            except Exception:
                continue

            if text != target:
                continue

            label_for = label.get_attribute("for")

            if label_for:

                locator = form.locator(
                    f"#{label_for}"
                ).first

                if locator.count() > 0:
                    return locator

            wrapped = label.locator(
                "input, textarea, select"
            ).first

            if wrapped.count() > 0:
                return wrapped

        # ----------------------------------------------------
        # Fuzzy match using field names
        # ----------------------------------------------------

        fields = form.locator(
            "input, textarea, select"
        )

        for index in range(fields.count()):

            element = fields.nth(index)

            name = self._field_name(
                element
            ).lower()

            if name == target:
                return element

        return None

    # ========================================================
    # FILL FIELD
    # ========================================================

    def fill_field(
        self,
        field_name: str,
        value: str,
    ) -> bool:
        """
        Fill a field by human-readable field name.
        """

        field = self._find_field(field_name)

        if field is None:
            return False

        input_type = (
            field.get_attribute("type")
            or ""
        ).lower()

        try:

            if input_type == "checkbox":

                desired = str(value).lower() in {
                    "true",
                    "yes",
                    "1",
                    "on",
                }

                if desired:
                    field.check()
                else:
                    field.uncheck()

                return True

            if input_type == "radio":

                field.check()

                return True

            tag_name = field.evaluate(
                "(element) => element.tagName.toLowerCase()"
            )

            if tag_name == "select":

                field.select_option(
                    label=str(value)
                )

                return True

            field.fill(str(value))

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
        """
        Upload a resume PDF.

        Raises:
            FileNotFoundError if the file does not exist.
        """

        path = Path(resume_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Resume not found: {resume_path}"
            )

        if not path.is_file():
            raise FileNotFoundError(
                f"Resume path is not a file: {resume_path}"
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

            if not field.get("required"):
                continue

            name = field.get("name", "")

            locator = self._find_field(name)

            if locator is None:
                missing_required.append(name)
                continue

            input_type = (
                locator.get_attribute("type")
                or ""
            ).lower()

            # ----------------------------------------------
            # File input
            # ----------------------------------------------

            if input_type == "file":

                if not self._resume_uploaded:

                    files = locator.input_value()

                    if not files:
                        missing_required.append(
                            name or "Resume"
                        )

                continue

            # ----------------------------------------------
            # Checkbox
            # ----------------------------------------------

            if input_type == "checkbox":

                if not locator.is_checked():
                    missing_required.append(name)

                continue

            # ----------------------------------------------
            # Normal value
            # ----------------------------------------------

            try:
                value = locator.input_value().strip()
            except Exception:
                value = ""

            if not value:
                missing_required.append(name)

        ready = len(missing_required) == 0

        return {
            "ready": ready,
            "missing_required_fields": missing_required,
            "resume_uploaded": self._resume_uploaded,
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
        Fill application fields and upload the resume.

        Does NOT submit the application.

        The result will be ready for explicit submission.
        """

        if not self._discovered_fields:
            self.discover()

        filled_fields = []

        failed_fields = []

        # ----------------------------------------------------
        # Fill fields
        # ----------------------------------------------------

        for field_name, value in fields.items():

            success = self.fill_field(
                field_name,
                value,
            )

            if success:
                filled_fields.append(field_name)
            else:
                failed_fields.append(field_name)

        # ----------------------------------------------------
        # Upload resume
        # ----------------------------------------------------

        resume_uploaded = False

        try:

            resume_uploaded = self.upload_resume(
                resume_path
            )

        except FileNotFoundError:
            raise

        except RuntimeError:
            resume_uploaded = False

        # ----------------------------------------------------
        # Validate
        # ----------------------------------------------------

        validation = self.validate()

        ready = validation["ready"]

        self._prepared = ready

        return {
            "success": ready,
            "status": (
                "ready_for_submission"
                if ready
                else "validation_failed"
            ),
            "filled_fields": filled_fields,
            "failed_fields": failed_fields,
            "resume_uploaded": resume_uploaded,
            "validation": validation,
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

        IMPORTANT:
        Explicit confirmation is required.

        Example:

            submitter.submit(confirm=True)

        Without confirmation, nothing is submitted.
        """

        # ----------------------------------------------------
        # Explicit confirmation
        # ----------------------------------------------------

        if not confirm:

            return {
                "success": False,
                "status": "confirmation_required",
                "message": (
                    "Application is ready, but final "
                    "submission requires explicit "
                    "confirmation."
                ),
            }

        # ----------------------------------------------------
        # Validate before submitting
        # ----------------------------------------------------

        validation = self.validate()

        if not validation["ready"]:

            return {
                "success": False,
                "status": "validation_failed",
                "validation": validation,
            }

        # ----------------------------------------------------
        # Make sure form exists
        # ----------------------------------------------------

        try:
            form = self._ensure_form()

        except RuntimeError as exc:

            return {
                "success": False,
                "status": "form_not_found",
                "message": str(exc),
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
                "status": "submit_button_not_found",
            }

        # ----------------------------------------------------
        # Submit
        # ----------------------------------------------------

        try:

            submit_button.click(
                timeout=self.timeout
            )

            return {
                "success": True,
                "status": "submitted",
            }

        except PlaywrightTimeoutError:

            return {
                "success": False,
                "status": "submission_timeout",
            }

        except Exception as exc:

            return {
                "success": False,
                "status": "submission_failed",
                "message": str(exc),
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