from app.core.sources.job_source import JobSource
from app.core.sources.job_source_manager import (
    JobSourceManager,
)


# ============================================================
# FAKE SOURCES
# ============================================================


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
                "description": (
                    "Electrical engineering role."
                ),
            }
        ]


class SecondFakeSource(JobSource):

    name = "second"

    def search(
        self,
        keywords,
        location=None,
    ):
        return [
            {
                "title": "Software Engineer",
                "company": "Another Company",
                "location": "Bangalore",
                "url": "https://example.com/job/2",
                "description": (
                    "Software engineering role."
                ),
            }
        ]


class DuplicateSource(JobSource):

    name = "duplicate"

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
                "description": (
                    "Same job from another source."
                ),
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


class UnavailableSource(JobSource):

    name = "unavailable"

    def is_available(self):
        return False

    def search(
        self,
        keywords,
        location=None,
    ):
        raise AssertionError(
            "Unavailable source must not be searched."
        )


class AvailabilityFailingSource(JobSource):

    name = "availability-failing"

    def is_available(self):
        raise RuntimeError(
            "Availability check failed"
        )

    def search(
        self,
        keywords,
        location=None,
    ):
        raise AssertionError(
            "Source with failed availability must not be searched."
        )


# ============================================================
# BASIC SEARCH
# ============================================================


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


# ============================================================
# MULTIPLE UNIQUE SOURCES
# ============================================================


def test_source_manager_multiple_sources():

    manager = JobSourceManager(
        sources=[
            FakeSource(),
            SecondFakeSource(),
        ]
    )

    results = manager.search(
        keywords="engineer"
    )

    assert len(results) == 2

    titles = {
        job["title"]
        for job in results
    }

    assert titles == {
        "Electrical Engineer",
        "Software Engineer",
    }


# ============================================================
# CROSS-SOURCE DUPLICATION
# ============================================================


def test_source_manager_preserves_cross_source_duplicates():

    manager = JobSourceManager(
        sources=[
            FakeSource(),
            DuplicateSource(),
        ]
    )

    results = manager.search(
        keywords="engineer"
    )

    # JobSourceManager does NOT deduplicate.
    # Deduplication belongs to AgentRunner.
    assert len(results) == 2

    assert results[0]["title"] == (
        "Electrical Engineer"
    )

    assert results[1]["title"] == (
        "Electrical Engineer"
    )

    assert results[0]["source"] == "fake"
    assert results[1]["source"] == "duplicate"


# ============================================================
# SOURCE FAILURE
# ============================================================


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


# ============================================================
# UNAVAILABLE SOURCE
# ============================================================


def test_unavailable_source_is_skipped():

    manager = JobSourceManager(
        sources=[
            UnavailableSource(),
            FakeSource(),
        ]
    )

    results = manager.search(
        keywords="engineer"
    )

    assert len(results) == 1

    assert results[0]["source"] == "fake"


# ============================================================
# AVAILABILITY FAILURE
# ============================================================


def test_availability_failure_does_not_stop_search():

    manager = JobSourceManager(
        sources=[
            AvailabilityFailingSource(),
            FakeSource(),
        ]
    )

    results = manager.search(
        keywords="engineer"
    )

    assert len(results) == 1

    assert results[0]["source"] == "fake"


# ============================================================
# EMPTY KEYWORDS
# ============================================================


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


# ============================================================
# WHITESPACE KEYWORDS
# ============================================================


def test_whitespace_keywords_rejected():

    manager = JobSourceManager()

    try:
        manager.search(
            keywords="   "
        )

        assert False

    except ValueError as exc:

        assert (
            str(exc)
            == "keywords cannot be empty."
        )


# ============================================================
# KEYWORD NORMALIZATION
# ============================================================


def test_keywords_are_stripped_before_search():

    class RecordingSource(JobSource):

        name = "recording"

        def __init__(self):
            self.received_keywords = None

        def search(
            self,
            keywords,
            location=None,
        ):
            self.received_keywords = keywords

            return []

    source = RecordingSource()

    manager = JobSourceManager(
        sources=[
            source
        ]
    )

    manager.search(
        keywords="  electrical engineer  "
    )

    assert source.received_keywords == (
        "electrical engineer"
    )


