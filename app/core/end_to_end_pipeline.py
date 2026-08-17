from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Optional

from app.core.agent_runner import AgentRunner
from app.outreach.contact_discovery import ContactDiscovery
from app.outreach.outreach_pipeline import (
    OutreachPipeline,
    OutreachResult,
)


class EndToEndPipeline:
    """
    High-level user-facing JobAgent workflow.

    Flow:

        Multi-source discovery
            ↓
        Deduplication
            ↓
        Resume matching
            ↓
        Job ranking
            ↓
        Contact discovery
            ↓
        Contact selection
            ↓
        Personalized outreach preparation

    Application preparation is available separately through
    prepare_application(). Actual external submission and email
    sending remain explicit confirmation-gated operations.

    This class coordinates existing components; it does not
    duplicate scraping, matching, ranking, contact-provider, or
    email-sending logic.
    """

    def __init__(
        self,
        runner: AgentRunner,
        contact_discovery: Optional[ContactDiscovery] = None,
        outreach_pipeline: Optional[OutreachPipeline] = None,
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
        Run the existing multi-source intelligence pipeline.
        """

        return (
            self.runner
            .discover_match_and_rank_from_sources(
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
        job: dict,
        **provider_options: Any,
    ) -> list[dict]:
        """
        Discover professional recruiter/HR contacts for a job.
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
        """
        Resolve the resume selected by JobMatchPipeline.

        Priority:

            explicit path
                ↓
            selected resume file in ResumeManager directory
                ↓
            configured master resume
        """

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

            pipeline = (
                self.runner.job_match_pipeline
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

        config = self.runner.config

        return str(
            config.application.resume_path
        ).strip()

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
        Discover contacts and prepare one personalized
        outreach message for a ranked job.

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

        contacts = self.discover_contacts(
            job,
            **provider_options,
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
                candidate=candidate or {},
                resume_path=resolved_resume,
            )
        )

        result = dict(
            ranked_result
        )

        result["contacts"] = contacts

        result["outreach"] = (
            self._outreach_to_dict(
                outreach
            )
        )

        result["resume_path"] = (
            resolved_resume
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
        Prepare outreach for every ranked result.
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
        """
        Run discovery through recruiter-outreach preparation.

        Default behavior:

            discovery
                ↓
            matching
                ↓
            ranking
                ↓
            contact discovery
                ↓
            outreach preparation

        No email is sent.
        No application is submitted.
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
        )

        result["outreach"] = prepared

        result["status"] = (
            "outreach_prepared"
            if prepared
            else "ranked"
        )

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
        """
        Send one previously prepared outreach message.

        confirm=False always prevents sending.
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
    # APPLICATION PREPARATION
    # ========================================================

    def prepare_application(
        self,
        ranked_result: dict,
        *,
        page: Any,
        fields: dict,
        resume_path: Optional[str] = None,
    ) -> dict:
        """
        Prepare a browser-based application for one ranked job.

        This does not submit the application.
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

        job_id = (
            self.runner
            .job_store
            ._job_id(job)
        )

        self.runner.job_store.add_job(
            job,
            status="discovered",
        )

        resolved_resume = (
            self.resolve_resume_path(
                ranked_result,
                explicit_path=resume_path,
            )
        )

        return (
            self.runner
            .prepare_application(
                page=page,
                job_id=job_id,
                resume_path=resolved_resume,
                fields=fields,
            )
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

        return asdict(
            outreach
        )


__all__ = [
    "EndToEndPipeline",
]