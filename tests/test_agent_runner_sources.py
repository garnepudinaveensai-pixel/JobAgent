from unittest.mock import MagicMock

from app.config import JobAgentConfig
from app.core.agent_runner import AgentRunner
from app.core.job_deduplicator import JobDeduplicator
from app.core.sources.job_source_manager import JobSourceManager


class FakeSource:

    name = "fake"

    def is_available(self):
        return True

    def search(
        self,
        keywords,
        location=None,
        **options,
    ):
        return [
            {
                "title": "Electrical Engineer",
                "company": "Example Company",
                "location": "Hyderabad",
                "url": "https://example.com/jobs/1",
                "description": "Electrical engineering role.",
                "source": "fake",
            }
        ]


class DuplicateSource:

    name = "duplicate"

    def is_available(self):
        return True

    def search(
        self,
        keywords,
        location=None,
        **options,
    ):
        return [
            {
                "title": "Electrical Engineer",
                "company": "Example Company",
                "location": "Hyderabad",
                "url": "https://example.com/jobs/1?utm_source=test",
                "description": "A richer electrical engineering role.",
                "source": "duplicate",
            }
        ]


def test_runner_has_source_manager(tmp_path):

    runner = AgentRunner(
        config=JobAgentConfig(),
        job_source_manager=JobSourceManager(),
    )

    assert runner.job_source_manager is not None


def test_runner_has_deduplicator(tmp_path):

    runner = AgentRunner(
        config=JobAgentConfig(),
    )

    assert isinstance(
        runner.deduplicator,
        JobDeduplicator,
    )


def test_runner_add_source():

    manager = JobSourceManager()

    runner = AgentRunner(
        job_source_manager=manager,
    )

    source = FakeSource()

    runner.add_source(
        source
    )

    assert source in runner.get_sources()


def test_runner_discover_from_sources():

    manager = JobSourceManager(
        sources=[
            FakeSource()
        ]
    )

    runner = AgentRunner(
        job_source_manager=manager,
    )

    jobs = runner.discover_from_sources(
        keywords="electrical engineer",
        location="Hyderabad",
    )

    assert len(jobs) == 1
    assert jobs[0]["title"] == (
        "Electrical Engineer"
    )


def test_runner_deduplicates_sources():

    manager = JobSourceManager(
        sources=[
            FakeSource(),
            DuplicateSource(),
        ]
    )

    runner = AgentRunner(
        job_source_manager=manager,
    )

    jobs = runner.discover_from_sources(
        keywords="electrical engineer",
        location="Hyderabad",
    )

    assert len(jobs) == 1

    assert jobs[0]["title"] == (
        "Electrical Engineer"
    )

    assert len(
        jobs[0]["source"]
        if isinstance(
            jobs[0]["source"],
            list,
        )
        else [jobs[0]["source"]]
    ) == 2