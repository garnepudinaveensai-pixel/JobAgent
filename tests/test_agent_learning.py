from app.agents.agent_learning import AgentLearning


def test_empty_history_has_neutral_learning_score():
    result = AgentLearning.analyze_history([])

    assert result["history_count"] == 0
    assert result["learning_score"] == 50.0
    assert result["confidence"] == 0.0


def test_successful_application_history_increases_score():
    history = [
        {
            "role_class": "electrical_core",
            "outcome": "interview",
        },
        {
            "role_class": "electrical_core",
            "outcome": "shortlisted",
        },
        {
            "role_class": "electrical_core",
            "outcome": "rejected",
        },
    ]

    result = AgentLearning.analyze_history(
        history,
        role_class="electrical_core",
    )

    assert result["history_count"] == 3
    assert result["successful_count"] == 2
    assert result["learning_score"] > 50
    assert result["confidence"] > 0


def test_repeated_rejections_reduce_score():
    history = [
        {
            "role_class": "software",
            "outcome": "rejected",
        },
        {
            "role_class": "software",
            "outcome": "rejected",
        },
        {
            "role_class": "software",
            "outcome": "rejected",
        },
    ]

    result = AgentLearning.analyze_history(
        history,
        role_class="software",
    )

    assert result["history_count"] == 3
    assert result["successful_count"] == 0
    assert result["learning_score"] < 50


def test_unrelated_roles_do_not_contaminate_role_learning():
    history = [
        {
            "role_class": "electrical_core",
            "outcome": "interview",
        },
        {
            "role_class": "software",
            "outcome": "rejected",
        },
    ]

    result = AgentLearning.analyze_history(
        history,
        role_class="electrical_core",
    )

    assert result["history_count"] == 1
    assert result["successful_count"] == 1
    assert result["learning_score"] > 50


def test_offer_is_strong_success_signal():
    history = [
        {
            "role_class": "automation",
            "outcome": "offer",
        },
    ]

    result = AgentLearning.analyze_history(
        history,
        role_class="automation",
    )

    assert result["learning_score"] >= 90
    assert result["successful_count"] == 1


def test_rejected_and_failed_are_negative_signals():
    history = [
        {
            "role_class": "embedded",
            "outcome": "rejected",
        },
        {
            "role_class": "embedded",
            "outcome": "failed",
        },
    ]

    result = AgentLearning.analyze_history(
        history,
        role_class="embedded",
    )

    assert result["learning_score"] < 50
    assert result["successful_count"] == 0


def test_learning_score_is_bounded():
    history = [
        {
            "role_class": "electrical_core",
            "outcome": "offer",
        }
        for _ in range(100)
    ]

    result = AgentLearning.analyze_history(
        history,
        role_class="electrical_core",
    )

    assert 0 <= result["learning_score"] <= 100
    assert 0 <= result["confidence"] <= 1


def test_learning_explanation_is_present():
    history = [
        {
            "role_class": "electrical_core",
            "outcome": "interview",
        },
        {
            "role_class": "electrical_core",
            "outcome": "rejected",
        },
    ]

    result = AgentLearning.analyze_history(
        history,
        role_class="electrical_core",
    )

    assert result["reason"]
    assert "electrical_core" in result["reason"]


def test_unknown_outcomes_are_ignored():
    history = [
        {
            "role_class": "electrical_core",
            "outcome": "unknown",
        },
        {
            "role_class": "electrical_core",
            "outcome": "applied",
        },
    ]

    result = AgentLearning.analyze_history(
        history,
        role_class="electrical_core",
    )

    assert result["history_count"] == 1