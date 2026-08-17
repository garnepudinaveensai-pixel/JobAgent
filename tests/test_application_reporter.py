from dataclasses import dataclass

from app.core.application_reporter import ApplicationReporter


def execution(status="applied", **extra):
    value = {
        "success": status == "applied",
        "decision": "APPLY",
        "status": status,
        "message": "",
        "job": {
            "title": "Electrical Engineer",
            "company": "Example Energy",
            "location": "Hyderabad",
        },
        "ranking_score": 91.5,
        "prepared": True,
        "submitted": status == "applied",
        "sent": False,
        "confirmation_required": False,
        "requires_human_action": False,
        "error": None,
    }
    value.update(extra)
    return value


def test_applied_report():
    report = ApplicationReporter.from_execution_result(execution())
    assert report.status == "applied"
    assert report.status_label == "APPLIED"
    assert report.submitted is True
    assert report.requires_human_action is False


def test_captcha_report_requires_human_action():
    report = ApplicationReporter.from_execution_result(
        execution(
            "captcha_detected",
            success=False,
            submitted=False,
            message="CAPTCHA detected.",
            requires_human_action=True,
        )
    )
    assert report.status_label == "CAPTCHA DETECTED"
    assert report.requires_human_action is True
    assert report.next_action


def test_login_required_report():
    report = ApplicationReporter.from_execution_result(
        execution("login_required", success=False, requires_human_action=True)
    )
    assert report.status_label == "LOGIN REQUIRED"
    assert report.requires_human_action is True


def test_job_unavailable_report():
    report = ApplicationReporter.from_execution_result(
        execution("job_unavailable", success=False)
    )
    assert report.status_label == "JOB UNAVAILABLE"
    assert report.next_action


def test_form_not_found_report():
    report = ApplicationReporter.from_execution_result(
        execution("form_not_found", success=False)
    )
    assert report.status_label == "FORM NOT FOUND"


def test_validation_failure_report():
    report = ApplicationReporter.from_execution_result(
        execution("validation_failed", success=False, error="Required field missing")
    )
    assert report.status_label == "VALIDATION FAILED"
    assert report.error == "Required field missing"


def test_confirmation_report():
    report = ApplicationReporter.from_execution_result(
        execution("confirmation_required", success=False, confirmation_required=True, submitted=False)
    )
    assert report.confirmation_required is True
    assert report.status_label == "CONFIRMATION REQUIRED"


def test_format_contains_core_application_information():
    text = ApplicationReporter.format_execution_result(
        execution("captcha_detected", success=False, message="CAPTCHA detected.", requires_human_action=True)
    )
    assert "JOB AGENT APPLICATION REPORT" in text
    assert "Electrical Engineer" in text
    assert "Example Energy" in text
    assert "CAPTCHA DETECTED" in text
    assert "Human Action Required: YES" in text
    assert "Next Action:" in text


def test_format_run_result():
    text = ApplicationReporter.format_run_result({
        "success": True,
        "status": "completed_with_errors",
        "keywords": "Electrical Engineer",
        "location": "Hyderabad",
        "discovered_count": 4,
        "processed_count": 3,
        "apply_count": 1,
        "review_count": 1,
        "skip_count": 1,
        "executed_count": 1,
        "submitted_count": 0,
        "sent_count": 0,
        "human_action_required_count": 1,
        "executions": [
            execution("captcha_detected", success=False, requires_human_action=True),
        ],
        "errors": [],
    })
    assert "JOB AGENT RUN REPORT" in text
    assert "Electrical Engineer" in text
    assert "CAPTCHA DETECTED" in text
    assert "HUMAN ACTION REQUIRED" in text


def test_render_auto_detects_execution_result():
    text = ApplicationReporter.render(execution("applied"))
    assert "JOB AGENT APPLICATION REPORT" in text


def test_render_auto_detects_run_result():
    text = ApplicationReporter.render({
        "status": "completed",
        "keywords": "Engineer",
        "location": None,
        "discovered_count": 1,
        "executions": [],
    })
    assert "JOB AGENT RUN REPORT" in text
