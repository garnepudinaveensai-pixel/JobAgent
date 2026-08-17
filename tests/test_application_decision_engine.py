import pytest

from app.core.application_decision_engine import (
    APPLY,
    OUTREACH,
    REVIEW,
    SKIP,
    ApplicationDecision,
    ApplicationDecisionConfig,
    ApplicationDecisionEngine,
    decide_application_action,
)


# ============================================================
# HELPERS
# ============================================================


def make_result(
    ranking_score=90,
    match_score=90,
    eligible=True,
    missing_required_skills=None,
    url="https://example.com/jobs/1",
    resume=None,
):
    return {
        "ranking_score": ranking_score,
        "job": {
            "title": "Electrical Engineer",
            "company": "Example Company",
            "location": "Hyderabad",
            "url": url,
        },
        "resume": resume
        or {
            "filename": "technical_resume.pdf",
            "name": "Naveen Sai",
        },
        "match": {
            "match_score": match_score,
            "eligible": eligible,
            "missing_required_skills": (
                missing_required_skills
                or []
            ),
            "selected_resume": resume
            or {
                "filename": "technical_resume.pdf",
                "name": "Naveen Sai",
            },
        },
    }


@pytest.fixture
def engine():
    return ApplicationDecisionEngine()


# ============================================================
# CONFIGURATION
# ============================================================


def test_default_configuration():
    config = ApplicationDecisionConfig()

    assert config.apply_score == 85
    assert config.review_score == 70
    assert config.outreach_score == 50


def test_invalid_threshold_order():
    with pytest.raises(
        ValueError,
        match="apply_score >= review_score >= outreach_score",
    ):
        ApplicationDecisionConfig(
            apply_score=50,
            review_score=70,
            outreach_score=40,
        )


def test_invalid_threshold_range():
    with pytest.raises(
        ValueError,
        match="between 0 and 100",
    ):
        ApplicationDecisionConfig(
            apply_score=101
        )


# ============================================================
# APPLY
# ============================================================


def test_high_score_with_application_url_returns_apply(
    engine,
):
    result = engine.decide(
        make_result(
            ranking_score=91.5,
            match_score=90,
        )
    )

    assert isinstance(
        result,
        ApplicationDecision,
    )

    assert result.decision == APPLY
    assert result.ranking_score == 91.5
    assert result.match_score == 90
    assert result.eligible is True
    assert result.application_url == (
        "https://example.com/jobs/1"
    )

    assert result.recommended_action == (
        "application"
    )


# ============================================================
# OUTREACH
# ============================================================


def test_high_score_without_application_url_returns_outreach(
    engine,
):
    result = engine.decide(
        make_result(
            ranking_score=91,
            url="",
        )
    )

    assert result.decision == OUTREACH
    assert result.recommended_action == (
        "outreach"
    )


def test_medium_score_without_application_url_returns_outreach(
    engine,
):
    result = engine.decide(
        make_result(
            ranking_score=60,
            url="",
        )
    )

    assert result.decision == OUTREACH


# ============================================================
# REVIEW
# ============================================================


def test_medium_score_with_application_url_returns_review(
    engine,
):
    result = engine.decide(
        make_result(
            ranking_score=75,
        )
    )

    assert result.decision == REVIEW
    assert result.recommended_action == (
        "manual_review"
    )


def test_missing_required_skill_returns_review(
    engine,
):
    result = engine.decide(
        make_result(
            ranking_score=95,
            missing_required_skills=[
                "PLC"
            ],
        )
    )

    assert result.decision == REVIEW

    assert result.missing_required_skills == (
        "PLC",
    )


# ============================================================
# SKIP
# ============================================================


def test_ineligible_job_returns_skip(
    engine,
):
    result = engine.decide(
        make_result(
            ranking_score=95,
            eligible=False,
        )
    )

    assert result.decision == SKIP
    assert result.recommended_action == (
        "none"
    )


