from app.core.application_history import (
    ApplicationHistory,
)


def job(url="https://example.com/jobs/1"):
    return {
        "job_id": "job-1",
        "title": "Electrical Engineer",
        "company": "Example Energy",
        "location": "Hyderabad",
        "url": url,
    }


def test_record_and_get(tmp_path):
    history = ApplicationHistory(str(tmp_path / "history.json"))

    record = history.record(
        job(),
        decision="apply",
        status="prepared",
    )

    assert record.status == "prepared"
    assert record.decision == "apply"
    assert history.has(job())
    assert history.get(job()).history_id == record.history_id


def test_duplicate_job_updates_existing_record(tmp_path):
    history = ApplicationHistory(str(tmp_path / "history.json"))

    first = history.record(job(), decision="apply", status="prepared")
    second = history.record(job(), decision="apply", status="applied", submitted=True)

    assert first.history_id == second.history_id
    assert history.count() == 1
    assert history.get(job()).status == "applied"
    assert history.get(job()).submitted is True


def test_canonical_url_prevents_tracking_parameter_duplicate(tmp_path):
    history = ApplicationHistory(str(tmp_path / "history.json"))

    history.record(job("https://example.com/jobs/1?utm_source=indeed"))

    assert history.has(
        job("https://example.com/jobs/1?utm_source=naukri")
    )


def test_company_title_identity_without_url(tmp_path):
    history = ApplicationHistory(str(tmp_path / "history.json"))

    first = {
        "title": "Electrical Engineer",
        "company": "Example Energy",
        "location": "Hyderabad",
    }
    second = {
        "title": " Electrical Engineer ",
        "company": " Example Energy ",
        "location": "Hyderabad",
    }

    history.record(first)
    assert history.has(second)


def test_job_id_identity_without_url(tmp_path):
    history = ApplicationHistory(str(tmp_path / "history.json"))

    first = {"job_id": "ABC-123", "title": "Engineer", "company": "X"}
    second = {"job_id": "abc-123", "title": "Changed Title", "company": "X"}

    history.record(first)
    assert history.has(second)


def test_persistence(tmp_path):
    path = tmp_path / "history.json"

    history = ApplicationHistory(str(path))
    history.record(job(), status="captcha_detected",
                   human_action_required=True)

    restored = ApplicationHistory(str(path))
    record = restored.get(job())

    assert record is not None
    assert record.status == "captcha_detected"
    assert record.human_action_required is True


def test_list_and_count_by_status(tmp_path):
    history = ApplicationHistory(str(tmp_path / "history.json"))

    history.record(job("https://example.com/1"), status="applied")
    history.record(job("https://example.com/2"), status="captcha_detected")

    assert history.count() == 2
    assert history.count("applied") == 1
    assert len(history.list_records(status="captcha_detected")) == 1


def test_is_processed_can_exclude_skipped(tmp_path):
    history = ApplicationHistory(str(tmp_path / "history.json"))

    history.record(job(), decision="skip", status="skipped")

    assert history.is_processed(job()) is True
    assert history.is_processed(job(), include_skipped=False) is False


def test_update_existing_record(tmp_path):
    history = ApplicationHistory(str(tmp_path / "history.json"))

    history.record(job(), decision="apply", status="prepared")

    updated = history.update(
        job(),
        status="login_required",
        human_action_required=True,
        error="Login required.",
    )

    assert updated.status == "login_required"
    assert updated.human_action_required is True
    assert updated.error == "Login required."


def test_remove(tmp_path):
    history = ApplicationHistory(str(tmp_path / "history.json"))

    history.record(job())

    assert history.remove(job()) is True
    assert history.has(job()) is False
    assert history.remove(job()) is False


def test_invalid_job_rejected(tmp_path):
    history = ApplicationHistory(str(tmp_path / "history.json"))

    import pytest
    with pytest.raises(ValueError):
        history.record({"title": "Engineer"})


def test_invalid_status_rejected(tmp_path):
    history = ApplicationHistory(str(tmp_path / "history.json"))

    import pytest
    with pytest.raises(ValueError, match="Invalid application history status"):
        history.record(job(), status="not-a-real-status")
