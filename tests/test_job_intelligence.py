from app.core.job_intelligence import JobIntelligence


def test_sales_role_is_not_a_target():
    result = JobIntelligence.analyze({
        "title": "Sales Engineer/Sales Executive - Electrical Equipment",
        "description": "Sell electrical equipment to customers.",
    })
    assert result["technical_target"] is False
    assert result["role_class"] == "non_target"


def test_recent_urgent_electrical_role_gets_high_priority():
    result = JobIntelligence.analyze({
        "title": "Electrical Engineer",
        "description": "Urgently hiring. Posted 1 day ago.",
    })
    assert result["technical_target"] is True
    assert result["freshness_score"] >= 90
    assert result["urgency_score"] >= 40
    assert result["priority_score"] > 80


def test_mixed_plumbing_role_is_excluded():
    result = JobIntelligence.analyze({
        "title": "Electrical & Plumbing Engineers",
        "description": "Electrical and plumbing design work.",
    })
    assert result["technical_target"] is False
    assert "plumbing" in result["excluded_terms"]
