from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.end_to_end_pipeline import (
    EndToEndPipeline,
)


# ============================================================
# FAKE STORE
# ============================================================


class FakeStore:

    def __init__(self):
        self.jobs = {}
        self.counter = 0
        self.status_updates = []

    def get_job(
        self,
        job_id,
    ):
        return self.jobs.get(
            job_id
        )

    def add_job(
        self,
        job,
        status="discovered",
    ):
        self.counter += 1

        item = dict(
            job
        )

        job_id = (
            item.get(
                "job_id"
            )
            or f"job-{self.counter}"
        )

        item["job_id"] = job_id
        item["status"] = status

        self.jobs[job_id] = item

        return job_id

    def update_status(
        self,
        job_id,
        status,
    ):
        if job_id not in self.jobs:
            return False

        self.jobs[job_id][
            "status"
        ] = status

        self.status_updates.append(
            (
                job_id,
                status,
            )
        )

        return True


# ============================================================
# FAKE APPLICATION ENGINE
# ============================================================


class FakeEngine:

    def __init__(self):
        self.prepare_calls = []
        self.submit_calls = []

    def prepare_application(
        self,
        ranked_result,
        **kwargs,
    ):
        self.prepare_calls.append(
            (
                ranked_result,
                kwargs,
            )
        )

        output = kwargs[
            "resume_output_path"
        ]

        Path(
            output
        ).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        Path(
            output
        ).write_text(
            "fake pdf",
            encoding="utf-8",
        )

        return {
            "success": True,
            "status": (
                "ready_for_submission"
            ),
            "resume_pdf": output,
            "validation": {
                "ready": True,
            },
            "resume_uploaded": True,
        }

    def submit_application(
        self,
        prepared_application,
        *,
        confirm=False,
    ):
        self.submit_calls.append(
            (
                prepared_application,
                confirm,
            )
        )

        if not confirm:
            return {
                "success": False,
                "status": (
                    "confirmation_required"
                ),
                "submitted": False,
            }

        return {
            "success": True,
            "status": "applied",
            "submitted": True,
        }


# ============================================================
# FAKE RUNNER
# ============================================================


class FakeRunner:

    def __init__(
        self,
        tmp_path,
    ):
        self.job_store = FakeStore()

        self.deduplicator = object()

        self.job_source_manager = object()

        self.job_match_pipeline = (
            SimpleNamespace(
                resume_manager=None
            )
        )

        self.config = SimpleNamespace(
            application=SimpleNamespace(
                resume_path=str(
                    tmp_path
                    / "master.pdf"
                ),
                tailored_resume_directory=str(
                    tmp_path
                    / "tailored"
                ),
            )
        )


# ============================================================
# RANKED RESULT
# ============================================================


def ranked_result():

    return {
        "ranking_score": 91.5,

        "job": {
            "title": (
                "Electrical Engineer"
            ),
            "company": (
                "Example Energy"
            ),
            "location": (
                "Hyderabad"
            ),
            "url": (
                "https://example.com/jobs/1"
            ),
        },

        "resume": {
            "filename": (
                "technical_resume.pdf"
            ),
        },

        "match": {
            "selected_resume": {
                "filename": (
                    "technical_resume.pdf"
                ),
                "name": (
                    "Naveen Sai"
                ),
                "skills": [
                    "Electrical Engineering",
                    "Python",
                ],
            }
        },
    }


# ============================================================
# PIPELINE FACTORY
# ============================================================


def make_pipeline(
    tmp_path,
):

    runner = FakeRunner(
        tmp_path
    )

    engine = FakeEngine()

    pipeline = EndToEndPipeline(
        runner=runner,
        application_engine=engine,
    )

    return (
        pipeline,
        runner,
        engine,
    )


# ============================================================
# PREPARATION
# ============================================================


