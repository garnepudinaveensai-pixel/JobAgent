from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


SAFETY_STATUSES = {
    "captcha_detected",
    "login_required",
    "human_action_required",
    "job_unavailable",
    "form_not_found",
    "navigation_failed",
    "submission_timeout",
    "submission_failed",
}

STATUS_LABELS = {
    "applied": "APPLIED",
    "skipped": "SKIPPED",
    "review": "MANUAL REVIEW",
    "outreach_prepared": "OUTREACH PREPARED",
    "confirmation_required": "CONFIRMATION REQUIRED",
    "captcha_detected": "CAPTCHA DETECTED",
    "login_required": "LOGIN REQUIRED",
    "human_action_required": "HUMAN ACTION REQUIRED",
    "job_unavailable": "JOB UNAVAILABLE",
    "form_not_found": "FORM NOT FOUND",
    "navigation_failed": "NAVIGATION FAILED",
    "validation_failed": "VALIDATION FAILED",
    "application_prepare_failed": "APPLICATION PREPARATION FAILED",
    "application_preparation_failed": "APPLICATION PREPARATION FAILED",
    "submission_timeout": "SUBMISSION TIMEOUT",
    "submission_failed": "SUBMISSION FAILED",
    "job_execution_failed": "JOB EXECUTION FAILED",
    "dry_run_completed": "DRY RUN COMPLETED",
    "completed": "COMPLETED",
    "completed_with_errors": "COMPLETED WITH ERRORS",
}

NEXT_ACTIONS = {
    "captcha_detected": "Complete the CAPTCHA or verification manually, then retry the application step.",
    "login_required": "Log in to the job site manually, then retry the application step.",
    "human_action_required": "Complete the requested human verification/action, then retry.",
    "job_unavailable": "Do not submit. Verify whether the job is still open or remove it from the queue.",
    "form_not_found": "Review the application URL and page structure before retrying.",
    "navigation_failed": "Verify the application URL and browser/network access before retrying.",
    "validation_failed": "Complete the missing or invalid application fields before submitting.",
    "application_prepare_failed": "Review the preparation error and correct the application inputs.",
    "application_preparation_failed": "Review the preparation error and correct the application inputs.",
    "submission_timeout": "Verify whether the application was submitted before attempting another submission.",
    "submission_failed": "Review the submission error and retry only after confirming the previous attempt did not succeed.",
    "confirmation_required": "Review the prepared application and explicitly confirm before submission.",
    "applied": "No further action is required unless the employer requests follow-up.",
    "skipped": "No application action was taken for this job.",
    "review": "Review the job manually before deciding whether to apply.",
    "outreach_prepared": "Review the prepared outreach message before sending it.",
}


