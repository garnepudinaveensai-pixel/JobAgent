from pathlib import Path

import pytest

from app.config import (
    JobAgentConfig,
    JobSearchConfig,
    ApplicationConfig,
    NotificationConfig,
    StorageConfig,
    create_default_config,
)


def test_create_default_config():
    config = create_default_config()

    assert isinstance(config, JobAgentConfig)


def test_default_job_search_config():
    config = JobSearchConfig()

    assert config.keywords == []
    assert config.locations == []
    assert config.minimum_match_score == 60.0
    assert config.auto_select_eligible is False


def test_default_application_config():
    config = ApplicationConfig()

    assert (
        config.resume_path
        == "data/resumes/master_resume.pdf"
    )

    assert (
        config.tailored_resume_directory
        == "data/resumes/tailored"
    )

    assert config.require_confirmation is True
    assert config.auto_submit is False


def test_default_notification_config():
    config = NotificationConfig()

    assert config.email == ""
    assert config.enabled is True

    assert config.notify_on_shortlist is True
    assert config.notify_on_rejection is True
    assert config.notify_on_interview is True
    assert config.notify_on_assessment is True
    assert config.notify_on_walk_in is True
    assert config.notify_on_status_change is True


def test_default_storage_config():
    config = StorageConfig()

    assert (
        config.jobs_file
        == "data/jobs/jobs.json"
    )

    assert (
        config.applications_file
        == "data/jobs/applications.json"
    )


def test_job_agent_config_contains_all_sections():
    config = create_default_config()

    assert isinstance(
        config.search,
        JobSearchConfig,
    )

    assert isinstance(
        config.application,
        ApplicationConfig,
    )

    assert isinstance(
        config.notification,
        NotificationConfig,
    )

    assert isinstance(
        config.storage,
        StorageConfig,
    )


def test_custom_job_search_config():
    config = JobSearchConfig(
        keywords=[
            "Electrical Engineer",
            "Automation Engineer",
        ],
        locations=[
            "Hyderabad",
            "Bangalore",
        ],
        minimum_match_score=75.0,
        auto_select_eligible=True,
    )

    assert config.keywords == [
        "Electrical Engineer",
        "Automation Engineer",
    ]

    assert config.locations == [
        "Hyderabad",
        "Bangalore",
    ]

    assert config.minimum_match_score == 75.0
    assert config.auto_select_eligible is True


def test_custom_application_config():
    config = ApplicationConfig(
        resume_path="data/resumes/my_resume.pdf",
        tailored_resume_directory="data/resumes/tailored",
        require_confirmation=True,
        auto_submit=False,
    )

    assert (
        config.resume_path
        == "data/resumes/my_resume.pdf"
    )

    assert (
        config.tailored_resume_directory
        == "data/resumes/tailored"
    )

    assert config.require_confirmation is True
    assert config.auto_submit is False


def test_custom_notification_config():
    config = NotificationConfig(
        email="test@example.com",
        enabled=True,
        notify_on_shortlist=True,
        notify_on_rejection=True,
        notify_on_interview=True,
        notify_on_assessment=True,
        notify_on_walk_in=True,
        notify_on_status_change=True,
    )

    assert config.email == "test@example.com"
    assert config.enabled is True
    assert config.notify_on_shortlist is True
    assert config.notify_on_rejection is True
    assert config.notify_on_interview is True
    assert config.notify_on_assessment is True
    assert config.notify_on_walk_in is True
    assert config.notify_on_status_change is True


def test_custom_storage_config():
    config = StorageConfig(
        jobs_file="custom/jobs.json",
        applications_file="custom/applications.json",
    )

    assert config.jobs_file == "custom/jobs.json"
    assert (
        config.applications_file
        == "custom/applications.json"
    )


def test_config_validation_accepts_valid_config():
    config = JobAgentConfig(
        notification=NotificationConfig(
            email="test@example.com"
        )
    )

    config.validate()


def test_config_validation_rejects_invalid_match_score():
    config = JobAgentConfig(
        search=JobSearchConfig(
            minimum_match_score=101.0
        ),
        notification=NotificationConfig(
            email="test@example.com"
        ),
    )

    with pytest.raises(ValueError):
        config.validate()


def test_config_validation_rejects_negative_match_score():
    config = JobAgentConfig(
        search=JobSearchConfig(
            minimum_match_score=-1.0
        ),
        notification=NotificationConfig(
            email="test@example.com"
        ),
    )

    with pytest.raises(ValueError):
        config.validate()


def test_config_validation_requires_resume_path():
    config = JobAgentConfig(
        application=ApplicationConfig(
            resume_path=""
        ),
        notification=NotificationConfig(
            email="test@example.com"
        ),
    )

    with pytest.raises(ValueError):
        config.validate()


def test_config_validation_requires_tailored_directory():
    config = JobAgentConfig(
        application=ApplicationConfig(
            tailored_resume_directory=""
        ),
        notification=NotificationConfig(
            email="test@example.com"
        ),
    )

    with pytest.raises(ValueError):
        config.validate()


def test_config_validation_requires_notification_email():
    config = JobAgentConfig(
        notification=NotificationConfig(
            email=""
        )
    )

    with pytest.raises(ValueError):
        config.validate()


def test_config_validation_allows_notifications_disabled():
    config = JobAgentConfig(
        notification=NotificationConfig(
            email="",
            enabled=False,
        )
    )

    config.validate()


def test_ensure_directories(tmp_path):
    jobs_file = tmp_path / "jobs" / "jobs.json"
    applications_file = (
        tmp_path
        / "applications"
        / "applications.json"
    )

    tailored_directory = (
        tmp_path
        / "resumes"
        / "tailored"
    )

    config = JobAgentConfig(
        application=ApplicationConfig(
            tailored_resume_directory=str(
                tailored_directory
            )
        ),
        notification=NotificationConfig(
            email="test@example.com"
        ),
        storage=StorageConfig(
            jobs_file=str(jobs_file),
            applications_file=str(
                applications_file
            ),
        ),
    )

    config.ensure_directories()

    assert tailored_directory.exists()
    assert jobs_file.parent.exists()
    assert applications_file.parent.exists()


def test_create_default_config_does_not_create_directories_automatically(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    config = create_default_config()

    assert isinstance(config, JobAgentConfig)

    # create_default_config() only creates the object.
    # Directory creation happens explicitly through
    # ensure_directories().
    assert not Path(
        "data/resumes/tailored"
    ).exists()