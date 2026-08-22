from app.agents.agent_memory import AgentMemory


def test_memory_starts_empty(tmp_path):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    assert memory.records() == []


def test_record_event_is_persisted(tmp_path):
    path = tmp_path / "memory.json"

    memory = AgentMemory(path)

    result = memory.record(
        "job_discovered",
        job_id="job-1",
        role_class="electrical_core",
    )

    assert result["event"] == "job_discovered"
    assert result["job_id"] == "job-1"

    restored = AgentMemory(path)

    assert len(
        restored.records()
    ) == 1

    assert (
        restored.records()[0]["job_id"]
        == "job-1"
    )


def test_application_outcome_is_learning_compatible(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    memory.record_application_outcome(
        outcome="interview",
        job_id="job-1",
        role_class="electrical_core",
    )

    history = (
        memory.application_history()
    )

    assert len(history) == 1
    assert (
        history[0]["event"]
        == "application_outcome"
    )
    assert (
        history[0]["outcome"]
        == "interview"
    )
    assert (
        history[0]["role_class"]
        == "electrical_core"
    )


def test_role_history_is_filtered(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    memory.record_application_outcome(
        outcome="interview",
        role_class="electrical_core",
    )

    memory.record_application_outcome(
        outcome="rejected",
        role_class="software",
    )

    history = (
        memory.application_history(
            role_class="electrical_core"
        )
    )

    assert len(history) == 1
    assert (
        history[0]["outcome"]
        == "interview"
    )


def test_outcome_filter_works(tmp_path):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    memory.record_application_outcome(
        outcome="interview",
        role_class="electrical_core",
    )

    memory.record_application_outcome(
        outcome="rejected",
        role_class="electrical_core",
    )

    history = memory.history(
        event="application_outcome",
        outcome="rejected",
    )

    assert len(history) == 1
    assert (
        history[0]["outcome"]
        == "rejected"
    )


def test_job_id_filter_works(tmp_path):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    memory.record_application_outcome(
        outcome="interview",
        job_id="job-1",
    )

    memory.record_application_outcome(
        outcome="rejected",
        job_id="job-2",
    )

    history = (
        memory.application_history(
            job_id="job-1"
        )
    )

    assert len(history) == 1
    assert (
        history[0]["job_id"]
        == "job-1"
    )


def test_count_returns_filtered_count(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    memory.record_application_outcome(
        outcome="interview",
        role_class="embedded",
    )

    memory.record_application_outcome(
        outcome="rejected",
        role_class="embedded",
    )

    memory.record_application_outcome(
        outcome="offer",
        role_class="software",
    )

    assert (
        memory.count(
            role_class="embedded"
        )
        == 2
    )

    assert (
        memory.count(
            outcome="offer"
        )
        == 1
    )


def test_clear_removes_persistent_memory(
    tmp_path,
):
    path = tmp_path / "memory.json"

    memory = AgentMemory(path)

    memory.record_application_outcome(
        outcome="interview",
        role_class="embedded",
    )

    memory.clear()

    assert memory.records() == []

    restored = AgentMemory(path)

    assert restored.records() == []


def test_invalid_event_is_rejected(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    try:
        memory.record("")
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError"
        )


def test_extra_fields_are_preserved(
    tmp_path,
):
    memory = AgentMemory(
        tmp_path / "memory.json"
    )

    result = memory.record(
        "application_attempt",
        job_id="job-9",
        browser="chrome",
        confirmed=True,
    )

    assert (
        result["browser"]
        == "chrome"
    )

    assert (
        result["confirmed"]
        is True
    )