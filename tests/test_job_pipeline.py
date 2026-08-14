from unittest.mock import MagicMock

from app.core.job_pipeline import JobPipeline


def test_job_pipeline_creation():
    browser = MagicMock()

    pipeline = JobPipeline(browser)

    assert pipeline.browser is browser
    assert pipeline.discovery is not None


def test_discover_greenhouse_jobs():
    browser = MagicMock()

    pipeline = JobPipeline(browser)

    pipeline.discovery.discover_greenhouse = MagicMock(
        return_value=[
            {
                "title": "Electrical Engineer",
                "company": "Example Company",
                "location": "India",
                "url": "https://example.com/job/1",
                "description": "Electrical engineering role.",
            }
        ]
    )

    jobs = pipeline.discover_greenhouse_jobs(
        board_url="https://example.com/jobs",
        keywords="Electrical Engineer",
        location="India",
    )

    assert len(jobs) == 1

    assert jobs[0] == {
        "title": "Electrical Engineer",
        "company": "Example Company",
        "location": "India",
        "url": "https://example.com/job/1",
        "description": "Electrical engineering role.",
    }


def test_normalize_jobs_removes_extra_whitespace():
    jobs = [
        {
            "title": "  Electrical Engineer  ",
            "company": " Example Company ",
            "location": " India ",
            "url": " https://example.com/job/1 ",
            "description": "  Test description. ",
        }
    ]

    result = JobPipeline._normalize_jobs(jobs)

    assert result == [
        {
            "title": "Electrical Engineer",
            "company": "Example Company",
            "location": "India",
            "url": "https://example.com/job/1",
            "description": "Test description.",
        }
    ]


def test_normalize_jobs_handles_missing_fields():
    jobs = [
        {
            "title": "Electrical Engineer",
        }
    ]

    result = JobPipeline._normalize_jobs(jobs)

    assert result == [
        {
            "title": "Electrical Engineer",
            "company": "",
            "location": "",
            "url": "",
            "description": "",
        }
    ]


def test_normalize_jobs_ignores_non_dict_items():
    jobs = [
        None,
        "invalid",
        123,
        {
            "title": "Valid Job",
        },
    ]

    result = JobPipeline._normalize_jobs(jobs)

    assert result == [
        {
            "title": "Valid Job",
            "company": "",
            "location": "",
            "url": "",
            "description": "",
        }
    ]