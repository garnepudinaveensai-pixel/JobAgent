from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from app.core.agent_runner import AgentRunner
from app.core.application_workflow import ApplicationWorkflow
from app.core.job_application_engine import JobApplicationEngine
from app.core.job_ranker import JobRanker
from app.outreach.contact_discovery import ContactDiscovery
from app.outreach.outreach_pipeline import (
    OutreachPipeline,
    OutreachResult,
)


class EndToEndPipeline:
    """
    High-level orchestration layer for JobAgent.

    Responsibilities
    -----------------

    Discovery
        ↓
    Matching
        ↓
    Ranking
        ↓
    Recruiter discovery
        ↓
    Outreach preparation

    AND

    Ranked job
        ↓
    Selected resume
        ↓
    Application preparation
        ↓
    Human confirmation
        ↓
    Application submission

    Safety
    ------

    - Discovery never sends email.
    - Outreach preparation never sends email.
    - Application preparation never submits.
    - confirm=False ALWAYS prevents submission.
    - confirm=True is required for actual submission.
    - The injected application engine is always respected.
    - Browser/page ownership remains below this orchestration layer.
    - A failure for one job does not stop unrelated jobs.
    """

    def __init__(
        self,
        runner: AgentRunner,
        contact_discovery: Optional[
            ContactDiscovery
        ] = None,
        outreach_pipeline: Optional[
            OutreachPipeline
        ] = None,
        application_engine: Optional[
            JobApplicationEngine
        ] = None,
        application_workflow: Optional[
            ApplicationWorkflow
        ] = None,
    ) -> None:

        if runner is None:
            raise ValueError(
                "runner cannot be None."
            )

        self.runner = runner

        self.contact_discovery = (
            contact_discovery
            if contact_discovery is not None
            else ContactDiscovery()
        )

        self.outreach_pipeline = (
            outreach_pipeline
            if outreach_pipeline is not None
            else OutreachPipeline()
        )

        self.application_workflow = (
            application_workflow
            if application_workflow is not None
            else ApplicationWorkflow()
        )

        # IMPORTANT:
        #
        # If an application_engine is explicitly supplied,
        # ALWAYS use it.
        #
        # This is essential for dependency injection,
        # testing, custom engines and future integrations.
        self.application_engine = (
            application_engine
            if application_engine is not None
            else self._build_application_engine()
        )

    # ========================================================
    # APPLICATION ENGINE
    # ========================================================

    def _build_application_engine(
        self,
    ) -> JobApplicationEngine:
        """
        Build the default application engine.

        The ApplicationWorkflow is injected into the engine
        so browser/form handling remains below this layer.
        """

        return JobApplicationEngine(
            job_source_manager=(
                self.runner.job_source_manager
            ),
            deduplicator=(
                self.runner.deduplicator
            ),
            job_match_pipeline=(
                self.runner.job_match_pipeline
            ),
            job_ranker=JobRanker,
            application_workflow=(
                self.application_workflow
            ),
            job_store=self.runner.job_store,
        )

    # ========================================================
    # DISCOVERY + RANKING
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
    ) -> list[dict]:
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

            if limit < 1:
                raise ValueError(
                    "limit must be >= 1."
                )

        return list(
            self.runner
            .discover_match_and_rank_from_sources(
                keywords=keywords,
                location=location,
                min_score=min_score,
                eligible_only=eligible_only,
                limit=limit,
                **source_options,
            )
            or []
        )

    # ========================================================
    # CONTACT DISCOVERY
    # ========================================================

    def discover_contacts(
        self,
        job: dict,
        **provider_options: Any,
    ) -> list[dict]:
        """
        Discover recruiter/HR contacts for one job.
        """

        if not isinstance(
            job,
            dict,
        ):
            raise TypeError(
                "job must be a dictionary."
            )

        company = str(
            job.get(
                "company",
                "",
            )
            or ""
        ).strip()

        if not company:
            return []

        contacts = (
            self.contact_discovery.discover(
                company=company,
                job=job,
                **provider_options,
            )
        )

        if contacts is None:
            return []

        return list(
            contacts
        )

    # ========================================================
    # RESUME RESOLUTION
    # ========================================================

    def resolve_resume_path(
        self,
        ranked_result: dict,
        explicit_path: Optional[str] = None,
    ) -> str:
        """
        Resolve the source resume selected by matching.
        """

        if not isinstance(
            ranked_result,
            dict,
        ):
            raise TypeError(
                "ranked_result must be a dictionary."
            )

        if explicit_path is not None:
            value = str(
                explicit_path
            ).strip()

            if value:
                return value

        resume = ranked_result.get(
            "resume"
        )

        filename = ""

        if isinstance(
            resume,
            dict,
        ):
            filename = str(
                resume.get(
                    "filename",
                    "",
                )
                or ""
            ).strip()

        if filename:
            pipeline = getattr(
                self.runner,
                "job_match_pipeline",
                None,
            )

            manager = getattr(
                pipeline,
                "resume_manager",
                None,
            )

            directory = getattr(
                manager,
                "resume_directory",
                None,
            )

            if directory:
                candidate = (
                    Path(directory)
                    / filename
                )

                if (
                    candidate.exists()
                    and candidate.is_file()
                ):
                    return str(
                        candidate
                    )

        config = getattr(
            self.runner,
            "config",
            None,
        )

        application_config = getattr(
            config,
            "application",
            None,
        )

        fallback = getattr(
            application_config,
            "resume_path",
            "",
        )

        return str(
            fallback or ""
        ).strip()

    def _resolve_selected_resume_data(
        self,
        ranked_result: dict,
    ) -> dict:
        """
        Return the exact resume selected by the matching
        pipeline.

        Selection order:

        1. match.selected_resume
        2. resume

        If neither exists, preparation cannot safely continue.
        """

        if not isinstance(
            ranked_result,
            dict,
        ):
            raise TypeError(
                "ranked_result must be a dictionary."
            )

        match = ranked_result.get(
            "match"
        )

        if isinstance(
            match,
            dict,
        ):
            selected = match.get(
                "selected_resume"
            )

            if isinstance(
                selected,
                dict,
            ):
                return dict(
                    selected
                )

        resume = ranked_result.get(
            "resume"
        )

        if isinstance(
            resume,
            dict,
        ):
            return dict(
                resume
            )

        raise ValueError(
            "ranked_result does not contain "
            "a usable selected resume."
        )

    # ========================================================
    # OUTREACH PREPARATION
    # ========================================================

    def prepare_outreach_for_job(
        self,
        ranked_result: dict,
        *,
        candidate: Optional[dict] = None,
        resume_path: Optional[str] = None,
        **provider_options: Any,
    ) -> dict:
        """
        Prepare outreach for one ranked job.

        Nothing is sent.
        """

        if not isinstance(
            ranked_result,
            dict,
        ):
            raise TypeError(
                "ranked_result must be a dictionary."
            )

        job = ranked_result.get(
            "job"
        )

        if not isinstance(
            job,
            dict,
        ):
            raise ValueError(
                "ranked_result does not contain "
                "a valid job."
            )

        contacts = (
            self.discover_contacts(
                job,
                **provider_options,
            )
        )

        resolved_resume = (
            self.resolve_resume_path(
                ranked_result,
                explicit_path=resume_path,
            )
        )

        outreach = (
            self.outreach_pipeline
            .prepare_outreach(
                contacts=contacts,
                job=job,
                candidate=(
                    candidate
                    if candidate is not None
                    else {}
                ),
                resume_path=resolved_resume,
            )
        )

        result = dict(
            ranked_result
        )

        result["contacts"] = contacts

        result["resume_path"] = (
            resolved_resume
        )

        result["outreach"] = (
            self._outreach_to_dict(
                outreach
            )
        )

        return result

    def prepare_outreach(
        self,
        ranked_results: Iterable[dict],
        *,
        candidate: Optional[dict] = None,
        resume_path: Optional[str] = None,
        **provider_options: Any,
    ) -> list[dict]:
        """
        Prepare outreach for multiple ranked jobs.

        A failure on one job is isolated.
        """

        prepared: list[dict] = []

        for ranked_result in (
            ranked_results or []
        ):
            if not isinstance(
                ranked_result,
                dict,
            ):
                continue

            try:
                prepared.append(
                    self.prepare_outreach_for_job(
                        ranked_result,
                        candidate=candidate,
                        resume_path=resume_path,
                        **provider_options,
                    )
                )

            except Exception as exc:
                failed = dict(
                    ranked_result
                )

                failed["outreach"] = {
                    "success": False,
                    "status": (
                        "outreach_failed"
                    ),
                    "error": str(
                        exc
                    ),
                }

                prepared.append(
                    failed
                )

        return prepared

    # ========================================================
    # APPLICATION HELPERS
    # ========================================================

    @staticmethod
    def _slug(
        value: str,
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
            or "job_application"
        )

    def _default_application_resume_path(
        self,
        ranked_result: dict,
    ) -> str:
        job = ranked_result.get(
            "job",
            {},
        )

        title = self._slug(
            job.get(
                "title",
                "application",
            )
        )

        company = self._slug(
            job.get(
                "company",
                "job",
            )
        )

        config = getattr(
            self.runner,
            "config",
            None,
        )

        application_config = getattr(
            config,
            "application",
            None,
        )

        directory = getattr(
            application_config,
            "tailored_resume_directory",
            "data/resumes/tailored",
        )

        return str(
            Path(directory)
            / f"{company}_{title}.pdf"
        )

    def _ensure_job_registered(
        self,
        job: dict,
    ) -> str:
        """
        Register the job once and return its stable ID.
        """

        if not isinstance(
            job,
            dict,
        ):
            raise TypeError(
                "job must be a dictionary."
            )

        existing_id = str(
            job.get(
                "job_id",
                "",
            )
            or ""
        ).strip()

        if existing_id:
            existing = (
                self.runner
                .job_store
                .get_job(
                    existing_id
                )
            )

            if existing is not None:
                return existing_id

        return (
            self.runner
            .job_store
            .add_job(
                dict(job),
                status="discovered",
            )
        )

    # ========================================================
    # APPLICATION PREPARATION
    # ========================================================

    def prepare_application_for_job(
        self,
        ranked_result: dict,
        *,
        page: Any,
        fields: Optional[dict] = None,
        resume_output_path: Optional[str] = None,
    ) -> dict:
        """
        Prepare an application.

        IMPORTANT:

        This method delegates to the configured
        application_engine.

        It does NOT directly create an ApplicationSubmitter.

        Therefore tests can inject FakeEngine and real
        production code can use JobApplicationEngine.
        """

        if not isinstance(
            ranked_result,
            dict,
        ):
            raise TypeError(
                "ranked_result must be a dictionary."
            )

        if page is None:
            raise ValueError(
                "page cannot be None."
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

        job = ranked_result.get(
            "job"
        )

        if not isinstance(
            job,
            dict,
        ):
            raise ValueError(
                "ranked_result does not contain "
                "a valid job."
            )

        job_url = str(
            job.get(
                "url",
                "",
            )
            or ""
        ).strip()

        if not job_url:
            raise ValueError(
                "Selected job must contain a URL."
            )

        # Resolve the exact resume chosen by matching.
        selected_resume = (
            self._resolve_selected_resume_data(
                ranked_result
            )
        )

        if resume_output_path is None:
            output_path = (
                self._default_application_resume_path(
                    ranked_result
                )
            )
        else:
            output_path = str(
                resume_output_path
            ).strip()

        if not output_path:
            raise ValueError(
                "resume_output_path cannot be empty."
            )

        job_id = (
            self._ensure_job_registered(
                job
            )
        )

        # ====================================================
        # CRITICAL FIX
        # ====================================================
        #
        # USE THE INJECTED APPLICATION ENGINE.
        #
        # Do NOT call ApplicationWorkflow directly here.
        #
        # This keeps the architecture testable and prevents
        # fake pages from accidentally reaching Playwright.
        #

        prepare = getattr(
            self.application_engine,
            "prepare_application",
            None,
        )

        if not callable(
            prepare
        ):
            raise AttributeError(
                "Application engine does not provide "
                "prepare_application()."
            )

        prepared = prepare(
            ranked_result,
            page=page,
            resume=selected_resume,
            resume_output_path=output_path,
            fields=fields,
        )

        if prepared is None:
            prepared = {}

        if not isinstance(
            prepared,
            dict,
        ):
            raise TypeError(
                "Application engine returned "
                "an unexpected result type."
            )

        result = dict(
            prepared
        )

        # Preserve orchestration metadata regardless of
        # what the underlying engine returned.

        result.setdefault(
            "job",
            job,
        )

        result["job_id"] = job_id

        result.setdefault(
            "ranked_result",
            ranked_result,
        )

        result.setdefault(
            "selected_resume",
            selected_resume,
        )

        result.setdefault(
            "source_resume_path",
            self.resolve_resume_path(
                ranked_result
            ),
        )

        result.setdefault(
            "resume_output_path",
            output_path,
        )

        result.setdefault(
            "ranking_score",
            ranked_result.get(
                "ranking_score",
                0.0,
            ),
        )

        safety_status = str(
            result.get(
                "status",
                "",
            )
            or ""
        ).strip()

        human_action_statuses = {
            "captcha_detected",
            "login_required",
            "human_action_required",
        }

        if safety_status in human_action_statuses:
            result["requires_human_action"] = True

        result.setdefault(
            "requires_human_action",
            bool(
                result.get(
                    "requires_human_action",
                    False,
                )
            ),
        )

        success = bool(
            result.get(
                "success",
                False,
            )
        )

        # Preserve structured browser safety states. A CAPTCHA,
        # authentication barrier, unavailable job, or missing
        # form is a known execution outcome, not an unexpected
        # application failure.
        safety_status = str(
            result.get(
                "status",
                "",
            )
            or ""
        ).strip()

        safety_job_statuses = {
            "captcha_detected": "captcha_detected",
            "login_required": "login_required",
            "human_action_required": "human_action_required",
            "job_unavailable": "job_unavailable",
            "form_not_found": "form_not_found",
            "navigation_failed": "navigation_failed",
            "validation_failed": "validation_failed",
        }

        if safety_status in safety_job_statuses:
            self.runner.job_store.update_status(
                job_id,
                safety_job_statuses[
                    safety_status
                ],
            )
        elif success:
            self.runner.job_store.update_status(
                job_id,
                "application_started",
            )
        else:
            self.runner.job_store.update_status(
                job_id,
                "application_failed",
            )

        return result

    def prepare_applications(
        self,
        ranked_results: Iterable[dict],
        *,
        page_factory: Callable[
            [dict],
            Any,
        ],
        fields: Optional[dict] = None,
        resume_output_directory: Optional[
            str
        ] = None,
    ) -> list[dict]:
        """
        Prepare multiple applications.

        page_factory(ranked_result) must return the browser
        page for that particular job.
        """

        if not callable(
            page_factory
        ):
            raise TypeError(
                "page_factory must be callable."
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

        prepared: list[dict] = []

        for ranked_result in (
            ranked_results or []
        ):
            if not isinstance(
                ranked_result,
                dict,
            ):
                continue

            job = ranked_result.get(
                "job",
                {},
            )

            output_path = None

            if resume_output_directory:
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

            try:
                page = page_factory(
                    ranked_result
                )

                prepared.append(
                    self.prepare_application_for_job(
                        ranked_result,
                        page=page,
                        fields=fields,
                        resume_output_path=output_path,
                    )
                )

            except Exception as exc:

                failed = dict(
                    ranked_result
                )

                failed["success"] = False

                failed["status"] = (
                    "application_preparation_failed"
                )

                failed["error"] = str(
                    exc
                )

                prepared.append(
                    failed
                )

        return prepared

    # ========================================================
    # APPLICATION SUBMISSION
    # ========================================================

    def submit_application(
        self,
        prepared_application: dict,
        *,
        confirm: bool = False,
    ) -> dict:
        """
        Submit one prepared application.

        SAFETY BARRIER:

            confirm=False
                ↓
            NEVER submit

        Only confirm=True may reach the application engine.
        """

        if not isinstance(
            prepared_application,
            dict,
        ):
            raise TypeError(
                "prepared_application must be a dictionary."
            )

        job_id = str(
            prepared_application.get(
                "job_id",
                "",
            )
            or ""
        ).strip()

        # ----------------------------------------------------
        # HARD SAFETY BARRIER
        # ----------------------------------------------------

        if not confirm:
            return {
                "success": False,
                "status": (
                    "confirmation_required"
                ),
                "submitted": False,
                "job_id": job_id,
            }

        submit = getattr(
            self.application_engine,
            "submit_application",
            None,
        )

        if not callable(
            submit
        ):
            raise AttributeError(
                "Application engine does not provide "
                "submit_application()."
            )

        result = submit(
            prepared_application,
            confirm=True,
        )

        if result is None:
            result = {
                "success": False,
                "status": (
                    "submission_returned_no_result"
                ),
                "submitted": False,
            }

        if isinstance(
            result,
            dict,
        ):
            output = dict(
                result
            )
        else:
            output = {
                "success": bool(
                    result
                ),
                "status": (
                    "applied"
                    if result
                    else "application_failed"
                ),
                "submitted": bool(
                    result
                ),
            }

        submitted = bool(
            output.get(
                "submitted",
                output.get(
                    "success",
                    False,
                ),
            )
        )

        output["submitted"] = (
            submitted
        )

        output["job_id"] = (
            job_id
        )

        if job_id:
            submission_status = str(
                output.get(
                    "status",
                    "",
                )
                or ""
            ).strip()

            safety_statuses = {
                "captcha_detected",
                "login_required",
                "human_action_required",
                "job_unavailable",
                "form_not_found",
                "navigation_failed",
                "validation_failed",
                "submission_timeout",
                "submission_failed",
            }

            if submission_status in safety_statuses:
                self.runner.job_store.update_status(
                    job_id,
                    submission_status,
                )
            else:
                self.runner.job_store.update_status(
                    job_id,
                    (
                        "applied"
                        if submitted
                        else "application_failed"
                    ),
                )

        return output

    # ========================================================
    # PREPARE + OPTIONAL SUBMIT
    # ========================================================

    def run_application(
        self,
        ranked_result: dict,
        *,
        page: Any,
        fields: Optional[dict] = None,
        resume_output_path: Optional[str] = None,
        confirm: bool = False,
    ) -> dict:
        """
        Prepare one application and optionally submit it.

        Default:

            confirm=False
                ↓
            prepare only

        Explicit:

            confirm=True
                ↓
            prepare
                ↓
            submit
        """

        prepared = (
            self.prepare_application_for_job(
                ranked_result,
                page=page,
                fields=fields,
                resume_output_path=(
                    resume_output_path
                ),
            )
        )

        if not prepared.get(
            "success",
            False,
        ):
            return {
                **prepared,
                "submitted": False,
            }

        # ----------------------------------------------------
        # Confirmation barrier
        # ----------------------------------------------------

        if not confirm:
            return {
                **prepared,
                "status": (
                    "confirmation_required"
                ),
                "submitted": False,
            }

        submission = (
            self.submit_application(
                prepared,
                confirm=True,
            )
        )

        return {
            **prepared,
            **submission,
            "submitted": bool(
                submission.get(
                    "submitted",
                    submission.get(
                        "success",
                        False,
                    ),
                )
            ),
        }

    # ========================================================
    # TOP APPLICATION
    # ========================================================

    def prepare_top_application(
        self,
        ranked_results: Iterable[dict],
        *,
        page: Any,
        fields: Optional[dict] = None,
        resume_output_path: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Select the highest-ranked job and prepare it.
        """

        ranked = [
            item
            for item in (
                ranked_results or []
            )
            if isinstance(
                item,
                dict,
            )
        ]

        if not ranked:
            return None

        best = max(
            ranked,
            key=lambda item: float(
                item.get(
                    "ranking_score",
                    0.0,
                )
                or 0.0
            ),
        )

        return (
            self.prepare_application_for_job(
                best,
                page=page,
                fields=fields,
                resume_output_path=(
                    resume_output_path
                ),
            )
        )

    # ========================================================
    # SAFE DISCOVERY RUN
    # ========================================================

    def run(
        self,
        keywords: str,
        location: Optional[str] = None,
        *,
        min_score: float = 60.0,
        eligible_only: bool = False,
        limit: Optional[int] = 10,
        prepare_outreach: bool = True,
        candidate: Optional[dict] = None,
        resume_path: Optional[str] = None,
        **source_options: Any,
    ) -> dict:
        """
        Safe intelligence run.

        Performs:

            discovery
            ↓
            matching
            ↓
            ranking
            ↓
            recruiter discovery
            ↓
            outreach preparation

        NEVER sends or submits.
        """

        ranked = self.discover_and_rank(
            keywords=keywords,
            location=location,
            min_score=min_score,
            eligible_only=eligible_only,
            limit=limit,
            **source_options,
        )

        result: dict[str, Any] = {
            "success": True,
            "status": (
                "ranked"
                if ranked
                else "no_matching_jobs"
            ),
            "jobs": ranked,
            "count": len(ranked),
            "outreach": [],
        }

        if (
            not ranked
            or not prepare_outreach
        ):
            return result

        prepared = self.prepare_outreach(
            ranked,
            candidate=candidate,
            resume_path=resume_path,
            **source_options,
        )

        result["outreach"] = (
            prepared
        )

        result["status"] = (
            "outreach_prepared"
            if prepared
            else "ranked"
        )

        return result

    # ========================================================
    # CONTROLLED OUTREACH EXECUTION
    # ========================================================

    def execute(
        self,
        keywords: str,
        location: Optional[str] = None,
        *,
        min_score: float = 60.0,
        eligible_only: bool = False,
        limit: Optional[int] = 10,
        candidate: Optional[dict] = None,
        resume_path: Optional[str] = None,
        prepare_outreach: bool = True,
        send_outreach: bool = False,
        confirm_outreach: bool = False,
        ranked_results: Optional[
            list[dict]
        ] = None,
        **source_options: Any,
    ) -> dict:
        """
        Controlled discovery + outreach execution.

        Application submission is intentionally separate because
        it requires a browser page and application-specific form
        data.
        """

        if ranked_results is None:
            ranked = (
                self.discover_and_rank(
                    keywords=keywords,
                    location=location,
                    min_score=min_score,
                    eligible_only=eligible_only,
                    limit=limit,
                    **source_options,
                )
            )
        else:
            ranked = list(
                ranked_results
            )

        result: dict[str, Any] = {
            "success": True,
            "status": (
                "jobs_ranked"
                if ranked
                else "no_matching_jobs"
            ),
            "jobs": ranked,
            "count": len(ranked),
            "outreach": [],
            "sent_outreach": [],
        }

        if (
            not ranked
            or not prepare_outreach
        ):
            return result

        prepared = self.prepare_outreach(
            ranked,
            candidate=candidate,
            resume_path=resume_path,
            **source_options,
        )

        result["outreach"] = (
            prepared
        )

        if not send_outreach:
            result["status"] = (
                "outreach_prepared"
            )
            return result

        sent: list[dict] = []

        for item in prepared:

            outreach = item.get(
                "outreach"
            )

            if not isinstance(
                outreach,
                dict,
            ):
                continue

            try:
                send_result = (
                    self.send_outreach(
                        item,
                        confirm=confirm_outreach,
                    )
                )

                sent.append(
                    {
                        "job": item.get(
                            "job"
                        ),
                        "result": (
                            self._outreach_to_dict(
                                send_result
                            )
                        ),
                    }
                )

            except Exception as exc:

                sent.append(
                    {
                        "job": item.get(
                            "job"
                        ),
                        "result": {
                            "success": False,
                            "status": (
                                "send_failed"
                            ),
                            "error": str(
                                exc
                            ),
                        },
                    }
                )

        result["sent_outreach"] = (
            sent
        )

        if not confirm_outreach:
            result["status"] = (
                "outreach_confirmation_required"
            )

        elif any(
            item["result"].get(
                "success",
                False,
            )
            for item in sent
        ):
            result["status"] = (
                "outreach_sent"
            )

        else:
            result["status"] = (
                "outreach_send_failed"
            )

        return result

    # ========================================================
    # OUTREACH SEND
    # ========================================================

    def send_outreach(
        self,
        prepared_result: dict,
        *,
        confirm: bool = False,
    ) -> OutreachResult:
        """
        Send one prepared outreach message.

        confirm=False NEVER sends.
        """

        if not isinstance(
            prepared_result,
            dict,
        ):
            raise TypeError(
                "prepared_result must be a dictionary."
            )

        job = prepared_result.get(
            "job"
        )

        if not isinstance(
            job,
            dict,
        ):
            raise ValueError(
                "prepared_result does not contain "
                "a valid job."
            )

        contacts = prepared_result.get(
            "contacts",
            [],
        )

        if not isinstance(
            contacts,
            list,
        ):
            contacts = list(
                contacts or []
            )

        resume_path = (
            prepared_result.get(
                "resume_path"
            )
        )

        return (
            self.outreach_pipeline
            .send_outreach(
                contacts=contacts,
                job=job,
                resume_path=resume_path,
                confirm=confirm,
            )
        )

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _outreach_to_dict(
        outreach: Optional[
            OutreachResult
        ],
    ) -> Optional[dict]:

        if outreach is None:
            return None

        if isinstance(
            outreach,
            dict,
        ):
            return dict(
                outreach
            )

        return asdict(
            outreach
        )


__all__ = [
    "EndToEndPipeline",
]