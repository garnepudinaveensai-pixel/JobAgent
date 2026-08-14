from pathlib import Path
from typing import Callable, Dict, Optional

from app.browser.application_submitter import ApplicationSubmitter
from app.core.application_orchestrator import ApplicationOrchestrator
from app.resume.resume_pdf_generator import generate_resume_pdf
from app.resume.resume_tailor import tailor_resume


class ApplicationWorkflow:
    """
    High-level workflow connecting:

    Job
        ↓
    Resume tailoring
        ↓
    Tailored PDF generation
        ↓
    Application preparation
        ↓
    Application submission

    This class coordinates the existing components.

    It does NOT:
    - discover jobs
    - decide whether a candidate matches a job
    - invent resume information
    - directly manipulate website-specific selectors
    """

    def __init__(
        self,
        orchestrator: Optional[ApplicationOrchestrator] = None,
        submitter_factory: Optional[
            Callable
        ] = None,
    ):
        self.orchestrator = orchestrator
        self.submitter_factory = (
            submitter_factory
            or ApplicationSubmitter
        )

    # ========================================================
    # RESUME
    # ========================================================

    @staticmethod
    def tailor_and_generate_resume(
        resume: Dict,
        job: Dict,
        output_path: str,
    ) -> Dict:
        """
        Tailor a resume for a job and generate its PDF.

        Returns metadata describing the generated resume.
        """

        tailored_resume = tailor_resume(
            resume,
            job,
        )

        output = Path(output_path)

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        pdf_path = generate_resume_pdf(
            tailored_resume,
            str(output),
        )

        return {
            "resume": tailored_resume,
            "pdf_path": str(pdf_path),
        }

    # ========================================================
    # PREPARE APPLICATION
    # ========================================================

    def prepare_application(
        self,
        page,
        resume: Dict,
        job: Dict,
        fields: Dict[str, str],
        resume_output_path: str,
    ) -> Dict:
        """
        Prepare an application without submitting it.

        Steps:

        1. Tailor resume.
        2. Generate tailored PDF.
        3. Open application page.
        4. Fill known application fields.
        5. Upload tailored resume.
        6. Validate the form.

        Submission remains a separate explicit operation.
        """

        job_url = str(
            job.get("url", "")
        ).strip()

        if not job_url:
            raise ValueError(
                "Job must contain a URL."
            )

        resume_result = (
            self.tailor_and_generate_resume(
                resume=resume,
                job=job,
                output_path=resume_output_path,
            )
        )

        submitter = self.submitter_factory(
            page
        )

        submitter.open(
            job_url
        )

        prepared = (
            submitter.prepare_application(
                resume_path=resume_result[
                    "pdf_path"
                ],
                fields=fields,
            )
        )

        return {
            "job": job,
            "tailored_resume": resume_result[
                "resume"
            ],
            "resume_pdf": resume_result[
                "pdf_path"
            ],
            "filled_fields": prepared.get(
                "filled_fields",
                [],
            ),
            "resume_uploaded": prepared.get(
                "resume_uploaded",
                False,
            ),
            "validation": prepared.get(
                "validation",
                {},
            ),
            "status": prepared.get(
                "status",
                "unknown",
            ),
            "success": prepared.get(
                "success",
                False,
            ),
            "submitter": submitter,
        }

    # ========================================================
    # SUBMIT
    # ========================================================

    @staticmethod
    def submit(
        prepared_application: Dict,
        confirm: bool = False,
    ) -> Dict:
        """
        Submit a prepared application.

        Submission requires explicit confirmation.

        This prevents accidental applications while testing
        or preparing applications.
        """

        submitter = prepared_application.get(
            "submitter"
        )

        if submitter is None:
            return {
                "success": False,
                "status": "not_prepared",
            }

        if not prepared_application.get(
            "validation",
            {},
        ).get(
            "ready",
            False,
        ):
            return {
                "success": False,
                "status": "validation_failed",
            }

        return submitter.submit(
            confirm=confirm
        )