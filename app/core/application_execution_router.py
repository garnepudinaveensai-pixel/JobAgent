from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional

from app.core.application_decision_engine import (
    APPLY,
    OUTREACH,
    REVIEW,
    SKIP,
    ApplicationDecision,
    ApplicationDecisionEngine,
)


# ============================================================
# EXECUTION RESULT
# ============================================================


@dataclass(frozen=True)
class ExecutionResult:
    """
    Result produced by the execution router.

    The router coordinates existing workflows. It does not
    implement application submission or email sending itself.
    """

    success: bool
    decision: str
    status: str
    message: str = ""

    job: dict[str, Any] = field(
        default_factory=dict
    )

    ranking_score: float = 0.0

    prepared: bool = False
    executed: bool = False
    submitted: bool = False
    sent: bool = False

    confirmation_required: bool = False

    result: Optional[dict[str, Any]] = None

    error: Optional[str] = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    requires_human_action: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "decision": self.decision,
            "status": self.status,
            "message": self.message,
            "job": dict(self.job),
            "ranking_score": self.ranking_score,
            "prepared": self.prepared,
            "executed": self.executed,
            "submitted": self.submitted,
            "sent": self.sent,
            "confirmation_required": (
                self.confirmation_required
            ),
            "result": (
                dict(self.result)
                if isinstance(
                    self.result,
                    dict,
                )
                else self.result
            ),
            "error": self.error,
            "metadata": dict(self.metadata),
            "requires_human_action": (
                self.requires_human_action
            ),
        }


# ============================================================
# EXECUTION ROUTER
# ============================================================


