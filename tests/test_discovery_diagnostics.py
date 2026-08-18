from app.browser.sites.indeed import IndeedSite
from app.browser.sites.naukri import NaukriSite
from app.core.sources.job_source import JobSource, SourceAccessError
from app.core.sources.job_source_manager import JobSourceManager


class FakeBlockedSource(JobSource):
    name = "indeed"

    def search(self, keywords, location=None, **options):
        raise SourceAccessError(
            "Verification required.",
            code="verification_required",
            requires_human_action=True,
        )


class FakeBody:
    def __init__(self, text):
        self.text = text

    def inner_text(self, timeout=None):
        return self.text


class FakePage:
    def __init__(self, body, title, url):
        self._body = body
        self._title = title
        self.url = url

    def title(self):
        return self._title

    def locator(self, selector):
        return FakeBody(self._body)


def test_source_access_error_is_reported_without_stopping_manager():
    class GoodSource(JobSource):
        name = "good"

        def search(self, keywords, location=None, **options):
            return [{"title": "Electrical Engineer"}]

    manager = JobSourceManager(
        [FakeBlockedSource(), GoodSource()]
    )

    results = manager.search("Electrical Engineer", "Hyderabad")

    assert len(results) == 1
    assert results[0]["source"] == "good"
    assert manager.last_diagnostics[0]["status"] == "blocked"
    assert manager.last_diagnostics[0]["code"] == "verification_required"
    assert manager.last_diagnostics[0]["requires_human_action"] is True
    assert manager.last_diagnostics[1]["status"] == "ok"


def test_indeed_verification_page_is_detected():
    site = IndeedSite(
        FakePage(
            "Additional Verification Required Cloudflare",
            "Just a moment...",
            "https://in.indeed.com/jobs?q=engineer",
        )
    )

    state = site.get_access_state()

    assert state["blocked"] is True
    assert state["code"] == "verification_required"
    assert state["requires_human_action"] is True


def test_naukri_normal_page_is_not_marked_blocked():
    site = NaukriSite(
        FakePage(
            "Find your dream job now",
            "Naukri",
            "https://www.naukri.com/jobs-in-india?k=engineer",
        )
    )

    state = site.get_access_state()

    assert state["blocked"] is False
