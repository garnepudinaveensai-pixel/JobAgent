from app.core.sources.job_source import JobSource
from app.core.sources.job_source_manager import JobSourceManager


class FakeSource(JobSource):

    name = "fake"

    def search(
        self,
        keywords,
        location=None,
    ):
        return [
            {
                "title": "Electrical Engineer",
                "company": "Example Company",
                "location": "Hyderabad",
                "url": "https://example.com/job/1",
                "description": "Electrical engineering role.",
            }
        ]


class FailingSource(JobSource):

    name = "failing"

    def search(
        self,
        keywords,
        location=None,
    ):
        raise RuntimeError(
            "Test source failure"
        )


def test_source_manager_search():

    manager = JobSourceManager()

    manager.add_source(
        FakeSource()
    )

    results = manager.search(
        keywords="electrical engineer",
        location="Hyderabad",
    )

    assert len(results) == 1

    assert results[0]["title"] == (
        "Electrical Engineer"
    )

    assert results[0]["source"] == "fake"


def test_source_manager_multiple_sources():

    manager = JobSourceManager(
        sources=[
            FakeSource(),
            FakeSource(),
        ]
    )

    results = manager.search(
        keywords="engineer"
    )

    assert len(results) == 2


def test_source_failure_does_not_stop_search():

    manager = JobSourceManager(
        sources=[
            FailingSource(),
            FakeSource(),
        ]
    )

    results = manager.search(
        keywords="engineer"
    )

    assert len(results) == 1

    assert results[0]["source"] == "fake"


def test_empty_keywords_rejected():

    manager = JobSourceManager()

    try:
        manager.search(
            keywords=""
        )

        assert False

    except ValueError as exc:

        assert (
            str(exc)
            == "keywords cannot be empty."
        )