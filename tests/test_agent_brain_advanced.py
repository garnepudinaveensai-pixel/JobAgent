from app.agents.agent_brain import (
    LocalAgentBrain,
)


def test_electrical_role_uses_multiple_signals():
    result = LocalAgentBrain.classify_job(
        {
            "title": "Electrical Engineer",
            "description": (
                "Power systems, transformers, "
                "switchgear and electrical maintenance."
            ),
        }
    )

    assert result.target is True
    assert result.intent == "electrical_core"

    assert result.role_score > 0
    assert result.technical_score > 0
    assert result.confidence > 0.5

    assert (
        result.evidence_strength
        in {
            "moderate",
            "strong",
            "very_strong",
        }
    )


def test_embedded_role_detects_embedded_evidence():
    result = LocalAgentBrain.classify_job(
        {
            "title": "Embedded Systems Engineer",
            "description": (
                "Embedded C, microcontroller, "
                "GPIO, ADC, PWM and firmware."
            ),
        }
    )

    assert result.target is True
    assert result.intent == "embedded"

    assert result.technical_score > 0
    assert result.role_score > 0


def test_automation_role_detects_plc_and_scada():
    result = LocalAgentBrain.classify_job(
        {
            "title": "Automation Engineer",
            "description": (
                "PLC, SCADA, HMI and industrial "
                "control systems."
            ),
        }
    )

    assert result.target is True
    assert result.intent == "automation"


def test_sales_title_is_hard_excluded_even_with_technical_terms():
    result = LocalAgentBrain.classify_job(
        {
            "title": (
                "Sales Engineer - Electrical Equipment"
            ),
            "description": (
                "Electrical equipment, power systems "
                "and customer sales."
            ),
        }
    )

    assert result.target is False
    assert result.intent == "non_target"
    assert result.confidence >= 0.9


def test_mixed_electrical_plumbing_role_is_rejected():
    result = LocalAgentBrain.classify_job(
        {
            "title": (
                "Electrical & Plumbing Engineers"
            ),
            "description": (
                "Electrical and plumbing design work."
            ),
        }
    )

    assert result.target is False
    assert result.intent == "non_target"

    assert (
        result.contradiction_score
        > 0
    )

    assert (
        "plumbing"
        in result.negative_signals
    )


def test_seniority_is_detected_without_rejecting_technical_role():
    result = LocalAgentBrain.classify_job(
        {
            "title": "Senior Electrical Engineer",
            "description": (
                "Power systems and electrical "
                "maintenance."
            ),
        }
    )

    assert result.target is True
    assert result.intent == "electrical_core"
    assert result.seniority == "senior"


def test_entry_level_is_detected():
    result = LocalAgentBrain.classify_job(
        {
            "title": (
                "Graduate Engineer Trainee - Electrical"
            ),
            "description": (
                "Electrical engineering and "
                "maintenance."
            ),
        }
    )

    assert result.target is True
    assert result.intent == "electrical_core"

    assert result.seniority == "entry"


def test_technical_role_with_unclear_family_remains_target():
    result = LocalAgentBrain.classify_job(
        {
            "title": "Technical Engineer",
            "description": (
                "Industrial equipment testing, "
                "thermography and vibration analysis."
            ),
        }
    )

    assert result.target is True
    assert result.intent == "technical"


def test_empty_job_is_uncertain():
    result = LocalAgentBrain.classify_job(
        {}
    )

    assert result.target is False
    assert result.intent == "uncertain"
    assert result.confidence == 0.0


def test_generic_nontechnical_job_is_uncertain():
    result = LocalAgentBrain.classify_job(
        {
            "title": "Office Executive",
            "description": (
                "Handle documentation and "
                "administrative activities."
            ),
        }
    )

    assert result.target is False
    assert result.intent == "uncertain"


def test_priority_remains_bounded():
    for values in (
        (0, 0, 0, 0),
        (100, 100, 100, 100),
        (200, 200, 200, 200),
        (-50, -50, -50, -50),
    ):
        priority = (
            LocalAgentBrain.rank_priority(
                target=True,
                freshness=values[0],
                urgency=values[1],
                match_score=values[2],
                eligibility=values[3],
            )
        )

        assert 0 <= priority <= 100


def test_non_target_always_has_zero_priority():
    priority = (
        LocalAgentBrain.rank_priority(
            target=False,
            freshness=100,
            urgency=100,
            match_score=100,
            eligibility=100,
        )
    )

    assert priority == 0


def test_missing_match_requires_review():
    action = (
        LocalAgentBrain.choose_action(
            technical_target=True,
            eligible=True,
            score=None,
            match_available=False,
        )
    )

    assert action == "REVIEW"


def test_non_target_can_never_apply():
    action = (
        LocalAgentBrain.choose_action(
            technical_target=False,
            eligible=True,
            score=100,
            match_available=True,
        )
    )

    assert action == "SKIP"