def test_low_score_returns_skip(
    engine,
):
    result = engine.decide(
        make_result(
            ranking_score=20,
        )
    )

    assert result.decision == SKIP


# ============================================================
# ELIGIBILITY
# ============================================================


def test_string_eligibility_true():
    engine = ApplicationDecisionEngine()

    result = make_result(
        ranking_score=90
    )

    result["match"]["eligible"] = "true"

    decision = engine.decide(
        result
    )

    assert decision.eligible is True
    assert decision.decision == APPLY


def test_string_eligibility_false():
    engine = ApplicationDecisionEngine()

    result = make_result(
        ranking_score=90
    )

    result["match"]["eligible"] = "false"

    decision = engine.decide(
        result
    )

    assert decision.eligible is False
    assert decision.decision == SKIP


# ============================================================
# RESUME
# ============================================================


def test_selected_resume_is_preserved(
    engine,
):
    resume = {
        "filename": "automation_resume.pdf",
        "name": "Naveen Sai",
        "skills": [
            "PLC",
            "SCADA",
        ],
    }

    result = engine.decide(
        make_result(
            ranking_score=90,
            resume=resume,
        )
    )

    assert result.selected_resume == resume


def test_resume_from_match_is_used():
    engine = ApplicationDecisionEngine()

    result = make_result(
        ranking_score=90
    )

    result["resume"] = None

    result["match"][
        "selected_resume"
    ] = {
        "filename": "embedded_resume.pdf",
        "name": "Naveen Sai",
    }

    decision = engine.decide(
        result
    )

    assert decision.selected_resume[
        "filename"
    ] == "embedded_resume.pdf"


# ============================================================
# URL RESOLUTION
# ============================================================


def test_application_url_has_priority():
    engine = ApplicationDecisionEngine()

    result = make_result(
        ranking_score=90,
        url="https://example.com/job",
    )

    result["application_url"] = (
        "https://example.com/apply"
    )

    decision = engine.decide(
        result
    )

    assert decision.application_url == (
        "https://example.com/apply"
    )


def test_job_apply_url_is_supported():
    engine = ApplicationDecisionEngine()

    result = make_result(
        ranking_score=90,
        url="",
    )

    result["job"]["apply_url"] = (
        "https://example.com/apply"
    )

    decision = engine.decide(
        result
    )

    assert decision.application_url == (
        "https://example.com/apply"
    )


# ============================================================
# INPUT VALIDATION
# ============================================================


def test_invalid_ranked_result_type(
    engine,
):
    with pytest.raises(
        TypeError,
        match="ranked_result must be a mapping",
    ):
        engine.decide(None)


def test_missing_job_and_match_are_handled(
    engine,
):
    result = {
        "ranking_score": 10
    }

    decision = engine.decide(
        result
    )

    assert decision.decision == SKIP
    assert decision.application_url == ""


# ============================================================
# SCORE NORMALIZATION
# ============================================================


def test_score_above_100_is_clamped():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        make_result(
            ranking_score=150
        )
    )

    assert result.ranking_score == 100


def test_negative_score_is_clamped():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        make_result(
            ranking_score=-10
        )
    )

    assert result.ranking_score == 0
    assert result.decision == SKIP


def test_invalid_score_becomes_zero():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        make_result(
            ranking_score="invalid"
        )
    )

    assert result.ranking_score == 0
    assert result.decision == SKIP


# ============================================================
# BATCH
# ============================================================


def test_decide_many(
    engine,
):
    results = [
        make_result(
            ranking_score=95
        ),
        make_result(
            ranking_score=75
        ),
        make_result(
            ranking_score=20
        ),
    ]

    decisions = engine.decide_many(
        results
    )

    assert len(decisions) == 3

    assert decisions[0].decision == APPLY
    assert decisions[1].decision == REVIEW
    assert decisions[2].decision == SKIP


def test_decide_many_empty(
    engine,
):
    assert engine.decide_many([]) == []


