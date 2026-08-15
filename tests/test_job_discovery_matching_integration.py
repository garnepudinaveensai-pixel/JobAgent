from pathlib import Path

import pytest

from app.core.job_match_pipeline import JobMatchPipeline


# ============================================================
# HELPERS
# ============================================================

def sample_discovered_jobs():
    return [
        {
            "title": "Electrical Engineer",
            "company": "Example Energy",
            "location": "Hyderabad",
            "url": "https://example.com/jobs/electrical-engineer",
            "description": (
                "Electrical engineering role involving "
                "industrial equipment, maintenance, automation, "
                "and power systems."
            ),
            "required_skills": [
                "electrical engineering",
                "maintenance",
                "automation",
            ],
            "preferred_skills": [
                "MATLAB",
                "power electronics",
            ],
            "experience_requirements": "0-2 years",
        },
        {
            "title": "Software Engineer",
            "company": "Example Software",
            "location": "Bangalore",
            "url": "https://example.com/jobs/software-engineer",
            "description": (
                "Software engineering role involving "
                "Python, APIs, databases, and web development."
            ),
            "required_skills": [
                "Python",
                "SQL",
                "APIs",
            ],
            "preferred_skills": [
                "FastAPI",
                "Docker",
            ],
            "experience_requirements": "1-3 years",
        },
    ]


def sample_resume():
    return {
        "name": "Naveen Sai",
        "degree": (
            "B.Tech Electrical & Electronics Engineering"
        ),
        "skills": [
            "Electrical Engineering",
            "Maintenance",
            "Automation",
            "MATLAB",
            "Power Electronics",
            "Embedded C",
            "C",
            "Python",
        ],
        "experience": [
            {
                "company": "Industrial Company",
                "role": "Condition-Based Maintenance Intern",
                "description": (
                    "Electrical equipment monitoring, "
                    "condition-based maintenance, "
                    "vibration analysis, and industrial operations."
                ),
            }
        ],
        "_filename": "test_resume.pdf",
        "_file": "resumes/test_resume.pdf",
        "_raw_text": (
            "Naveen Sai\n"
            "B.Tech Electrical & Electronics Engineering\n"
            "Electrical Engineering\n"
            "Maintenance\n"
            "Automation\n"
            "MATLAB\n"
            "Power Electronics\n"
            "Python\n"
        ),
    }


# ============================================================
# FAKE DEPENDENCIES
# ============================================================

class FakeBrowser:
    """
    Browser dependency used only for integration testing.

    No real browser is opened.
    """

    pass


class FakeJobPipeline:
    """
    Fake JobPipeline that behaves like the real discovery
    pipeline from the perspective of JobMatchPipeline.
    """

    def discover_greenhouse_jobs(
        self,
        board_url,
        keywords,
        location=None,
    ):
        assert board_url
        assert keywords

        return sample_discovered_jobs()


class FakeResumeManager:
    """
    Fake ResumeManager that returns a known parsed resume.
    """

    def load_all_resumes(self):
        return [
            sample_resume()
        ]


# ============================================================
# DISCOVERY + MATCHING
# ============================================================

def test_discovery_and_matching_pipeline():
    pipeline = JobMatchPipeline(
        browser=FakeBrowser(),
        resume_manager=FakeResumeManager(),
    )

    # Replace the real browser-backed discovery pipeline
    # with a deterministic fake for this integration test.
    pipeline.job_pipeline = FakeJobPipeline()

    results = pipeline.discover_and_match_greenhouse(
        board_url="https://example.com/greenhouse",
        keywords="Electrical Engineer",
        location="Hyderabad",
    )

    assert isinstance(results, list)
    assert len(results) == 2

    # Strongest match should be first.
    first = results[0]

    assert "job" in first
    assert "resume" in first
    assert "match" in first

    assert first["job"]["title"] == (
        "Electrical Engineer"
    )

    assert first["resume"]["filename"] == (
        "test_resume.pdf"
    )

    assert "match_score" in first["match"]


# ============================================================
# RESULT SORTING
# ============================================================

