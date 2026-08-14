from unittest.mock import Mock

from app.core.job_processor import JobProcessor


def make_processor():
    browser = Mock()

    resume = {
        "name": "Naveen Sai",
        "skills": [
            "Python",
            "C",
            "Embedded C",
        ],
        "core_competencies": [
            "Electrical Engineering",
            "Predictive Maintenance",
        ],
    }

    return JobProcessor(
        browser=browser,
        resume=resume,
    )


def test_process_greenhouse_jobs():
    processor = make_processor()

    processor.pipeline.discover_greenhouse_jobs = Mock(
        return_value=[
            {
                "title": "Graduate Engineer Trainee",
                "company": "Example Company",
                "location": "India",
                "url": "https://example.com/job/1",
                "description": (
                    "Electrical Engineering "
                    "Python Predictive Maintenance"
                ),
            }
        ]
    )

    results = processor.process_greenhouse_jobs(
        board_url="https://example.com",
        keywords="Electrical Engineer",
        location="India",
    )

    assert len(results) == 1

    result = results[0]

    assert result["title"] == "Graduate Engineer Trainee"
    assert result["company"] == "Example Company"
    assert result["location"] == "India"
    assert result["url"] == "https://example.com/job/1"

    assert "match" in result
    assert "match_score" in result["match"]
    assert "recommendation" in result["match"]


def test_filter_by_recommendation():
    processor = make_processor()

    results = [
        {
            "title": "Job A",
            "match": {
                "match_score": 100,
                "recommendation": "APPLY",
            },
        },
        {
            "title": "Job B",
            "match": {
                "match_score": 50,
                "recommendation": "CONSIDER",
            },
        },
    ]

    filtered = processor.filter_jobs(
        results,
        recommendation="APPLY",
    )

    assert len(filtered) == 1
    assert filtered[0]["title"] == "Job A"


def test_filter_by_minimum_score():
    processor = make_processor()

    results = [
        {
            "title": "Job A",
            "match": {"match_score": 90},
        },
        {
            "title": "Job B",
            "match": {"match_score": 50},
        },
    ]

    filtered = processor.filter_jobs(
        results,
        minimum_score=80,
    )

    assert len(filtered) == 1
    assert filtered[0]["title"] == "Job A"


def test_filter_by_both_conditions():
    processor = make_processor()

    results = [
        {
            "title": "Job A",
            "match": {
                "match_score": 90,
                "recommendation": "APPLY",
            },
        },
        {
            "title": "Job B",
            "match": {
                "match_score": 95,
                "recommendation": "CONSIDER",
            },
        },
    ]

    filtered = processor.filter_jobs(
        results,
        recommendation="APPLY",
        minimum_score=80,
    )

    assert len(filtered) == 1
    assert filtered[0]["title"] == "Job A"


def test_sort_by_match_score():
    processor = make_processor()

    results = [
        {
            "title": "Job A",
            "match": {"match_score": 60},
        },
        {
            "title": "Job B",
            "match": {"match_score": 95},
        },
        {
            "title": "Job C",
            "match": {"match_score": 80},
        },
    ]

    sorted_results = processor.sort_by_match_score(
        results
    )

    assert [
        result["title"]
        for result in sorted_results
    ] == [
        "Job B",
        "Job C",
        "Job A",
    ]