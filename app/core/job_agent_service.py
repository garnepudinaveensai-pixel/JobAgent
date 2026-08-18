from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from app.core.agent_runner import AgentRunner
from app.core.application_history import ApplicationHistory
from app.core.application_lifecycle import (
    ApplicationLifecycle,
)
from app.core.application_decision_engine import (
    ApplicationDecisionEngine,
)
from app.core.application_execution_router import (
    ApplicationExecutionRouter,
    ExecutionResult,
)
from app.core.end_to_end_pipeline import (
    EndToEndPipeline,
)
from app.outreach.outreach_pipeline import (
    OutreachPipeline,
)


# ============================================================
# SERVICE RESULT
# ============================================================


@dataclass(frozen=True)
class JobAgentRunResult:
    """
    Result of one complete JobAgent run.
    """

    success: bool
    status: str

    keywords: str
    location: Optional[str]

    discovered_count: int = 0
    processed_count: int = 0

    apply_count: int = 0
    outreach_count: int = 0
    review_count: int = 0
    skip_count: int = 0

    executed_count: int = 0
    submitted_count: int = 0
    sent_count: int = 0

    jobs: list[dict[str, Any]] = field(
        default_factory=list
    )

    executions: list[dict[str, Any]] = field(
        default_factory=list
    )

    errors: list[dict[str, Any]] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    human_action_required_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================
# MASTER SERVICE
# ============================================================


