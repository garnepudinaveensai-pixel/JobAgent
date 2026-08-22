from app.core.job_intelligence import JobIntelligence


def test_job_intelligence_exposes_candidate_fit():
    result = JobIntelligence.analyze(
        {
            "title": "Electrical Engineer",
            "description": (
                "Electrical engineering, "
                "power systems and maintenance."
            ),
            "match": {
                "match_score": 95,
                "resume_score": 95,
                "eligible": True,
                "missing_required_skills": [],
            },
        }
    )

    assert result["technical_target"] is True
    assert result["candidate_fit_score"] >= 90
    assert result["fit_level"] == "excellent"
    assert result["fit_confidence"] > 0.8
    assert result["eligibility_score"] == 100


def test_job_intelligence_handles_unknown_candidate_fit():
    result = JobIntelligence.analyze(
        {
            "title": "Electrical Engineer",
            "description": (
                "Electrical engineering."
            ),
        }
    )

    assert result["technical_target"] is True
    assert result["fit_level"] == "unknown"
    assert result["candidate_fit_score"] == 0
    assert result["recommended_action"] == "REVIEW"


def test_missing_required_skills_reduce_candidate_fit():
    result = JobIntelligence.analyze(
        {
            "title": "Automation Engineer",
            "description": (
                "PLC, SCADA and industrial automation."
            ),
            "match": {
                "match_score": 95,
                "resume_score": 95,
                "eligible": True,
                "missing_required_skills": [
                    "PLC",
                    "SCADA",
                ],
            },
        }
    )

    assert result["technical_target"] is True
    assert result["candidate_fit_score"] < 90
    assert result["fit_level"] != "excellent"
    assert "PLC" in result["missing_required_skills"]
    assert "SCADA" in result["missing_required_skills"]


def test_ineligible_candidate_is_not_high_fit():
    result = JobIntelligence.analyze(
        {
            "title": "Electrical Engineer",
            "description": (
                "Electrical engineering."
            ),
            "match": {
                "match_score": 95,
                "resume_score": 95,
                "eligible": False,
                "missing_required_skills": [],
            },
        }
    )

    assert result["technical_target"] is True
    assert result["eligibility_score"] == 0
    assert result["candidate_fit_score"] < 70


def test_candidate_fit_reason_is_explainable():
    result = JobIntelligence.analyze(
        {
            "title": "Electrical Engineer",
            "description": (
                "Electrical engineering."
            ),
            "match": {
                "match_score": 90,
                "resume_score": 90,
                "eligible": True,
                "missing_required_skills": [
                    "PLC",
                ],
            },
        }
    )

    assert "fit_reason" in result
    assert "role_fit=electrical_core" in result["fit_reason"]
    assert "match_score=90.0" in result["fit_reason"]
    assert "eligibility=confirmed" in result["fit_reason"]
    assert "missing_required=PLC" in result["fit_reason"]


def test_non_target_never_gets_candidate_priority():
    result = JobIntelligence.analyze(
        {
            "title": "Sales Engineer",
            "description": (
                "Sales of electrical equipment."
            ),
            "match": {
                "match_score": 100,
                "resume_score": 100,
                "eligible": True,
                "missing_required_skills": [],
            },
        }
    )

    assert result["technical_target"] is False
    assert result["priority_score"] == 0
    assert result["recommended_action"] == "SKIP"