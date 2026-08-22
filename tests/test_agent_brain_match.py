from app.agents.agent_brain import LocalAgentBrain


def test_excellent_candidate_fit():
    result = LocalAgentBrain.evaluate_candidate_fit(
        intent="electrical_core",
        confidence=0.95,
        match_score=95,
        eligible=True,
        missing_required_skills=[],
    )

    assert result["candidate_fit_score"] >= 90
    assert result["fit_level"] == "excellent"
    assert result["fit_confidence"] > 0.8
    assert result["eligibility_score"] == 100


def test_strong_candidate_fit():
    result = LocalAgentBrain.evaluate_candidate_fit(
        intent="embedded",
        confidence=0.85,
        match_score=80,
        eligible=True,
        missing_required_skills=[],
    )

    assert result["candidate_fit_score"] >= 70
    assert result["fit_level"] == "strong"


def test_moderate_candidate_fit():
    result = LocalAgentBrain.evaluate_candidate_fit(
        intent="automation",
        confidence=0.75,
        match_score=60,
        eligible=True,
        missing_required_skills=[],
    )

    assert result["fit_level"] == "moderate"
    assert result["candidate_fit_score"] >= 55


def test_missing_required_skills_reduce_fit():
    result = LocalAgentBrain.evaluate_candidate_fit(
        intent="automation",
        confidence=0.90,
        match_score=95,
        eligible=True,
        missing_required_skills=[
            "PLC",
            "SCADA",
        ],
    )

    assert result["candidate_fit_score"] < 90
    assert result["missing_required_skills"] == (
        "PLC",
        "SCADA",
    )


def test_ineligible_candidate_has_zero_eligibility_score():
    result = LocalAgentBrain.evaluate_candidate_fit(
        intent="electrical_core",
        confidence=0.95,
        match_score=95,
        eligible=False,
        missing_required_skills=[],
    )

    assert result["eligibility_score"] == 0
    assert result["candidate_fit_score"] < 70


def test_unknown_match_score_produces_unknown_fit():
    result = LocalAgentBrain.evaluate_candidate_fit(
        intent="electrical_core",
        confidence=0.90,
        match_score=None,
        eligible=None,
        missing_required_skills=[],
    )

    assert result["candidate_fit_score"] == 0
    assert result["fit_level"] == "unknown"
    assert result["fit_confidence"] < 0.5


def test_string_missing_skill_is_supported():
    result = LocalAgentBrain.evaluate_candidate_fit(
        intent="embedded",
        confidence=0.90,
        match_score=90,
        eligible=True,
        missing_required_skills="RTOS",
    )

    assert result["missing_required_skills"] == (
        "RTOS",
    )


def test_invalid_match_score_is_treated_as_unknown():
    result = LocalAgentBrain.evaluate_candidate_fit(
        intent="software",
        confidence=0.80,
        match_score="invalid",
        eligible=True,
        missing_required_skills=[],
    )

    assert result["candidate_fit_score"] == 0
    assert result["fit_level"] == "unknown"


def test_fit_reason_is_explainable():
    result = LocalAgentBrain.evaluate_candidate_fit(
        intent="electrical_core",
        confidence=0.90,
        match_score=90,
        eligible=True,
        missing_required_skills=[
            "PLC",
        ],
    )

    assert "role_fit=electrical_core" in result["fit_reason"]
    assert "match_score=90.0" in result["fit_reason"]
    assert "eligibility=confirmed" in result["fit_reason"]
    assert "missing_required=PLC" in result["fit_reason"]