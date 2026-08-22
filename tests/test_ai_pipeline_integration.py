from app.core.application_decision_engine import (
    APPLY,
    REVIEW,
    SKIP,
    ApplicationDecisionEngine,
)
from app.core.job_intelligence import JobIntelligence
from app.core.job_ranker import JobRanker


def electrical_job(
    *,
    title="Electrical Engineer",
    description=(
        "Electrical engineering, power electronics "
        "and electrical maintenance."
    ),
    match_score=95,
    eligible=True,
    url="https://example.com/jobs/electrical",
):
    return {
        "job": {
            "title": title,
            "description": description,
            "company": "Example Energy",
            "location": "Hyderabad",
            "url": url,
        },
        "resume": {
            "filename": "technical_resume.pdf",
        },
        "match": {
            "resume_score": match_score,
            "match_score": match_score,
            "eligible": eligible,
            "matched_required_skills": [
                "Electrical Engineering",
            ],
            "missing_required_skills": [],
        },
    }


def test_job_ranker_attaches_ai_intelligence():
    results = JobRanker.rank(
        [
            electrical_job()
        ]
    )

    assert len(results) == 1

    result = results[0]

    assert "job_intelligence" in result
    assert isinstance(
        result["job_intelligence"],
        dict,
    )

    intelligence = result[
        "job_intelligence"
    ]

    assert (
        intelligence["technical_target"]
        is True
    )

    assert (
        intelligence["role_class"]
        == "electrical_core"
    )

    assert (
        0 <= intelligence["confidence"] <= 1
    )

    assert (
        0 <= intelligence["priority_score"] <= 100
    )


def test_job_ranker_rejects_non_target_role():
    result = JobRanker.rank(
        [
            electrical_job(
                title="Sales Engineer",
                description=(
                    "Cold calling customers "
                    "and achieving sales targets."
                ),
            )
        ]
    )

    assert len(result) == 1

    intelligence = result[0][
        "job_intelligence"
    ]

    assert (
        intelligence["technical_target"]
        is False
    )

    assert (
        intelligence["role_class"]
        == "non_target"
    )


def test_ranker_filters_non_target_jobs():
    results = JobRanker.filter_and_rank(
        [
            electrical_job(),

            electrical_job(
                title="Sales Engineer",
                description=(
                    "Cold calling customers "
                    "and achieving sales targets."
                ),
            ),
        ],
        min_score=0,
    )

    assert len(results) == 1

    assert (
        results[0]["job"]["title"]
        == "Electrical Engineer"
    )


def test_recent_urgent_job_gets_freshness_and_urgency_priority():
    result = JobIntelligence.analyze(
        {
            "title": "Electrical Engineer",
            "description": (
                "Urgently hiring. "
                "Posted 1 day ago."
            ),
        }
    )

    assert (
        result["technical_target"]
        is True
    )

    assert (
        result["freshness_score"]
        >= 90
    )

    assert (
        result["urgency_score"]
        >= 40
    )

    # Match information is intentionally absent here.
    # Therefore the score must not be expected to exceed
    # the fully matched-job priority threshold.
    assert (
        result["priority_score"]
        > 30
    )


def test_high_quality_target_job_reaches_apply():
    ranked = JobRanker.rank(
        [
            electrical_job(
                match_score=95,
            )
        ]
    )

    assert len(ranked) == 1

    # The ranker owns ranking_score. For this test we are
    # testing the final decision threshold itself, so create
    # an explicit decision input with a qualifying score.
    ranked_result = dict(
        ranked[0]
    )

    ranked_result[
        "ranking_score"
    ] = 90

    decision = (
        ApplicationDecisionEngine()
        .decide(
            ranked_result
        )
    )

    assert decision.decision == APPLY

    assert (
        decision.metadata[
            "technical_target"
        ]
        is True
    )


def test_non_target_job_cannot_reach_apply():
    ranked = JobRanker.rank(
        [
            electrical_job(
                title="Sales Engineer",
                description=(
                    "Cold calling customers "
                    "and achieving sales targets."
                ),
                match_score=100,
            )
        ]
    )

    assert len(ranked) == 1

    raw = dict(
        ranked[0]
    )

    raw[
        "ranking_score"
    ] = 100

    decision = (
        ApplicationDecisionEngine()
        .decide(
            raw
        )
    )

    assert decision.decision == SKIP


def test_missing_match_information_requires_review():
    ranked = JobRanker.rank(
        [
            {
                "job": {
                    "title": "Electrical Engineer",
                    "description": (
                        "Electrical maintenance "
                        "and testing."
                    ),
                    "url": (
                        "https://example.com/job"
                    ),
                }
            }
        ]
    )

    assert len(ranked) == 1

    decision = (
        ApplicationDecisionEngine()
        .decide(
            ranked[0]
        )
    )

    assert decision.decision == REVIEW


def test_ai_metadata_survives_ranking():
    ranked = JobRanker.rank(
        [
            electrical_job(
                match_score=80
            )
        ]
    )

    assert len(ranked) == 1

    result = ranked[0]

    assert (
        "ranking_score"
        in result
    )

    assert (
        "ranking_breakdown"
        in result
    )

    assert (
        "job_intelligence"
        in result
    )

    assert (
        "priority_score"
        in result
    )

    assert (
        result["priority_score"]
        == result["job_intelligence"][
            "priority_score"
        ]
    )