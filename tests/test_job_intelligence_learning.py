from app.core.job_intelligence import JobIntelligence


def electrical_job():
    return {
        "title": "Electrical Engineer",
        "description": (
            "Electrical engineering, "
            "power systems and maintenance."
        ),
        "match": {
            "match_score": 85,
            "resume_score": 85,
            "eligible": True,
            "missing_required_skills": [],
        },
    }


def test_job_intelligence_exposes_learning_fields():
    result = JobIntelligence.analyze(
        electrical_job(),
        history=[
            {
                "role_class": "electrical_core",
                "outcome": "interview",
            },
            {
                "role_class": "electrical_core",
                "outcome": "shortlisted",
            },
        ],
    )

    assert "learning_score" in result
    assert "learning_confidence" in result
    assert "learning_adjustment" in result
    assert "learning_reason" in result


def test_successful_history_boosts_learning_signal():
    result = JobIntelligence.analyze(
        electrical_job(),
        history=[
            {
                "role_class": "electrical_core",
                "outcome": "interview",
            },
            {
                "role_class": "electrical_core",
                "outcome": "offer",
            },
        ],
    )

    assert result["learning_score"] > 50
    assert result["learning_confidence"] > 0
    assert result["learning_adjustment"] > 0


def test_negative_history_reduces_learning_signal():
    result = JobIntelligence.analyze(
        electrical_job(),
        history=[
            {
                "role_class": "electrical_core",
                "outcome": "rejected",
            },
            {
                "role_class": "electrical_core",
                "outcome": "failed",
            },
        ],
    )

    assert result["learning_score"] < 50
    assert result["learning_adjustment"] < 0


def test_unrelated_history_does_not_change_role_learning():
    result = JobIntelligence.analyze(
        electrical_job(),
        history=[
            {
                "role_class": "software",
                "outcome": "offer",
            },
            {
                "role_class": "software",
                "outcome": "interview",
            },
        ],
    )

    assert result["learning_score"] == 50.0
    assert result["learning_confidence"] == 0.0
    assert result["learning_adjustment"] == 0.0


def test_no_history_is_neutral():
    result = JobIntelligence.analyze(
        electrical_job()
    )

    assert result["learning_score"] == 50.0
    assert result["learning_confidence"] == 0.0
    assert result["learning_adjustment"] == 0.0


def test_learning_never_overrides_non_target():
    result = JobIntelligence.analyze(
        {
            "title": "Sales Engineer",
            "description": (
                "Sales of electrical equipment."
            ),
            "match": {
                "match_score": 100,
                "eligible": True,
                "missing_required_skills": [],
            },
        },
        history=[
            {
                "role_class": "non_target",
                "outcome": "offer",
            },
            {
                "role_class": "non_target",
                "outcome": "offer",
            },
        ],
    )

    assert result["technical_target"] is False
    assert result["priority_score"] == 0
    assert result["recommended_action"] == "SKIP"


def test_learning_adjustment_is_bounded():
    result = JobIntelligence.analyze(
        electrical_job(),
        history=[
            {
                "role_class": "electrical_core",
                "outcome": "offer",
            }
            for _ in range(100)
        ],
    )

    assert -10 <= result["learning_adjustment"] <= 10
    assert 0 <= result["priority_score"] <= 100


def test_learning_reason_is_explainable():
    result = JobIntelligence.analyze(
        electrical_job(),
        history=[
            {
                "role_class": "electrical_core",
                "outcome": "interview",
            },
        ],
    )

    assert result["learning_reason"]
    assert "electrical_core" in result["learning_reason"]