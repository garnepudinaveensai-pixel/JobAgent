import pytest
from unittest.mock import MagicMock

from app.core.job_pipeline import JobPipeline


def test_job_pipeline_creation():
    browser = MagicMock()

    pipeline = JobPipeline(
        browser
    )

    assert pipeline.browser is browser
    assert pipeline.discovery is not None


def test_discover_greenhouse_jobs():
    browser = MagicMock()

    pipeline = JobPipeline(
        browser
    )

    pipeline.discovery.discover_greenhouse = (
        MagicMock(
            return_value=[
                {
                    "title": "Electrical Engineer",
                    "company": "Example Company",
                    "location": "India",
                    "url": (
                        "https://example.com/job/1"
                    ),
                    "description": (
                        "Electrical engineering "
                        "role requiring Python "
                        "and MATLAB."
                    ),
                }
            ]
        )
    )

    jobs = pipeline.discover_greenhouse_jobs(
        board_url="https://example.com/jobs",
        keywords="Electrical Engineer",
        location="India",
    )

    assert len(jobs) == 1

    job = jobs[0]

    assert job["title"] == (
        "Electrical Engineer"
    )

    assert job["company"] == (
        "Example Company"
    )

    assert job["location"] == "India"

    assert job["url"] == (
        "https://example.com/job/1"
    )

    assert job["description"] == (
        "Electrical engineering "
        "role requiring Python "
        "and MATLAB."
    )

    assert job["job_title"] == (
        "Electrical Engineer"
    )

    assert "Python" in job["all_keywords"]
    assert "MATLAB" in job["all_keywords"]

    assert "required_skills" in job
    assert "preferred_skills" in job
    assert "experience_requirements" in job


def test_normalize_jobs_removes_extra_whitespace():
    jobs = [
        {
            "title": "  Electrical Engineer  ",
            "company": " Example Company ",
            "location": " India ",
            "url": (
                " https://example.com/job/1 "
            ),
            "description": (
                "  Test description. "
            ),
        }
    ]

    result = JobPipeline._normalize_jobs(
        jobs
    )

    assert len(result) == 1

    job = result[0]

    assert job["title"] == (
        "Electrical Engineer"
    )

    assert job["company"] == (
        "Example Company"
    )

    assert job["location"] == "India"

    assert job["url"] == (
        "https://example.com/job/1"
    )

    assert job["description"] == (
        "Test description."
    )

    assert job["job_title"] == (
        "Electrical Engineer"
    )

    assert isinstance(
        job["required_skills"],
        list,
    )

    assert isinstance(
        job["preferred_skills"],
        list,
    )

    assert isinstance(
        job["all_keywords"],
        list,
    )

    assert job[
        "experience_requirements"
    ] == ""


def test_normalize_jobs_handles_missing_fields():
    jobs = [
        {
            "title": "Electrical Engineer",
        }
    ]

    result = JobPipeline._normalize_jobs(
        jobs
    )

    assert len(result) == 1

    job = result[0]

    assert job["title"] == (
        "Electrical Engineer"
    )

    assert job["company"] == ""
    assert job["location"] == ""
    assert job["url"] == ""
    assert job["description"] == ""

    assert job["job_title"] == (
        "Electrical Engineer"
    )

    assert job["summary"] == ""

    assert job["required_skills"] == []
    assert job["preferred_skills"] == []

    # parse_job derives keywords from the title.
    assert isinstance(
        job["all_keywords"],
        list,
    )

    assert "Electrical" in (
        job["all_keywords"]
    )

    assert job[
        "experience_requirements"
    ] == ""


def test_normalize_jobs_ignores_non_dict_items():
    jobs = [
        None,
        "invalid",
        123,
        {
            "title": "Valid Job",
        },
    ]

    result = JobPipeline._normalize_jobs(
        jobs
    )

    assert len(result) == 1

    job = result[0]

    assert job["title"] == (
        "Valid Job"
    )

    assert job["company"] == ""
    assert job["location"] == ""
    assert job["url"] == ""
    assert job["description"] == ""

    assert job["job_title"] == (
        "Valid Job"
    )

    assert job["required_skills"] == []
    assert job["preferred_skills"] == []

    assert isinstance(
        job["all_keywords"],
        list,
    )

    assert job[
        "experience_requirements"
    ] == ""


def test_normalize_jobs_preserves_existing_parser_fields():
    jobs = [
        {
            "title": "Automation Engineer",
            "company": "Example",
            "location": "Hyderabad",
            "url": (
                "https://example.com/job"
            ),
            "description": (
                "Automation role."
            ),
            "required_skills": [
                "PLC",
                "Python",
            ],
            "preferred_skills": [
                "SCADA",
            ],
            "experience_requirements": (
                "2 years"
            ),
        }
    ]

    result = JobPipeline._normalize_jobs(
        jobs
    )

    assert len(result) == 1

    job = result[0]

    assert job["title"] == (
        "Automation Engineer"
    )

    assert job["job_title"] == (
        "Automation Engineer"
    )

    assert job["required_skills"] == [
        "PLC",
        "Python",
    ]

    assert job["preferred_skills"] == [
        "SCADA",
    ]

    assert job[
        "experience_requirements"
    ] == "2 years"

    assert isinstance(
        job["all_keywords"],
        list,
    )


def test_normalize_jobs_handles_none():
    assert (
        JobPipeline._normalize_jobs(
            None
        )
        == []
    )


def test_normalize_jobs_handles_empty_list():
    assert (
        JobPipeline._normalize_jobs(
            []
        )
        == []
    )


def test_discover_greenhouse_requires_board_url():
    pipeline = JobPipeline(
        MagicMock()
    )

    with pytest.raises(
        ValueError,
        match="Greenhouse board URL cannot be empty",
    ):
        pipeline.discover_greenhouse_jobs(
            board_url="",
            keywords="engineer",
        )


def test_discover_greenhouse_requires_keywords():
    pipeline = JobPipeline(
        MagicMock()
    )

    with pytest.raises(
        ValueError,
        match="Greenhouse keywords cannot be empty",
    ):
        pipeline.discover_greenhouse_jobs(
            board_url="https://example.com/jobs",
            keywords="",
        )