class JobAgentService:
    """
    Master user-facing orchestration service.

    Responsibilities
    ----------------
    1. Discover jobs.
    2. Match and rank jobs.
    3. Run the application decision engine.
    4. Route decisions through ApplicationExecutionRouter.
    5. Prepare applications or recruiter outreach.
    6. Optionally execute confirmed actions.
    7. Continue processing when one job fails.
    8. Return one unified result.

    Safety
    ------
    - run() defaults to dry_run=True.
    - confirm defaults to False.
    - Actual submission/sending remains controlled by the
      lower-level execution router.
    """

    def __init__(
        self,
        runner: AgentRunner,
        *,
        end_to_end_pipeline: Optional[
            EndToEndPipeline
        ] = None,
        decision_engine: Optional[
            ApplicationDecisionEngine
        ] = None,
        execution_router: Optional[
            ApplicationExecutionRouter
        ] = None,
        outreach_pipeline: Optional[
            OutreachPipeline
        ] = None,
        application_history: Optional[ApplicationHistory] = None,
        application_lifecycle: Optional[
            ApplicationLifecycle
        ] = None,
    ) -> None:

        if runner is None:
            raise ValueError(
                "runner cannot be None."
            )

        self.runner = runner
        self.application_history = application_history
        self.application_lifecycle = (
            application_lifecycle
        )

        # ----------------------------------------------------
        # Existing high-level pipeline
        # ----------------------------------------------------

        self.end_to_end_pipeline = (
            end_to_end_pipeline
            if end_to_end_pipeline is not None
            else EndToEndPipeline(
                runner=runner
            )
        )

        # ----------------------------------------------------
        # Decision engine
        # ----------------------------------------------------

        self.decision_engine = (
            decision_engine
            if decision_engine is not None
            else ApplicationDecisionEngine()
        )

        # ----------------------------------------------------
        # Outreach pipeline
        # ----------------------------------------------------

        self.outreach_pipeline = (
            outreach_pipeline
            if outreach_pipeline is not None
            else getattr(
                self.end_to_end_pipeline,
                "outreach_pipeline",
                None,
            )
        )

        # ----------------------------------------------------
        # Execution router
        # ----------------------------------------------------

        self.execution_router = (
            execution_router
            if execution_router is not None
            else self._build_execution_router()
        )

    # ========================================================
    # ROUTER
    # ========================================================

    def _build_execution_router(
        self,
    ) -> ApplicationExecutionRouter:
        """
        Build the execution router around the existing
        application and outreach components.
        """

        return ApplicationExecutionRouter(
            decision_engine=self.decision_engine,
            application_pipeline=(
                self.end_to_end_pipeline
            ),
            outreach_pipeline=(
                self.outreach_pipeline
            ),
        )

    # ========================================================
    # DISCOVERY
    # ========================================================

    def discover_and_rank(
        self,
        keywords: str,
        location: Optional[str] = None,
        *,
        min_score: float = 60.0,
        eligible_only: bool = False,
        limit: Optional[int] = 10,
        **source_options: Any,
    ) -> list[dict[str, Any]]:
        """
        Discover, match, deduplicate and rank jobs.
        """

        if not isinstance(
            keywords,
            str,
        ):
            raise TypeError(
                "keywords must be a string."
            )

        keywords = keywords.strip()

        if not keywords:
            raise ValueError(
                "keywords cannot be empty."
            )

        if limit is not None:
            if not isinstance(
                limit,
                int,
            ):
                raise TypeError(
                    "limit must be an integer or None."
                )

            if limit <= 0:
                raise ValueError(
                    "limit must be greater than zero."
                )

        return list(
            self.end_to_end_pipeline.discover_and_rank(
                keywords=keywords,
                location=location,
                min_score=min_score,
                eligible_only=eligible_only,
                limit=limit,
                **source_options,
            )
        )

    # ========================================================
    # CONTACT DISCOVERY
    # ========================================================

    def discover_contacts(
        self,
        job: Mapping[str, Any],
        **provider_options: Any,
    ) -> list[dict[str, Any]]:
        """
        Discover recruiter/HR contacts for one job.
        """

        if not isinstance(
            job,
            Mapping,
        ):
            raise TypeError(
                "job must be a mapping."
            )

        result = (
            self.end_to_end_pipeline.discover_contacts(
                dict(job),
                **provider_options,
            )
        )

        if result is None:
            return []

        return list(result)

    # ========================================================
    # DECISION
    # ========================================================

    def decide(
        self,
        ranked_result: Mapping[str, Any],
    ) -> Any:
        """
        Run the application decision engine exactly once
        for the requested operation.
        """

        if not isinstance(
            ranked_result,
            Mapping,
        ):
            raise TypeError(
                "ranked_result must be a mapping."
            )

        return self.decision_engine.decide(
            ranked_result
        )

    def decide_many(
        self,
        ranked_results: list[
            Mapping[str, Any]
        ],
    ) -> list[Any]:
        """
        Decide actions for multiple ranked jobs.
        """

        if not isinstance(
            ranked_results,
            list,
        ):
            raise TypeError(
                "ranked_results must be a list."
            )

        decisions = []

        for ranked_result in ranked_results:

            if not isinstance(
                ranked_result,
                Mapping,
            ):
                continue

            decisions.append(
                self.decide(
                    ranked_result
                )
            )

        return decisions

    # ========================================================
    # APPLICATION HISTORY
    # ========================================================

    @staticmethod
    def _history_job(
        ranked_result: Mapping[str, Any],
    ) -> Optional[dict[str, Any]]:
        job = ranked_result.get("job")
        if not isinstance(job, Mapping):
            return None
        return dict(job)

    def _history_blocking_record(
        self,
        ranked_result: Mapping[str, Any],
    ) -> Optional[Any]:
        """Return a history record that should prevent a duplicate action."""
        if self.application_history is None:
            return None

        job = self._history_job(ranked_result)
        if job is None:
            return None

        record = self.application_history.get(job)
        if record is None:
            return None

        # These states represent an action already taken or a state
        # requiring human intervention. Do not automatically repeat it.
        blocking_statuses = {
            "applied",
            "outreach_sent",
            "confirmation_required",
            "captcha_detected",
            "login_required",
            "human_action_required",
            "job_unavailable",
            "form_not_found",
            "navigation_failed",
        }

        return record if record.status in blocking_statuses else None

    def _record_execution_history(
        self,
        ranked_result: Mapping[str, Any],
        decision: Any,
        result: ExecutionResult,
    ) -> None:
        """Persist an execution outcome without changing its result."""
        if self.application_history is None:
            return

        job = self._history_job(ranked_result)
        if job is None:
            return

        decision_name = str(
            getattr(decision, "decision", "")
        ).strip().lower()
        status = str(result.status or "error").strip().lower()

        allowed = {
            "discovered", "review", "skipped", "prepared",
            "confirmation_required", "applied", "outreach_sent",
            "captcha_detected", "login_required", "human_action_required",
            "job_unavailable", "form_not_found", "navigation_failed",
            "validation_failed", "application_prepare_failed",
            "submission_timeout", "submission_failed", "send_failed", "error",
        }
        history_status = status if status in allowed else "error"

        self.application_history.update(
            job,
            decision=decision_name,
            status=history_status,
            human_action_required=bool(
                getattr(result, "requires_human_action", False)
            ),
            submitted=bool(getattr(result, "submitted", False)),
            sent=bool(getattr(result, "sent", False)),
            error=(
                str(result.error)
                if getattr(result, "error", None)
                else None
            ),
            metadata={
                "execution_status": result.status,
                "success": bool(result.success),
                "ranking_score": self._score(ranked_result),
            },
        )

    def _duplicate_result(
        self,
        ranked_result: Mapping[str, Any],
        record: Any,
    ) -> ExecutionResult:
        job = self._history_job(ranked_result) or {}
        return ExecutionResult(
            success=True,
            decision="skip",
            status="duplicate_prevented",
            message=(
                "Application action prevented because this job already "
                f"has history status '{record.status}'."
            ),
            job=job,
            ranking_score=self._score(ranked_result),
            metadata={
                "duplicate_prevented": True,
                "history_id": record.history_id,
                "history_status": record.status,
                "history_identity": record.identity,
                "human_action_required": record.human_action_required,
            },
            requires_human_action=bool(record.human_action_required),
        )

    # ========================================================
    # LIFECYCLE
    # ========================================================

    def _evaluate_lifecycle(
        self,
        ranked_result: Mapping[str, Any],
    ) -> Optional[Any]:
        """
        Evaluate application lifecycle before invoking the
        decision engine.

        Lifecycle handling is opt-in through the constructor so
        existing callers that do not provide a lifecycle object
        retain their previous behavior.
        """
        if self.application_lifecycle is None:
            return None

        job = ranked_result.get("job")

        if not isinstance(job, Mapping):
            return None

        return self.application_lifecycle.evaluate(
            dict(job)
        )

    @staticmethod
    def _lifecycle_result(
        ranked_result: Mapping[str, Any],
        action: Any,
        *,
        success: bool,
        decision: str,
        status: str,
        requires_human_action: bool = False,
    ) -> ExecutionResult:
        """
        Convert a lifecycle action into an ExecutionResult
        without invoking the application router.
        """
        job = ranked_result.get("job")

        if not isinstance(job, Mapping):
            job = {}

        metadata = {
            "lifecycle_action": getattr(
                action,
                "action",
                "",
            ),
            "history_status": getattr(
                action,
                "status",
                "",
            ),
            "eligible": bool(
                getattr(
                    action,
                    "eligible",
                    False,
                )
            ),
        }

        due_at = getattr(
            action,
            "due_at",
            None,
        )

        if due_at is not None:
            metadata["due_at"] = due_at

        action_metadata = getattr(
            action,
            "metadata",
            None,
        )

        if isinstance(
            action_metadata,
            Mapping,
        ):
            metadata.update(
                dict(action_metadata)
            )

        return ExecutionResult(
            success=success,
            decision=decision,
            status=status,
            message=str(
                getattr(
                    action,
                    "reason",
                    "",
                )
            ),
            job=dict(job),
            ranking_score=JobAgentService._score(
                ranked_result
            ),
            requires_human_action=(
                requires_human_action
            ),
            metadata=metadata,
        )

    # ========================================================
    # INTERNAL EXECUTION
    # ========================================================

    def _execute_with_decision(
        self,
        ranked_result: Mapping[str, Any],
        decision: Any,
        *,
        page: Any = None,
        fields: Optional[
            dict[str, Any]
        ] = None,
        candidate: Optional[
            dict[str, Any]
        ] = None,
        contacts: Optional[
            Iterable[dict]
        ] = None,
        resume: Optional[dict] = None,
        resume_path: Optional[str] = None,
        resume_output_path: Optional[str] = None,
        confirm: bool = False,
        dry_run: bool = False,
        **provider_options: Any,
    ) -> ExecutionResult:
        """
        Execute a previously calculated decision.

        IMPORTANT:
        This method receives an already calculated decision.
        It deliberately does NOT call the decision engine again.

        This prevents the batch workflow from evaluating the
        same job twice.
        """

        resolved_contacts = (
            list(contacts)
            if contacts is not None
            else []
        )

        decision_name = getattr(
            decision,
            "decision",
            "",
        )

        # ----------------------------------------------------
        # Contact discovery
        # ----------------------------------------------------

        if (
            decision_name == "outreach"
            and contacts is None
        ):
            job = ranked_result.get(
                "job"
            )

            if isinstance(
                job,
                Mapping,
            ):
                try:
                    resolved_contacts = (
                        self.discover_contacts(
                            job,
                            **provider_options,
                        )
                    )
                except Exception:
                    # Let the router handle the resulting
                    # outreach failure state.
                    resolved_contacts = []

        # ----------------------------------------------------
        # Resume path
        # ----------------------------------------------------

        resolved_resume_path = (
            resume_path
        )

        if (
            resolved_resume_path is None
            and decision_name == "outreach"
        ):
            try:
                resolved_resume_path = (
                    self.end_to_end_pipeline
                    .resolve_resume_path(
                        dict(ranked_result)
                    )
                )
            except Exception:
                resolved_resume_path = None

        # ----------------------------------------------------
        # Router
        # ----------------------------------------------------

        return self.execution_router.route(
            ranked_result,
            decision=decision,
            page=page,
            fields=fields or {},
            contacts=resolved_contacts,
            resume=resume,
            resume_output_path=(
                resume_output_path
            ),
            confirm=confirm,
            dry_run=dry_run,
        )

    # ========================================================
    # SINGLE JOB EXECUTION
    # ========================================================

    def execute_ranked_job(
        self,
        ranked_result: Mapping[str, Any],
        *,
        decision: Any = None,
        page: Any = None,
        fields: Optional[
            dict[str, Any]
        ] = None,
        candidate: Optional[
            dict[str, Any]
        ] = None,
        contacts: Optional[
            Iterable[dict]
        ] = None,
        resume: Optional[dict] = None,
        resume_path: Optional[str] = None,
        resume_output_path: Optional[str] = None,
        confirm: bool = False,
        dry_run: bool = False,
        **provider_options: Any,
    ) -> ExecutionResult:
        """
        Execute one ranked job.

        If decision is supplied, it is reused.
        Otherwise the decision engine is called once.
        """

        if not isinstance(
            ranked_result,
            Mapping,
        ):
            raise TypeError(
                "ranked_result must be a mapping."
            )

        # ----------------------------------------------------
        # LIFECYCLE
        # ----------------------------------------------------
        lifecycle_action = self._evaluate_lifecycle(
            ranked_result
        )

        if lifecycle_action is not None:
            lifecycle_action_name = str(
                getattr(
                    lifecycle_action,
                    "action",
                    "",
                )
            ).strip().lower()

            if lifecycle_action_name == "human_action":
                return self._lifecycle_result(
                    ranked_result,
                    lifecycle_action,
                    success=False,
                    decision="review",
                    status="human_action_required",
                    requires_human_action=True,
                )

            if lifecycle_action_name == "closed":
                return self._lifecycle_result(
                    ranked_result,
                    lifecycle_action,
                    success=True,
                    decision="skip",
                    status="closed",
                )

            if lifecycle_action_name == "wait_retry":
                return self._lifecycle_result(
                    ranked_result,
                    lifecycle_action,
                    success=True,
                    decision="skip",
                    status="retry_waiting",
                )

            if lifecycle_action_name == "retry_exhausted":
                return self._lifecycle_result(
                    ranked_result,
                    lifecycle_action,
                    success=True,
                    decision="skip",
                    status="retry_exhausted",
                )

            if lifecycle_action_name == "review":
                return self._lifecycle_result(
                    ranked_result,
                    lifecycle_action,
                    success=False,
                    decision="review",
                    status="lifecycle_review_required",
                    requires_human_action=True,
                )

            if lifecycle_action_name == "follow_up":
                blocking_record = self._history_blocking_record(
                    ranked_result
                )

                if blocking_record is not None:
                    return self._duplicate_result(
                        ranked_result,
                        blocking_record,
                    )

        # ----------------------------------------------------
        # DUPLICATE PREVENTION
        # ----------------------------------------------------
        blocking_record = self._history_blocking_record(
            ranked_result
        )
        if blocking_record is not None:
            return self._duplicate_result(
                ranked_result,
                blocking_record,
            )

        # ----------------------------------------------------
        # IMPORTANT:
        # Reuse an existing decision when the caller already
        # evaluated the job.
        # ----------------------------------------------------

        if decision is None:
            decision = self.decide(
                ranked_result
            )

        result = self._execute_with_decision(
            ranked_result,
            decision,
            page=page,
            fields=fields,
            candidate=candidate,
            contacts=contacts,
            resume=resume,
            resume_path=resume_path,
            resume_output_path=(
                resume_output_path
            ),
            confirm=confirm,
            dry_run=dry_run,
            **provider_options,
        )

        self._record_execution_history(
            ranked_result,
            decision,
            result,
        )

        return result

    # ========================================================
    # BATCH EXECUTION
    # ========================================================

    def execute_ranked_jobs(
        self,
        ranked_results: list[
            Mapping[str, Any]
        ],
        *,
        page_factory: Any = None,
        fields: Optional[
            dict[str, Any]
        ] = None,
        candidate: Optional[
            dict[str, Any]
        ] = None,
        resume: Optional[dict] = None,
        resume_path: Optional[str] = None,
        resume_output_directory: Optional[
            str
        ] = None,
        confirm: bool = False,
        dry_run: bool = False,
        **provider_options: Any,
    ) -> list[ExecutionResult]:
        """
        Execute multiple ranked jobs.

        Each job is evaluated exactly once.

        A failure on one job is isolated so unrelated jobs
        continue processing.
        """

        if not isinstance(
            ranked_results,
            list,
        ):
            raise TypeError(
                "ranked_results must be a list."
            )

        if fields is None:
            fields = {}

        if not isinstance(
            fields,
            dict,
        ):
            raise TypeError(
                "fields must be a dictionary."
            )

        if (
            page_factory is not None
            and not callable(page_factory)
        ):
            raise TypeError(
                "page_factory must be callable."
            )

        results: list[
            ExecutionResult
        ] = []

        for ranked_result in ranked_results:

            if not isinstance(
                ranked_result,
                Mapping,
            ):
                continue

            page = None

            try:
                blocking_record = self._history_blocking_record(
                    ranked_result
                )
                if blocking_record is not None:
                    results.append(
                        self._duplicate_result(
                            ranked_result,
                            blocking_record,
                        )
                    )
                    continue

                # ------------------------------------------------
                # LIFECYCLE
                # ------------------------------------------------

                lifecycle_action = (
                    self._evaluate_lifecycle(
                        ranked_result
                    )
                )

                if lifecycle_action is not None:
                    lifecycle_action_name = str(
                        getattr(
                            lifecycle_action,
                            "action",
                            "",
                        )
                    ).strip().lower()

                    if lifecycle_action_name == "human_action":
                        results.append(
                            self._lifecycle_result(
                                ranked_result,
                                lifecycle_action,
                                success=False,
                                decision="review",
                                status="human_action_required",
                                requires_human_action=True,
                            )
                        )
                        continue

                    if lifecycle_action_name == "closed":
                        results.append(
                            self._lifecycle_result(
                                ranked_result,
                                lifecycle_action,
                                success=True,
                                decision="skip",
                                status="closed",
                            )
                        )
                        continue

                    if lifecycle_action_name == "wait_retry":
                        results.append(
                            self._lifecycle_result(
                                ranked_result,
                                lifecycle_action,
                                success=True,
                                decision="skip",
                                status="retry_waiting",
                            )
                        )
                        continue

                    if lifecycle_action_name == "retry_exhausted":
                        results.append(
                            self._lifecycle_result(
                                ranked_result,
                                lifecycle_action,
                                success=True,
                                decision="skip",
                                status="retry_exhausted",
                            )
                        )
                        continue

                    if lifecycle_action_name == "review":
                        results.append(
                            self._lifecycle_result(
                                ranked_result,
                                lifecycle_action,
                                success=False,
                                decision="review",
                                status="lifecycle_review_required",
                                requires_human_action=True,
                            )
                        )
                        continue

                # ------------------------------------------------
                # DECIDE EXACTLY ONCE
                # ------------------------------------------------

                decision = self.decide(
                    ranked_result
                )

                decision_name = getattr(
                    decision,
                    "decision",
                    "",
                )

                # ------------------------------------------------
                # Browser page
                # ------------------------------------------------

                if (
                    decision_name == "apply"
                    and page_factory is not None
                ):
                    page = page_factory(
                        ranked_result
                    )

                # ------------------------------------------------
                # Output path
                # ------------------------------------------------

                output_path = None

                if (
                    resume_output_directory
                    and decision_name == "apply"
                ):
                    job = ranked_result.get(
                        "job",
                        {},
                    )

                    if isinstance(
                        job,
                        Mapping,
                    ):
                        filename = (
                            f"{self._slug(job.get('company', 'job'))}_"
                            f"{self._slug(job.get('title', 'application'))}.pdf"
                        )

                        output_path = str(
                            Path(
                                resume_output_directory
                            )
                            / filename
                        )

                # ------------------------------------------------
                # Execute the ALREADY calculated decision
                # ------------------------------------------------

                result = (
                    self.execute_ranked_job(
                        ranked_result,
                        decision=decision,
                        page=page,
                        fields=fields,
                        candidate=candidate,
                        resume=resume,
                        resume_path=resume_path,
                        resume_output_path=(
                            output_path
                        ),
                        confirm=confirm,
                        dry_run=dry_run,
                        **provider_options,
                    )
                )

                results.append(
                    result
                )

            except Exception as exc:

                job = (
                    dict(
                        ranked_result.get(
                            "job",
                            {},
                        )
                    )
                    if isinstance(
                        ranked_result.get(
                            "job",
                            {},
                        ),
                        Mapping,
                    )
                    else {}
                )

                score = self._score(
                    ranked_result
                )

                results.append(
                    ExecutionResult(
                        success=False,
                        decision="error",
                        status="job_execution_failed",
                        message=(
                            "Unexpected failure while "
                            "processing this job."
                        ),
                        job=job,
                        ranking_score=score,
                        error=str(exc),
                    )
                )

        return results

    # ========================================================
    # COMPLETE RUN
    # ========================================================

    def run(
        self,
        keywords: str,
        location: Optional[str] = None,
        *,
        min_score: float = 60.0,
        eligible_only: bool = False,
        limit: Optional[int] = 10,
        page_factory: Any = None,
        fields: Optional[
            dict[str, Any]
        ] = None,
        candidate: Optional[
            dict[str, Any]
        ] = None,
        resume: Optional[dict] = None,
        resume_path: Optional[str] = None,
        resume_output_directory: Optional[
            str
        ] = None,
        confirm: bool = False,
        dry_run: bool = True,
        **source_options: Any,
    ) -> JobAgentRunResult:
        """
        Run the complete JobAgent workflow.

        Default behavior is safe:

            dry_run=True
            confirm=False
        """

        if not isinstance(
            keywords,
            str,
        ):
            raise TypeError(
                "keywords must be a string."
            )

        keywords = keywords.strip()

        if not keywords:
            raise ValueError(
                "keywords cannot be empty."
            )

        # ----------------------------------------------------
        # DISCOVERY + RANKING
        # ----------------------------------------------------

        try:
            ranked_jobs = (
                self.discover_and_rank(
                    keywords=keywords,
                    location=location,
                    min_score=min_score,
                    eligible_only=eligible_only,
                    limit=limit,
                    **source_options,
                )
            )

        except Exception as exc:
            return JobAgentRunResult(
                success=False,
                status="discovery_failed",
                keywords=keywords,
                location=location,
                errors=[
                    {
                        "stage": "discovery",
                        "error": str(exc),
                    }
                ],
            )

        if not ranked_jobs:
            return JobAgentRunResult(
                success=True,
                status="no_matching_jobs",
                keywords=keywords,
                location=location,
                discovered_count=0,
                processed_count=0,
                metadata={
                    "dry_run": dry_run,
                    "confirm": confirm,
                },
            )

        # ----------------------------------------------------
        # EXECUTION
        # ----------------------------------------------------

        executions = (
            self.execute_ranked_jobs(
                ranked_jobs,
                page_factory=page_factory,
                fields=fields,
                candidate=candidate,
                resume=resume,
                resume_path=resume_path,
                resume_output_directory=(
                    resume_output_directory
                ),
                confirm=confirm,
                dry_run=dry_run,
                **source_options,
            )
        )

        # ----------------------------------------------------
        # SUMMARY
        # ----------------------------------------------------

        return self._build_run_result(
            keywords=keywords,
            location=location,
            ranked_jobs=ranked_jobs,
            executions=executions,
            dry_run=dry_run,
            confirm=confirm,
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    @staticmethod
    def _build_run_result(
        *,
        keywords: str,
        location: Optional[str],
        ranked_jobs: list[dict],
        executions: list[
            ExecutionResult
        ],
        dry_run: bool,
        confirm: bool,
    ) -> JobAgentRunResult:

        apply_count = 0
        outreach_count = 0
        review_count = 0
        skip_count = 0

        executed_count = 0
        submitted_count = 0
        sent_count = 0
        human_action_required_count = 0

        errors: list[
            dict[str, Any]
        ] = []

        for execution in executions:

            decision = execution.decision

            if decision == "apply":
                apply_count += 1

            elif decision == "outreach":
                outreach_count += 1

            elif decision == "review":
                review_count += 1

            elif decision == "skip":
                skip_count += 1

            if execution.executed:
                executed_count += 1

            if execution.submitted:
                submitted_count += 1

            if execution.sent:
                sent_count += 1

            if execution.requires_human_action:
                human_action_required_count += 1

            if not execution.success:
                errors.append(
                    {
                        "job": execution.job,
                        "decision": decision,
                        "status": execution.status,
                        "error": execution.error,
                        "requires_human_action": (
                            execution.requires_human_action
                        ),
                    }
                )

        failed_count = len(
            errors
        )

        # ----------------------------------------------------
        # Status
        #
        # A dry-run should remain a dry-run result even if an
        # individual job could not be prepared. The failures
        # are preserved in errors.
        # ----------------------------------------------------

        if dry_run:
            status = "dry_run_completed"
        elif failed_count:
            status = "completed_with_errors"
        else:
            status = "completed"

        return JobAgentRunResult(
            success=True,
            status=status,
            keywords=keywords,
            location=location,
            discovered_count=len(
                ranked_jobs
            ),
            processed_count=len(
                executions
            ),
            apply_count=apply_count,
            outreach_count=outreach_count,
            review_count=review_count,
            skip_count=skip_count,
            executed_count=executed_count,
            submitted_count=submitted_count,
            sent_count=sent_count,
            human_action_required_count=(
                human_action_required_count
            ),
            jobs=[
                dict(job)
                for job in ranked_jobs
            ],
            executions=[
                execution.to_dict()
                for execution in executions
            ],
            errors=errors,
            metadata={
                "dry_run": dry_run,
                "confirm": confirm,
                "failed_count": failed_count,
                "human_action_required_count": (
                    human_action_required_count
                ),
            },
        )

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _slug(
        value: Any,
    ) -> str:

        chars = []

        for char in str(
            value or ""
        ).lower():

            chars.append(
                char
                if char.isalnum()
                else "_"
            )

        slug = "".join(
            chars
        ).strip("_")

        while "__" in slug:
            slug = slug.replace(
                "__",
                "_",
            )

        return (
            slug
            or "job"
        )

    @staticmethod
    def _score(
        ranked_result: Mapping[str, Any],
    ) -> float:

        try:
            return float(
                ranked_result.get(
                    "ranking_score",
                    0.0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0.0


__all__ = [
    "JobAgentRunResult",
    "JobAgentService",
]