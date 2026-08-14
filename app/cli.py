import argparse
from typing import Optional

from app.config import create_default_config
from app.jobs.job_store import JobStore


# ============================================================
# CONFIGURATION
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    """
    Build the command-line interface parser.
    """

    parser = argparse.ArgumentParser(
        prog="jobagent",
        description="JobAgent - automated job search and application assistant.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # --------------------------------------------------------
    # CONFIG
    # --------------------------------------------------------

    config_parser = subparsers.add_parser(
        "config",
        help="Show current JobAgent configuration.",
    )

    config_parser.set_defaults(
        handler=handle_config,
    )

    # --------------------------------------------------------
    # JOBS
    # --------------------------------------------------------

    jobs_parser = subparsers.add_parser(
        "jobs",
        help="Manage discovered jobs.",
    )

    jobs_subparsers = jobs_parser.add_subparsers(
        dest="jobs_command",
        required=True,
    )

    jobs_subparsers.add_parser(
        "list",
        help="List discovered jobs.",
    ).set_defaults(
        handler=handle_jobs_list,
    )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status_parser = subparsers.add_parser(
        "status",
        help="Show application status.",
    )

    status_parser.add_argument(
        "--status",
        dest="job_status",
        default=None,
        help="Filter by application status.",
    )

    status_parser.set_defaults(
        handler=handle_status,
    )

    return parser


# ============================================================
# COMMAND HANDLERS
# ============================================================

def handle_config(args) -> int:
    """
    Display current configuration.
    """

    config = create_default_config()

    print("JobAgent Configuration")
    print("----------------------")

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
        f"Auto-select eligible: "
        f"{config.search.auto_select_eligible}"
    )

    print(
        f"Require confirmation: "
        f"{config.application.require_confirmation}"
    )

    print(
        f"Auto-submit: "
        f"{config.application.auto_submit}"
    )

    print(
        f"Notification email: "
        f"{config.notification.email or '(not configured)'}"
    )

    print(
        f"Notifications enabled: "
        f"{config.notification.enabled}"
    )

    return 0


def handle_jobs_list(args) -> int:
    """
    Display stored jobs.
    """

    store = JobStore()

    jobs = store.get_all_jobs()

    if not jobs:
        print("No jobs found.")
        return 0

    for index, job in enumerate(
        jobs,
        start=1,
    ):
        print(
            f"{index}. "
            f"{job.get('title', '')} | "
            f"{job.get('company', '')} | "
            f"{job.get('location', '')}"
        )

        print(
            f"   Status: "
            f"{job.get('status', '')}"
        )

        print(
            f"   URL: "
            f"{job.get('url', '')}"
        )

    return 0


def handle_status(args) -> int:
    """
    Display application statuses.
    """

    store = JobStore()

    if args.job_status:
        jobs = store.get_jobs_by_status(
            args.job_status
        )
    else:
        jobs = store.get_all_jobs()

    if not jobs:
        print("No applications found.")
        return 0

    for index, job in enumerate(
        jobs,
        start=1,
    ):
        print(
            f"{index}. "
            f"{job.get('title', '')}"
        )

        print(
            f"   Company: "
            f"{job.get('company', '')}"
        )

        print(
            f"   Status: "
            f"{job.get('status', '')}"
        )

        print(
            f"   URL: "
            f"{job.get('url', '')}"
        )

    return 0


# ============================================================
# MAIN
# ============================================================

def main(
    argv: Optional[list[str]] = None,
) -> int:
    """
    Main CLI entry point.
    """

    parser = build_parser()

    args = parser.parse_args(argv)

    handler = getattr(
        args,
        "handler",
        None,
    )

    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(
        main()
    )