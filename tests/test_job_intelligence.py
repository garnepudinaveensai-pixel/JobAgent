from app.core.job_intelligence import JobIntelligence


def test_sales_role_is_not_a_target():
    result = JobIntelligence.analyze(
        {
            "title": (
                "Sales Engineer/Sales Executive "
                "- Electrical Equipment"
            ),
            "description": (
                "Sell electrical equipment to customers."
            ),
        }
    )

    assert result["technical_target"] is False
    assert result["role_class"] == "non_target"
    assert result["recommended_action"] == "SKIP"


def test_recent_urgent_electrical_role_gets_high_priority():
    result = JobIntelligence.analyze(
        {
            "title": "Electrical Engineer",
            "description": (
                "Urgently hiring. "
                "Posted 1 day ago."
            ),
            "match": {
                "match_score": 85,
                "eligible": True,
            },
        }
    )

    assert result["technical_target"] is True
    assert result["role_class"] == "electrical_core"

    assert result["freshness_score"] >= 90
    assert result["urgency_score"] >= 40

    assert result["priority_score"] > 80
    assert result["recommended_action"] == "APPLY"


def test_recent_job_without_match_data_is_still_prioritized():
    result = JobIntelligence.analyze(
        {
            "title": "Electrical Engineer",
            "description": (
                "Posted 1 day ago."
            ),
        }
    )

    assert result["technical_target"] is True
    assert result["freshness_score"] >= 90

    # Without matching information the job should still
    # receive meaningful priority, but must not be treated
    # as fully qualified.
    assert result["priority_score"] > 30
    assert result["recommended_action"] == "REVIEW"


def test_mixed_plumbing_role_is_excluded():
    result = JobIntelligence.analyze(
        {
            "title": (
                "Electrical & Plumbing Engineers"
            ),
            "description": (
                "Electrical and plumbing design work."
            ),
        }
    )

    assert result["technical_target"] is False
    assert "plumbing" in result["excluded_terms"]
    assert result["recommended_action"] == "SKIP"


def test_embedded_engineer_is_target():
    result = JobIntelligence.analyze(
        {
            "title": "Embedded Systems Engineer",
            "description": (
                "Embedded C, microcontroller, "
                "GPIO, ADC and firmware development."
            ),
        }
    )

    assert result["technical_target"] is True
    assert result["role_class"] == "embedded"


def test_software_engineer_is_target():
    result = JobIntelligence.analyze(
        {
            "title": "Software Engineer",
            "description": (
                "Python, SQL, Git and backend "
                "software development."
            ),
        }
    )

    assert result["technical_target"] is True
    assert result["role_class"] == "software"


def test_automation_engineer_is_target():
    result = JobIntelligence.analyze(
        {
            "title": "Automation Engineer",
            "description": (
                "PLC, SCADA, industrial automation "
                "and control systems."
            ),
        }
    )

    assert result["technical_target"] is True
    assert result["role_class"] == "automation"


def test_closed_job_is_not_applied():
    result = JobIntelligence.analyze(
        {
            "title": "Electrical Engineer",
            "description": (
                "Electrical maintenance engineer."
            ),
            "status": "closed",
            "match": {
                "match_score": 95,
                "eligible": True,
            },
        }
    )

    assert result["technical_target"] is True
    assert result["recommended_action"] == "SKIP"


def test_low_match_target_job_requires_review():
    result = JobIntelligence.analyze(
        {
            "title": "Electrical Engineer",
            "description": (
                "Electrical testing and maintenance."
            ),
            "match": {
                "match_score": 60,
                "eligible": True,
            },
        }
    )

    assert result["technical_target"] is True
    assert result["recommended_action"] == "REVIEW"


def test_high_match_target_job_can_apply():
    result = JobIntelligence.analyze(
        {
            "title": "Electrical Engineer",
            "description": (
                "Electrical engineering and "
                "predictive maintenance."
            ),
            "match": {
                "match_score": 90,
                "eligible": True,
            },
        }
    )

    assert result["technical_target"] is True
    assert result["priority_score"] > 50
    assert result["recommended_action"] == "APPLY"