from app.core.application_decision_engine import (
    APPLY,
    REVIEW,
    SKIP,
    ApplicationDecisionEngine,
)


def make_result(
    title,
    description,
    ranking_score=90,
    match_score=90,
    eligible=True,
    **job_fields,
):
    return {
        "job": {
            "title": title,
            "description": description,
            "url": "https://example.com/job",
            **job_fields,
        },
        "resume": {
            "filename": "technical_resume.pdf",
        },
        "match": {
            "match_score": match_score,
            "resume_score": match_score,
            "eligible": eligible,
            "missing_required_skills": [],
        },
        "ranking_score": ranking_score,
    }


def test_sales_engineer_is_never_applied():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        make_result(
            "Sales Engineer",
            "Cold calling customers and meeting sales targets.",
            ranking_score=95,
            match_score=95,
        )
    )

    assert result.decision == SKIP
    assert (
        result.metadata["technical_target"]
        is False
    )


def test_electrical_engineer_can_be_applied():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        make_result(
            "Electrical Engineer",
            (
                "Electrical engineering, "
                "power electronics and maintenance."
            ),
            ranking_score=90,
            match_score=90,
        )
    )

    assert result.decision == APPLY
    assert (
        result.metadata["technical_target"]
        is True
    )


def test_embedded_engineer_can_be_applied():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        make_result(
            "Embedded Systems Engineer",
            (
                "Embedded C, microcontrollers, "
                "GPIO, ADC and firmware."
            ),
            ranking_score=88,
            match_score=88,
        )
    )

    assert result.decision == APPLY


def test_missing_match_information_requires_review():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        {
            "job": {
                "title": "Electrical Engineer",
                "description": (
                    "Electrical maintenance engineer."
                ),
                "url": "https://example.com/job",
            },
            "ranking_score": 80,
        }
    )

    assert result.decision == REVIEW


def test_ineligible_job_is_skipped():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        make_result(
            "Electrical Engineer",
            "Electrical engineering.",
            ranking_score=95,
            match_score=95,
            eligible=False,
        )
    )

    assert result.decision == SKIP


def test_missing_required_skill_requires_review():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        {
            "job": {
                "title": "Electrical Engineer",
                "description": (
                    "Electrical engineering."
                ),
                "url": "https://example.com/job",
            },
            "resume": {
                "filename": "technical_resume.pdf",
            },
            "match": {
                "match_score": 95,
                "resume_score": 95,
                "eligible": True,
                "missing_required_skills": [
                    "PLC",
                ],
            },
            "ranking_score": 95,
        }
    )

    assert result.decision == REVIEW


def test_closed_job_is_skipped():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        make_result(
            "Electrical Engineer",
            "Electrical engineering.",
            ranking_score=95,
            match_score=95,
            status="closed",
        )
    )

    assert result.decision == SKIP


def test_priority_information_is_preserved():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        make_result(
            "Electrical Engineer",
            (
                "Urgently hiring. "
                "Electrical maintenance."
            ),
            ranking_score=90,
            match_score=90,
        )
    )

    assert (
        "priority_score"
        in result.metadata
    )

    assert (
        result.metadata["priority_score"]
        >= 0
    )
    