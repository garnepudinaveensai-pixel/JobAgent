from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional
import inspect


class JobApplicationEngine:
    """
    Top-level orchestration layer for JobAgent.

    Responsibilities
    ----------------
    Discovery
        ↓
    Deduplication
        ↓
    Resume matching
        ↓
    Job ranking
        ↓
    Job selection
        ↓
    Resume tailoring
        ↓
    Resume PDF generation
        ↓
    Application preparation
        ↓
    Explicit confirmation
        ↓
    Application submission
        ↓
    Application status

    This class intentionally delegates the individual operations
    to existing project components.

    It does NOT:
        - implement job scraping
        - implement resume matching
        - implement ranking mathematics
        - implement browser automation
        - invent resume information
        - silently submit applications

    Submission always requires:
        confirm=True
    """

    def __init__(
        self,
        *,
        job_source_manager=None,
        deduplicator=None,
        job_match_pipeline=None,
        job_ranker=None,
        application_workflow=None,
        job_store=None,
    ):
        self.job_source_manager = job_source_manager
        self.deduplicator = deduplicator
        self.job_match_pipeline = job_match_pipeline
        self.job_ranker = job_ranker
        self.application_workflow = application_workflow
        self.job_store = job_store

    # ============================================================
    # VALIDATION
    # ============================================================

    @staticmethod
    def _validate_keywords(keywords: str) -> str:
        if not isinstance(keywords, str):
            raise TypeError(
                "keywords must be a string."
            )

        keywords = keywords.strip()

        if not keywords:
            raise ValueError(
                "keywords cannot be empty."
            )

        return keywords

    @staticmethod
    def _validate_limit(
        limit: Optional[int],
    ) -> None:
        if limit is None:
            return

        if not isinstance(limit, int):
            raise TypeError(
                "limit must be an integer or None."
            )

        if limit < 1:
            raise ValueError(
                "limit must be at least 1."
            )

    @staticmethod
    def _validate_min_score(
        min_score: float,
    ) -> None:
        if not isinstance(
            min_score,
            (int, float),
        ):
            raise TypeError(
                "min_score must be numeric."
            )

        if min_score < 0:
            raise ValueError(
                "min_score cannot be negative."
            )

        if min_score > 100:
            raise ValueError(
                "min_score cannot exceed 100."
            )

    @staticmethod
    def _validate_job_result(
        result: Any,
    ) -> bool:
        if not isinstance(result, dict):
            return False

        job = result.get("job")

        return isinstance(job, dict)

    # ============================================================
    # DISCOVERY
    # ============================================================

    def discover_jobs(
        self,
        keywords: str,
        location: Optional[str] = None,
        **source_options,
    ) -> list[dict]:
        """
        Discover jobs from all configured sources.

        The source manager is expected to expose:

            search(
                keywords=...,
                location=...,
                **source_options,
            )

        Results are deduplicated when a deduplicator is configured.
        """

        keywords = self._validate_keywords(
            keywords
        )

        if self.job_source_manager is None:
            raise RuntimeError(
                "Job source manager is not configured."
            )

        search = getattr(
            self.job_source_manager,
            "search",
            None,
        )

        if not callable(search):
            raise AttributeError(
                "Job source manager does not provide search()."
            )

        jobs = search(
            keywords=keywords,
            location=location,
            **source_options,
        )

        if jobs is None:
            return []

        jobs = list(jobs)

        if self.deduplicator is not None:
            deduplicate = getattr(
                self.deduplicator,
                "deduplicate",
                None,
            )

            if callable(deduplicate):
                jobs = list(
                    deduplicate(jobs) or []
                )

        return [
            job
            for job in jobs
            if isinstance(job, dict)
        ]

    # ============================================================
    # MATCHING
    # ============================================================

    def match_jobs(
        self,
        jobs: Optional[Iterable[dict]],
    ) -> list[dict]:
        """
        Match discovered jobs against available resumes.

        Delegates to JobMatchPipeline.match_jobs().
        """

        if not jobs:
            return []

        if self.job_match_pipeline is None:
            raise RuntimeError(
                "Job match pipeline is not configured."
            )

        match_jobs = getattr(
            self.job_match_pipeline,
            "match_jobs",
            None,
        )

        if not callable(match_jobs):
            raise AttributeError(
                "Job match pipeline does not provide match_jobs()."
            )

        results = match_jobs(
            list(jobs)
        )

        if results is None:
            return []

        return [
            result
            for result in results
            if self._validate_job_result(result)
        ]

    # ============================================================
    # RANKING
    # ============================================================

    def rank_jobs(
        self,
        matched_results: Optional[list[dict]],
        *,
        min_score: float = 0.0,
        eligible_only: bool = False,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """
        Rank matched jobs using the existing JobRanker.

        The existing JobRanker normalizes its ranking score to
        0-100 and preserves the original result fields.
        """

        self._validate_min_score(
            min_score
        )

        self._validate_limit(
            limit
        )

        if not matched_results:
            return []

        if self.job_ranker is None:
            raise RuntimeError(
                "Job ranker is not configured."
            )

        # Prefer filter_and_rank because it handles:
        #   min_score
        #   eligible_only
        #   limit
        filter_and_rank = getattr(
            self.job_ranker,
            "filter_and_rank",
            None,
        )

        if callable(filter_and_rank):
            ranked = filter_and_rank(
                matched_results,
                min_score=min_score,
                eligible_only=eligible_only,
                limit=limit,
            )

            return list(
                ranked or []
            )

        # Compatibility fallback for rank-only implementations.
        rank = getattr(
            self.job_ranker,
            "rank",
            None,
        )

        if not callable(rank):
            raise AttributeError(
                "Job ranker does not provide rank() "
                "or filter_and_rank()."
            )

        ranked = list(
            rank(matched_results) or []
        )

        filtered = []

        for result in ranked:
            score = result.get(
                "ranking_score",
                0.0,
            )

            if score < min_score:
                continue

            if eligible_only:
                match = result.get(
                    "match",
                    {},
                )

                if not isinstance(
                    match,
                    dict,
                ):
                    continue

                if not match.get(
                    "eligible",
                    False,
                ):
                    continue

            filtered.append(result)

        if limit is not None:
            filtered = filtered[:limit]

        return filtered

    # ============================================================
    # DISCOVER + MATCH + RANK
    # ============================================================

    def discover_and_rank(
        self,
        keywords: str,
        location: Optional[str] = None,
        *,
        min_score: float = 0.0,
        eligible_only: bool = False,
        limit: Optional[int] = None,
        **source_options,
    ) -> list[dict]:
        """
        Execute the complete discovery intelligence pipeline.

        Flow:

            sources
              ↓
            deduplication
              ↓
            matching
              ↓
            ranking
              ↓
            filtering
        """

        jobs = self.discover_jobs(
            keywords=keywords,
            location=location,
            **source_options,
        )

        if not jobs:
            return []

        matched = self.match_jobs(
            jobs
        )

        if not matched:
            return []

        return self.rank_jobs(
            matched,
            min_score=min_score,
            eligible_only=eligible_only,
            limit=limit,
        )

    # ============================================================
    # BEST JOB
    # ============================================================

    def select_best_job(
        self,
        ranked_results: Optional[list[dict]],
    ) -> Optional[dict]:
        """
        Return the highest-ranked result.

        JobRanker already sorts highest → lowest, but this method
        defensively checks the ranking score.
        """

        if not ranked_results:
            return None

        valid_results = [
            result
            for result in ranked_results
            if self._validate_job_result(result)
        ]

        if not valid_results:
            return None

        return max(
            valid_results,
            key=lambda result: float(
                result.get(
                    "ranking_score",
                    0.0,
                )
            ),
        )

    # ============================================================
    # RESUME EXTRACTION
    # ============================================================

    @staticmethod
    def extract_selected_resume(
        ranked_result: dict,
    ) -> dict:
        """
        Extract the selected resume metadata from a ranked result.

        JobMatchPipeline produces:

            {
                "job": ...,
                "resume": ...,
                "match": ...
            }
        """

        if not isinstance(
            ranked_result,
            dict,
        ):
            raise TypeError(
                "ranked_result must be a dictionary."
            )

        resume = ranked_result.get(
            "resume"
        )

        if not isinstance(
            resume,
            dict,
        ):
            raise ValueError(
                "Ranked result does not contain "
                "a valid resume."
            )

        return resume

    # ============================================================
    # APPLICATION PREPARATION
    # ============================================================

    def prepare_application(
        self,
        ranked_result: dict,
        *,
        page: Any = None,
        resume: Optional[dict] = None,
        resume_output_path: str,
        fields: Optional[dict] = None,
    ) -> dict:
        """
        Prepare an application for the selected job.

        This delegates to ApplicationWorkflow.prepare_application().

        Expected ApplicationWorkflow API:

            prepare_application(
                page=page,
                job=job,
                resume=resume,
                fields=fields,
                resume_output_path=path,
            )

        ``page`` is optional at this engine boundary for backwards
        compatibility with non-browser workflow doubles.  When a
        browser-aware workflow accepts ``page`` and a page is supplied,
        the page is forwarded to it.

        The workflow itself performs:

            resume tailoring
            ↓
            PDF generation
            ↓
            application page opening
            ↓
            field preparation
            ↓
            resume upload

        No submission occurs here.
        """

        if self.application_workflow is None:
            raise RuntimeError(
                "Application workflow is not configured."
            )

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
                "ranked_result does not contain a valid job."
            )

        if resume is None:
            resume = ranked_result.get(
                "match",
                {},
            ).get(
                "selected_resume"
            )

        if resume is None:
            raise ValueError(
                "No parsed resume data was supplied. "
                "Pass resume=... when preparing an application."
            )

        if not isinstance(
            resume,
            dict,
        ):
            raise TypeError(
                "resume must be a dictionary."
            )

        if not isinstance(
            resume_output_path,
            str,
        ):
            raise TypeError(
                "resume_output_path must be a string."
            )

        if not resume_output_path.strip():
            raise ValueError(
                "resume_output_path cannot be empty."
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

        prepare = getattr(
            self.application_workflow,
            "prepare_application",
            None,
        )

        if not callable(prepare):
            raise AttributeError(
                "Application workflow does not provide "
                "prepare_application()."
            )

        # The browser-aware ApplicationWorkflow requires a Playwright
        # page, while older injected test doubles and lightweight
        # workflows may not accept one.  Build the call from the actual
        # callable signature instead of catching TypeError from inside
        # the workflow (which could hide a real application bug).
        prepare_kwargs = {
            "job": job,
            "resume": resume,
            "fields": fields,
            "resume_output_path": resume_output_path,
        }

        if page is not None:
            try:
                parameters = inspect.signature(
                    prepare
                ).parameters
            except (TypeError, ValueError):
                parameters = {}

            accepts_page = (
                "page" in parameters
                or any(
                    parameter.kind
                    == inspect.Parameter.VAR_KEYWORD
                    for parameter in parameters.values()
                )
            )

            if accepts_page:
                prepare_kwargs["page"] = page

        result = prepare(
            **prepare_kwargs
        )

        if result is None:
            return {}

        if not isinstance(
            result,
            dict,
        ):
            raise TypeError(
                "Application workflow returned an "
                "unexpected result type."
            )

        # Preserve orchestration metadata.
        prepared = dict(result)

        prepared.setdefault(
            "job",
            job,
        )

        prepared.setdefault(
            "selected_resume",
            resume,
        )

        prepared.setdefault(
            "ranking_score",
            ranked_result.get(
                "ranking_score",
                0.0,
            ),
        )

        prepared.setdefault(
            "ranked_result",
            ranked_result,
        )

        return prepared

    # ============================================================
    # SUBMISSION
    # ============================================================

    def submit_application(
        self,
        prepared_application: dict,
        *,
        confirm: bool = False,
    ) -> dict:
        """
        Submit a prepared application.

        SAFETY RULE
        -----------
        confirm=False ALWAYS prevents submission.

        This method never converts False to True automatically.
        """

        if not isinstance(
            prepared_application,
            dict,
        ):
            raise TypeError(
                "prepared_application must be a dictionary."
            )

        if not confirm:
            return {
                "success": False,
                "status": "confirmation_required",
                "submitted": False,
            }

        if self.application_workflow is None:
            raise RuntimeError(
                "Application workflow is not configured."
            )

        submit = getattr(
            self.application_workflow,
            "submit",
            None,
        )

        if not callable(submit):
            raise AttributeError(
                "Application workflow does not provide submit()."
            )

        result = submit(
            prepared_application,
            confirm=True,
        )

        if result is None:
            return {
                "success": False,
                "status": "submission_returned_no_result",
                "submitted": False,
            }

        if isinstance(
            result,
            dict,
        ):
            submitted = dict(result)

            submitted.setdefault(
                "submitted",
                bool(
                    submitted.get(
                        "success",
                        False,
                    )
                ),
            )

            return submitted

        return {
            "success": bool(result),
            "status": (
                "applied"
                if result
                else "submission_failed"
            ),
            "submitted": bool(result),
        }

    # ============================================================
    # COMPLETE PREPARATION
    # ============================================================

    def prepare_top_application(
        self,
        ranked_results: list[dict],
        *,
        resume: Optional[dict] = None,
        resume_output_path: str,
        fields: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Select the highest-ranked job and prepare its application.
        """

        best = self.select_best_job(
            ranked_results
        )

        if best is None:
            return None

        return self.prepare_application(
            best,
            resume=resume,
            resume_output_path=resume_output_path,
            fields=fields,
        )

    # ============================================================
    # COMPLETE PIPELINE
    # ============================================================

    def run(
        self,
        keywords: str,
        location: Optional[str] = None,
        *,
        min_score: float = 0.0,
        eligible_only: bool = False,
        limit: Optional[int] = 10,
        resume: Optional[dict] = None,
        resume_output_path: Optional[str] = None,
        fields: Optional[dict] = None,
        confirm: bool = False,
        prepare_application: bool = False,
        **source_options,
    ) -> dict:
        """
        Run the complete intelligent pipeline.

        By default:

            discovery
            ↓
            matching
            ↓
            ranking

        If prepare_application=True:

            ranking
              ↓
            application preparation

        If confirm=True:

            application preparation
              ↓
            submission

        IMPORTANT:
            confirm=True only has an effect when
            prepare_application=True.
        """

        ranked = self.discover_and_rank(
            keywords=keywords,
            location=location,
            min_score=min_score,
            eligible_only=eligible_only,
            limit=limit,
            **source_options,
        )

        result = {
            "success": True,
            "status": (
                "jobs_ranked"
                if ranked
                else "no_matching_jobs"
            ),
            "jobs": ranked,
            "count": len(ranked),
            "selected_job": self.select_best_job(
                ranked
            ),
            "prepared_application": None,
            "submission": None,
        }

        if not prepare_application:
            return result

        if not resume_output_path:
            raise ValueError(
                "resume_output_path is required when "
                "prepare_application=True."
            )

        prepared = self.prepare_top_application(
            ranked,
            resume=resume,
            resume_output_path=resume_output_path,
            fields=fields,
        )

        result["prepared_application"] = prepared

        if prepared is None:
            result["status"] = (
                "no_application_prepared"
            )
            return result

        result["status"] = (
            "application_prepared"
        )

        if confirm:
            submission = self.submit_application(
                prepared,
                confirm=True,
            )

            result["submission"] = submission

            if submission.get(
                "submitted",
                False,
            ):
                result["status"] = (
                    "application_submitted"
                )
            else:
                result["status"] = (
                    "submission_failed"
                )

        return result

    # ============================================================
    # STORAGE
    # ============================================================

    def store_jobs(
        self,
        jobs: Optional[Iterable[dict]],
    ) -> list[str]:
        """
        Store jobs using the existing JobStore.

        Invalid jobs are skipped.
        """

        if not jobs:
            return []

        if self.job_store is None:
            raise RuntimeError(
                "Job store is not configured."
            )

        add_job = getattr(
            self.job_store,
            "add_job",
            None,
        )

        if not callable(add_job):
            raise AttributeError(
                "Job store does not provide add_job()."
            )

        ids = []

        for job in jobs:
            if not isinstance(
                job,
                dict,
            ):
                continue

            try:
                job_id = add_job(
                    job,
                    status="discovered",
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            ids.append(
                job_id
            )

        return ids

    # ============================================================
    # APPLICATION STATUS
    # ============================================================

    def update_application_status(
        self,
        job_id: str,
        status: str,
        details: Optional[dict] = None,
    ) -> bool:
        """
        Delegate application status updates to the configured
        ApplicationPipeline/compatible object.
        """

        if self.application_workflow is not None:
            update = getattr(
                self.application_workflow,
                "update_application_status",
                None,
            )

            if callable(update):
                return bool(
                    update(
                        job_id=job_id,
                        status=status,
                        details=details,
                    )
                )

        raise RuntimeError(
            "No application status updater is configured."
        )

    def get_application_status(
        self,
        job_id: str,
    ) -> Optional[str]:
        """
        Delegate application status retrieval.
        """

        if self.application_workflow is not None:
            getter = getattr(
                self.application_workflow,
                "get_application_status",
                None,
            )

            if callable(getter):
                return getter(
                    job_id
                )

        raise RuntimeError(
            "No application status getter is configured."
        )