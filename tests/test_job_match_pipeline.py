from unittest.mock import MagicMock

from app.core.job_match_pipeline import JobMatchPipeline


# ============================================================
# HELPERS
# ============================================================

def make_resume(
    filename,
    skills,
    competencies=None,
):
    return {
        "_filename": filename,
        "name": "Test Candidate",
        "skills": skills,
        "core_competencies": (
            competencies or []
        ),
    }


# ============================================================
# CREATION
# ============================================================

def test_pipeline_creation():
    browser = MagicMock()
    resume_manager = MagicMock()

    pipeline = JobMatchPipeline(
        browser=browser,
        resume_manager=resume_manager,
    )

    assert pipeline.browser is browser
    assert (
        pipeline.resume_manager
        is resume_manager
    )
    assert pipeline.job_pipeline is not None


# ============================================================
# JOB PREPARATION
# ============================================================

def test_prepare_job_for_matching():
    job = {
        "title": "Electrical Engineer",
        "company": "Example",
        "location": "India",
        "url": (
            "https://example.com/job"
        ),
        "description": (
            "Electrical engineering role"
        ),
        "required_skills": [
            "Python",
            "Electrical Engineering",
        ],
        "preferred_skills": [
            "Automation",
        ],
        "experience_requirements": (
            "Fresher"
        ),
    }

    result = (
        JobMatchPipeline
        ._prepare_job_for_matching(
            job
        )
    )

    assert (
        result["title"]
        == "Electrical Engineer"
    )

    assert (
        result["company"]
        == "Example"
    )

    assert (
        result["location"]
        == "India"
    )

    assert (
        result["required_skills"]
        == [
            "Python",
            "Electrical Engineering",
        ]
    )

    assert (
        result["preferred_skills"]
        == [
            "Automation",
        ]
    )

    assert (
        result[
            "experience_requirements"
        ]
        == "Fresher"
    )


# ============================================================
# SORTING
# ============================================================

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

    result = (
        JobMatchPipeline
        ._sort_results(
            results
        )
    )

    assert [
        item["match"]["match_score"]
        for item in result
    ] == [
        95,
        70,
        40,
    ]


def test_sort_results_supports_resume_score():
    results = [
        {
            "match": {
                "resume_score": 100,
            }
        },
        {
            "match": {
                "resume_score": 500,
            }
        },
        {
            "match": {
                "resume_score": 250,
            }
        },
    ]

    result = (
        JobMatchPipeline
        ._sort_results(
            results
        )
    )

    assert [
        item["match"]["resume_score"]
        for item in result
    ] == [
        500,
        250,
        100,
    ]


def test_sort_results_handles_invalid_scores():
    results = [
        {
            "match": {
                "match_score": "invalid",
            }
        },
        {
            "match": {
                "match_score": 500,
            }
        },
        {
            "match": {},
        },
    ]

    result = (
        JobMatchPipeline
        ._sort_results(
            results
        )
    )

    assert (
        result[0]["match"][
            "match_score"
        ]
        == 500
    )


# ============================================================
# MATCH RESULT COMPATIBILITY
# ============================================================

def test_match_result_adds_match_score_from_resume_score():

    selection = {
        "resume_score": 10560,
    }

    result = (
        JobMatchPipeline
        ._ensure_match_compatibility(
            selection
        )
    )

    assert (
        result["resume_score"]
        == 10560
    )

    assert (
        result["match_score"]
        == 10560
    )


def test_match_result_adds_resume_score_from_match_score():

    selection = {
        "match_score": 750,
    }

    result = (
        JobMatchPipeline
        ._ensure_match_compatibility(
            selection
        )
    )

    assert (
        result["match_score"]
        == 750
    )

    assert (
        result["resume_score"]
        == 750
    )


def test_match_result_preserves_both_scores():

    selection = {
        "match_score": 1300,
        "resume_score": 1300,
    }

    result = (
        JobMatchPipeline
        ._ensure_match_compatibility(
            selection
        )
    )

    assert (
        result["match_score"]
        == 1300
    )

    assert (
        result["resume_score"]
        == 1300
    )


