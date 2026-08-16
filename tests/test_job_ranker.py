from app.core.job_ranker import JobRanker


def make_result(
    *,
    resume_score=1000,
    eligible=True,
    title="Electrical Engineer",
    required_skills=None,
    preferred_skills=None,
    experience="Fresher",
    location="Hyderabad",
):
    return {
        "job": {
            "title": title,
            "job_title": title,
            "company": "Example Company",
            "location": location,
            "required_skills": (
                required_skills
                if required_skills is not None
                else [
                    "Python",
                    "Electrical Engineering",
                ]
            ),
            "preferred_skills": (
                preferred_skills
                if preferred_skills is not None
                else [
                    "MATLAB",
                ]
            ),
            "all_keywords": [
                "Electrical",
                "Engineering",
            ],
            "experience_requirements": experience,
        },
        "resume": {
            "filename": "technical_resume.pdf",
            "name": "Test Candidate",
        },
        "match": {
            "resume_score": resume_score,
            "match_score": resume_score,
            "eligible": eligible,
            "selected_resume": {
                "skills": [
                    "Python",
                    "Electrical Engineering",
                    "MATLAB",
                ]
            },
        },
    }


def test_rank_empty_results():
    assert JobRanker.rank([]) == []
    assert JobRanker.rank(None) == []


def test_rank_returns_highest_first():
    results = [
        make_result(
            resume_score=100,
        ),
        make_result(
            resume_score=5000,
        ),
        make_result(
            resume_score=1000,
        ),
    ]

    ranked = JobRanker.rank(results)

    assert len(ranked) == 3

    assert (
        ranked[0]["match"]["resume_score"]
        == 5000
    )


def test_rank_adds_ranking_score():
    results = [
        make_result(
            resume_score=1000
        )
    ]

    ranked = JobRanker.rank(results)

    assert (
        "ranking_score"
        in ranked[0]
    )

    assert isinstance(
        ranked[0]["ranking_score"],
        float,
    )

    assert (
        0
        <= ranked[0]["ranking_score"]
        <= 100
    )


def test_rank_adds_breakdown():
    result = JobRanker.rank(
        [
            make_result()
        ]
    )[0]

    breakdown = result[
        "ranking_breakdown"
    ]

    assert breakdown["resume"] >= 0
    assert breakdown["required_skills"] >= 0
    assert breakdown["preferred_skills"] >= 0
    assert breakdown["title"] >= 0
    assert breakdown["experience"] >= 0
    assert breakdown["location"] >= 0
    assert 0 <= breakdown["total"] <= 100


def test_filter_by_minimum_score():
    low_result = make_result(
        resume_score=1,
        required_skills=[
            "Quantum Computing",
        ],
        preferred_skills=[
            "Quantum Physics",
        ],
        title="Completely Unrelated Role",
        experience="5 years",
        location="",
    )

    high_result = make_result(
        resume_score=10000,
    )

    results = [
        low_result,
        high_result,
    ]

    filtered = JobRanker.filter_and_rank(
        results,
        min_score=50,
    )

    assert len(filtered) == 1

    assert (
        filtered[0]["match"]["resume_score"]
        == 10000
    )

    assert (
        filtered[0]["ranking_score"]
        >= 50
    )

def test_filter_eligible_only():
    results = [
        make_result(
            resume_score=5000,
            eligible=True,
        ),
        make_result(
            resume_score=6000,
            eligible=False,
        ),
    ]

    filtered = JobRanker.filter_and_rank(
        results,
        eligible_only=True,
    )

    assert len(filtered) == 1

    assert (
        filtered[0]["match"][
            "eligible"
        ]
        is True
    )


def test_filter_limit():
    results = [
        make_result(
            resume_score=100,
        ),
        make_result(
            resume_score=200,
        ),
        make_result(
            resume_score=300,
        ),
    ]

    filtered = JobRanker.filter_and_rank(
        results,
        limit=2,
    )

    assert len(filtered) == 2


def test_invalid_min_score_raises():
    try:
        JobRanker.filter_and_rank(
            [],
            min_score=-1,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError"
        )


def test_invalid_max_score_raises():
    try:
        JobRanker.filter_and_rank(
            [],
            min_score=101,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError"
        )


def test_invalid_limit_raises():
    try:
        JobRanker.filter_and_rank(
            [],
            limit=-1,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError"
        )


def test_invalid_results_are_ignored():
    results = [
        None,
        "invalid",
        123,
        {},
        make_result(),
    ]

    ranked = JobRanker.rank(results)

    assert len(ranked) == 1


def test_fresher_job_gets_high_experience_score():
    result = JobRanker.rank(
        [
            make_result(
                experience="Fresher"
            )
        ]
    )[0]

    assert (
        result["ranking_breakdown"][
            "experience"
        ]
        == 100.0
    )


def test_empty_experience_is_neutral():
    result = JobRanker.rank(
        [
            make_result(
                experience=""
            )
        ]
    )[0]

    assert (
        result["ranking_breakdown"][
            "experience"
        ]
        == 75.0
    )


def test_unknown_location_is_neutral():
    result = JobRanker.rank(
        [
            make_result(
                location=""
            )
        ]
    )[0]

    assert (
        result["ranking_breakdown"][
            "location"
        ]
        == 50.0
    )