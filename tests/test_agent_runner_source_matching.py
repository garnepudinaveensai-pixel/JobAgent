from unittest.mock import MagicMock

import pytest

from app.config import JobAgentConfig
from app.core.agent_runner import AgentRunner
from app.core.sources.job_source import JobSource
from app.core.sources.job_source_manager import JobSourceManager


# ============================================================
# FAKE SOURCE
# ============================================================

class FakeSource(JobSource):

    name = "fake"

    def search(
        self,
        keywords,
        location=None,
        **options,
    ):
        return [
            {
                "title": "Electrical Engineer",
                "company": "Example Company",
                "location": "Hyderabad",
                "url": (
                    "https://example.com/jobs/1"
                ),
                "description": (
                    "Electrical engineering "
                    "role requiring Python."
                ),
            }
        ]


# ============================================================
# HELPERS
# ============================================================

def make_runner(
    match_pipeline=None,
):
    manager = JobSourceManager(
        sources=[
            FakeSource()
        ]
    )

    return AgentRunner(
        config=JobAgentConfig(),
        job_source_manager=manager,
        job_match_pipeline=match_pipeline,
    )


# ============================================================
# CONFIGURATION
# ============================================================

def test_discover_and_match_requires_pipeline():
    runner = make_runner()

    with pytest.raises(
        RuntimeError,
        match="JobMatchPipeline is not configured",
    ):
        runner.discover_and_match_from_sources(
            keywords="Electrical Engineer",
            location="Hyderabad",
        )


# ============================================================
# BASIC DISCOVERY + MATCHING
# ============================================================

def test_discover_and_match_from_sources():

    match_pipeline = MagicMock()

    match_pipeline.match_jobs.return_value = [
        {
            "job": {
                "title": "Electrical Engineer",
                "company": "Example Company",
            },
            "resume": {
                "filename": "technical_resume.pdf",
                "name": "Test Candidate",
            },
            "match": {
                "match_score": 100.0,
                "resume_score": 100.0,
                "eligible": True,
                "recommendation": "APPLY",
            },
        }
    ]

    runner = make_runner(
        match_pipeline=match_pipeline
    )

    results = (
        runner.discover_and_match_from_sources(
            keywords="Electrical Engineer",
            location="Hyderabad",
        )
    )

    assert len(results) == 1

    assert (
        results[0]["job"]["title"]
        == "Electrical Engineer"
    )

    assert (
        results[0]["resume"]["filename"]
        == "technical_resume.pdf"
    )

    assert (
        results[0]["match"]["match_score"]
        == 100.0
    )

    assert (
        results[0]["match"]["eligible"]
        is True
    )

    assert (
        results[0]["match"]["recommendation"]
        == "APPLY"
    )

    match_pipeline.match_jobs.assert_called_once()


# ============================================================
# EMPTY KEYWORDS
# ============================================================

def test_discover_and_match_rejects_empty_keywords():

    match_pipeline = MagicMock()

    runner = make_runner(
        match_pipeline=match_pipeline
    )

    with pytest.raises(
        ValueError,
        match="keywords cannot be empty",
    ):
        runner.discover_and_match_from_sources(
            keywords="   "
        )


# ============================================================
# SOURCE OPTIONS
# ============================================================

def test_discover_and_match_forwards_source_options():

    match_pipeline = MagicMock()

    match_pipeline.match_jobs.return_value = []

    runner = make_runner(
        match_pipeline=match_pipeline
    )

    results = (
        runner.discover_and_match_from_sources(
            keywords="Electrical Engineer",
            location="Hyderabad",
            board_url=(
                "https://example.com/jobs"
            ),
        )
    )

    assert results == []

    match_pipeline.match_jobs.assert_called_once()


# ============================================================
# DISCOVERY RESULT IS PASSED TO MATCHER
# ============================================================

def test_discovery_results_flow_into_matching():

    match_pipeline = MagicMock()

    match_pipeline.match_jobs.side_effect = (
        lambda jobs: [
            {
                "job": job,
                "resume": {
                    "filename": (
                        "technical_resume.pdf"
                    ),
                    "name": "Test Candidate",
                },
                "match": {
                    "match_score": 90.0,
                    "resume_score": 90.0,
                    "eligible": True,
                    "recommendation": "APPLY",
                },
            }
            for job in jobs
        ]
    )

    runner = make_runner(
        match_pipeline=match_pipeline
    )

    results = (
        runner.discover_and_match_from_sources(
            keywords="Electrical Engineer",
            location="Hyderabad",
        )
    )

    assert len(results) == 1

    job = results[0]["job"]

    assert (
        job["title"]
        == "Electrical Engineer"
    )

    assert (
        job["company"]
        == "Example Company"
    )

    assert (
        job["location"]
        == "Hyderabad"
    )

    match_pipeline.match_jobs.assert_called_once()

    passed_jobs = (
        match_pipeline
        .match_jobs
        .call_args.args[0]
    )

    assert len(passed_jobs) == 1

    assert (
        passed_jobs[0]["title"]
        == "Electrical Engineer"
    )


# ============================================================
# NO DISCOVERED JOBS
# ============================================================

def test_discover_and_match_returns_empty_when_no_jobs():

    match_pipeline = MagicMock()

    match_pipeline.match_jobs.return_value = []

    runner = make_runner(
        match_pipeline=match_pipeline
    )

    # Replace the source manager's search method so that
    # discovery produces no jobs.
    runner.job_source_manager.search = (
        MagicMock(
            return_value=[]
        )
    )

    results = (
        runner.discover_and_match_from_sources(
            keywords="Electrical Engineer",
            location="Hyderabad",
        )
    )

    assert results == []

    match_pipeline.match_jobs.assert_not_called()


# ============================================================
# MATCH PIPELINE RECEIVES DEDUPLICATED RESULTS
# ============================================================

def test_matching_uses_discovery_pipeline_output():

    match_pipeline = MagicMock()

    match_pipeline.match_jobs.side_effect = (
        lambda jobs: jobs
    )

    runner = make_runner(
        match_pipeline=match_pipeline
    )

    results = (
        runner.discover_and_match_from_sources(
            keywords="Electrical Engineer",
            location="Hyderabad",
        )
    )

    assert len(results) == 1

    assert (
        results[0]["title"]
        == "Electrical Engineer"
    )