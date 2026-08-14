from playwright.sync_api import Page, Locator


class BaseJobSite:
    """
    Common browser utilities shared by all JobAgent site adapters.

    Site-specific classes such as Greenhouse, LinkedIn, Indeed,
    and Naukri will inherit from this class later.
    """

    name: str = ""

    def __init__(self, page: Page):
        self.page = page

    # ========================================================
    # SITE
    # ========================================================

    @property
    def site_name(self) -> str:
        """Return the human-readable site name."""
        return self.name or self.__class__.__name__

    # ========================================================
    # NAVIGATION
    # ========================================================

    def open(self, url: str) -> None:
        """Navigate to a URL."""
        if not url or not url.strip():
            raise ValueError("URL cannot be empty.")

        self.page.goto(
            url,
            wait_until="domcontentloaded",
        )

    def wait_for_page(self) -> None:
        """Wait until the page reaches the load state."""
        self.page.wait_for_load_state("domcontentloaded")

    # ========================================================
    # PAGE INFORMATION
    # ========================================================

    def get_title(self) -> str:
        """Return the current page title."""
        return self.page.title()

    def get_current_url(self) -> str:
        """Return the current page URL."""
        return self.page.url

    # ========================================================
    # LOCATORS
    # ========================================================

    def find(self, selector: str) -> Locator:
        """Return a Playwright locator."""
        if not selector or not selector.strip():
            raise ValueError("Selector cannot be empty.")

        return self.page.locator(selector)

    # ========================================================
    # ACTIONS
    # ========================================================

    def click(self, selector: str) -> None:
        """Click an element."""
        self.find(selector).click()

    def fill(self, selector: str, value: str) -> None:
        """Fill an input element."""
        self.find(selector).fill(value)

    # ========================================================
    # EXTRACTION
    # ========================================================

    def get_text(self, selector: str) -> str:
        """Return text content of an element."""
        return self.find(selector).inner_text()

    def is_visible(self, selector: str) -> bool:
        """Return whether an element is visible."""
        return self.find(selector).is_visible()

    # ========================================================
    # SAFE ACTIONS
    # ========================================================

    def safe_click(self, selector: str) -> bool:
        """
        Attempt to click an element.

        Returns:
            True  -> click succeeded
            False -> click failed
        """
        try:
            self.click(selector)
            return True
        except Exception:
            return False

    def safe_fill(self, selector: str, value: str) -> bool:
        """
        Attempt to fill an input.

        Returns:
            True  -> fill succeeded
            False -> fill failed
        """
        try:
            self.fill(selector, value)
            return True
        except Exception:
            return False

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self) -> None:
        """Close the current page."""
        try:
            self.page.close()
        except Exception:
            pass