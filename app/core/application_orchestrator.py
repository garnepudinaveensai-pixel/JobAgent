from typing import Any, Callable, Dict, Optional


class ApplicationOrchestrator:
    """
    Coordinates the complete job-application workflow.

    Responsibilities:
    - Prepare an application
    - Fill application fields
    - Upload the selected resume
    - Validate the application
    - Stop for user confirmation
    - Submit only after explicit confirmation
    - Record application status
    - Optionally send a notification

    This class coordinates existing components. It does not
    implement browser automation itself.
    """

    def __init__(
        self,
        submitter,
        application_tracker=None,
        job_store=None,
        notifier=None,
    ):
        self.submitter = submitter
        self.application_tracker = application_tracker
        self.job_store = job_store
        self.notifier = notifier

        self.current_job: Optional[Dict[str, Any]] = None
        self.current_job_id: Optional[str] = None
        self.current_resume_path: Optional[str] = None

        self._prepared = False
        self._submitted = False

    # ========================================================
    # JOB
    # ========================================================

    def set_job(
        self,
        job: Dict[str, Any],
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Set the job currently being applied to.
        """

        if not isinstance(job, dict):
            raise TypeError("job must be a dictionary.")

        self.current_job = dict(job)

        self.current_job_id = (
            job_id
            or job.get("job_id")
            or job.get("url")
        )

        if not self.current_job_id:
            raise ValueError(
                "Job must contain job_id or url."
            )

        return {
            "success": True,
            "job_id": self.current_job_id,
        }

    # ========================================================
    # PREPARE
    # ========================================================

    def prepare_application(
        self,
        resume_path: str,
        fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Prepare an application without submitting it.

        The workflow:
            fill fields
            upload resume
            validate
            stop before submission
        """

        if self.current_job is None:
            raise RuntimeError(
                "No job selected. Call set_job() first."
            )

        if not isinstance(fields, dict):
            raise TypeError(
                "fields must be a dictionary."
            )

        self.current_resume_path = resume_path

        result = self.submitter.prepare_application(
            resume_path=resume_path,
            fields=fields,
        )

        validation = result.get(
            "validation",
            {},
        )

        ready = bool(
            validation.get("ready", False)
        )

        self._prepared = ready
        self._submitted = False

        status = (
            "ready_for_submission"
            if ready
            else "validation_failed"
        )

        self._record_status(
            "application_started"
        )

        return {
            "success": ready,
            "status": status,
            "job_id": self.current_job_id,
            "filled_fields": result.get(
                "filled_fields",
                [],
            ),
            "resume_uploaded": result.get(
                "resume_uploaded",
                False,
            ),
            "validation": validation,
        }

    # ========================================================
    # CONFIRMATION
    # ========================================================

    def requires_confirmation(self) -> bool:
        """
        Return True when the application is prepared and
        waiting for user confirmation.
        """

        return self._prepared and not self._submitted

    # ========================================================
    # SUBMIT
    # ========================================================

    def submit_application(
        self,
        confirm: bool = False,
    ) -> Dict[str, Any]:
        """
        Submit the prepared application.

        Submission is blocked unless:
        - preparation succeeded
        - validation succeeded
        - confirm=True
        """

        if self.current_job is None:
            raise RuntimeError(
                "No job selected."
            )

        if not self._prepared:
            return {
                "success": False,
                "status": "not_ready",
                "job_id": self.current_job_id,
            }

        if not confirm:
            return {
                "success": False,
                "status": "confirmation_required",
                "job_id": self.current_job_id,
            }

        result = self.submitter.submit(
            confirm=True
        )

        success = bool(
            result.get("success", False)
        )

        if success:
            self._submitted = True

            self._record_status("applied")

            self._notify(
                event="application_submitted",
                data={
                    "job": self.current_job,
                    "job_id": self.current_job_id,
                    "status": "applied",
                },
            )

        else:
            self._record_status(
                "application_failed"
            )

        return {
            **result,
            "job_id": self.current_job_id,
        }

    # ========================================================
    # COMPLETE WORKFLOW
    # ========================================================

    def run(
        self,
        job: Dict[str, Any],
        resume_path: str,
        fields: Dict[str, Any],
        confirm: bool = False,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the complete preparation/submission workflow.

        By default, the application stops before submission.

        Set confirm=True only when the application should
        actually be submitted.
        """

        self.set_job(
            job=job,
            job_id=job_id,
        )

        preparation = self.prepare_application(
            resume_path=resume_path,
            fields=fields,
        )

        if not preparation["success"]:
            return preparation

        if not confirm:
            return {
                **preparation,
                "status": "confirmation_required",
                "submitted": False,
            }

        submission = self.submit_application(
            confirm=True
        )

        return {
            **preparation,
            **submission,
            "submitted": bool(
                submission.get("success", False)
            ),
        }

    # ========================================================
    # STATUS
    # ========================================================

    def get_state(self) -> Dict[str, Any]:
        """
        Return the current orchestration state.
        """

        if self._submitted:
            status = "submitted"
        elif self._prepared:
            status = "ready_for_submission"
        else:
            status = "not_prepared"

        return {
            "job_id": self.current_job_id,
            "prepared": self._prepared,
            "submitted": self._submitted,
            "requires_confirmation": (
                self.requires_confirmation()
            ),
            "status": status,
        }

    # ========================================================
    # INTERNAL STATUS RECORDING
    # ========================================================

    def _record_status(
        self,
        status: str,
    ) -> None:
        """
        Record status using the available JobStore.
        """

        if (
            self.job_store is None
            or self.current_job_id is None
        ):
            return

        try:
            updated = self.job_store.update_status(
                self.current_job_id,
                status,
            )

            if not updated:
                return

        except (
            ValueError,
            AttributeError,
        ):
            return

    # ========================================================
    # INTERNAL NOTIFICATION
    # ========================================================

    def _notify(
        self,
        event: str,
        data: Dict[str, Any],
    ) -> None:
        """
        Send a notification when a notifier is configured.

        Supports notifiers exposing either:
            notify(event, data)
        or:
            send(subject, message)
        """

        if self.notifier is None:
            return

        try:
            notify_method = getattr(
                self.notifier,
                "notify",
                None,
            )

            if callable(notify_method):
                notify_method(
                    event,
                    data,
                )
                return

            send_method = getattr(
                self.notifier,
                "send",
                None,
            )

            if callable(send_method):
                job = data.get(
                    "job",
                    {},
                )

                company = job.get(
                    "company",
                    "",
                )

                title = job.get(
                    "title",
                    "",
                )

                send_method(
                    subject=(
                        f"JobAgent: Application submitted"
                    ),
                    message=(
                        f"Application submitted for "
                        f"{title} at {company}."
                    ),
                )

        except Exception:
            # Notification failure must never make an
            # already-submitted application look failed.
            return