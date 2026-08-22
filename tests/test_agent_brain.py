from app.agents.agent_brain import LocalAgentBrain


def test_sales_role_is_rejected():
    result = LocalAgentBrain.classify_job(
        {
            "title": "Sales Engineer",
            "description": (
                "Cold calling customers and "
                "achieving monthly sales targets."
            ),
        }
    )

    assert result.target is False
    assert result.intent == "non_target"


def test_electrical_role_is_detected():
    result = LocalAgentBrain.classify_job(
        {
            "title": "Electrical Engineer",
            "description": (
                "Power electronics, electrical "
                "maintenance and testing."
            ),
        }
    )

    assert result.target is True
    assert result.intent == "electrical_core"
    assert result.confidence > 0.5


def test_embedded_role_is_detected():
    result = LocalAgentBrain.classify_job(
        {
            "title": "Embedded Systems Engineer",
            "description": (
                "Embedded C, microcontroller, "
                "GPIO and firmware development."
            ),
        }
    )

    assert result.target is True
    assert result.intent == "embedded"


def test_priority_prefers_strong_recent_job():
    priority = LocalAgentBrain.rank_priority(
        target=True,
        freshness=100,
        urgency=100,
        match_score=95,
        eligibility=100,
    )

    assert priority > 90


def test_non_target_can_never_be_applied():
    action = LocalAgentBrain.choose_action(
        technical_target=False,
        eligible=True,
        score=99,
    )

    assert action == "SKIP"