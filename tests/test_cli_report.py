import json

from app.cli import main


def test_report_command_renders_execution_result(tmp_path, capsys):
    path = tmp_path / "result.json"
    path.write_text(json.dumps({
        "success": False,
        "decision": "APPLY",
        "status": "captcha_detected",
        "message": "CAPTCHA detected.",
        "requires_human_action": True,
        "job": {
            "title": "Electrical Engineer",
            "company": "Example Energy",
            "location": "Hyderabad",
        },
        "ranking_score": 91.5,
        "prepared": False,
        "submitted": False,
    }), encoding="utf-8")

    assert main(["report", "--input", str(path)]) == 0
    output = capsys.readouterr().out
    assert "JOB AGENT APPLICATION REPORT" in output
    assert "CAPTCHA DETECTED" in output
    assert "Human Action Required: YES" in output


def test_report_command_missing_file_returns_error(tmp_path, capsys):
    assert main(["report", "--input", str(tmp_path / "missing.json")]) == 1
    assert "Report failed:" in capsys.readouterr().out
