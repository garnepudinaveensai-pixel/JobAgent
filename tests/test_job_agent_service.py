from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.application_execution_router import (
    ExecutionResult,
)
from app.core.application_decision_engine import (
    ApplicationDecisionEngine,
)
from app.core.job_agent_service import (
    JobAgentService,
)


# ============================================================
# HELPERS
# ============================================================


def make_job(
    *,
    job_id="job-001",
):
    return {
        "job_id": job_id,
        "title": "Electrical Engineer",
        "company": "Example Energy",
        "location": "Hyderabad",
        "url": "https://example.com/jobs/1",
    }


def make_ranked(
    *,
    score=90,
):
    return {
        "ranking_score": score,
        "job": make_job(),
        "resume": {
            "filename": "technical_resume.pdf",
            "name": "Naveen Sai",
        },
        "match": {
            "resume_score": score,
            "match_score": score,
            "eligible": True,
            "selected_resume": {
                "filename": "technical_resume.pdf",
                "name": "Naveen Sai",
                "skills": [
                    "Electrical Engineering",
                    "Python",
                ],
            },
        },
    }


class FakeRunner:
    def __init__(self):
        self.job_source_manager = MagicMock()
        self.deduplicator = MagicMock()
        self.job_match_pipeline = MagicMock()

        self.job_store = MagicMock()

        self.config = SimpleNamespace(
            application=SimpleNamespace(
                resume_path=(
                    "data/resumes/master_resume.pdf"
                ),
                tailored_resume_directory=(
                    "data/resumes/tailored"
                ),
            )
        )


class FakeEndToEnd:
    def __init__(
        self,
        ranked=None,
    ):
        self.ranked = (
            ranked
            if ranked is not None
            else [
                make_ranked(
                    score=90
                ),
                make_ranked(
                    score=70
                ),
            ]
        )

        self.discover_calls = []
        self.contact_calls = []

    def discover_and_rank(
        self,
        **kwargs,
    ):
        self.discover_calls.append(
            kwargs
        )

        return list(
            self.ranked
        )

    def discover_contacts(
        self,
        job,
        **kwargs,
    ):
        self.contact_calls.append(
            (
                job,
                kwargs,
            )
        )

        return [
            {
                "email": "recruiter@example.com",
                "name": "Recruiter",
                "role": "Talent Acquisition",
            }
        ]

    def resolve_resume_path(
        self,
        ranked_result,
        explicit_path=None,
    ):
        if explicit_path:
            return explicit_path

        return (
            "data/resumes/master_resume.pdf"
        )


class FakeDecision:
    def __init__(
        self,
        decision,
    ):
        self.decision = decision
        self.reason = "test"


class FakeDecisionEngine:
    def __init__(
        self,
        decisions,
    ):
        self.decisions = list(
            decisions
        )
        self.calls = []

    def decide(
        self,
        ranked_result,
    ):
        self.calls.append(
            ranked_result
        )

        return self.decisions.pop(
            0
        )


class FakeRouter:
    def __init__(self):
        self.calls = []

    def route(
        self,
        ranked_result,
        **kwargs,
    ):
        self.calls.append(
            (
                ranked_result,
                kwargs,
            )
        )

        return ExecutionResult(
            success=True,
            decision="review",
            status="manual_review",
            message="test",
            job=dict(
                ranked_result["job"]
            ),
            ranking_score=float(
                ranked_result.get(
                    "ranking_score",
                    0,
                )
            ),
        )


# ============================================================
# CONSTRUCTION
# ============================================================


def test_service_requires_runner():

    with pytest.raises(
        ValueError,
        match="runner cannot be None",
    ):
        JobAgentService(
            None
        )


def test_service_constructs_with_dependencies():

    runner = FakeRunner()
    end_to_end = FakeEndToEnd()

    service = JobAgentService(
        runner,
        end_to_end_pipeline=end_to_end,
    )

    assert service.runner is runner
    assert (
        service.end_to_end_pipeline
        is end_to_end
    )
    assert isinstance(
        service.decision_engine,
        ApplicationDecisionEngine,
    )


# ============================================================
# DISCOVERY
# ============================================================


def test_discover_and_rank_rejects_empty_keywords():

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakeEndToEnd(),
    )

    with pytest.raises(
        ValueError,
        match="keywords cannot be empty",
    ):
        service.discover_and_rank(
            "   "
        )


def test_discover_and_rank_delegates():

    runner = FakeRunner()
    pipeline = FakeEndToEnd()

    service = JobAgentService(
        runner,
        end_to_end_pipeline=pipeline,
    )

    result = service.discover_and_rank(
        "Electrical Engineer",
        location="Hyderabad",
        min_score=65,
        eligible_only=True,
        limit=5,
    )

    assert len(result) == 2

    assert (
        pipeline.discover_calls[0][
            "keywords"
        ]
        == "Electrical Engineer"
    )

    assert (
        pipeline.discover_calls[0][
            "location"
        ]
        == "Hyderabad"
    )

    assert (
        pipeline.discover_calls[0][
            "min_score"
        ]
        == 65
    )


