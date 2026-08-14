from app.cli import (
    build_parser,
    main,
)


# ============================================================
# PARSER
# ============================================================

def test_build_parser():
    parser = build_parser()

    assert parser is not None


# ============================================================
# CONFIG
# ============================================================

def test_config_command(capsys):
    result = main(
        ["config"]
    )

    assert result == 0

    output = capsys.readouterr().out

    assert "JobAgent Configuration" in output
    assert "Resume:" in output
    assert "Minimum match score:" in output
    assert "Auto-submit:" in output
    assert "Notification email:" in output


# ============================================================
# JOBS
# ============================================================

def test_jobs_list_command_empty_store(
    tmp_path,
    monkeypatch,
    capsys,
):
    storage = (
        tmp_path
        / "jobs"
        / "jobs.json"
    )

    monkeypatch.setattr(
        "app.cli.JobStore",
        lambda: __import__(
            "app.jobs.job_store",
            fromlist=["JobStore"],
        ).JobStore(
            storage_path=str(storage)
        ),
    )

    result = main(
        ["jobs", "list"]
    )

    assert result == 0

    output = capsys.readouterr().out

    assert "No jobs found." in output


# ============================================================
# STATUS
# ============================================================

def test_status_command_empty_store(
    tmp_path,
    monkeypatch,
    capsys,
):
    storage = (
        tmp_path
        / "jobs"
        / "jobs.json"
    )

    monkeypatch.setattr(
        "app.cli.JobStore",
        lambda: __import__(
            "app.jobs.job_store",
            fromlist=["JobStore"],
        ).JobStore(
            storage_path=str(storage)
        ),
    )

    result = main(
        ["status"]
    )

    assert result == 0

    output = capsys.readouterr().out

    assert "No applications found." in output


def test_status_command_with_filter(
    tmp_path,
    monkeypatch,
    capsys,
):
    from app.jobs.job_store import JobStore

    storage = (
        tmp_path
        / "jobs"
        / "jobs.json"
    )

    store = JobStore(
        storage_path=str(storage)
    )

    store.add_job(
        {
            "title": "Electrical Engineer",
            "company": "Example Company",
            "location": "Hyderabad",
            "url": "https://example.com/job/1",
        },
        status="shortlisted",
    )

    monkeypatch.setattr(
        "app.cli.JobStore",
        lambda: JobStore(
            storage_path=str(storage)
        ),
    )

    result = main(
        [
            "status",
            "--status",
            "shortlisted",
        ]
    )

    assert result == 0

    output = capsys.readouterr().out

    assert "Electrical Engineer" in output
    assert "Example Company" in output
    assert "shortlisted" in output


# ============================================================
# JOB LIST
# ============================================================

def test_jobs_list_command_with_jobs(
    tmp_path,
    monkeypatch,
    capsys,
):
    from app.jobs.job_store import JobStore

    storage = (
        tmp_path
        / "jobs"
        / "jobs.json"
    )

    store = JobStore(
        storage_path=str(storage)
    )

    store.add_job(
        {
            "title": "Graduate Engineer Trainee",
            "company": "Example Company",
            "location": "Bangalore",
            "url": "https://example.com/job/2",
        }
    )

    monkeypatch.setattr(
        "app.cli.JobStore",
        lambda: JobStore(
            storage_path=str(storage)
        ),
    )

    result = main(
        ["jobs", "list"]
    )

    assert result == 0

    output = capsys.readouterr().out

    assert "Graduate Engineer Trainee" in output
    assert "Example Company" in output
    assert "Bangalore" in output


# ============================================================
# INVALID COMMAND
# ============================================================

def test_invalid_command():
    try:
        main(
            ["invalid-command"]
        )
    except SystemExit as exc:
        assert exc.code != 0