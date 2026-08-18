from __future__ import annotations

import argparse
from typing import Optional

from app.config import create_default_config
from app.main import (
    create_application_page_factory,
    create_job_agent_service,
    create_runner,
)
from app.jobs.job_store import JobStore
from app.core.application_reporter import ApplicationReporter


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
    # END-TO-END INTELLIGENCE
    # ========================================================

    run_parser = subparsers.add_parser(
        "run",
        help=(
            "Run multi-source discovery, matching, ranking, "
            "recruiter discovery, and outreach preparation."
        ),
    )

    run_parser.add_argument(
        "--keywords",
        required=True,
        help="Job search keywords.",
    )

    run_parser.add_argument(
        "--location",
        default=None,
        help="Optional job location.",
    )

    run_parser.add_argument(
        "--board-url",
        default=None,
        help=(
            "Optional public board URL for sources that "
            "require one, such as Greenhouse, Lever, or Workday."
        ),
    )

    run_parser.add_argument(
        "--min-score",
        type=float,
        default=60.0,
        help="Minimum ranking score from 0 to 100.",
    )

    run_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of ranked jobs.",
    )

    run_parser.add_argument(
        "--eligible-only",
        action="store_true",
        help="Keep only eligible matches.",
    )

    run_parser.add_argument(
        "--no-outreach",
        action="store_true",
        help=(
            "Do not prepare recruiter outreach for outreach decisions."
        ),
    )

    run_parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Explicitly allow real application/email execution. "
            "Without this flag the run is dry-run only."
        ),
    )

    run_parser.add_argument(
        "--outreach-after-apply",
        action="store_true",
        help=(
            "After a successful application, also prepare/send recruiter outreach "
            "for the same job. Sending still requires --execute."
        ),
    )

    run_parser.add_argument(
        "--keep-browser-open",
        action="store_true",
        help=(
            "Keep the browser open after the run for manual inspection. "
            "Press Enter in the terminal to close it."
        ),
    )

    run_parser.set_defaults(
        handler=handle_run,
    )

    # ========================================================
    # LOGIN / SESSION SETUP
    # ========================================================

    login_parser = subparsers.add_parser(
        "login",
        help=(
            "Open a persistent browser profile so you can log in once "
            "to job sites. Cookies/session state are reused later."
        ),
    )

    login_parser.add_argument(
        "--sites",
        default="naukri,indeed,linkedin",
        help=(
            "Comma-separated sites to open. Supported defaults: "
            "naukri, indeed, linkedin. You may also provide URLs "
            "through --urls."
        ),
    )

    login_parser.add_argument(
        "--urls",
        default=None,
        help=(
            "Optional comma-separated URLs to open in the same persistent "
            "profile."
        ),
    )

    login_parser.set_defaults(
        handler=handle_login,
    )

    # ========================================================
    # REPORT
    # ========================================================

    report_parser = subparsers.add_parser(
        "report",
        help="Render a saved JobAgent result JSON file.",
    )

    report_parser.add_argument(
        "--input",
        required=True,
        help="Path to a JSON file containing an execution or run result.",
    )

    report_parser.set_defaults(
        handler=handle_report,
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
        f"Persistent browser profile: "
        f"{config.browser.persistent}"
    )

    print(
        f"Browser profile directory: "
        f"{config.browser.profile_directory}"
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
# END-TO-END HANDLER
# ============================================================


def handle_run(args) -> int:
    """Run the integrated JobAgent service.

    Default mode is safe: applications and outreach are prepared
    but no real submission/sending is allowed. Real execution is
    available only through the explicit ``--execute`` flag.
    """

    print("=" * 60)
    print("JobAgent End-to-End Run")
    print("=" * 60)
    print(f"Keywords: {args.keywords}")
    print(f"Location: {args.location or '(any)'}")
    print(f"Minimum score: {args.min_score}")
    print(f"Limit: {args.limit}")
    print(
        "Execution mode: "
        f"{'LIVE (explicitly enabled)' if args.execute else 'DRY RUN'}"
    )
    print(
        "Outreach preparation: "
        f"{'disabled' if args.no_outreach else 'enabled'}"
    )
    print(
        "Outreach after apply: "
        f"{'enabled' if args.outreach_after_apply and not args.no_outreach else 'disabled'}"
    )
    print()

    service = None
    browser = None

    try:
        service = create_job_agent_service()
        browser = getattr(
            service.runner,
            "browser_manager",
            None,
        )

        source_options = {}
        if args.board_url:
            source_options["board_url"] = args.board_url

        page_factory = create_application_page_factory(
            service
        )

        result = service.run(
            keywords=args.keywords,
            location=args.location,
            min_score=args.min_score,
            limit=args.limit,
            eligible_only=args.eligible_only,
            page_factory=page_factory,
            confirm=bool(args.execute),
            dry_run=not bool(args.execute),
            also_outreach=(
                bool(args.outreach_after_apply)
                and not bool(args.no_outreach)
            ),
            **source_options,
        )

    except Exception as exc:
        print(f"Run failed: {exc}")
        return 1
    finally:
        if browser is not None and not getattr(args, "keep_browser_open", False):
            try:
                browser.close()
            except Exception:
                pass

    data = result.to_dict()

    print()
    print(f"Status: {data.get('status', '')}")
    print(f"Discovered jobs: {data.get('discovered_count', 0)}")
    print(f"Processed jobs: {data.get('processed_count', 0)}")
    print(f"Apply decisions: {data.get('apply_count', 0)}")
    print(f"Outreach decisions: {data.get('outreach_count', 0)}")
    print(f"Review decisions: {data.get('review_count', 0)}")
    print(f"Skipped: {data.get('skip_count', 0)}")
    print(f"Submitted: {data.get('submitted_count', 0)}")
    print(f"Emails sent: {data.get('sent_count', 0)}")
    print(
        "Human action required: "
        f"{data.get('human_action_required_count', 0)}"
    )

    diagnostics = (
        data.get("metadata", {}) or {}
    ).get("source_diagnostics", []) or []

    if diagnostics:
        print()
        print("SOURCE DIAGNOSTICS")
        print("-" * 60)
        for diagnostic in diagnostics:
            source = diagnostic.get("source", "unknown")
            status = diagnostic.get("status", "unknown")
            jobs = diagnostic.get("jobs", 0)
            error = diagnostic.get("error")
            print(f"{source}: {status} | jobs={jobs}")
            if error:
                print(f"   {error}")
            if diagnostic.get("requires_human_action"):
                print("   HUMAN ACTION REQUIRED")

    executions = data.get("executions", []) or []
    if executions:
        print()
        print("RESULTS")
        print("-" * 60)

        for index, execution in enumerate(executions, start=1):
            job = execution.get("job", {}) or {}
            print(
                f"{index}. {job.get('title', '')} | "
                f"{job.get('company', '')}"
            )
            print(
                f"   Decision: {execution.get('decision', '')}"
            )
            print(
                f"   Status: {execution.get('status', '')}"
            )
            print(
                f"   Score: {execution.get('ranking_score', '')}"
            )
            if execution.get("requires_human_action"):
                print("   HUMAN ACTION REQUIRED")
            if execution.get("error"):
                print(
                    f"   Error: {execution.get('error')}"
                )

    if not args.execute:
        print()
        print(
            "DRY RUN: no application was submitted and "
            "no email was sent."
        )
    else:
        print()
        print(
            "LIVE execution was explicitly enabled with --execute."
        )

    if getattr(args, "keep_browser_open", False) and browser is not None:
        try:
            input("Browser is still open. Press Enter to close it... ")
        finally:
            try:
                browser.close()
            except Exception:
                pass

    # JobAgent's run result intentionally remains successful when
    # individual jobs fail; those failures are exposed in errors.
    return 0 if data.get("success", False) else 1


# ============================================================
# LOGIN / SESSION HANDLER
# ============================================================


def handle_login(args) -> int:
    """Open the persistent JobAgent browser profile for one-time logins."""

    site_urls = {
        "naukri": "https://www.naukri.com/",
        "indeed": "https://in.indeed.com/",
        "linkedin": "https://www.linkedin.com/",
        "foundit": "https://www.foundit.in/",
        "shine": "https://www.shine.com/",
        "glassdoor": "https://www.glassdoor.co.in/",
    }

    config = create_default_config()
    config.ensure_directories()

    requested_urls = []

    if args.urls:
        requested_urls.extend(
            value.strip()
            for value in str(args.urls).split(",")
            if value.strip()
        )

    if args.sites:
        for name in str(args.sites).split(","):
            key = name.strip().lower()
            if not key:
                continue
            url = site_urls.get(key)
            if url:
                requested_urls.append(url)
            else:
                print(
                    f"Unknown site '{key}'. Use --urls for a custom site URL."
                )

    # Preserve order while removing duplicate URLs.
    requested_urls = list(dict.fromkeys(requested_urls))

    if not requested_urls:
        print("No valid sites or URLs were supplied.")
        return 2

    from app.browser.browser_manager import BrowserManager

    browser = BrowserManager(
        headless=False,
        timeout=config.browser.timeout,
        persistent_profile_dir=config.browser.profile_directory,
    )

    print("=" * 60)
    print("JobAgent Persistent Login Setup")
    print("=" * 60)
    print(f"Profile: {browser.profile_directory}")
    print()
    print("Log in manually in the opened browser windows.")
    print("Do not give JobAgent your passwords or OTPs.")
    print("CAPTCHA/verification must always be completed by you.")
    print()

    try:
        browser.start()

        for url in requested_urls:
            try:
                page = browser.open(url)
                print(f"Opened: {url}")
                print(f"Current URL: {page.url}")
            except Exception as exc:
                print(f"Could not open {url}: {exc}")

        input(
            "\nAfter you finish logging in, press Enter to save the session and close the browser... "
        )
        return 0

    finally:
        browser.close()


# ============================================================
# REPORT HANDLER
# ============================================================


def handle_report(args) -> int:
    """Render a saved execution/run result as a human-readable report."""

    try:
        result = ApplicationReporter.load_json(args.input)
        print(ApplicationReporter.render(result))
        return 0
    except Exception as exc:
        print(f"Report failed: {exc}")
        return 1


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