# ============================================================
# CONTACTS
# ============================================================


def test_discover_contacts_delegates():

    pipeline = FakeEndToEnd()

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=pipeline,
    )

    contacts = service.discover_contacts(
        make_job()
    )

    assert len(contacts) == 1

    assert (
        contacts[0]["email"]
        == "recruiter@example.com"
    )

    assert len(
        pipeline.contact_calls
    ) == 1


def test_discover_contacts_requires_mapping():

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakeEndToEnd(),
    )

    with pytest.raises(
        TypeError,
        match="job must be a mapping",
    ):
        service.discover_contacts(
            None
        )


# ============================================================
# DECISION
# ============================================================


def test_decide_delegates():

    engine = FakeDecisionEngine(
        [
            FakeDecision(
                "review"
            )
        ]
    )

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakeEndToEnd(),
        decision_engine=engine,
    )

    ranked = make_ranked()

    result = service.decide(
        ranked
    )

    assert result.decision == (
        "review"
    )

    assert engine.calls == [
        ranked
    ]


def test_decide_many_requires_list():

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakeEndToEnd(),
        decision_engine=FakeDecisionEngine(
            []
        ),
    )

    with pytest.raises(
        TypeError,
        match="ranked_results must be a list",
    ):
        service.decide_many(
            None
        )


# ============================================================
# SINGLE EXECUTION
# ============================================================


def test_execute_ranked_job_routes_result():

    engine = FakeDecisionEngine(
        [
            FakeDecision(
                "review"
            )
        ]
    )

    router = FakeRouter()

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakeEndToEnd(),
        decision_engine=engine,
        execution_router=router,
    )

    ranked = make_ranked()

    result = service.execute_ranked_job(
        ranked,
        fields={
            "full_name": "Naveen Sai"
        },
    )

    assert result.success is True

    assert len(
        router.calls
    ) == 1

    passed_ranked, kwargs = (
        router.calls[0]
    )

    assert passed_ranked == ranked

    assert kwargs["fields"][
        "full_name"
    ] == "Naveen Sai"


def test_outreach_execution_discovers_contacts():

    engine = FakeDecisionEngine(
        [
            FakeDecision(
                "outreach"
            )
        ]
    )

    router = FakeRouter()

    pipeline = FakeEndToEnd()

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=pipeline,
        decision_engine=engine,
        execution_router=router,
    )

    service.execute_ranked_job(
        make_ranked()
    )

    assert len(
        pipeline.contact_calls
    ) == 1

    _, kwargs = router.calls[0][1].get(
        "contacts"
    ), router.calls[0][1]

    assert (
        router.calls[0][1]["contacts"][0][
            "email"
        ]
        == "recruiter@example.com"
    )


# ============================================================
# BATCH
# ============================================================


def test_execute_ranked_jobs_continues():

    engine = FakeDecisionEngine(
        [
            FakeDecision(
                "review"
            ),
            FakeDecision(
                "skip"
            ),
        ]
    )

    router = FakeRouter()

    pipeline = FakeEndToEnd(
        [
            make_ranked(
                score=90
            ),
            make_ranked(
                score=20
            ),
        ]
    )

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=pipeline,
        decision_engine=engine,
        execution_router=router,
    )

    results = (
        service.execute_ranked_jobs(
            pipeline.ranked
        )
    )

    assert len(results) == 2
    assert len(router.calls) == 2


def test_execute_ranked_jobs_requires_list():

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakeEndToEnd(),
    )

    with pytest.raises(
        TypeError,
        match="ranked_results must be a list",
    ):
        service.execute_ranked_jobs(
            None
        )


def test_execute_ranked_jobs_rejects_bad_page_factory():

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakeEndToEnd(),
    )

    with pytest.raises(
        TypeError,
        match="page_factory must be callable",
    ):
        service.execute_ranked_jobs(
            [
                make_ranked()
            ],
            page_factory="invalid",
        )


# ============================================================
# COMPLETE RUN
# ============================================================


def test_run_no_jobs():

    pipeline = FakeEndToEnd(
        ranked=[]
    )

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=pipeline,
    )

    result = service.run(
        "Electrical Engineer"
    )

    assert result.success is True

    assert result.status == (
        "no_matching_jobs"
    )

    assert (
        result.discovered_count
        == 0
    )

    assert (
        result.processed_count
        == 0
    )


