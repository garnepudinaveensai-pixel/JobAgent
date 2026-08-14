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


# ============================================================
# CONFIGURATION
# ============================================================


def load_config() -> JobAgentConfig:
    """
    Load the default JobAgent configuration.

    This function can later be extended to support:

    - environment variables
    - .env files
    - JSON configuration
    - YAML configuration
    - user-specific configuration
    """

    return create_default_config()


def create_runner(
    config: Optional[JobAgentConfig] = None,
) -> AgentRunner:
    """
    Create and initialize an AgentRunner.

    If a configuration is supplied, it is used directly.
    Otherwise, the default configuration is loaded.

    Required directories are created before the runner
    is returned.
    """

    if config is None:
        config = load_config()

    config.ensure_directories()

    return AgentRunner(
        config=config,
    )


# ============================================================
# LEGACY SETTINGS SUPPORT
# ============================================================


def load_settings() -> dict:
    """
    Backward-compatible loader for the old settings.json
    format.

    The newer JobAgent architecture uses JobAgentConfig.

    Returns:
        Dictionary containing legacy settings.

    If config/settings.json does not exist, an empty
    dictionary is returned.
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

    A fresh installation may have notifications enabled but
    no email address configured yet.

    Instead of modifying the user's original configuration,
    create a copy and disable notifications only for this
    runtime session.

    Other configuration errors are still allowed to fail
    normally during validation.
    """

    runtime_config = copy.deepcopy(
        config
    )

    if (
        runtime_config.notification.enabled
        and not runtime_config.notification.email.strip()
    ):
        runtime_config.notification.enabled = False

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
        Perform a safe startup and configuration check.

    Returns:
        0 on success.
        1 on configuration/startup failure.
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
        # Load user's configuration.
        config = load_config()

        # Create a runtime-safe copy.
        runtime_config = _prepare_runtime_config(
            config
        )

        # Validate the runtime configuration.
        runtime_config.validate()

        # Create required directories only after
        # configuration has passed validation.
        runtime_config.ensure_directories()

        # Create high-level runner.
        runner = AgentRunner(
            config=runtime_config,
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