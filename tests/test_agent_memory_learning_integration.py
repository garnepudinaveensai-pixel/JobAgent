from app.agents.agent_memory import AgentMemory
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


def test_memory_can_feed_job_intelligence(tmp_path):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    memory.record_application_outcome(
        outcome="interview",
        role_class="electrical_core",
    )

    memory.record_application_outcome(
        outcome="shortlisted",
        role_class="electrical_core",
    )

    result = JobIntelligence.analyze(
        electrical_job(),
        memory=memory,
    )

    assert result["learning_history_count"] == 2
    assert result["learning_confidence"] > 0
    assert result["learning_score"] > 50


def test_memory_uses_only_matching_role_history(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    memory.record_application_outcome(
        outcome="offer",
        role_class="software",
    )

    memory.record_application_outcome(
        outcome="rejected",
        role_class="electrical_core",
    )

    result = JobIntelligence.analyze(
        electrical_job(),
        memory=memory,
    )

    assert result["learning_history_count"] == 1
    assert result["learning_score"] < 50


def test_explicit_history_still_works_with_memory(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    memory.record_application_outcome(
        outcome="rejected",
        role_class="electrical_core",
    )

    result = JobIntelligence.analyze(
        electrical_job(),
        history=[
            {
                "role_class": "electrical_core",
                "outcome": "offer",
            },
        ],
        memory=memory,
    )

    # Explicit history takes precedence over automatic
    # memory retrieval.
    assert result["learning_history_count"] == 1
    assert result["learning_score"] > 50


def test_empty_memory_is_neutral(tmp_path):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    result = JobIntelligence.analyze(
        electrical_job(),
        memory=memory,
    )

    assert result["learning_history_count"] == 0
    assert result["learning_score"] == 50.0
    assert result["learning_confidence"] == 0.0
    assert result["learning_adjustment"] == 0.0


def test_no_memory_remains_backward_compatible():
    result = JobIntelligence.analyze(
        electrical_job()
    )

    assert result["learning_history_count"] == 0
    assert result["learning_score"] == 50.0
    assert result["learning_confidence"] == 0.0


def test_non_target_does_not_use_memory_to_create_priority(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    memory.record_application_outcome(
        outcome="offer",
        role_class="non_target",
    )

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
        memory=memory,
    )

    assert result["technical_target"] is False
    assert result["priority_score"] == 0
    assert result["recommended_action"] == "SKIP"