class ApplicationExecutionRouter:
    """
    Central router connecting application decisions to execution.

    Flow:

        ranked result
             ↓
        decision engine
             ↓
        ┌─────┼──────────────┐
        ↓     ↓              ↓
       APPLY OUTREACH       REVIEW
        ↓     ↓              ↓
     Apply  Recruiter      Review
     Flow   Flow            Queue
        │     │
        └──┬──┘
           ↓
       Confirmation
           ↓
        Execution

    SKIP results are ignored.

    Safety:
        - Preparation and execution are separate.
        - Real application submission requires confirm=True.
        - Real email sending requires confirm=True.
        - dry_run can be used for safe integration testing.
    """

    def __init__(
        self,
        decision_engine: Optional[
            ApplicationDecisionEngine
        ] = None,
        application_pipeline: Any = None,
        outreach_pipeline: Any = None,
        review_handler: Any = None,
    ):
        self.decision_engine = (
            decision_engine
            if decision_engine is not None
            else ApplicationDecisionEngine()
        )

        self.application_pipeline = (
            application_pipeline
        )

        self.outreach_pipeline = (
            outreach_pipeline
        )

        self.review_handler = (
            review_handler
        )

    # ========================================================
    # SINGLE JOB
    # ========================================================

    def route(
        self,
        ranked_result: Mapping[str, Any],
        *,
        decision: Optional[ApplicationDecision] = None,
        page: Any = None,
        fields: Optional[dict[str, Any]] = None,
        contacts: Optional[
            Iterable[dict]
        ] = None,
        resume: Optional[dict] = None,
        resume_path: Optional[str] = None,
        resume_output_path: Optional[str] = None,
        confirm: bool = False,
        dry_run: bool = False,
        also_outreach: bool = False,
    ) -> ExecutionResult:
        """
        Decide and route one ranked job.

        No real submission or email sending happens unless
        confirm=True.

        dry_run=True prevents real execution even when
        confirm=True.
        """

        if not isinstance(
            ranked_result,
            Mapping,
        ):
            raise TypeError(
                "ranked_result must be a mapping."
            )

        if decision is None:
            decision = self.decision_engine.decide(
                ranked_result
            )
        elif not isinstance(
            decision,
            ApplicationDecision,
        ):
            raise TypeError(
                "decision must be an ApplicationDecision or None."
            )

        job = self._extract_job(
            ranked_result
        )

        ranking_score = self._extract_score(
            ranked_result
        )

        # Normalize decision values at the router boundary.
        #
        # ApplicationDecisionEngine uses canonical uppercase
        # constants (APPLY/OUTREACH/REVIEW/SKIP), while
        # lightweight integrations and test doubles may return
        # equivalent lowercase values. Treat decision values
        # case-insensitively without weakening the explicit
        # decision validation above.
        decision_value = str(
            getattr(decision, "decision", "")
        ).strip().upper()

        if decision_value == APPLY:
            return self._route_apply(
                ranked_result=ranked_result,
                decision=decision,
                job=job,
                ranking_score=ranking_score,
                page=page,
                fields=fields or {},
                contacts=contacts or [],
                resume=resume,
                resume_path=resume_path,
                resume_output_path=(
                    resume_output_path
                ),
                confirm=confirm,
                dry_run=dry_run,
                also_outreach=also_outreach,
            )

        if decision_value == OUTREACH:
            return self._route_outreach(
                ranked_result=ranked_result,
                decision=decision,
                job=job,
                ranking_score=ranking_score,
                contacts=contacts or [],
                resume=resume,
                resume_path=resume_path,
                confirm=confirm,
                dry_run=dry_run,
            )

        if decision_value == REVIEW:
            return self._route_review(
                ranked_result=ranked_result,
                decision=decision,
                job=job,
                ranking_score=ranking_score,
            )

        return self._route_skip(
            ranked_result=ranked_result,
            decision=decision,
            job=job,
            ranking_score=ranking_score,
        )

    # ========================================================
    # BATCH
    # ========================================================

    def route_many(
        self,
        ranked_results: list[
            Mapping[str, Any]
        ],
        **kwargs: Any,
    ) -> list[ExecutionResult]:
        """
        Route multiple ranked jobs.

        Input must be a list.
        """

        if not isinstance(
            ranked_results,
            list,
        ):
            raise TypeError(
                "ranked_results must be a list."
            )

        return [
            self.route(
                result,
                **kwargs,
            )
            for result in ranked_results
        ]

    # ========================================================
    # APPLY
    # ========================================================

    def _route_apply(
        self,
        *,
        ranked_result: Mapping[str, Any],
        decision: ApplicationDecision,
        job: dict[str, Any],
        ranking_score: float,
        page: Any,
        fields: dict[str, Any],
        contacts: Iterable[dict],
        resume: Optional[dict],
        resume_path: Optional[str],
        resume_output_path: Optional[str],
        confirm: bool,
        dry_run: bool,
        also_outreach: bool = False,
    ) -> ExecutionResult:

        if self.application_pipeline is None:
            return ExecutionResult(
                success=False,
                decision=APPLY,
                status="application_pipeline_missing",
                message=(
                    "No application pipeline is configured."
                ),
                job=job,
                ranking_score=ranking_score,
                error=(
                    "application_pipeline is not configured."
                ),
            )

        # ----------------------------------------------------
        # PREPARATION
        # ----------------------------------------------------

        try:
            prepared = (
                self._prepare_application(
                    ranked_result=ranked_result,
                    page=page,
                    fields=fields,
                    resume=resume,
                    resume_output_path=(
                        resume_output_path
                    ),
                )
            )

        except Exception as exc:
            return ExecutionResult(
                success=False,
                decision=APPLY,
                status="application_prepare_failed",
                message=(
                    "Application preparation failed."
                ),
                job=job,
                ranking_score=ranking_score,
                error=str(exc),
            )

        if not isinstance(
            prepared,
            Mapping,
        ):
            return ExecutionResult(
                success=False,
                decision=APPLY,
                status="invalid_application_result",
                message=(
                    "Application pipeline returned "
                    "an invalid preparation result."
                ),
                job=job,
                ranking_score=ranking_score,
                error=(
                    "Application preparation result "
                    "must be a mapping."
                ),
            )

        if not prepared.get(
            "success",
            False,
        ):
            preparation_status = str(
                prepared.get(
                    "status",
                    "application_prepare_failed",
                )
                or "application_prepare_failed"
            )

            # Preserve safety-critical browser states so they can
            # propagate to the caller unchanged. Generic preparation
            # failures retain the router's historical public status.
            safety_statuses = {
                "captcha_detected",
                "login_required",
                "human_action_required",
                "job_unavailable",
                "form_not_found",
                "navigation_failed",
                "submission_timeout",
                "submission_failed",
            }

            if preparation_status not in safety_statuses:
                preparation_status = (
                    "application_prepare_failed"
                )

            requires_human_action = bool(
                prepared.get(
                    "requires_human_action",
                    False,
                )
            )

            if preparation_status in {
                "captcha_detected",
                "login_required",
                "human_action_required",
            }:
                requires_human_action = True

            return ExecutionResult(
                success=False,
                decision=APPLY,
                status=preparation_status,
                message=str(
                    prepared.get(
                        "message",
                        "Application could not be prepared.",
                    )
                ),
                job=job,
                ranking_score=ranking_score,
                prepared=True,
                result=dict(prepared),
                error=(
                    str(
                        prepared.get("error")
                    )
                    if prepared.get("error")
                    else None
                ),
                requires_human_action=(
                    requires_human_action
                ),
            )

        # ----------------------------------------------------
        # DRY RUN
        # ----------------------------------------------------

        if dry_run:
            metadata = {
                "dry_run": True,
            }

            if also_outreach:
                try:
                    outreach_prepared = self._prepare_outreach(
                        contacts=contacts or [],
                        job=job,
                        resume=resume,
                        resume_path=resume_path,
                    )
                    metadata["outreach_prepared"] = (
                        dict(outreach_prepared)
                        if isinstance(outreach_prepared, Mapping)
                        else outreach_prepared
                    )
                    metadata["outreach_status"] = (
                        "dry_run_ready"
                        if isinstance(outreach_prepared, Mapping)
                        and outreach_prepared.get("success", False)
                        else "outreach_prepare_failed"
                    )
                except Exception as exc:
                    metadata["outreach_status"] = "outreach_failed"
                    metadata["outreach_error"] = str(exc)

            return ExecutionResult(
                success=True,
                decision=APPLY,
                status="dry_run_ready",
                message=(
                    "Application prepared successfully. "
                    "Dry-run prevented submission."
                ),
                job=job,
                ranking_score=ranking_score,
                prepared=True,
                executed=False,
                submitted=False,
                confirmation_required=False,
                result=dict(prepared),
                metadata=metadata,
            )

        # ----------------------------------------------------
        # CONFIRMATION
        # ----------------------------------------------------

        if not confirm:
            return ExecutionResult(
                success=True,
                decision=APPLY,
                status="confirmation_required",
                message=(
                    "Application is prepared and "
                    "requires explicit confirmation."
                ),
                job=job,
                ranking_score=ranking_score,
                prepared=True,
                executed=False,
                submitted=False,
                confirmation_required=True,
                result=dict(prepared),
            )

        # ----------------------------------------------------
        # SUBMISSION
        # ----------------------------------------------------

        try:
            submitted = (
                self._submit_application(
                    prepared,
                    confirm=True,
                )
            )

        except Exception as exc:
            return ExecutionResult(
                success=False,
                decision=APPLY,
                status="application_submit_failed",
                message=(
                    "Application submission failed."
                ),
                job=job,
                ranking_score=ranking_score,
                prepared=True,
                executed=False,
                submitted=False,
                result=dict(prepared),
                error=str(exc),
            )

        if not isinstance(
            submitted,
            Mapping,
        ):
            return ExecutionResult(
                success=False,
                decision=APPLY,
                status="invalid_submission_result",
                message=(
                    "Application pipeline returned "
                    "an invalid submission result."
                ),
                job=job,
                ranking_score=ranking_score,
                prepared=True,
                executed=False,
                submitted=False,
                result=dict(prepared),
                error=(
                    "Submission result must be a mapping."
                ),
            )

        success = bool(
            submitted.get(
                "success",
                False,
            )
        )

        submission_status = str(
            submitted.get(
                "status",
                "applied"
                if success
                else "application_submit_failed",
            )
        )

        requires_human_action = bool(
            submitted.get(
                "requires_human_action",
                submission_status
                in {
                    "captcha_detected",
                    "login_required",
                    "human_action_required",
                },
            )
        )

        submitted_flag = bool(
            submitted.get(
                "submitted",
                success,
            )
        )

        metadata = {
            "application_result": dict(submitted),
        }

        if success and also_outreach:
            try:
                outreach_prepared = self._prepare_outreach(
                    contacts=contacts or [],
                    job=job,
                    resume=resume,
                    resume_path=(
                        str(
                            prepared.get("resume_pdf")
                            or resume_path
                            or ""
                        ).strip()
                        or None
                    ),
                )
                metadata["outreach_prepared"] = (
                    dict(outreach_prepared)
                    if isinstance(outreach_prepared, Mapping)
                    else outreach_prepared
                )

                if (
                    isinstance(outreach_prepared, Mapping)
                    and outreach_prepared.get("success", False)
                ):
                    if dry_run:
                        metadata["outreach_status"] = "dry_run_ready"
                    elif not confirm:
                        metadata["outreach_status"] = "confirmation_required"
                    else:
                        sent = self._send_outreach(
                            contacts=contacts or [],
                            job=job,
                            resume=resume,
                            resume_path=(
                                str(
                                    prepared.get("resume_pdf")
                                    or resume_path
                                    or ""
                                ).strip()
                                or None
                            ),
                            confirm=True,
                        )
                        metadata["outreach_result"] = (
                            dict(sent)
                            if isinstance(sent, Mapping)
                            else sent
                        )
                        if isinstance(sent, Mapping):
                            metadata["outreach_status"] = str(
                                sent.get(
                                    "status",
                                    "sent"
                                    if sent.get("success", False)
                                    else "outreach_send_failed",
                                )
                            )
                            metadata["outreach_sent"] = bool(
                                sent.get(
                                    "sent",
                                    sent.get("success", False),
                                )
                            )
                        else:
                            metadata["outreach_status"] = "outreach_send_failed"
                            metadata["outreach_sent"] = False
                else:
                    metadata["outreach_status"] = "outreach_prepare_failed"
            except Exception as exc:
                metadata["outreach_status"] = "outreach_failed"
                metadata["outreach_error"] = str(exc)

        return ExecutionResult(
            success=success,
            decision=APPLY,
            status=submission_status,
            message=(
                "Application submitted successfully."
                if success
                else "Application submission failed."
            ),
            job=job,
            ranking_score=ranking_score,
            prepared=True,
            executed=success,
            submitted=submitted_flag,
            sent=bool(metadata.get("outreach_sent", False)),
            confirmation_required=False,
            result=dict(submitted),
            error=(
                str(submitted.get("error"))
                if submitted.get("error")
                else None
            ),
            metadata=metadata,
            requires_human_action=requires_human_action,
        )

    # ========================================================
    # OUTREACH
    # ========================================================

    def _route_outreach(
        self,
        *,
        ranked_result: Mapping[str, Any],
        decision: ApplicationDecision,
        job: dict[str, Any],
        ranking_score: float,
        contacts: Iterable[dict],
        resume: Optional[dict],
        resume_path: Optional[str],
        confirm: bool,
        dry_run: bool,
    ) -> ExecutionResult:

        if self.outreach_pipeline is None:
            return ExecutionResult(
                success=False,
                decision=OUTREACH,
                status="outreach_pipeline_missing",
                message=(
                    "No outreach pipeline is configured."
                ),
                job=job,
                ranking_score=ranking_score,
                error=(
                    "outreach_pipeline is not configured."
                ),
            )

        try:
            prepared = (
                self._prepare_outreach(
                    contacts=contacts,
                    job=job,
                    resume=resume,
                    resume_path=resume_path,
                )
            )

        except Exception as exc:
            return ExecutionResult(
                success=False,
                decision=OUTREACH,
                status="outreach_prepare_failed",
                message=(
                    "Outreach preparation failed."
                ),
                job=job,
                ranking_score=ranking_score,
                error=str(exc),
            )

        if not isinstance(
            prepared,
            Mapping,
        ):
            return ExecutionResult(
                success=False,
                decision=OUTREACH,
                status="invalid_outreach_result",
                message=(
                    "Outreach pipeline returned "
                    "an invalid preparation result."
                ),
                job=job,
                ranking_score=ranking_score,
                error=(
                    "Outreach preparation result "
                    "must be a mapping."
                ),
            )

        if not prepared.get(
            "success",
            False,
        ):
            return ExecutionResult(
                success=False,
                decision=OUTREACH,
                status="outreach_prepare_failed",
                message=(
                    "Outreach could not be prepared."
                ),
                job=job,
                ranking_score=ranking_score,
                prepared=True,
                result=dict(prepared),
                error=str(
                    prepared.get(
                        "error",
                        "Outreach preparation failed.",
                    )
                ),
            )

        # ----------------------------------------------------
        # DRY RUN
        # ----------------------------------------------------

        if dry_run:
            return ExecutionResult(
                success=True,
                decision=OUTREACH,
                status="dry_run_ready",
                message=(
                    "Outreach prepared successfully. "
                    "Dry-run prevented sending."
                ),
                job=job,
                ranking_score=ranking_score,
                prepared=True,
                result=dict(prepared),
                metadata={
                    "dry_run": True,
                },
            )

        # ----------------------------------------------------
        # CONFIRMATION
        # ----------------------------------------------------

        if not confirm:
            return ExecutionResult(
                success=True,
                decision=OUTREACH,
                status="confirmation_required",
                message=(
                    "Outreach is prepared and "
                    "requires explicit confirmation."
                ),
                job=job,
                ranking_score=ranking_score,
                prepared=True,
                confirmation_required=True,
                result=dict(prepared),
            )

        # ----------------------------------------------------
        # SEND
        # ----------------------------------------------------

        try:
            sent = self._send_outreach(
                contacts=contacts,
                job=job,
                resume=resume,
                resume_path=resume_path,
                confirm=True,
            )

        except Exception as exc:
            return ExecutionResult(
                success=False,
                decision=OUTREACH,
                status="outreach_send_failed",
                message=(
                    "Outreach sending failed."
                ),
                job=job,
                ranking_score=ranking_score,
                prepared=True,
                result=dict(prepared),
                error=str(exc),
            )

        if not isinstance(
            sent,
            Mapping,
        ):
            return ExecutionResult(
                success=False,
                decision=OUTREACH,
                status="invalid_outreach_send_result",
                message=(
                    "Outreach pipeline returned "
                    "an invalid send result."
                ),
                job=job,
                ranking_score=ranking_score,
                prepared=True,
                result=dict(prepared),
                error=(
                    "Outreach send result "
                    "must be a mapping."
                ),
            )

        success = bool(
            sent.get(
                "success",
                False,
            )
        )

        return ExecutionResult(
            success=success,
            decision=OUTREACH,
            status=str(
                sent.get(
                    "status",
                    "sent"
                    if success
                    else "outreach_send_failed",
                )
            ),
            message=(
                "Outreach sent successfully."
                if success
                else "Outreach sending failed."
            ),
            job=job,
            ranking_score=ranking_score,
            prepared=True,
            executed=success,
            sent=bool(
                sent.get(
                    "sent",
                    success,
                )
            ),
            result=dict(sent),
            error=(
                str(
                    sent.get("error")
                )
                if sent.get("error")
                else None
            ),
        )

    # ========================================================
    # REVIEW
    # ========================================================

    def _route_review(
        self,
        *,
        ranked_result: Mapping[str, Any],
        decision: ApplicationDecision,
        job: dict[str, Any],
        ranking_score: float,
    ) -> ExecutionResult:

        review_result = None

        if self.review_handler is not None:
            try:
                if hasattr(
                    self.review_handler,
                    "add",
                ):
                    review_result = (
                        self.review_handler.add(
                            ranked_result
                        )
                    )

                elif callable(
                    self.review_handler
                ):
                    review_result = (
                        self.review_handler(
                            ranked_result
                        )
                    )

            except Exception as exc:
                return ExecutionResult(
                    success=False,
                    decision=REVIEW,
                    status="review_handler_failed",
                    message=(
                        "Review handler failed."
                    ),
                    job=job,
                    ranking_score=ranking_score,
                    error=str(exc),
                )

        return ExecutionResult(
            success=True,
            decision=REVIEW,
            status="manual_review",
            message=(
                "Job requires manual review."
            ),
            job=job,
            ranking_score=ranking_score,
            prepared=False,
            executed=False,
            result=(
                dict(review_result)
                if isinstance(
                    review_result,
                    Mapping,
                )
                else review_result
            ),
        )

    # ========================================================
    # SKIP
    # ========================================================

    @staticmethod
    def _route_skip(
        *,
        ranked_result: Mapping[str, Any],
        decision: ApplicationDecision,
        job: dict[str, Any],
        ranking_score: float,
    ) -> ExecutionResult:

        return ExecutionResult(
            success=True,
            decision=SKIP,
            status="skipped",
            message=(
                "Job was below the action threshold "
                "and has been skipped."
            ),
            job=job,
            ranking_score=ranking_score,
            prepared=False,
            executed=False,
        )

    # ========================================================
    # APPLICATION ADAPTERS
    # ========================================================

    def _prepare_application(
        self,
        *,
        ranked_result: Mapping[str, Any],
        page: Any,
        fields: dict[str, Any],
        resume: Optional[dict],
        resume_output_path: Optional[str],
    ) -> Any:
        pipeline = self.application_pipeline

        if hasattr(
            pipeline,
            "prepare_application_for_job",
        ):
            return pipeline.prepare_application_for_job(
                ranked_result,
                page=page,
                fields=fields,
                resume=resume,
                resume_output_path=(
                    resume_output_path
                ),
            )

        if hasattr(
            pipeline,
            "prepare_application",
        ):
            return pipeline.prepare_application(
                ranked_result,
                page=page,
                fields=fields,
                resume=resume,
                resume_output_path=(
                    resume_output_path
                ),
            )

        raise TypeError(
            "Unsupported application pipeline. "
            "Expected prepare_application_for_job() "
            "or prepare_application()."
        )

    @staticmethod
    def _submit_application(
        prepared: Mapping[str, Any],
        *,
        confirm: bool,
    ) -> Any:

        submitter = prepared.get(
            "submitter"
        )

        if submitter is not None and hasattr(
            submitter,
            "submit",
        ):
            return submitter.submit(
                confirm=confirm
            )

        pipeline_result = prepared.get(
            "pipeline"
        )

        if pipeline_result is not None and hasattr(
            pipeline_result,
            "submit_application",
        ):
            return pipeline_result.submit_application(
                prepared,
                confirm=confirm,
            )

        if prepared.get(
            "submitted"
        ):
            return {
                "success": True,
                "status": "applied",
                "submitted": True,
            }

        raise TypeError(
            "Prepared application does not expose "
            "a supported submission method."
        )

    # ========================================================
    # OUTREACH ADAPTERS
    # ========================================================

    def _prepare_outreach(
        self,
        *,
        contacts: Iterable[dict],
        job: dict[str, Any],
        resume: Optional[dict],
        resume_path: Optional[str] = None,
    ) -> Any:

        pipeline = self.outreach_pipeline

        if hasattr(
            pipeline,
            "prepare_outreach",
        ):
            return pipeline.prepare_outreach(
                contacts=contacts,
                job=job,
                resume=resume,
                resume_path=resume_path,
            )

        if hasattr(
            pipeline,
            "compose_outreach",
        ):
            return pipeline.compose_outreach(
                contacts=contacts,
                job=job,
                candidate=resume,
            )

        raise TypeError(
            "Unsupported outreach pipeline. "
            "Expected prepare_outreach() "
            "or compose_outreach()."
        )

    def _send_outreach(
        self,
        *,
        contacts: Iterable[dict],
        job: dict[str, Any],
        resume: Optional[dict],
        resume_path: Optional[str] = None,
        confirm: bool,
    ) -> Any:

        pipeline = self.outreach_pipeline

        if hasattr(
            pipeline,
            "send_outreach",
        ):
            return pipeline.send_outreach(
                contacts=contacts,
                job=job,
                resume=resume,
                resume_path=resume_path,
                confirm=confirm,
            )

        if hasattr(
            pipeline,
            "send",
        ):
            return pipeline.send(
                contacts=contacts,
                job=job,
                resume=resume,
                confirm=confirm,
            )

        raise TypeError(
            "Unsupported outreach pipeline. "
            "Expected send_outreach() "
            "or send()."
        )

    # ========================================================
    # EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_job(
        ranked_result: Mapping[str, Any],
    ) -> dict[str, Any]:

        job = ranked_result.get(
            "job"
        )

        if isinstance(
            job,
            Mapping,
        ):
            return dict(job)

        return {}

    @staticmethod
    def _extract_score(
        ranked_result: Mapping[str, Any],
    ) -> float:

        try:
            return float(
                ranked_result.get(
                    "ranking_score",
                    0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0.0


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================


def execute_ranked_job(
    ranked_result: Mapping[str, Any],
    *,
    decision_engine: Optional[
        ApplicationDecisionEngine
    ] = None,
    application_pipeline: Any = None,
    outreach_pipeline: Any = None,
    review_handler: Any = None,
    **kwargs: Any,
) -> ExecutionResult:
    """
    Convenience function for routing one ranked job.
    """

    router = ApplicationExecutionRouter(
        decision_engine=decision_engine,
        application_pipeline=application_pipeline,
        outreach_pipeline=outreach_pipeline,
        review_handler=review_handler,
    )

    return router.route(
        ranked_result,
        **kwargs,
    )


__all__ = [
    "ExecutionResult",
    "ApplicationExecutionRouter",
    "execute_ranked_job",
]