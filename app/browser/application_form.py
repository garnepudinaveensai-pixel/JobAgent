from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from playwright.sync_api import Locator, Page


@dataclass
class FormField:
    """
    Represents a detected application form field.
    """

    field_type: str
    name: str = ""
    label: str = ""
    selector: str = ""
    required: bool = False
    value: str = ""


@dataclass
class ApplicationForm:
    """
    Safe abstraction around a job application form.

    Responsibilities:
    - Detect common form fields
    - Read field metadata
    - Fill simple fields
    - Upload a resume
    - Inspect the form before submission

    This class DOES NOT submit applications yet.
    """

    page: Page
    fields: list[FormField] = field(
        default_factory=list
    )

    # ========================================================
    # FORM DISCOVERY
    # ========================================================

    def discover_fields(self) -> list[FormField]:
        """
        Discover common input fields on the current page.
        """

        self.fields = []

        inputs = self.page.locator(
            "input, textarea, select"
        )

        count = inputs.count()

        for index in range(count):
            element = inputs.nth(index)

            try:
                field = self._inspect_element(
                    element
                )

                if field is not None:
                    self.fields.append(field)

            except Exception:
                continue

        return self.fields

    def _inspect_element(
        self,
        element: Locator,
    ) -> Optional[FormField]:
        """
        Inspect one form element and normalize its metadata.
        """

        tag = element.evaluate(
            "(el) => el.tagName.toLowerCase()"
        )

        field_type = (
            element.get_attribute("type")
            or tag
            or ""
        ).lower()

        name = (
            element.get_attribute("name")
            or ""
        ).strip()

        element_id = (
            element.get_attribute("id")
            or ""
        ).strip()

        placeholder = (
            element.get_attribute("placeholder")
            or ""
        ).strip()

        aria_label = (
            element.get_attribute("aria-label")
            or ""
        ).strip()

        label = self._find_label(
            element,
            element_id,
        )

        if not label:
            label = (
                aria_label
                or placeholder
                or name
                or element_id
            )

        required = (
            element.get_attribute("required")
            is not None
        )

        selector = self._build_selector(
            element,
            element_id,
            name,
        )

        return FormField(
            field_type=field_type,
            name=name,
            label=label,
            selector=selector,
            required=required,
        )

    # ========================================================
    # LABEL DETECTION
    # ========================================================

    def _find_label(
        self,
        element: Locator,
        element_id: str,
    ) -> str:
        """
        Attempt to find a human-readable label.
        """

        try:
            if element_id:
                label = self.page.locator(
                    f'label[for="{element_id}"]'
                ).first

                if label.count():
                    text = label.inner_text().strip()

                    if text:
                        return text

            parent_label = element.locator(
                "xpath=ancestor::label[1]"
            )

            if parent_label.count():
                text = parent_label.inner_text().strip()

                if text:
                    return text

        except Exception:
            pass

        return ""

    # ========================================================
    # SELECTOR
    # ========================================================

    @staticmethod
    def _build_selector(
        element: Locator,
        element_id: str,
        name: str,
    ) -> str:
        """
        Build a stable selector for later interaction.
        """

        if element_id:
            return f"#{element_id}"

        if name:
            escaped_name = (
                name.replace("\\", "\\\\")
                .replace('"', '\\"')
            )

            return (
                f'input[name="{escaped_name}"], '
                f'textarea[name="{escaped_name}"], '
                f'select[name="{escaped_name}"]'
            )

        return ""

    # ========================================================
    # FIND
    # ========================================================

    def find(
        self,
        label: str,
    ) -> Optional[FormField]:
        """
        Find a discovered field using its label/name.
        """

        target = label.strip().lower()

        if not target:
            return None

        for field in self.fields:
            values = [
                field.label,
                field.name,
                field.selector,
            ]

            for value in values:
                if (
                    value
                    and target in value.lower()
                ):
                    return field

        return None

    # ========================================================
    # FILL
    # ========================================================

    def fill(
        self,
        label: str,
        value: str,
    ) -> bool:
        """
        Fill a discovered text-like field.
        """

        field = self.find(label)

        if field is None:
            return False

        if not field.selector:
            return False

        try:
            locator = self.page.locator(
                field.selector
            ).first

            locator.fill(str(value))

            field.value = str(value)

            return True

        except Exception:
            return False

    # ========================================================
    # SELECT
    # ========================================================

    def select(
        self,
        label: str,
        value: str,
    ) -> bool:
        """
        Select an option from a <select> field.
        """

        field = self.find(label)

        if field is None:
            return False

        if field.field_type != "select":
            return False

        if not field.selector:
            return False

        try:
            locator = self.page.locator(
                field.selector
            ).first

            locator.select_option(
                label=value
            )

            field.value = value

            return True

        except Exception:
            return False

    # ========================================================
    # RESUME UPLOAD
    # ========================================================

    def upload_resume(
        self,
        resume_path: str,
    ) -> bool:
        """
        Upload a resume to the first file input.

        The file must already exist.
        """

        path = Path(resume_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Resume not found: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Resume path is not a file: {path}"
            )

        file_inputs = self.page.locator(
            'input[type="file"]'
        )

        if file_inputs.count() == 0:
            return False

        try:
            file_inputs.first.set_input_files(
                str(path.resolve())
            )

            return True

        except Exception:
            return False

    # ========================================================
    # FORM INFORMATION
    # ========================================================

    def get_required_fields(
        self,
    ) -> list[FormField]:
        """
        Return all detected required fields.
        """

        return [
            field
            for field in self.fields
            if field.required
        ]

    def get_file_inputs(self) -> int:
        """
        Return the number of file upload fields.
        """

        return self.page.locator(
            'input[type="file"]'
        ).count()

    def get_unfilled_required_fields(
        self,
    ) -> list[FormField]:
        """
        Return required fields that have not been filled
        through this abstraction.
        """

        return [
            field
            for field in self.get_required_fields()
            if not field.value.strip()
        ]

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate_before_submission(
        self,
    ) -> dict:
        """
        Validate the currently detected form.

        This does NOT submit anything.
        """

        missing = (
            self.get_unfilled_required_fields()
        )

        return {
            "ready": len(missing) == 0,
            "total_fields": len(self.fields),
            "required_fields": len(
                self.get_required_fields()
            ),
            "missing_required_fields": [
                field.label
                for field in missing
            ],
            "file_inputs": self.get_file_inputs(),
        }