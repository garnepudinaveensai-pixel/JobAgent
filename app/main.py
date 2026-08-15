from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Optional

from app.config import (
    JobAgentConfig,
    create_default_config,
)
from app.core.agent_runner import AgentRunner
from app.jobs.job_store import JobStore


# ============================================================
# CONFIGURATION
# ============================================================


def load_config() -> JobAgentConfig:
    """
    Load the default JobAgent configuration.

    This can later be extended to support:
        - environment variables
        - .env files
        - JSON configuration
        - YAML configuration
        - user-specific configuration
    """

    return create_default_config()


# ============================================================
# RUNNER CREATION
# ============================================================


def create_runner(
    config: Optional[JobAgentConfig] = None,
) -> AgentRunner:
    """
    Create a fully wired AgentRunner.

    Components:

        JobStore
            ↓
        BrowserManager
            ↓
        ResumeManager
            ↓
        JobMatchPipeline
            ↓
        AgentRunner

    The same JobStore instance is shared with AgentRunner.

    IMPORTANT:
        This function intentionally does NOT call
        config.validate().

        Tests and programmatic callers may create a default
        JobAgentConfig with notifications enabled but without
        an email address.

        Runtime validation is performed by main() after the
        runtime-safe configuration has been prepared.
    """

    # --------------------------------------------------------
    # Load configuration
    # --------------------------------------------------------

    if config is None:
        config = load_config()

    # --------------------------------------------------------
    # Prepare required directories
    # --------------------------------------------------------

    config.ensure_directories()

    # --------------------------------------------------------
    # Shared JobStore
    # --------------------------------------------------------

    job_store = JobStore(
        storage_path=config.storage.jobs_file,
    )

    # --------------------------------------------------------
    # Browser
    # --------------------------------------------------------

    from app.browser.browser_manager import BrowserManager

    browser = BrowserManager(
        headless=False,
    )

    # --------------------------------------------------------
    # Resume manager
    # --------------------------------------------------------

    from app.resume.resume_manager import ResumeManager

    resume_manager = ResumeManager(
        resume_directory="resumes",
        cache_directory="data/cache/resumes",
    )

    # --------------------------------------------------------
    # Job discovery + matching pipeline
    # --------------------------------------------------------

    from app.core.job_match_pipeline import JobMatchPipeline

    job_match_pipeline = JobMatchPipeline(
        browser=browser,
        resume_manager=resume_manager,
    )

    # --------------------------------------------------------
    # Fully wired AgentRunner
    # --------------------------------------------------------

    return AgentRunner(
        config=config,
        job_store=job_store,
        job_match_pipeline=job_match_pipeline,
    )


# ============================================================
# LEGACY SETTINGS SUPPORT
# ============================================================


def load_settings() -> dict:
    """
    Backward-compatible loader for the old settings.json
    format.

    Returns an empty dictionary when the legacy settings file
    does not exist.
    """

    settings_path = Path(
        "config/settings.json"
    )

    if not settings_path.exists():
        return {}

    try:
        with settings_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

    except json.JSONDecodeError as exc:
        raise ValueError(
            "Invalid JSON in config/settings.json."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            "config/settings.json must contain "
            "a JSON object."
        )

    return data


# ============================================================
# RUNTIME CONFIGURATION
# ============================================================


def _prepare_runtime_config(
    config: JobAgentConfig,
) -> JobAgentConfig:
    """
    Prepare a safe runtime copy of the configuration.

    If notifications are enabled but no notification email
    is configured, notifications are disabled only for this
    runtime session.

    The original configuration object is not modified.
    """

    runtime_config = copy.deepcopy(
        config
    )

    notification = runtime_config.notification

    if (
        notification.enabled
        and not notification.email.strip()
    ):
        notification.enabled = False

    return runtime_config


# ============================================================
# STARTUP DISPLAY
# ============================================================


def _print_startup_summary(
    config: JobAgentConfig,
    runner: AgentRunner,
) -> None:
    """
    Display a human-readable JobAgent startup summary.
    """

    summary = runner.summary()

    print("=" * 60)
    print("JobAgent")
    print("=" * 60)

    print(
        "JobAgent started successfully."
    )

    print()

    print(
        f"Resume: "
        f"{config.application.resume_path}"
    )

    print(
        f"Tailored resumes: "
        f"{config.application.tailored_resume_directory}"
    )

    print(
        f"Minimum match score: "
        f"{config.search.minimum_match_score}"
    )

    print(
        f"Notifications enabled: "
        f"{config.notification.enabled}"
    )

    print(
        f"Notification email: "
        f"{config.notification.email or '(not configured)'}"
    )

    print()

    print(
        f"Stored jobs: "
        f"{summary.get('total', 0)}"
    )

    print(
        f"Discovered: "
        f"{summary.get('discovered', 0)}"
    )

    print(
        f"Matched: "
        f"{summary.get('matched', 0)}"
    )

    print(
        f"Selected: "
        f"{summary.get('selected', 0)}"
    )

    print(
        f"Application started: "
        f"{summary.get('application_started', 0)}"
    )

    print(
        f"Applied: "
        f"{summary.get('applied', 0)}"
    )

    print(
        f"Application failed: "
        f"{summary.get('application_failed', 0)}"
    )

    print(
        f"Shortlisted: "
        f"{summary.get('shortlisted', 0)}"
    )

    print(
        f"Rejected: "
        f"{summary.get('rejected', 0)}"
    )

    print(
        f"Interview: "
        f"{summary.get('interview', 0)}"
    )

    print(
        f"Assessment: "
        f"{summary.get('assessment', 0)}"
    )

    print(
        f"Walk-in: "
        f"{summary.get('walk_in', 0)}"
    )

    print(
        f"Status changes: "
        f"{summary.get('status_changed', 0)}"
    )

    print()

    print(
        "Automatic application submission is "
        "not triggered during startup."
    )

    print("=" * 60)


# ============================================================
# MAIN APPLICATION
# ============================================================


def main(
    argv: Optional[list[str]] = None,
) -> int:
    """
    Main JobAgent entry point.

    With command-line arguments:
        Delegate to the CLI.

    Without arguments:
        Perform safe startup and configuration check.

    Returns:
        0 on success.
        1 on startup/configuration failure.
    """

    # --------------------------------------------------------
    # Resolve command-line arguments
    # --------------------------------------------------------

    if argv is None:
        argv = sys.argv[1:]

    # --------------------------------------------------------
    # CLI MODE
    # --------------------------------------------------------

    if argv:
        from app.cli import main as cli_main

        return cli_main(argv)

    # --------------------------------------------------------
    # NORMAL STARTUP MODE
    # --------------------------------------------------------

    try:
        # Load original configuration.
        config = load_config()

        # Create a safe runtime copy.
        runtime_config = _prepare_runtime_config(
            config
        )

        # Validate ONLY the runtime configuration.
        runtime_config.validate()

        # Create the fully wired runner.
        runner = create_runner(
            config=runtime_config
        )

        # Display startup information.
        _print_startup_summary(
            config=runtime_config,
            runner=runner,
        )

        return 0

    # --------------------------------------------------------
    # CONFIGURATION ERRORS
    # --------------------------------------------------------

    except ValueError as exc:

        print(
            f"Configuration error: {exc}"
        )

        return 1

    # --------------------------------------------------------
    # UNEXPECTED ERRORS
    # --------------------------------------------------------

    except Exception as exc:

        print(
            f"JobAgent startup failed: {exc}"
        )

        return 1


# ============================================================
# PYTHON ENTRY POINT
# ============================================================


if __name__ == "__main__":
    raise SystemExit(
        main()
    )