# ============================================================
# GREENHOUSE DISCOVERY + MATCHING
# ============================================================

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
                    "title": (
                        "Electrical Engineer"
                    ),
                    "company": (
                        "Example Company"
                    ),
                    "location": "India",
                    "url": (
                        "https://example.com/job/1"
                    ),
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

    results = (
        pipeline
        .discover_and_match_greenhouse(
            board_url=(
                "https://example.com/jobs"
            ),
            keywords=(
                "Electrical Engineer"
            ),
            location="India",
        )
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

    # The current resume selector uses a
    # weighted/raw score rather than a
    # percentage from 0-100.
    assert (
        isinstance(
            result["match"][
                "match_score"
            ],
            (int, float),
        )
    )

    assert (
        result["match"][
            "match_score"
        ]
        > 0
    )

    assert (
        result["match"][
            "match_score"
        ]
        == result["match"][
            "resume_score"
        ]
    )

    assert (
        result["match"]["eligible"]
        is True
    )

    assert (
        result["match"][
            "recommendation"
        ]
        == "APPLY"
    )


# ============================================================
# BEST RESUME SELECTION
# ============================================================

def test_best_resume_is_selected():

    browser = MagicMock()
    resume_manager = MagicMock()

    resume_manager.load_all_resumes.return_value = [
        make_resume(
            "weak_resume.pdf",
            [
                "Python",
            ],
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
                    "title": (
                        "Electrical Engineer"
                    ),
                    "company": "Example",
                    "location": "India",
                    "url": (
                        "https://example.com/job"
                    ),
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

    results = (
        pipeline
        .discover_and_match_greenhouse(
            board_url=(
                "https://example.com/jobs"
            ),
            keywords=(
                "Electrical Engineer"
            ),
        )
    )

    assert len(results) == 1

    result = results[0]

    assert (
        result["resume"]["filename"]
        == "strong_resume.pdf"
    )

    # Do NOT require score == 100.
    #
    # The current selector uses a weighted
    # raw score. We only require that the
    # selected resume has a valid positive
    # score and that the compatibility alias
    # is correct.

    assert (
        isinstance(
            result["match"][
                "match_score"
            ],
            (int, float),
        )
    )

    assert (
        result["match"][
            "match_score"
        ]
        > 0
    )

    assert (
        result["match"][
            "match_score"
        ]
        == result["match"][
            "resume_score"
        ]
    )

    assert (
        result["match"]["eligible"]
        is True
    )

    assert (
        result["match"][
            "recommendation"
        ]
        == "APPLY"
    )


# ============================================================
# SOURCE-AGNOSTIC MATCHING
# ============================================================

def test_match_jobs_returns_empty_for_no_jobs():

    browser = MagicMock()
    resume_manager = MagicMock()

    pipeline = JobMatchPipeline(
        browser=browser,
        resume_manager=resume_manager,
    )

    assert (
        pipeline.match_jobs([])
        == []
    )

    assert (
        pipeline.match_jobs(None)
        == []
    )


def test_match_jobs_returns_empty_without_resumes():

    browser = MagicMock()
    resume_manager = MagicMock()

    resume_manager.load_all_resumes.return_value = []

    pipeline = JobMatchPipeline(
        browser=browser,
        resume_manager=resume_manager,
    )

    jobs = [
        {
            "title": "Electrical Engineer",
            "company": "Example",
            "location": "India",
            "url": (
                "https://example.com/job"
            ),
            "description": (
                "Electrical engineering."
            ),
        }
    ]

    result = pipeline.match_jobs(
        jobs
    )

    assert result == []


def test_match_jobs_ignores_invalid_items():

    browser = MagicMock()
    resume_manager = MagicMock()

    resume_manager.load_all_resumes.return_value = [
        make_resume(
            "technical_resume.pdf",
            [
                "Python",
                "Electrical Engineering",
            ],
        )
    ]

    pipeline = JobMatchPipeline(
        browser=browser,
        resume_manager=resume_manager,
    )

    jobs = [
        None,
        "invalid",
        123,
    ]

    result = pipeline.match_jobs(
        jobs
    )

    assert result == []