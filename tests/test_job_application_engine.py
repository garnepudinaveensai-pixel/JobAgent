from __future__ import annotations

from pathlib import Path

import pytest

from app.core.job_application_engine import (
    JobApplicationEngine,
)


# ============================================================
# TEST FAKES
# ============================================================


class FakeSourceManager:
    def __init__(self, jobs=None):
        self.jobs = list(jobs or [])
        self.calls = []

    def search(
        self,
        keywords,
        location=None,
        **source_options,
    ):
        self.calls.append(
            {
                "keywords": keywords,
                "location": location,
                "source_options": source_options,
            }
        )

        return list(self.jobs)


class FakeDeduplicator:
    def __init__(self):
        self.calls = []

    def deduplicate(self, jobs):
        self.calls.append(
            list(jobs)
        )

        unique = []
        seen = set()

        for job in jobs:
            key = job.get(
                "job_id"
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append(job)

        return unique


class FakeMatchPipeline:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.calls = []

    def match_jobs(self, jobs):
        self.calls.append(
            list(jobs)
        )

        return list(self.results)


class FakeRanker:
    def __init__(self):
        self.calls = []

    def filter_and_rank(
        self,
        results,
        *,
        min_score=0.0,
        eligible_only=False,
        limit=None,
    ):
        self.calls.append(
            {
                "results": list(results),
                "min_score": min_score,
                "eligible_only": eligible_only,
                "limit": limit,
            }
        )

        filtered = []

        for result in results:
            score = result.get(
                "ranking_score",
                0,
            )

            if score < min_score:
                continue

            if eligible_only:
                match = result.get(
                    "match",
                    {},
                )

                if not match.get(
                    "eligible",
                    False,
                ):
                    continue

            filtered.append(result)

        filtered.sort(
            key=lambda item: item.get(
                "ranking_score",
                0,
            ),
            reverse=True,
        )

        if limit is not None:
            filtered = filtered[:limit]

        return filtered


class FakeApplicationWorkflow:
    def __init__(self):
        self.prepare_calls = []
        self.submit_calls = []

    def prepare_application(
        self,
        *,
        job,
        resume,
        fields,
        resume_output_path,
    ):
        self.prepare_calls.append(
            {
                "job": job,
                "resume": resume,
                "fields": fields,
                "resume_output_path": resume_output_path,
            }
        )

        Path(
            resume_output_path
        ).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        Path(
            resume_output_path
        ).write_text(
            "fake resume",
            encoding="utf-8",
        )

        return {
            "success": True,
            "status": "ready_for_submission",
            "resume_pdf": resume_output_path,
            "resume_uploaded": True,
            "submitter": object(),
        }

    def submit(
        self,
        prepared_application,
        confirm=False,
    ):
        self.submit_calls.append(
            {
                "prepared_application": prepared_application,
                "confirm": confirm,
            }
        )

        if not confirm:
            return {
                "success": False,
                "status": "confirmation_required",
                "submitted": False,
            }

        return {
            "success": True,
            "status": "applied",
            "submitted": True,
        }


class FakeJobStore:
    def __init__(self):
        self.jobs = []
        self.counter = 0

    def add_job(
        self,
        job,
        status="discovered",
    ):
        self.counter += 1

        job = dict(job)

        job_id = job.get(
            "job_id",
            f"job-{self.counter}",
        )

        job["job_id"] = job_id
        job["status"] = status

        self.jobs.append(job)

        return job_id


# ============================================================
# TEST DATA
# ============================================================


def make_job(
    job_id="job-1",
    title="Automation Engineer",
):
    return {
        "job_id": job_id,
        "title": title,
        "company": "Example Technologies",
        "location": "Hyderabad",
        "url": (
            "https://example.com/jobs/"
            f"{job_id}"
        ),
        "description": (
            "Automation engineering role."
        ),
    }


def make_match_result(
    job_id="job-1",
    score=80,
    eligible=True,
):
    job = make_job(
        job_id=job_id
    )

    resume = {
        "filename": "automation_resume.pdf",
        "name": "Naveen Sai",
        "skills": [
            "C",
            "Embedded C",
            "MATLAB",
            "Simulink",
        ],
    }

    return {
        "job": job,
        "resume": {
            "filename": (
                "automation_resume.pdf"
            ),
            "name": "Naveen Sai",
        },
        "match": {
            "eligible": eligible,
            "match_score": score,
            "selected_resume": resume,
        },
        "ranking_score": score,
    }


def make_engine(
    jobs=None,
    matched_results=None,
):
    source_manager = FakeSourceManager(
        jobs=jobs
    )

    deduplicator = FakeDeduplicator()

    matcher = FakeMatchPipeline(
        results=matched_results
    )

    ranker = FakeRanker()

    workflow = FakeApplicationWorkflow()

    store = FakeJobStore()

    engine = JobApplicationEngine(
        job_source_manager=source_manager,
        deduplicator=deduplicator,
        job_match_pipeline=matcher,
        job_ranker=ranker,
        application_workflow=workflow,
        job_store=store,
    )

    return (
        engine,
        source_manager,
        deduplicator,
        matcher,
        ranker,
        workflow,
        store,
    )


# ============================================================
# VALIDATION
# ============================================================


def test_empty_keywords_are_rejected():
    engine, *_ = make_engine()

    with pytest.raises(ValueError):
        engine.discover_jobs("")


def test_whitespace_keywords_are_rejected():
    engine, *_ = make_engine()

    with pytest.raises(ValueError):
        engine.discover_jobs("   ")


def test_non_string_keywords_are_rejected():
    engine, *_ = make_engine()

    with pytest.raises(TypeError):
        engine.discover_jobs(None)


def test_invalid_limit_is_rejected():
    engine, *_ = make_engine()

    with pytest.raises(ValueError):
        engine.rank_jobs(
            [],
            limit=0,
        )


def test_invalid_min_score_is_rejected():
    engine, *_ = make_engine()

    with pytest.raises(ValueError):
        engine.rank_jobs(
            [],
            min_score=101,
        )


# ============================================================
# DISCOVERY
# ============================================================


def test_discover_jobs_calls_source_manager():
    jobs = [
        make_job("job-1"),
        make_job("job-2"),
    ]

    (
        engine,
        source_manager,
        deduplicator,
        *_,
    ) = make_engine(
        jobs=jobs
    )

    result = engine.discover_jobs(
        keywords="Electrical Engineer",
        location="Hyderabad",
        source="all",
    )

    assert len(result) == 2

    assert (
        source_manager.calls[0]["keywords"]
        == "Electrical Engineer"
    )

    assert (
        source_manager.calls[0]["location"]
        == "Hyderabad"
    )

    assert (
        source_manager.calls[0]["source_options"]
        == {"source": "all"}
    )

    assert len(
        deduplicator.calls
    ) == 1


def test_discover_jobs_deduplicates_results():
    jobs = [
        make_job("job-1"),
        make_job("job-1"),
        make_job("job-2"),
    ]

    engine, *_ = make_engine(
        jobs=jobs
    )

    result = engine.discover_jobs(
        "Electrical Engineer"
    )

    assert len(result) == 2


def test_discover_jobs_returns_empty_when_source_returns_none():
    engine, source_manager, *_ = make_engine()

    source_manager.jobs = []

    result = engine.discover_jobs(
        "Electrical Engineer"
    )

    assert result == []


def test_discovery_forwards_source_options():
    jobs = [
        make_job("job-1")
    ]

    (
        engine,
        source_manager,
        *_,
    ) = make_engine(
        jobs=jobs
    )

    engine.discover_jobs(
        keywords="Automation",
        location="Hyderabad",
        max_results=25,
        source_names=[
            "indeed",
            "naukri",
        ],
    )

    call = source_manager.calls[0]

    assert call["source_options"] == {
        "max_results": 25,
        "source_names": [
            "indeed",
            "naukri",
        ],
    }


# ============================================================
# MATCHING
# ============================================================


def test_match_jobs_delegates_to_match_pipeline():
    jobs = [
        make_job("job-1"),
    ]

    matches = [
        make_match_result("job-1")
    ]

    (
        engine,
        _,
        _,
        matcher,
        *_,
    ) = make_engine(
        jobs=jobs,
        matched_results=matches,
    )

    result = engine.match_jobs(
        jobs
    )

    assert result == matches

    assert (
        matcher.calls[0]
        == jobs
    )


def test_match_jobs_returns_empty_for_empty_input():
    engine, *_ = make_engine()

    assert (
        engine.match_jobs([])
        == []
    )


def test_match_jobs_requires_match_pipeline():
    engine = JobApplicationEngine()

    with pytest.raises(RuntimeError):
        engine.match_jobs(
            [make_job()]
        )


# ============================================================
# RANKING
# ============================================================


def test_rank_jobs_uses_ranker():
    results = [
        make_match_result(
            "job-1",
            score=70,
        ),
        make_match_result(
            "job-2",
            score=90,
        ),
    ]

    engine, *_rest = make_engine(
        matched_results=results
    )

    result = engine.rank_jobs(
        results,
        min_score=60,
    )

    assert [
        item["ranking_score"]
        for item in result
    ] == [
        90,
        70,
    ]


def test_rank_jobs_applies_minimum_score():
    results = [
        make_match_result(
            "job-1",
            score=40,
        ),
        make_match_result(
            "job-2",
            score=85,
        ),
    ]

    engine, *_ = make_engine()

    result = engine.rank_jobs(
        results,
        min_score=60,
    )

    assert len(result) == 1
    assert (
        result[0]["job"]["job_id"]
        == "job-2"
    )


def test_rank_jobs_applies_eligible_only():
    results = [
        make_match_result(
            "job-1",
            score=90,
            eligible=False,
        ),
        make_match_result(
            "job-2",
            score=80,
            eligible=True,
        ),
    ]

    engine, *_ = make_engine()

    result = engine.rank_jobs(
        results,
        eligible_only=True,
    )

    assert len(result) == 1

    assert (
        result[0]["job"]["job_id"]
        == "job-2"
    )


def test_rank_jobs_applies_limit():
    results = [
        make_match_result(
            "job-1",
            score=90,
        ),
        make_match_result(
            "job-2",
            score=80,
        ),
        make_match_result(
            "job-3",
            score=70,
        ),
    ]

    engine, *_ = make_engine()

    result = engine.rank_jobs(
        results,
        limit=2,
    )

    assert len(result) == 2

    assert [
        item["ranking_score"]
        for item in result
    ] == [
        90,
        80,
    ]


# ============================================================
# DISCOVERY + MATCHING + RANKING
# ============================================================


def test_discover_and_rank_runs_complete_intelligence_pipeline():
    jobs = [
        make_job("job-1"),
        make_job("job-2"),
    ]

    matches = [
        make_match_result(
            "job-1",
            score=70,
        ),
        make_match_result(
            "job-2",
            score=95,
        ),
    ]

    (
        engine,
        source_manager,
        deduplicator,
        matcher,
        ranker,
        _,
        _,
    ) = make_engine(
        jobs=jobs,
        matched_results=matches,
    )

    result = engine.discover_and_rank(
        keywords="Automation Engineer",
        location="Hyderabad",
        min_score=60,
        limit=5,
    )

    assert len(result) == 2

    assert (
        result[0]["job"]["job_id"]
        == "job-2"
    )

    assert len(
        source_manager.calls
    ) == 1

    assert len(
        deduplicator.calls
    ) == 1

    assert len(
        matcher.calls
    ) == 1

    assert len(
        ranker.calls
    ) == 1


def test_discover_and_rank_returns_empty_when_no_jobs():
    (
        engine,
        *_,
    ) = make_engine(
        jobs=[],
        matched_results=[],
    )

    result = engine.discover_and_rank(
        "Automation Engineer"
    )

    assert result == []


# ============================================================
# BEST JOB
# ============================================================


def test_select_best_job_returns_highest_score():
    results = [
        make_match_result(
            "job-1",
            score=65,
        ),
        make_match_result(
            "job-2",
            score=92,
        ),
        make_match_result(
            "job-3",
            score=75,
        ),
    ]

    engine, *_ = make_engine()

    best = engine.select_best_job(
        results
    )

    assert best is not None

    assert (
        best["job"]["job_id"]
        == "job-2"
    )


def test_select_best_job_returns_none_for_empty_input():
    engine, *_ = make_engine()

    assert (
        engine.select_best_job([])
        is None
    )


# ============================================================
# RESUME EXTRACTION
# ============================================================


def test_extract_selected_resume():
    result = make_match_result()

    engine, *_ = make_engine()

    resume = (
        engine.extract_selected_resume(
            result
        )
    )

    assert (
        resume["filename"]
        == "automation_resume.pdf"
    )


def test_extract_selected_resume_rejects_invalid_result():
    engine, *_ = make_engine()

    with pytest.raises(ValueError):
        engine.extract_selected_resume(
            {
                "job": make_job()
            }
        )


# ============================================================
# APPLICATION PREPARATION
# ============================================================


def test_prepare_application_delegates_to_workflow(
    tmp_path,
):
    result = make_match_result()

    resume = {
        "name": "Naveen Sai",
        "skills": [
            "Embedded C",
            "MATLAB",
        ],
    }

    (
        engine,
        _,
        _,
        _,
        _,
        workflow,
        _,
    ) = make_engine()

    output_path = (
        tmp_path
        / "resume.pdf"
    )

    prepared = engine.prepare_application(
        result,
        resume=resume,
        resume_output_path=str(
            output_path
        ),
        fields={
            "Name": "Naveen Sai",
            "Email": "naveen@example.com",
        },
    )

    assert (
        prepared["success"]
        is True
    )

    assert (
        prepared["status"]
        == "ready_for_submission"
    )

    assert (
        prepared["job"]
        == result["job"]
    )

    assert output_path.exists()

    assert len(
        workflow.prepare_calls
    ) == 1


def test_prepare_application_requires_resume_path():
    result = make_match_result()

    engine, *_ = make_engine()

    with pytest.raises(ValueError):
        engine.prepare_application(
            result,
            resume={},
            resume_output_path="",
        )


def test_prepare_application_rejects_invalid_job():
    engine, *_ = make_engine()

    with pytest.raises(ValueError):
        engine.prepare_application(
            {
                "resume": {}
            },
            resume={},
            resume_output_path="resume.pdf",
        )


# ============================================================
# SUBMISSION SAFETY
# ============================================================


def test_submission_requires_explicit_confirmation():
    engine, *rest = make_engine()

    workflow = rest[4]

    prepared = {
        "success": True,
        "status": "ready_for_submission",
    }

    result = engine.submit_application(
        prepared,
        confirm=False,
    )

    assert (
        result["success"]
        is False
    )

    assert (
        result["status"]
        == "confirmation_required"
    )

    assert (
        result["submitted"]
        is False
    )

    assert (
        workflow.submit_calls
        == []
    )


def test_submission_occurs_with_confirmation():
    engine, *rest = make_engine()

    workflow = rest[4]

    prepared = {
        "success": True,
        "status": "ready_for_submission",
    }

    result = engine.submit_application(
        prepared,
        confirm=True,
    )

    assert (
        result["success"]
        is True
    )

    assert (
        result["submitted"]
        is True
    )

    assert len(
        workflow.submit_calls
    ) == 1

    assert (
        workflow.submit_calls[0]["confirm"]
        is True
    )


# ============================================================
# TOP APPLICATION
# ============================================================


def test_prepare_top_application_selects_best_job(
    tmp_path,
):
    results = [
        make_match_result(
            "job-1",
            score=70,
        ),
        make_match_result(
            "job-2",
            score=95,
        ),
    ]

    engine, *rest = make_engine()

    workflow = rest[4]

    output_path = (
        tmp_path
        / "best.pdf"
    )

    prepared = engine.prepare_top_application(
        results,
        resume={
            "name": "Naveen Sai",
            "skills": [
                "MATLAB"
            ],
        },
        resume_output_path=str(
            output_path
        ),
        fields={},
    )

    assert (
        prepared["job"]["job_id"]
        == "job-2"
    )

    assert (
        len(workflow.prepare_calls)
        == 1
    )


# ============================================================
# COMPLETE RUN
# ============================================================


def test_run_only_discovers_matches_and_ranks():
    jobs = [
        make_job("job-1"),
    ]

    matches = [
        make_match_result(
            "job-1",
            score=88,
        )
    ]

    engine, *_ = make_engine(
        jobs=jobs,
        matched_results=matches,
    )

    result = engine.run(
        keywords="Automation Engineer",
        location="Hyderabad",
        limit=10,
    )

    assert (
        result["success"]
        is True
    )

    assert (
        result["status"]
        == "jobs_ranked"
    )

    assert result["count"] == 1

    assert (
        result["selected_job"]
        is not None
    )

    assert (
        result["prepared_application"]
        is None
    )

    assert (
        result["submission"]
        is None
    )


def test_run_prepares_application(
    tmp_path,
):
    jobs = [
        make_job("job-1"),
    ]

    matches = [
        make_match_result(
            "job-1",
            score=90,
        )
    ]

    engine, *rest = make_engine(
        jobs=jobs,
        matched_results=matches,
    )

    workflow = rest[4]

    output_path = (
        tmp_path
        / "generated"
        / "resume.pdf"
    )

    result = engine.run(
        keywords="Automation Engineer",
        location="Hyderabad",
        limit=1,
        resume={
            "name": "Naveen Sai",
            "skills": [
                "Embedded C",
                "MATLAB",
            ],
        },
        resume_output_path=str(
            output_path
        ),
        fields={
            "Name": "Naveen Sai"
        },
        prepare_application=True,
    )

    assert (
        result["status"]
        == "application_prepared"
    )

    assert (
        result["prepared_application"]
        is not None
    )

    assert (
        output_path.exists()
    )

    assert (
        len(workflow.prepare_calls)
        == 1
    )

    assert (
        result["submission"]
        is None
    )


def test_run_does_not_submit_without_confirmation(
    tmp_path,
):
    matches = [
        make_match_result(
            "job-1",
            score=95,
        )
    ]

    engine, *rest = make_engine(
        jobs=[
            make_job("job-1")
        ],
        matched_results=matches,
    )

    workflow = rest[4]

    result = engine.run(
        keywords="Automation Engineer",
        resume={
            "name": "Naveen Sai"
        },
        resume_output_path=str(
            tmp_path
            / "resume.pdf"
        ),
        prepare_application=True,
        confirm=False,
    )

    assert (
        result["status"]
        == "application_prepared"
    )

    assert (
        result["submission"]
        is None
    )

    assert (
        workflow.submit_calls
        == []
    )


def test_run_submits_only_after_confirmation(
    tmp_path,
):
    matches = [
        make_match_result(
            "job-1",
            score=95,
        )
    ]

    engine, *rest = make_engine(
        jobs=[
            make_job("job-1")
        ],
        matched_results=matches,
    )

    workflow = rest[4]

    result = engine.run(
        keywords="Automation Engineer",
        resume={
            "name": "Naveen Sai"
        },
        resume_output_path=str(
            tmp_path
            / "resume.pdf"
        ),
        prepare_application=True,
        confirm=True,
    )

    assert (
        result["status"]
        == "application_submitted"
    )

    assert (
        result["submission"]["submitted"]
        is True
    )

    assert (
        len(workflow.submit_calls)
        == 1
    )


# ============================================================
# STORAGE
# ============================================================


def test_store_jobs():
    engine, *rest = make_engine()

    store = rest[5]

    jobs = [
        make_job("job-1"),
        make_job("job-2"),
        "invalid",
        None,
    ]

    ids = engine.store_jobs(
        jobs
    )

    assert ids == [
        "job-1",
        "job-2",
    ]

    assert len(
        store.jobs
    ) == 2


def test_store_jobs_requires_store():
    engine = JobApplicationEngine()

    with pytest.raises(RuntimeError):
        engine.store_jobs(
            [make_job()]
        )


# ============================================================
# SAFETY / EDGE CASES
# ============================================================


def test_submission_never_happens_when_confirm_is_false():
    engine, *rest = make_engine()

    workflow = rest[4]

    prepared = {
        "success": True,
        "status": "ready_for_submission",
    }

    for value in (
        False,
        0,
        None,
        "",
    ):
        result = engine.submit_application(
            prepared,
            confirm=value,
        )

        assert (
            result["submitted"]
            is False
        )

    assert (
        workflow.submit_calls
        == []
    )


def test_engine_does_not_modify_ranked_results():
    original = make_match_result(
        "job-1",
        score=90,
    )

    results = [
        original
    ]

    engine, *_ = make_engine()

    best = engine.select_best_job(
        results
    )

    assert (
        best is original
    )

    assert (
        original["ranking_score"]
        == 90
    )


def test_run_returns_no_matching_jobs_status():
    engine, *_ = make_engine(
        jobs=[],
        matched_results=[],
    )

    result = engine.run(
        "Automation Engineer"
    )

    assert (
        result["success"]
        is True
    )

    assert (
        result["status"]
        == "no_matching_jobs"
    )

    assert (
        result["count"]
        == 0
    )