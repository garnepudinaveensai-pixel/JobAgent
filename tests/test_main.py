from pathlib import Path

from app.config import (
    JobAgentConfig,
    JobSearchConfig,
    ApplicationConfig,
    NotificationConfig,
)
from app.main import (
    create_runner,
    load_config,
    load_settings,
    main,
)


def test_load_config():

    config = load_config()

    assert isinstance(
        config,
        JobAgentConfig,
    )


def test_load_config_has_default_search_config():

    config = load_config()

    assert isinstance(
        config.search,
        JobSearchConfig,
    )


def test_load_config_has_application_config():

    config = load_config()

    assert isinstance(
        config.application,
        ApplicationConfig,
    )


def test_load_config_has_notification_config():

    config = load_config()

    assert isinstance(
        config.notification,
        NotificationConfig,
    )


def test_create_runner():

    config = JobAgentConfig()

    runner = create_runner(
        config=config,
    )

    assert runner is not None

    assert runner.config is config


def test_create_runner_creates_directories(
    tmp_path,
):

    config = JobAgentConfig()

    config.application.tailored_resume_directory = str(
        tmp_path / "tailored"
    )

    config.storage.jobs_file = str(
        tmp_path / "jobs" / "jobs.json"
    )

    config.storage.applications_file = str(
        tmp_path / "applications" / "applications.json"
    )

    runner = create_runner(
        config=config,
    )

    assert runner is not None

    assert Path(
        config.application.tailored_resume_directory
    ).exists()

    assert Path(
        config.storage.jobs_file
    ).parent.exists()

    assert Path(
        config.storage.applications_file
    ).parent.exists()


def test_load_settings_returns_dict():

    settings = load_settings()

    assert isinstance(
        settings,
        dict,
    )


def test_main_without_arguments(
    capsys,
    tmp_path,
    monkeypatch,
):

    config = JobAgentConfig()

    config.application.tailored_resume_directory = str(
        tmp_path / "tailored"
    )

    config.storage.jobs_file = str(
        tmp_path / "jobs" / "jobs.json"
    )

    config.storage.applications_file = str(
        tmp_path / "applications" / "applications.json"
    )

    monkeypatch.setattr(
        "app.main.load_config",
        lambda: config,
    )

    result = main([])

    captured = capsys.readouterr()

    assert result == 0

    assert (
        "JobAgent started successfully."
        in captured.out
    )

    assert (
        "Automatic application submission"
        in captured.out
    )


def test_main_invalid_configuration(
    capsys,
    monkeypatch,
):

    config = JobAgentConfig()

    config.search.minimum_match_score = 150

    monkeypatch.setattr(
        "app.main.load_config",
        lambda: config,
    )

    result = main([])

    captured = capsys.readouterr()

    assert result == 1

    assert (
        "Configuration error:"
        in captured.out
    )


def test_main_cli_delegates(
    monkeypatch,
):

    called = {}

    def fake_cli(argv):

        called["argv"] = argv

        return 7

    monkeypatch.setattr(
        "app.cli.main",
        fake_cli,
    )

    result = main(
        [
            "config",
        ]
    )

    assert result == 7

    assert called["argv"] == [
        "config",
    ]