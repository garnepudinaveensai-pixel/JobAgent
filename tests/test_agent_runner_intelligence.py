from unittest.mock import MagicMock

import pytest

from app.config import JobAgentConfig
from app.core.agent_runner import AgentRunner
from app.core.sources.job_source_manager import JobSourceManager


class FakeSource:

    name = "fake"

    def is_available(self):
        return True

    def get_supported_options(self):
        return set()

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
                    "https://example.com/job/1"
                ),
                "description": (
                    "Electrical engineering "
                    "role requiring Python."
                ),
            },
            {
                "title": "Automation Engineer",
                "company": "Automation Company",
                "location": "Bangalore",
                "url": (
                    "https://example.com/job/2"
                ),
                "description": (
                    "Industrial automation "
                    "engineering role."
                ),
            },
        ]


def make_runner(match_pipeline):
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


def test_discover_match_and_rank_requires_pipeline():

    runner = AgentRunner(
        config=JobAgentConfig(),
        job_source_manager=JobSourceManager(),
    )

    with pytest.raises(
        RuntimeError,
        match="JobMatchPipeline is not configured",
    ):
        runner.discover_match_and_rank_from_sources(
            keywords="Electrical Engineer"
        )


def test_discover_match_and_rank_returns_ranked_results():

    match_pipeline = MagicMock()

    match_pipeline.match_jobs.return_value = [
        {
            "job": {
                "title": "Electrical Engineer",
                "job_title": "Electrical Engineer",
                "company": "Example Company",
                "location": "Hyderabad",
                "required_skills": [
                    "Python",
                    "Electrical Engineering",
                ],
                "preferred_skills": [],
                "all_keywords": [
                    "Python",
                    "Electrical Engineering",
                ],
                "experience_requirements": (
                    "fresher"
                ),
            },
            "resume": {
                "filename": (
                    "technical_resume.pdf"
                ),
                "name": "Test Candidate",
            },
            "match": {
                "resume_score": 90.0,
                "match_score": 90.0,
                "eligible": True,
                "matched_required_skills": [
                    "Python",
                    "Electrical Engineering",
                ],
                "missing_required_skills": [],
                "matched_preferred_skills": [],
                "missing_preferred_skills": [],
                "resume_keywords": [
                    "Python",
                    "Electrical Engineering",
                ],
            },
        }
    ]

    runner = make_runner(
        match_pipeline
    )

    results = (
        runner
        .discover_match_and_rank_from_sources(
            keywords="Electrical Engineer",
            location="Hyderabad",
        )
    )

    assert len(results) == 1

    result = results[0]

    assert (
        result["job"]["title"]
        == "Electrical Engineer"
    )

    assert (
        "ranking_score"
        in result
    )

    assert (
        isinstance(
            result["ranking_score"],
            (int, float),
        )
    )

    assert (
        0 <= result["ranking_score"] <= 100
    )

    assert (
        "ranking_breakdown"
        in result
    )


def test_minimum_score_filters_results():

    match_pipeline = MagicMock()

    match_pipeline.match_jobs.return_value = [
        {
            "job": {
                "title": "Electrical Engineer",
                "company": "Example",
                "location": "Hyderabad",
                "required_skills": [],
                "preferred_skills": [],
                "all_keywords": [],
                "experience_requirements": "",
            },
            "resume": {
                "filename": "technical_resume.pdf",
            },
            "match": {
                "resume_score": 90,
                "match_score": 90,
                "eligible": True,
            },
        }
    ]

    runner = make_runner(
        match_pipeline
    )

    results = (
        runner
        .discover_match_and_rank_from_sources(
            keywords="Electrical Engineer",
            min_score=50,
        )
    )

    assert len(results) == 1

    assert (
        results[0]["ranking_score"]
        >= 50
    )


def test_eligible_only_filters_ineligible_results():

    match_pipeline = MagicMock()

    match_pipeline.match_jobs.return_value = [
        {
            "job": {
                "title": "Electrical Engineer",
                "company": "Example",
                "location": "Hyderabad",
                "required_skills": [],
                "preferred_skills": [],
                "all_keywords": [],
            },
            "resume": {
                "filename": "technical_resume.pdf",
            },
            "match": {
                "resume_score": 90,
                "match_score": 90,
                "eligible": False,
            },
        }
    ]

    runner = make_runner(
        match_pipeline
    )

    results = (
        runner
        .discover_match_and_rank_from_sources(
            keywords="Electrical Engineer",
            eligible_only=True,
        )
    )

    assert results == []


def test_limit_restricts_results():

    match_pipeline = MagicMock()

    match_pipeline.match_jobs.return_value = [
        {
            "job": {
                "title": "Electrical Engineer",
                "company": "Example A",
                "location": "Hyderabad",
                "required_skills": [],
                "preferred_skills": [],
                "all_keywords": [],
            },
            "resume": {
                "filename": "technical_resume.pdf",
            },
            "match": {
                "resume_score": 90,
                "match_score": 90,
                "eligible": True,
            },
        },
        {
            "job": {
                "title": "Automation Engineer",
                "company": "Example B",
                "location": "Bangalore",
                "required_skills": [],
                "preferred_skills": [],
                "all_keywords": [],
            },
            "resume": {
                "filename": "automation_resume.pdf",
            },
            "match": {
                "resume_score": 80,
                "match_score": 80,
                "eligible": True,
            },
        },
    ]

    runner = make_runner(
        match_pipeline
    )

    results = (
        runner
        .discover_match_and_rank_from_sources(
            keywords="Engineer",
            limit=1,
        )
    )

    assert len(results) == 1