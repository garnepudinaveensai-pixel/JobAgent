from playwright.sync_api import sync_playwright

from app.browser.application_navigator import ApplicationNavigator


def test_direct_apply_control_is_detected():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content('<button>Apply</button>')
        navigator = ApplicationNavigator(page)
        assert navigator.find_apply_control() is not None
        browser.close()


def test_apply_filter_is_not_treated_as_application():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content('<button>Apply filters</button>')
        navigator = ApplicationNavigator(page)
        assert navigator.find_apply_control() is None
        browser.close()