def test_decide_many_requires_list(
    engine,
):
    with pytest.raises(
        TypeError,
        match="ranked_results must be a list",
    ):
        engine.decide_many(None)


# ============================================================
# FILTER
# ============================================================


def test_filter_by_decision(
    engine,
):
    results = [
        make_result(
            ranking_score=95
        ),
        make_result(
            ranking_score=75
        ),
        make_result(
            ranking_score=20
        ),
    ]

    filtered = engine.filter_by_decision(
        results,
        APPLY,
    )

    assert len(filtered) == 1
    assert (
        filtered[0]["ranking_score"]
        == 95
    )


def test_filter_invalid_decision(
    engine,
):
    with pytest.raises(
        ValueError,
        match="Invalid decision",
    ):
        engine.filter_by_decision(
            [],
            "INVALID",
        )


# ============================================================
# CONFIGURABLE BEHAVIOR
# ============================================================


def test_custom_thresholds():
    config = ApplicationDecisionConfig(
        apply_score=90,
        review_score=80,
        outreach_score=60,
    )

    engine = ApplicationDecisionEngine(
        config=config
    )

    result = engine.decide(
        make_result(
            ranking_score=85
        )
    )

    assert result.decision == REVIEW


def test_disable_missing_skill_review():
    config = ApplicationDecisionConfig(
        review_on_missing_required_skills=False
    )

    engine = ApplicationDecisionEngine(
        config=config
    )

    result = engine.decide(
        make_result(
            ranking_score=95,
            missing_required_skills=[
                "PLC"
            ],
        )
    )

    assert result.decision == APPLY


def test_disable_outreach_without_application_url():
    config = ApplicationDecisionConfig(
        outreach_when_application_unavailable=False
    )

    engine = ApplicationDecisionEngine(
        config=config
    )

    result = engine.decide(
        make_result(
            ranking_score=95,
            url="",
        )
    )

    assert result.decision == REVIEW


# ============================================================
# SERIALIZATION
# ============================================================


def test_decision_to_dict(
    engine,
):
    decision = engine.decide(
        make_result(
            ranking_score=92
        )
    )

    data = decision.to_dict()

    assert data["decision"] == APPLY
    assert data["ranking_score"] == 92
    assert data["eligible"] is True

    assert (
        data["recommended_action"]
        == "application"
    )

    assert isinstance(
        data["missing_required_skills"],
        list,
    )


def test_convenience_function():
    data = decide_application_action(
        make_result(
            ranking_score=92
        )
    )

    assert data["decision"] == APPLY
    assert data["ranking_score"] == 92


# ============================================================
# EDGE CASES
# ============================================================


def test_missing_required_skills_string_is_supported():
    engine = ApplicationDecisionEngine()

    result = make_result(
        ranking_score=95
    )

    result["match"][
        "missing_required_skills"
    ] = "PLC"

    decision = engine.decide(
        result
    )

    assert decision.decision == REVIEW
    assert decision.missing_required_skills == (
        "PLC",
    )


def test_duplicate_missing_skills_are_removed():
    engine = ApplicationDecisionEngine()

    result = make_result(
        ranking_score=95
    )

    result["match"][
        "missing_required_skills"
    ] = [
        "PLC",
        "PLC",
        "SCADA",
    ]

    decision = engine.decide(
        result
    )

    assert decision.missing_required_skills == (
        "PLC",
        "SCADA",
    )


def test_exact_apply_threshold():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        make_result(
            ranking_score=85
        )
    )

    assert result.decision == APPLY


def test_exact_review_threshold():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        make_result(
            ranking_score=70
        )
    )

    assert result.decision == REVIEW


def test_exact_outreach_threshold_without_url():
    engine = ApplicationDecisionEngine()

    result = engine.decide(
        make_result(
            ranking_score=50,
            url="",
        )
    )

    assert result.decision == OUTREACH