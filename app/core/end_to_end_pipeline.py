from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Optional

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
    High-level user-facing JobAgent workflow.

    The ranked result is the single source of truth for both
    recruiter outreach and application preparation.

    Flow:

        Multi-source discovery
            ↓
        Deduplication
            ↓
        Resume matching
            ↓
        Job ranking
            ↓
        ┌───────────────┬────────────────┐
        ↓               ↓                ↓
    Recruiter       Application       Ranking data
    discovery       preparation       + selected resume
        ↓               ↓
    Outreach         Tailored PDF
    preparation      + form
        ↓               ↓
    Outreach        Confirmation
    tracking            ↓
                    Submission
                        ↓
                    Job status

    Nothing is sent or submitted unless the caller explicitly
    passes confirm=True to the corresponding send/submit method.
    """

    def __init__(
        self,
        runner: AgentRunner,
        contact_discovery: Optional[ContactDiscovery] = None,
        outreach_pipeline: Optional[OutreachPipeline] = None,
        application_engine: Optional[JobApplicationEngine] = None,
    ) -> None:
        if runner is None:
            raise ValueError("runner cannot be None.")

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

        self.application_engine = (
            application_engine
            if application_engine is not None
            else self._build_application_engine()
        )

    # ========================================================
    # APPLICATION ENGINE
    # ========================================================

    def _build_application_engine(self) -> JobApplicationEngine:
        """Build the application engine from existing runner components."""

        return JobApplicationEngine(
            job_source_manager=self.runner.job_source_manager,
            deduplicator=self.runner.deduplicator,
            job_match_pipeline=self.runner.job_match_pipeline,
            job_ranker=JobRanker,
            application_workflow=ApplicationWorkflow(),
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
        """Run the existing multi-source intelligence pipeline."""

        return self.runner.discover_match_and_rank_from_sources(
            keywords=keywords,
            location=location,
            min_score=min_score,
            eligible_only=eligible_only,
            limit=limit,
            **source_options,
        )

    # ========================================================
    # CONTACT DISCOVERY
    # ========================================================

    def discover_contacts(
        self,
        job: dict,
        **provider_options: Any,
    ) -> list[dict]:
        """Discover professional recruiter/HR contacts for a job."""

        if not isinstance(job, dict):
            raise TypeError("job must be a dictionary.")

        company = str(job.get("company", "") or "").strip()

        if not company:
            return []

        return self.contact_discovery.discover(
            company=company,
            job=job,
            **provider_options,
        )

    # ========================================================
    # RESUME PATH
    # ========================================================

    def resolve_resume_path(
        self,
        ranked_result: dict,
        explicit_path: Optional[str] = None,
    ) -> str:
        """Resolve the original resume selected by JobMatchPipeline."""

        if explicit_path is not None:
            value = str(explicit_path).strip()
            if value:
                return value

        resume = ranked_result.get("resume")
        filename = ""

        if isinstance(resume, dict):
            filename = str(resume.get("filename", "") or "").strip()

        if filename:
            pipeline = self.runner.job_match_pipeline
            manager = getattr(pipeline, "resume_manager", None)
            directory = getattr(manager, "resume_directory", None)

            if directory:
                candidate = Path(directory) / filename
                if candidate.exists() and candidate.is_file():
                    return str(candidate)

        return str(self.runner.config.application.resume_path).strip()

    def _resolve_selected_resume_data(self, ranked_result: dict) -> dict:
        """Return the full parsed resume selected by the matcher."""

        if not isinstance(ranked_result, dict):
            raise TypeError("ranked_result must be a dictionary.")

        resume = ranked_result.get("resume")
        match = ranked_result.get("match")

        if isinstance(match, dict):
            selected = match.get("selected_resume")
            if isinstance(selected, dict):
                return dict(selected)

        if isinstance(resume, dict):
            # Some compatibility paths place the full parsed resume
            # directly in result["resume"].
            return dict(resume)

        raise ValueError(
            "ranked_result does not contain a usable selected resume."
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
        """Prepare one personalized outreach message. Nothing is sent."""

        if not isinstance(ranked_result, dict):
            raise TypeError("ranked_result must be a dictionary.")

        job = ranked_result.get("job")
        if not isinstance(job, dict):
            raise ValueError(
                "ranked_result does not contain a valid job."
            )

        contacts = self.discover_contacts(job, **provider_options)
        resolved_resume = self.resolve_resume_path(
            ranked_result,
            explicit_path=resume_path,
        )

        outreach = self.outreach_pipeline.prepare_outreach(
            contacts=contacts,
            job=job,
            candidate=candidate or {},
            resume_path=resolved_resume,
        )

        result = dict(ranked_result)
        result["contacts"] = contacts
        result["outreach"] = self._outreach_to_dict(outreach)
        result["resume_path"] = resolved_resume
        return result

    def prepare_outreach(
        self,
        ranked_results: Iterable[dict],
        *,
        candidate: Optional[dict] = None,
        resume_path: Optional[str] = None,
        **provider_options: Any,
    ) -> list[dict]:
        """Prepare outreach for every ranked result."""

        prepared: list[dict] = []
        for ranked_result in ranked_results or []:
            if not isinstance(ranked_result, dict):
                continue
            prepared.append(
                self.prepare_outreach_for_job(
                    ranked_result,
                    candidate=candidate,
                    resume_path=resume_path,
                    **provider_options,
                )
            )
        return prepared

    # ========================================================
    # APPLICATION PREPARATION
    # ========================================================

    @staticmethod
    def _slug(value: str) -> str:
        chars = []
        for char in str(value or "").lower():
            chars.append(char if char.isalnum() else "_")
        slug = "".join(chars).strip("_")
        while "__" in slug:
            slug = slug.replace("__", "_")
        return slug or "job_application"

    def _default_application_resume_path(
        self,
        ranked_result: dict,
    ) -> str:
        job = ranked_result.get("job", {})
        title = self._slug(job.get("title", "application"))
        company = self._slug(job.get("company", "job"))

        directory = Path(
            self.runner.config.application.tailored_resume_directory
        )
        return str(directory / f"{company}_{title}.pdf")

    def _ensure_job_registered(self, job: dict) -> str:
        """Register the ranked job once and return its stable job id."""

        existing_id = str(job.get("job_id", "") or "").strip()
        if existing_id and self.runner.job_store.get_job(existing_id) is not None:
            return existing_id

        return self.runner.job_store.add_job(
            dict(job),
            status="discovered",
        )

    def prepare_application_for_job(
        self,
        ranked_result: dict,
        *,
        page: Any,
        fields: dict,
        resume_output_path: Optional[str] = None,
    ) -> dict:
        """
        Prepare an application using the exact ranked job and the
        resume selected by the matching pipeline.

        Preparation includes tailoring/generating the resume,
        opening the job URL, filling fields, uploading the tailored
        resume, and validating the form. It NEVER submits.
        """

        if not isinstance(ranked_result, dict):
            raise TypeError("ranked_result must be a dictionary.")

        if page is None:
            raise ValueError("page cannot be None.")

        if not isinstance(fields, dict):
            raise TypeError("fields must be a dictionary.")

        job = ranked_result.get("job")
        if not isinstance(job, dict):
            raise ValueError(
                "ranked_result does not contain a valid job."
            )

        if not str(job.get("url", "") or "").strip():
            raise ValueError("Selected job must contain a URL.")

        selected_resume = self._resolve_selected_resume_data(
            ranked_result
        )

        output_path = (
            str(resume_output_path).strip()
            if resume_output_path is not None
            else self._default_application_resume_path(ranked_result)
        )

        if not output_path:
            raise ValueError("resume_output_path cannot be empty.")

        job_id = self._ensure_job_registered(job)

        prepared = self.application_engine.prepare_application(
            ranked_result,
            resume=selected_resume,
            resume_output_path=output_path,
            fields=fields,
        )

        result = dict(prepared or {})
        result["job"] = job
        result["job_id"] = job_id
        result["ranked_result"] = ranked_result
        result["selected_resume"] = selected_resume
        result["source_resume_path"] = self.resolve_resume_path(
            ranked_result
        )
        result["ranking_score"] = ranked_result.get(
            "ranking_score",
            0.0,
        )

        if result.get("success"):
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
        page_factory,
        fields: dict,
        resume_output_directory: Optional[str] = None,
    ) -> list[dict]:
        """
        Prepare multiple applications without submitting them.

        `page_factory(ranked_result)` must return the browser page to
        use for that job. A page is intentionally supplied by the
        caller so browser/session ownership remains explicit.
        """

        prepared: list[dict] = []
        for ranked_result in ranked_results or []:
            if not isinstance(ranked_result, dict):
                continue

            output_path = None
            if resume_output_directory:
                job = ranked_result.get("job", {})
                filename = (
                    f"{self._slug(job.get('company', 'job'))}_"
                    f"{self._slug(job.get('title', 'application'))}.pdf"
                )
                output_path = str(
                    Path(resume_output_directory) / filename
                )

            page = page_factory(ranked_result)
            prepared.append(
                self.prepare_application_for_job(
                    ranked_result,
                    page=page,
                    fields=fields,
                    resume_output_path=output_path,
                )
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

        confirm=False is an unconditional safety barrier.
        """

        if not isinstance(prepared_application, dict):
            raise TypeError(
                "prepared_application must be a dictionary."
            )

        job_id = str(
            prepared_application.get("job_id", "") or ""
        ).strip()

        if not confirm:
            return {
                "success": False,
                "status": "confirmation_required",
                "submitted": False,
                "job_id": job_id,
            }

        result = self.application_engine.submit_application(
            prepared_application,
            confirm=True,
        )

        submitted = bool(
            result.get("submitted", result.get("success", False))
        ) if isinstance(result, dict) else bool(result)

        if job_id:
            self.runner.job_store.update_status(
                job_id,
                "applied" if submitted else "application_failed",
            )

        if isinstance(result, dict):
            output = dict(result)
        else:
            output = {
                "success": submitted,
                "status": "applied" if submitted else "application_failed",
            }

        output.setdefault("submitted", submitted)
        output["job_id"] = job_id
        return output

    def run_application(
        self,
        ranked_result: dict,
        *,
        page: Any,
        fields: dict,
        resume_output_path: Optional[str] = None,
        confirm: bool = False,
    ) -> dict:
        """Prepare an application and optionally submit after confirmation."""

        prepared = self.prepare_application_for_job(
            ranked_result,
            page=page,
            fields=fields,
            resume_output_path=resume_output_path,
        )

        if not prepared.get("success"):
            return {
                **prepared,
                "submitted": False,
            }

        if not confirm:
            return {
                **prepared,
                "status": "confirmation_required",
                "submitted": False,
            }

        submission = self.submit_application(
            prepared,
            confirm=True,
        )

        return {
            **prepared,
            **submission,
            "submitted": bool(
                submission.get("submitted", submission.get("success", False))
            ),
        }

    # ========================================================
    # COMPLETE SAFE RUN
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
        """Run discovery through recruiter-outreach preparation."""

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
            "status": "ranked" if ranked else "no_matching_jobs",
            "jobs": ranked,
            "count": len(ranked),
            "outreach": [],
        }

        if not ranked or not prepare_outreach:
            return result

        prepared = self.prepare_outreach(
            ranked,
            candidate=candidate,
            resume_path=resume_path,
        )

        result["outreach"] = prepared
        result["status"] = "outreach_prepared" if prepared else "ranked"
        return result

    # ========================================================
    # EXPLICIT SEND
    # ========================================================

    def send_outreach(
        self,
        prepared_result: dict,
        *,
        confirm: bool = False,
    ) -> OutreachResult:
        """Send one previously prepared outreach message."""

        if not isinstance(prepared_result, dict):
            raise TypeError("prepared_result must be a dictionary.")

        job = prepared_result.get("job")
        if not isinstance(job, dict):
            raise ValueError(
                "prepared_result does not contain a valid job."
            )

        contacts = prepared_result.get("contacts", [])
        if not isinstance(contacts, list):
            contacts = list(contacts or [])

        resume_path = prepared_result.get("resume_path")

        return self.outreach_pipeline.send_outreach(
            contacts=contacts,
            job=job,
            resume_path=resume_path,
            confirm=confirm,
        )

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _outreach_to_dict(
        outreach: Optional[OutreachResult],
    ) -> Optional[dict]:
        if outreach is None:
            return None
        return asdict(outreach)


__all__ = ["EndToEndPipeline"]
