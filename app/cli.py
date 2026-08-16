from __future__ import annotations

import argparse
from typing import Optional

from app.config import create_default_config
from app.main import create_runner
from app.jobs.job_store import JobStore


# ============================================================
# PARSER
# ============================================================


def build_parser() -> argparse.ArgumentParser:
    """
    Build the JobAgent command-line interface.
    """

    parser = argparse.ArgumentParser(
        prog="jobagent",
        description=(
            "JobAgent - automated job search and "
            "application assistant."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # ========================================================
    # CONFIG
    # ========================================================

    config_parser = subparsers.add_parser(
        "config",
        help="Show current JobAgent configuration.",
    )

    config_parser.set_defaults(
        handler=handle_config,
    )

    # ========================================================
    # JOBS
    # ========================================================

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

    # ========================================================
    # DISCOVER
    # ========================================================

    discover_parser = subparsers.add_parser(
        "discover",
        help=(
            "Discover and match jobs from a supported "
            "job-board source."
        ),
    )

    discover_parser.add_argument(
        "--source",
        choices=[
            "greenhouse",
            "lever",
            "workday",
            "indeed",
            "naukri",
        ],
        default="greenhouse",
        help=(
            "Job source. "
            "Default: greenhouse."
        ),
    )

    discover_parser.add_argument(
        "--board-url",
        required=True,
        help=(
            "Public job-board URL. "
            "Example: "
            "https://boards.greenhouse.io/company"
        ),
    )

    discover_parser.add_argument(
        "--keywords",
        required=True,
        help=(
            "Job search keywords. "
            "Example: electrical engineer"
        ),
    )

    discover_parser.add_argument(
        "--location",
        default=None,
        help=(
            "Optional job location. "
            "Example: Hyderabad"
        ),
    )

    discover_parser.add_argument(
        "--store",
        action="store_true",
        help=(
            "Store discovered jobs in the "
            "JobAgent database."
        ),
    )

    discover_parser.set_defaults(
        handler=handle_discover,
    )

    # ========================================================
    # STATUS
    # ========================================================

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
# CONFIG HANDLER
# ============================================================


def handle_config(args) -> int:
    """
    Display current JobAgent configuration.
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


# ============================================================
# JOB LIST HANDLER
# ============================================================


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


# ============================================================
# DISCOVERY HANDLER
# ============================================================


def handle_discover(args) -> int:
    """
    Discover jobs from a selected supported source.

    By default this only discovers and displays results.

    If --store is supplied, discovered jobs are also
    persisted in the JobAgent job database.
    """

    print("=" * 60)
    print("JobAgent Job Discovery")
    print("=" * 60)

    print(
        f"Source: {args.source}"
    )

    print(
        f"Board URL: {args.board_url}"
    )

    print(
        f"Keywords: {args.keywords}"
    )

    print(
        f"Location: "
        f"{args.location or '(any)'}"
    )

    print()

    print(
        "Starting browser and discovering jobs..."
    )

    try:
        runner = create_runner()

        results = runner.discover_from_sources(
            keywords=args.keywords,
            location=args.location,
            board_url=args.board_url,
        )

        # Keep only jobs belonging to the requested
        # source.
        results = [
            job
            for job in results
            if job.get("source") == args.source
        ]

    except Exception as exc:
        print()
        print(
            f"Discovery failed: {exc}"
        )
        return 1

    print()

    if not results:
        print(
            "No matching jobs were found."
        )
        return 0

    print(
        f"Jobs discovered: "
        f"{len(results)}"
    )

    print()

    # --------------------------------------------------------
    # Display results
    # --------------------------------------------------------

    for index, job in enumerate(
        results,
        start=1,
    ):
        title = job.get(
            "title",
            "",
        )

        company = job.get(
            "company",
            "",
        )

        location = job.get(
            "location",
            "",
        )

        url = job.get(
            "url",
            "",
        )

        description = job.get(
            "description",
            "",
        )

        print(
            f"{index}. {title}"
        )

        print(
            f"   Company: {company}"
        )

        print(
            f"   Location: {location}"
        )

        print(
            f"   Source: {job.get('source', '')}"
        )

        if url:
            print(
                f"   URL: {url}"
            )

        if description:
            print(
                f"   Description: "
                f"{description[:200]}"
            )

        print()

    # --------------------------------------------------------
    # Optional storage
    # --------------------------------------------------------

    if args.store:
        print(
            "Storing discovered jobs..."
        )

        runner = create_runner()

        job_ids = runner.store_jobs(
            results
        )

        print(
            f"Stored jobs: "
            f"{len(job_ids)}"
        )

    return 0


# ============================================================
# STATUS HANDLER
# ============================================================


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
        print(
            "No applications found."
        )
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

    args = parser.parse_args(
        argv
    )

    handler = getattr(
        args,
        "handler",
        None,
    )

    if handler is None:
        parser.print_help()
        return 1

    return handler(
        args
    )


# ============================================================
# PYTHON ENTRY POINT
# ============================================================


if __name__ == "__main__":
    raise SystemExit(
        main()
    )