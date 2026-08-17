from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.end_to_end_pipeline import EndToEndPipeline


class FakeStore:
    def __init__(self):
        self.jobs = {}
        self.counter = 0
        self.status_updates = []

    def get_job(self, job_id):
        return self.jobs.get(job_id)

    def add_job(self, job, status="discovered"):
        self.counter += 1
        item = dict(job)
        job_id = item.get("job_id") or f"job-{self.counter}"
        item["job_id"] = job_id
        item["status"] = status
        self.jobs[job_id] = item
        return job_id

    def update_status(self, job_id, status):
        if job_id not in self.jobs:
            return False
        self.jobs[job_id]["status"] = status
        self.status_updates.append((job_id, status))
        return True


class FakeEngine:
    def __init__(self):
        self.prepare_calls = []
        self.submit_calls = []

    def prepare_application(self, ranked_result, **kwargs):
        self.prepare_calls.append((ranked_result, kwargs))
        output = kwargs["resume_output_path"]
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text("fake pdf", encoding="utf-8")
        return {
            "success": True,
            "status": "ready_for_submission",
            "resume_pdf": output,
            "validation": {"ready": True},
            "resume_uploaded": True,
        }

    def submit_application(self, prepared_application, *, confirm=False):
        self.submit_calls.append((prepared_application, confirm))
        assert confirm is True
        return {
            "success": True,
            "status": "applied",
            "submitted": True,
        }


class FakeRunner:
    def __init__(self, tmp_path):
        self.job_store = FakeStore()
        self.deduplicator = object()
        self.job_source_manager = object()
        self.job_match_pipeline = SimpleNamespace(resume_manager=None)
        self.config = SimpleNamespace(
            application=SimpleNamespace(
                resume_path=str(tmp_path / "master.pdf"),
                tailored_resume_directory=str(tmp_path / "tailored"),
            )
        )


def ranked_result():
    return {
        "ranking_score": 91.5,
        "job": {
            "title": "Electrical Engineer",
            "company": "Example Energy",
            "location": "Hyderabad",
            "url": "https://example.com/jobs/1",
        },
        "resume": {
            "filename": "technical_resume.pdf",
        },
        "match": {
            "selected_resume": {
                "filename": "technical_resume.pdf",
                "name": "Naveen Sai",
                "skills": [
                    "Electrical Engineering",
                    "Python",
                ],
            }
        },
    }


def make_pipeline(tmp_path):
    runner = FakeRunner(tmp_path)
    engine = FakeEngine()
    pipeline = EndToEndPipeline(
        runner=runner,
        application_engine=engine,
    )
    return pipeline, runner, engine


def test_prepare_application_uses_ranked_selected_resume(tmp_path):
    pipeline, runner, engine = make_pipeline(tmp_path)

    result = pipeline.prepare_application_for_job(
        ranked_result(),
        page=object(),
        fields={"full_name": "Naveen Sai"},
    )

    assert result["success"] is True
    assert result["job_id"] == "job-1"
    assert result["selected_resume"]["name"] == "Naveen Sai"
    assert result["ranking_score"] == 91.5
    assert runner.job_store.get_job("job-1")["status"] == (
        "application_started"
    )

    assert len(engine.prepare_calls) == 1
    _, kwargs = engine.prepare_calls[0]
    assert kwargs["resume"]["filename"] == "technical_resume.pdf"
    assert kwargs["fields"]["full_name"] == "Naveen Sai"


def test_prepare_application_stops_before_submission(tmp_path):
    pipeline, _, engine = make_pipeline(tmp_path)

    prepared = pipeline.prepare_application_for_job(
        ranked_result(),
        page=object(),
        fields={},
    )

    result = pipeline.submit_application(
        prepared,
        confirm=False,
    )

    assert result["success"] is False
    assert result["status"] == "confirmation_required"
    assert result["submitted"] is False
    assert engine.submit_calls == []


def test_confirmed_application_is_submitted_and_tracked(tmp_path):
    pipeline, runner, engine = make_pipeline(tmp_path)

    prepared = pipeline.prepare_application_for_job(
        ranked_result(),
        page=object(),
        fields={},
    )

    result = pipeline.submit_application(
        prepared,
        confirm=True,
    )

    assert result["success"] is True
    assert result["submitted"] is True
    assert result["status"] == "applied"
    assert runner.job_store.get_job("job-1")["status"] == "applied"
    assert engine.submit_calls[0][1] is True


def test_run_application_prepares_only_without_confirmation(tmp_path):
    pipeline, runner, engine = make_pipeline(tmp_path)

    result = pipeline.run_application(
        ranked_result(),
        page=object(),
        fields={},
        confirm=False,
    )

    assert result["success"] is True
    assert result["status"] == "confirmation_required"
    assert result["submitted"] is False
    assert runner.job_store.get_job("job-1")["status"] == (
        "application_started"
    )
    assert engine.submit_calls == []


def test_application_requires_ranked_selected_resume(tmp_path):
    pipeline, _, _ = make_pipeline(tmp_path)

    invalid = ranked_result()
    invalid["match"] = {}
    invalid["resume"] = None

    with pytest.raises(ValueError, match="selected resume"):
        pipeline.prepare_application_for_job(
            invalid,
            page=object(),
            fields={},
        )
