import pytest

from app.browser.browser_manager import BrowserManager, browser_session


def test_browser_manager_start_and_close():
    manager = BrowserManager(headless=True)

    manager.start()

    assert manager.browser is not None

    manager.close()

    assert manager.browser is None
    assert manager.page is None


def test_browser_manager_open():
    manager = BrowserManager(headless=True)

    try:
        page = manager.open("https://example.com")

        assert page is not None
        assert "Example Domain" in page.title()
        assert "example.com" in page.url
    finally:
        manager.close()


def test_browser_manager_requires_start_for_context():
    manager = BrowserManager(headless=True)

    with pytest.raises(RuntimeError):
        manager.create_context()


def test_browser_manager_reuses_browser():
    manager = BrowserManager(headless=True)

    try:
        manager.start()

        first_browser = manager.browser

        manager.start()

        assert manager.browser is first_browser
    finally:
        manager.close()


def test_empty_url_rejected():
    manager = BrowserManager(headless=True)

    with pytest.raises(ValueError):
        manager.open("")


def test_browser_session():
    with browser_session(headless=True) as manager:
        assert manager.browser is not None

        page = manager.open("https://example.com")

        assert "Example Domain" in page.title()


def test_context_manager():
    with BrowserManager(headless=True) as manager:
        assert manager.browser is not None

    assert manager.browser is None