def test_results_are_sorted_by_match_score():
    pipeline = JobMatchPipeline(
        browser=FakeBrowser(),
        resume_manager=FakeResumeManager(),
    )

    results = [
        {
            "job": {
                "title": "Job A",
            },
            "resume": {
                "filename": "resume.pdf",
            },
            "match": {
                "match_score": 40,
            },
        },
        {
            "job": {
                "title": "Job B",
            },
            "resume": {
                "filename": "resume.pdf",
            },
            "match": {
                "match_score": 90,
            },
        },
        {
            "job": {
                "title": "Job C",
            },
            "resume": {
                "filename": "resume.pdf",
            },
            "match": {
                "match_score": 60,
            },
        },
    ]

    sorted_results = pipeline._sort_results(
        results
    )

    scores = [
        item["match"]["match_score"]
        for item in sorted_results
    ]

    assert scores == [90, 60, 40]


# ============================================================
# JOB PREPARATION
# ============================================================

def test_discovered_job_is_prepared_for_matching():
    job = sample_discovered_jobs()[0]

    prepared = (
        JobMatchPipeline._prepare_job_for_matching(
            job
        )
    )

    assert prepared["title"] == (
        "Electrical Engineer"
    )

    assert prepared["company"] == (
        "Example Energy"
    )

    assert prepared["location"] == (
        "Hyderabad"
    )

    assert prepared["url"] == (
        "https://example.com/jobs/electrical-engineer"
    )

    assert prepared["description"]

    assert prepared["required_skills"] == [
        "electrical engineering",
        "maintenance",
        "automation",
    ]

    assert prepared["preferred_skills"] == [
        "MATLAB",
        "power electronics",
    ]

    assert prepared["experience_requirements"] == (
        "0-2 years"
    )


# ============================================================
# INVALID DISCOVERY RESULTS
# ============================================================

def test_job_pipeline_ignores_invalid_discovered_items():
    from app.core.job_pipeline import JobPipeline

    jobs = [
        sample_discovered_jobs()[0],
        None,
        "invalid",
        123,
        sample_discovered_jobs()[1],
    ]

    normalized = JobPipeline._normalize_jobs(
        jobs
    )

    assert len(normalized) == 2

    assert normalized[0]["title"] == (
        "Electrical Engineer"
    )

    assert normalized[1]["title"] == (
        "Software Engineer"
    )


# ============================================================
# NO RESUMES
# ============================================================

def test_discovery_matching_returns_empty_when_no_resumes():
    class EmptyResumeManager:
        def load_all_resumes(self):
            return []

    pipeline = JobMatchPipeline(
        browser=FakeBrowser(),
        resume_manager=EmptyResumeManager(),
    )

    pipeline.job_pipeline = FakeJobPipeline()

    results = pipeline.discover_and_match_greenhouse(
        board_url="https://example.com/greenhouse",
        keywords="Electrical Engineer",
        location="Hyderabad",
    )

    assert results == []


# ============================================================
# MULTIPLE RESUMES
# ============================================================

def test_best_resume_is_selected_for_each_job():
    class MultipleResumeManager:
        def load_all_resumes(self):
            electrical_resume = sample_resume()

            software_resume = {
                "name": "Software Candidate",
                "degree": "B.Tech Computer Science",
                "skills": [
                    "Python",
                    "SQL",
                    "APIs",
                    "FastAPI",
                    "Docker",
                ],
                "experience": [
                    {
                        "company": "Software Company",
                        "role": "Software Engineer",
                        "description": (
                            "Python, SQL, APIs and "
                            "web development."
                        ),
                    }
                ],
                "_filename": "software_resume.pdf",
                "_file": "resumes/software_resume.pdf",
                "_raw_text": (
                    "Software Candidate\n"
                    "B.Tech Computer Science\n"
                    "Python SQL APIs FastAPI Docker\n"
                ),
            }

            return [
                electrical_resume,
                software_resume,
            ]

    pipeline = JobMatchPipeline(
        browser=FakeBrowser(),
        resume_manager=MultipleResumeManager(),
    )

    pipeline.job_pipeline = FakeJobPipeline()

    results = pipeline.discover_and_match_greenhouse(
        board_url="https://example.com/greenhouse",
        keywords="Engineer",
        location=None,
    )

    assert len(results) == 2

    electrical_result = next(
        result
        for result in results
        if result["job"]["title"]
        == "Electrical Engineer"
    )

    software_result = next(
        result
        for result in results
        if result["job"]["title"]
        == "Software Engineer"
    )

    assert electrical_result["resume"]["filename"] == (
        "test_resume.pdf"
    )

    assert software_result["resume"]["filename"] == (
        "software_resume.pdf"
    )