# ============================================================
# NORMALIZATION
# ============================================================


def test_source_manager_normalizes_common_fields():

    class MessySource(JobSource):

        name = "messy"

        def search(
            self,
            keywords,
            location=None,
        ):
            return [
                {
                    "title": "  Electrical Engineer  ",
                    "company": " Example Company ",
                    "location": " Hyderabad ",
                    "url": " https://example.com/job/1 ",
                    "description": (
                        " Electrical engineering role. "
                    ),
                    "custom_field": "preserved",
                }
            ]

    manager = JobSourceManager(
        sources=[
            MessySource()
        ]
    )

    results = manager.search(
        keywords="engineer"
    )

    assert len(results) == 1

    job = results[0]

    assert job["title"] == (
        "Electrical Engineer"
    )

    assert job["company"] == (
        "Example Company"
    )

    assert job["location"] == (
        "Hyderabad"
    )

    assert job["url"] == (
        "https://example.com/job/1"
    )

    assert job["description"] == (
        "Electrical engineering role."
    )

    assert job["custom_field"] == (
        "preserved"
    )

    assert job["source"] == "messy"


# ============================================================
# INVALID SOURCE RESULTS
# ============================================================


def test_invalid_source_results_are_ignored():

    class InvalidSource(JobSource):

        name = "invalid"

        def search(
            self,
            keywords,
            location=None,
        ):
            return [
                None,
                "invalid",
                123,
                {
                    "title": "Valid Job",
                },
            ]

    manager = JobSourceManager(
        sources=[
            InvalidSource()
        ]
    )

    results = manager.search(
        keywords="engineer"
    )

    assert len(results) == 1

    assert results[0]["title"] == (
        "Valid Job"
    )

    assert results[0]["company"] == ""
    assert results[0]["location"] == ""
    assert results[0]["url"] == ""
    assert results[0]["description"] == ""
    assert results[0]["source"] == "invalid"


# ============================================================
# NONE RESULTS
# ============================================================


def test_none_source_results_are_ignored():

    class EmptySource(JobSource):

        name = "empty"

        def search(
            self,
            keywords,
            location=None,
        ):
            return None

    manager = JobSourceManager(
        sources=[
            EmptySource()
        ]
    )

    results = manager.search(
        keywords="engineer"
    )

    assert results == []


# ============================================================
# SOURCE MANAGEMENT
# ============================================================


def test_add_source_does_not_duplicate_instance():

    manager = JobSourceManager()

    source = FakeSource()

    manager.add_source(
        source
    )

    manager.add_source(
        source
    )

    assert len(
        manager.get_sources()
    ) == 1


def test_get_sources_returns_copy():

    source = FakeSource()

    manager = JobSourceManager(
        sources=[
            source
        ]
    )

    sources = manager.get_sources()

    sources.clear()

    assert len(
        manager.get_sources()
    ) == 1

def test_source_specific_options_are_filtered():

    class RecordingSource(JobSource):

        name = "recording"

        def __init__(self):
            self.received_options = None

        def get_supported_options(self):
            return {
                "board_url",
            }

        def search(
            self,
            keywords,
            location=None,
            **options,
        ):
            self.received_options = options

            return []

    source = RecordingSource()

    manager = JobSourceManager(
        sources=[
            source
        ]
    )

    manager.search(
        keywords="engineer",
        board_url="https://example.com",
        career_url="https://company.com/careers",
        user_url="https://example.com/job",
    )

    assert source.received_options == {
        "board_url": "https://example.com",
    }


def test_source_without_supported_options_receives_none():

    class BasicSource(JobSource):

        name = "basic"

        def __init__(self):
            self.received_options = None

        def search(
            self,
            keywords,
            location=None,
            **options,
        ):
            self.received_options = options

            return []

    source = BasicSource()

    manager = JobSourceManager(
        sources=[
            source
        ]
    )

    manager.search(
        keywords="engineer",
        board_url="https://example.com",
    )

    assert source.received_options == {}