def test_prepare_application_uses_injected_engine(
    tmp_path,
):

    pipeline, runner, engine = (
        make_pipeline(
            tmp_path
        )
    )

    result = (
        pipeline.prepare_application_for_job(
            ranked_result(),
            page=object(),
            fields={
                "full_name": (
                    "Naveen Sai"
                )
            },
        )
    )

    assert result[
        "success"
    ] is True

    assert result[
        "job_id"
    ] == "job-1"

    assert result[
        "selected_resume"
    ][
        "name"
    ] == "Naveen Sai"

    assert result[
        "ranking_score"
    ] == 91.5

    assert (
        runner.job_store
        .get_job(
            "job-1"
        )[
            "status"
        ]
        == "application_started"
    )

    assert len(
        engine.prepare_calls
    ) == 1

    ranked, kwargs = (
        engine.prepare_calls[0]
    )

    assert ranked[
        "job"
    ][
        "company"
    ] == "Example Energy"

    assert kwargs[
        "resume"
    ][
        "filename"
    ] == "technical_resume.pdf"

    assert kwargs[
        "fields"
    ][
        "full_name"
    ] == "Naveen Sai"

    assert kwargs[
        "page"
    ] is not None


# ============================================================
# PREPARATION MUST NOT SUBMIT
# ============================================================


def test_prepare_application_stops_before_submission(
    tmp_path,
):

    pipeline, _, engine = (
        make_pipeline(
            tmp_path
        )
    )

    prepared = (
        pipeline.prepare_application_for_job(
            ranked_result(),
            page=object(),
            fields={},
        )
    )

    assert prepared[
        "success"
    ] is True

    assert engine.submit_calls == []


# ============================================================
# CONFIRMATION BARRIER
# ============================================================


def test_submission_requires_confirmation(
    tmp_path,
):

    pipeline, _, engine = (
        make_pipeline(
            tmp_path
        )
    )

    prepared = (
        pipeline.prepare_application_for_job(
            ranked_result(),
            page=object(),
            fields={},
        )
    )

    result = (
        pipeline.submit_application(
            prepared,
            confirm=False,
        )
    )

    assert result[
        "success"
    ] is False

    assert result[
        "status"
    ] == "confirmation_required"

    assert result[
        "submitted"
    ] is False

    assert engine.submit_calls == []


# ============================================================
# CONFIRMED SUBMISSION
# ============================================================


def test_confirmed_application_is_submitted_and_tracked(
    tmp_path,
):

    pipeline, runner, engine = (
        make_pipeline(
            tmp_path
        )
    )

    prepared = (
        pipeline.prepare_application_for_job(
            ranked_result(),
            page=object(),
            fields={},
        )
    )

    result = (
        pipeline.submit_application(
            prepared,
            confirm=True,
        )
    )

    assert result[
        "success"
    ] is True

    assert result[
        "submitted"
    ] is True

    assert result[
        "status"
    ] == "applied"

    assert (
        runner.job_store
        .get_job(
            "job-1"
        )[
            "status"
        ]
        == "applied"
    )

    assert len(
        engine.submit_calls
    ) == 1

    assert (
        engine.submit_calls[0][1]
        is True
    )


# ============================================================
# RUN APPLICATION — PREPARE ONLY
# ============================================================


def test_run_application_prepares_only_without_confirmation(
    tmp_path,
):

    pipeline, runner, engine = (
        make_pipeline(
            tmp_path
        )
    )

    result = (
        pipeline.run_application(
            ranked_result(),
            page=object(),
            fields={},
            confirm=False,
        )
    )

    assert result[
        "success"
    ] is True

    assert result[
        "status"
    ] == "confirmation_required"

    assert result[
        "submitted"
    ] is False

    assert (
        runner.job_store
        .get_job(
            "job-1"
        )[
            "status"
        ]
        == "application_started"
    )

    assert engine.submit_calls == []


# ============================================================
# RUN APPLICATION — CONFIRMED
# ============================================================


def test_run_application_submits_when_confirmed(
    tmp_path,
):

    pipeline, runner, engine = (
        make_pipeline(
            tmp_path
        )
    )

    result = (
        pipeline.run_application(
            ranked_result(),
            page=object(),
            fields={},
            confirm=True,
        )
    )

    assert result[
        "success"
    ] is True

    assert result[
        "submitted"
    ] is True

    assert result[
        "status"
    ] == "applied"

    assert (
        runner.job_store
        .get_job(
            "job-1"
        )[
            "status"
        ]
        == "applied"
    )

    assert len(
        engine.submit_calls
    ) == 1

    assert (
        engine.submit_calls[0][1]
        is True
    )