@dataclass(frozen=True)
class ApplicationReport:
    """Human-readable summary of one application execution result."""

    job_title: str = ""
    company: str = ""
    location: str = ""
    ranking_score: Optional[float] = None
    decision: str = ""
    status: str = ""
    status_label: str = ""
    success: bool = False
    prepared: bool = False
    submitted: bool = False
    sent: bool = False
    confirmation_required: bool = False
    requires_human_action: bool = False
    message: str = ""
    error: str = ""
    reason: str = ""
    next_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ApplicationReporter:
    """Render structured JobAgent application results for humans and logs."""

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        if hasattr(value, "to_dict") and callable(value.to_dict):
            converted = value.to_dict()
            return dict(converted) if isinstance(converted, Mapping) else {}
        if hasattr(value, "__dataclass_fields__"):
            return asdict(value)
        return {}

    @classmethod
    def _status(cls, data: Mapping[str, Any]) -> str:
        status = str(data.get("status", "")).strip().lower()
        if status:
            return status
        if data.get("submitted"):
            return "applied"
        if data.get("requires_human_action"):
            return "human_action_required"
        return "unknown"

    @classmethod
    def _job(cls, data: Mapping[str, Any]) -> dict[str, Any]:
        job = data.get("job")
        return dict(job) if isinstance(job, Mapping) else {}

    @classmethod
    def from_execution_result(cls, result: Any) -> ApplicationReport:
        data = cls._as_dict(result)
        job = cls._job(data)
        status = cls._status(data)
        decision = str(data.get("decision", "")).strip().upper()
        metadata = data.get("metadata") if isinstance(data.get("metadata"), Mapping) else {}
        result_data = data.get("result") if isinstance(data.get("result"), Mapping) else {}

        requires_human = bool(
            data.get("requires_human_action")
            or metadata.get("requires_human_action")
            or result_data.get("requires_human_action")
            or status in SAFETY_STATUSES and status in {
                "captcha_detected",
                "login_required",
                "human_action_required",
            }
        )

        reason = str(
            data.get("message")
            or data.get("error")
            or result_data.get("message", "")
            or result_data.get("error", "")
            or ""
        ).strip()

        return ApplicationReport(
            job_title=str(job.get("title", "")).strip(),
            company=str(job.get("company", "")).strip(),
            location=str(job.get("location", "")).strip(),
            ranking_score=(
                float(data["ranking_score"])
                if data.get("ranking_score") is not None
                else None
            ),
            decision=decision,
            status=status,
            status_label=STATUS_LABELS.get(status, status.replace("_", " ").upper()),
            success=bool(data.get("success", False)),
            prepared=bool(data.get("prepared", result_data.get("prepared", False))),
            submitted=bool(data.get("submitted", result_data.get("submitted", False))),
            sent=bool(data.get("sent", result_data.get("sent", False))),
            confirmation_required=bool(data.get("confirmation_required", result_data.get("confirmation_required", False))),
            requires_human_action=requires_human,
            message=str(data.get("message", "") or "").strip(),
            error=str(data.get("error", "") or result_data.get("error", "") or "").strip(),
            reason=reason,
            next_action=NEXT_ACTIONS.get(status, "Review the result and determine the next safe action."),
        )

    @classmethod
    def format_execution_result(cls, result: Any) -> str:
        report = cls.from_execution_result(result)
        lines = [
            "=" * 60,
            "JOB AGENT APPLICATION REPORT",
            "=" * 60,
            "",
        ]
        if report.job_title:
            lines.append(f"Job: {report.job_title}")
        if report.company:
            lines.append(f"Company: {report.company}")
        if report.location:
            lines.append(f"Location: {report.location}")
        if report.ranking_score is not None:
            lines.append(f"Match Score: {report.ranking_score:g}")
        if report.job_title or report.company or report.location or report.ranking_score is not None:
            lines.append("")

        lines.extend([
            f"Decision: {report.decision or '(not specified)'}",
            f"Status: {report.status_label}",
            "",
            f"Prepared: {'YES' if report.prepared else 'NO'}",
            f"Submitted: {'YES' if report.submitted else 'NO'}",
            f"Outreach Sent: {'YES' if report.sent else 'NO'}",
            f"Confirmation Required: {'YES' if report.confirmation_required else 'NO'}",
            f"Human Action Required: {'YES' if report.requires_human_action else 'NO'}",
        ])

        if report.reason:
            lines.extend(["", "Reason:", f"  {report.reason}"])
        if report.error and report.error != report.reason:
            lines.extend(["", "Error:", f"  {report.error}"])
        if report.next_action:
            lines.extend(["", "Next Action:", f"  {report.next_action}"])

        lines.extend(["", "=" * 60])
        return "\n".join(lines)

    @classmethod
    def format_run_result(cls, result: Any) -> str:
        data = cls._as_dict(result)
        lines = [
            "=" * 60,
            "JOB AGENT RUN REPORT",
            "=" * 60,
            "",
            f"Status: {STATUS_LABELS.get(str(data.get('status', '')).lower(), str(data.get('status', '')).upper() or 'UNKNOWN')}",
            f"Keywords: {data.get('keywords', '')}",
            f"Location: {data.get('location') or '(any)'}",
            "",
            f"Discovered: {data.get('discovered_count', 0)}",
            f"Processed: {data.get('processed_count', 0)}",
            f"Apply: {data.get('apply_count', 0)}",
            f"Review: {data.get('review_count', 0)}",
            f"Skip: {data.get('skip_count', 0)}",
            f"Executed: {data.get('executed_count', 0)}",
            f"Submitted: {data.get('submitted_count', 0)}",
            f"Outreach Sent: {data.get('sent_count', 0)}",
            f"Human Action Required: {data.get('human_action_required_count', 0)}",
        ]
        executions = data.get("executions", [])
        if isinstance(executions, Iterable) and not isinstance(executions, (str, bytes, Mapping)):
            execution_list = list(executions)
            if execution_list:
                lines.extend(["", "EXECUTIONS", "-" * 60])
                for index, execution in enumerate(execution_list, 1):
                    report = cls.from_execution_result(execution)
                    title = report.job_title or "Unknown job"
                    company = f" | {report.company}" if report.company else ""
                    lines.append(f"{index}. {title}{company} — {report.status_label}")
                    if report.requires_human_action:
                        lines.append("   HUMAN ACTION REQUIRED")
        errors = data.get("errors", [])
        if errors:
            lines.extend(["", "ERRORS", "-" * 60])
            for error in errors:
                lines.append(f"- {error}")
        lines.extend(["", "=" * 60])
        return "\n".join(lines)

    @classmethod
    def render(cls, result: Any) -> str:
        data = cls._as_dict(result)
        if "executions" in data or "discovered_count" in data:
            return cls.format_run_result(result)
        return cls.format_execution_result(result)

    @staticmethod
    def load_json(path: str | Path) -> Any:
        value = str(path).strip()
        if not value:
            raise ValueError("JSON input path cannot be empty.")
        file_path = Path(value)
        if not file_path.exists():
            raise FileNotFoundError(f"JSON input not found: {file_path}")
        if not file_path.is_file():
            raise IsADirectoryError(f"JSON input is not a file: {file_path}")
        with file_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
