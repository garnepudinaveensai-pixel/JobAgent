from unittest.mock import MagicMock

from app.core.job_match_pipeline import JobMatchPipeline


def make_resume(
    filename,
    skills,
    competencies=None,
):
    return {
        "_filename": filename,
        "name": "Test Candidate",
        "skills": skills,
        "core_competencies": competencies or [],
    }


def test_pipeline_creation():
    browser = MagicMock()
    resume_manager = MagicMock()

    pipeline = JobMatchPipeline(
        browser=browser,
        resume_manager=resume_manager,
    )

    assert pipeline.browser is browser
    assert pipeline.resume_manager is resume_manager
    assert pipeline.job_pipeline is not None


def test_prepare_job_for_matching():
    job = {
        "title": "Electrical Engineer",
        "company": "Example",
        "location": "India",
        "url": "https://example.com/job",
        "description": "Electrical engineering role",
        "required_skills": [
            "Python",
            "Electrical Engineering",
        ],
        "preferred_skills": [
            "Automation",
        ],
        "experience_requirements": "Fresher",
    }

    result = JobMatchPipeline._prepare_job_for_matching(
        job
    )

    assert result["title"] == "Electrical Engineer"
    assert result["company"] == "Example"
    assert result["required_skills"] == [
        "Python",
        "Electrical Engineering",
    ]
    assert result["preferred_skills"] == [
        "Automation",
    ]


def test_sort_results():
    results = [
        {
            "match": {
                "match_score": 40,
            }
        },
        {
            "match": {
                "match_score": 95,
            }
        },
        {
            "match": {
                "match_score": 70,
            }
        },
    ]

    result = JobMatchPipeline._sort_results(
        results
    )

    assert [
        item["match"]["match_score"]
        for item in result
    ] == [95, 70, 40]


def test_discover_and_match_greenhouse():
    browser = MagicMock()
    resume_manager = MagicMock()

    resume_manager.load_all_resumes.return_value = [
        make_resume(
            "technical_resume.pdf",
            [
                "Python",
                "Electrical Engineering",
                "Predictive Maintenance",
            ],
        ),
        make_resume(
            "software_resume.pdf",
            [
                "Python",
            ],
        ),
    ]

    pipeline = JobMatchPipeline(
        browser=browser,
        resume_manager=resume_manager,
    )

    pipeline.job_pipeline.discover_greenhouse_jobs = (
        MagicMock(
            return_value=[
                {
                    "title": "Electrical Engineer",
                    "company": "Example Company",
                    "location": "India",
                    "url": "https://example.com/job/1",
                    "description": "",
                    "required_skills": [
                        "Python",
                        "Electrical Engineering",
                    ],
                    "preferred_skills": [
                        "Predictive Maintenance",
                    ],
                    "experience_requirements": "",
                }
            ]
        )
    )

    results = pipeline.discover_and_match_greenhouse(
        board_url="https://example.com/jobs",
        keywords="Electrical Engineer",
        location="India",
    )

    assert len(results) == 1

    result = results[0]

    assert (
        result["job"]["title"]
        == "Electrical Engineer"
    )

    assert (
        result["resume"]["filename"]
        == "technical_resume.pdf"
    )

    assert (
        result["match"]["match_score"]
        == 100.0
    )

    assert result["match"]["eligible"] is True
    assert (
        result["match"]["recommendation"]
        == "APPLY"
    )


def test_best_resume_is_selected():
    browser = MagicMock()
    resume_manager = MagicMock()

    resume_manager.load_all_resumes.return_value = [
        make_resume(
            "weak_resume.pdf",
            ["Python"],
        ),
        make_resume(
            "strong_resume.pdf",
            [
                "Python",
                "Electrical Engineering",
            ],
        ),
    ]

    pipeline = JobMatchPipeline(
        browser=browser,
        resume_manager=resume_manager,
    )

    pipeline.job_pipeline.discover_greenhouse_jobs = (
        MagicMock(
            return_value=[
                {
                    "title": "Electrical Engineer",
                    "company": "Example",
                    "location": "India",
                    "url": "https://example.com/job",
                    "description": "",
                    "required_skills": [
                        "Python",
                        "Electrical Engineering",
                    ],
                    "preferred_skills": [],
                    "experience_requirements": "",
                }
            ]
        )
    )

    results = pipeline.discover_and_match_greenhouse(
        board_url="https://example.com/jobs",
        keywords="Electrical Engineer",
    )

    assert len(results) == 1

    assert (
        results[0]["resume"]["filename"]
        == "strong_resume.pdf"
    )

    assert (
        results[0]["match"]["match_score"]
        == 100.0
    )