# ============================================================
# SELECTED RESUME IS REQUIRED
# ============================================================


def test_application_requires_ranked_selected_resume(
    tmp_path,
):

    pipeline, _, _ = (
        make_pipeline(
            tmp_path
        )
    )

    invalid = ranked_result()

    invalid[
        "match"
    ] = {}

    invalid[
        "resume"
    ] = None

    with pytest.raises(
        ValueError,
        match="selected resume",
    ):
        pipeline.prepare_application_for_job(
            invalid,
            page=object(),
            fields={},
        )


# ============================================================
# INVALID PAGE
# ============================================================


def test_application_requires_page(
    tmp_path,
):

    pipeline, _, _ = (
        make_pipeline(
            tmp_path
        )
    )

    with pytest.raises(
        ValueError,
        match="page cannot be None",
    ):
        pipeline.prepare_application_for_job(
            ranked_result(),
            page=None,
            fields={},
        )


# ============================================================
# INVALID JOB
# ============================================================


def test_application_requires_valid_job(
    tmp_path,
):

    pipeline, _, _ = (
        make_pipeline(
            tmp_path
        )
    )

    invalid = ranked_result()

    invalid[
        "job"
    ] = None

    with pytest.raises(
        ValueError,
        match="valid job",
    ):
        pipeline.prepare_application_for_job(
            invalid,
            page=object(),
            fields={},
        )


# ============================================================
# JOB URL REQUIRED
# ============================================================


def test_application_requires_job_url(
    tmp_path,
):

    pipeline, _, _ = (
        make_pipeline(
            tmp_path
        )
    )

    invalid = ranked_result()

    invalid[
        "job"
    ]["url"] = ""

    with pytest.raises(
        ValueError,
        match="URL",
    ):
        pipeline.prepare_application_for_job(
            invalid,
            page=object(),
            fields={},
        )


# ============================================================
# INVALID FIELDS
# ============================================================


def test_application_requires_dictionary_fields(
    tmp_path,
):

    pipeline, _, _ = (
        make_pipeline(
            tmp_path
        )
    )

    with pytest.raises(
        TypeError,
        match="fields must be a dictionary",
    ):
        pipeline.prepare_application_for_job(
            ranked_result(),
            page=object(),
            fields=[],
        )


# ============================================================
# INVALID RANKED RESULT
# ============================================================


def test_application_requires_dictionary_ranked_result(
    tmp_path,
):

    pipeline, _, _ = (
        make_pipeline(
            tmp_path
        )
    )

    with pytest.raises(
        TypeError,
        match="ranked_result must be a dictionary",
    ):
        pipeline.prepare_application_for_job(
            None,
            page=object(),
            fields={},
        )


# ============================================================
# MULTIPLE APPLICATIONS
# ============================================================


def test_prepare_multiple_applications_isolates_failures(
    tmp_path,
):

    pipeline, runner, engine = (
        make_pipeline(
            tmp_path
        )
    )

    valid = ranked_result()

    invalid = ranked_result()

    invalid[
        "match"
    ] = {}

    invalid[
        "resume"
    ] = None

    results = (
        pipeline.prepare_applications(
            [
                valid,
                invalid,
            ],
            page_factory=lambda _: object(),
            fields={},
        )
    )

    assert len(
        results
    ) == 2

    assert results[0][
        "success"
    ] is True

    assert results[1][
        "success"
    ] is False

    assert results[1][
        "status"
    ] == (
        "application_preparation_failed"
    )


# ============================================================
# TOP APPLICATION
# ============================================================


def test_prepare_top_application_selects_highest_score(
    tmp_path,
):

    pipeline, _, engine = (
        make_pipeline(
            tmp_path
        )
    )

    first = ranked_result()

    first[
        "ranking_score"
    ] = 70.0

    second = ranked_result()

    second[
        "ranking_score"
    ] = 95.0

    result = (
        pipeline.prepare_top_application(
            [
                first,
                second,
            ],
            page=object(),
            fields={},
        )
    )

    assert result[
        "success"
    ] is True

    assert result[
        "ranking_score"
    ] == 95.0

    assert len(
        engine.prepare_calls
    ) == 1