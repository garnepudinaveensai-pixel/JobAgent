from contextlib import contextmanager
from typing import Generator, Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright


class BrowserManager:
    """
    Centralized Playwright browser manager for JobAgent.

    Responsibilities:
    - Start and stop Playwright safely
    - Launch Chromium
    - Create isolated browser contexts
    - Create pages
    - Reuse one browser instance during a workflow
    - Clean up resources reliably
    """

    def __init__(
        self,
        headless: bool = False,
        timeout: int = 30000,
    ):
        self.headless = headless
        self.timeout = timeout

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    # ========================================================
    # START
    # ========================================================

    def start(self) -> "BrowserManager":
        """
        Start Playwright and launch Chromium.

        Returns:
            BrowserManager: self, allowing chained usage.
        """

        if self._browser is not None:
            return self

        self._playwright = sync_playwright().start()

        self._browser = self._playwright.chromium.launch(
            headless=self.headless
        )

        return self

    # ========================================================
    # CONTEXT
    # ========================================================

    def create_context(self) -> BrowserContext:
        """
        Create a fresh browser context.

        A context provides isolated cookies, storage,
        sessions, and browser state.
        """

        if self._browser is None:
            raise RuntimeError(
                "BrowserManager is not started. "
                "Call start() first."
            )

        if self._context is not None:
            self._context.close()

        self._context = self._browser.new_context()

        self._context.set_default_timeout(
            self.timeout
        )

        self._context.set_default_navigation_timeout(
            self.timeout
        )

        return self._context

    # ========================================================
    # PAGE
    # ========================================================

    def new_page(self) -> Page:
        """
        Create a new page in a fresh browser context.
        """

        context = self.create_context()

        self._page = context.new_page()

        return self._page

    # ========================================================
    # CURRENT PAGE
    # ========================================================

    @property
    def page(self) -> Optional[Page]:
        """Return the currently active page."""

        return self._page

    # ========================================================
    # BROWSER
    # ========================================================

    @property
    def browser(self) -> Optional[Browser]:
        """Return the active browser instance."""

        return self._browser

    # ========================================================
    # NAVIGATION
    # ========================================================

    def open(self, url: str) -> Page:
        """
        Open a URL in a new page.
        """

        if not url.strip():
            raise ValueError("URL cannot be empty.")

        if self._browser is None:
            self.start()

        page = self.new_page()

        page.goto(
            url,
            wait_until="domcontentloaded",
        )

        return page

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self) -> None:
        """
        Safely close page, context, browser, and Playwright.
        """

        if self._page is not None:
            try:
                self._page.close()
            except Exception:
                pass

            self._page = None

        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass

            self._context = None

        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass

            self._browser = None

        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass

            self._playwright = None

    # ========================================================
    # CONTEXT MANAGER
    # ========================================================

    def __enter__(self) -> "BrowserManager":
        """Allow use with the `with` statement."""

        return self.start()

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        """Always clean up browser resources."""

        self.close()


@contextmanager
def browser_session(
    headless: bool = False,
    timeout: int = 30000,
) -> Generator[BrowserManager, None, None]:
    """
    Convenience context manager for a complete browser session.

    Example:

        with browser_session() as browser:
            page = browser.open("https://example.com")
    """

    manager = BrowserManager(
        headless=headless,
        timeout=timeout,
    )

    try:
        manager.start()
        yield manager

    finally:
        manager.close()