def test_run_discovery_failure():

    pipeline = MagicMock()

    pipeline.discover_and_rank.side_effect = (
        RuntimeError(
            "source unavailable"
        )
    )

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=pipeline,
    )

    result = service.run(
        "Electrical Engineer"
    )

    assert result.success is False

    assert result.status == (
        "discovery_failed"
    )

    assert len(
        result.errors
    ) == 1

    assert (
        result.errors[0]["stage"]
        == "discovery"
    )


def test_run_builds_summary():

    pipeline = FakeEndToEnd(
        [
            make_ranked(
                score=90
            ),
            make_ranked(
                score=70
            ),
        ]
    )

    engine = FakeDecisionEngine(
        [
            FakeDecision(
                "apply"
            ),
            FakeDecision(
                "review"
            ),
        ]
    )

    router = FakeRouter()

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=pipeline,
        decision_engine=engine,
        execution_router=router,
    )

    result = service.run(
        "Electrical Engineer",
        location="Hyderabad",
        dry_run=True,
    )

    assert result.success is True

    assert result.status == (
        "dry_run_completed"
    )

    assert (
        result.discovered_count
        == 2
    )

    assert (
        result.processed_count
        == 2
    )

    assert (
        len(result.executions)
        == 2
    )

    assert (
        result.metadata["dry_run"]
        is True
    )


def test_run_defaults_to_safe_mode():

    pipeline = FakeEndToEnd(
        [
            make_ranked()
        ]
    )

    engine = FakeDecisionEngine(
        [
            FakeDecision(
                "review"
            )
        ]
    )

    router = FakeRouter()

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=pipeline,
        decision_engine=engine,
        execution_router=router,
    )

    result = service.run(
        "Electrical Engineer"
    )

    assert result.metadata[
        "dry_run"
    ] is True

    assert result.metadata[
        "confirm"
    ] is False


# ============================================================
# SERIALIZATION
# ============================================================


def test_run_result_to_dict():

    pipeline = FakeEndToEnd(
        ranked=[]
    )

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=pipeline,
    )

    result = service.run(
        "Electrical Engineer"
    )

    data = result.to_dict()

    assert isinstance(
        data,
        dict,
    )

    assert data[
        "keywords"
    ] == "Electrical Engineer"

    assert "jobs" in data

    assert "executions" in data

    assert "errors" in data


# ============================================================
# CONTINUE AFTER ONE JOB FAILURE
# ============================================================


def test_batch_continues_after_router_exception():

    engine = FakeDecisionEngine(
        [
            FakeDecision(
                "review"
            ),
            FakeDecision(
                "review"
            ),
        ]
    )

    class FailingRouter:
        def __init__(self):
            self.count = 0

        def route(
            self,
            ranked_result,
            **kwargs,
        ):
            self.count += 1

            if self.count == 1:
                raise RuntimeError(
                    "first job failed"
                )

            return ExecutionResult(
                success=True,
                decision="review",
                status="manual_review",
                job=dict(
                    ranked_result["job"]
                ),
                ranking_score=70,
            )

    router = FailingRouter()

    pipeline = FakeEndToEnd(
        [
            make_ranked(
                score=90
            ),
            make_ranked(
                score=70
            ),
        ]
    )

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=pipeline,
        decision_engine=engine,
        execution_router=router,
    )

    results = (
        service.execute_ranked_jobs(
            pipeline.ranked
        )
    )

    assert len(results) == 2

    assert (
        results[0].success
        is False
    )

    assert (
        results[0].status
        == "job_execution_failed"
    )

    assert (
        results[1].success
        is True
    )


# ============================================================
# OUTPUT PATH
# ============================================================


def test_batch_builds_tailored_resume_path(
    tmp_path,
):

    engine = FakeDecisionEngine(
        [
            FakeDecision(
                "apply"
            )
        ]
    )

    router = FakeRouter()

    pipeline = FakeEndToEnd(
        [
            make_ranked()
        ]
    )

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=pipeline,
        decision_engine=engine,
        execution_router=router,
    )

    service.execute_ranked_jobs(
        pipeline.ranked,
        resume_output_directory=str(
            tmp_path
        ),
    )

    kwargs = router.calls[0][1]

    output_path = kwargs[
        "resume_output_path"
    ]

    assert output_path is not None

    assert output_path.endswith(
        ".pdf"
    )

    assert (
        "example_energy"
        in output_path
    )

    assert (
        "electrical_engineer"
        in output_path
    )


# ============================================================
# INVALID KEYWORDS
# ============================================================


def test_run_rejects_empty_keywords():

    service = JobAgentService(
        FakeRunner(),
        end_to_end_pipeline=FakeEndToEnd(),
    )

    with pytest.raises(
        ValueError,
        match="keywords cannot be empty",
    ):
        service.run(
            "   "
        )