from contextlib import contextmanager
from typing import Generator, Optional
from urllib.parse import urlparse

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)


class BrowserManager:
    """
    Centralized Playwright browser manager for JobAgent.

    Responsibilities:
    - Start and stop Playwright safely.
    - Launch Chromium.
    - Reuse one browser instance.
    - Reuse one browser context during a session.
    - Create multiple pages when required.
    - Apply consistent timeouts.
    - Validate URLs before navigation.
    - Clean up resources reliably.
    """

    def __init__(
        self,
        headless: bool = False,
        timeout: int = 30000,
    ):
        if timeout <= 0:
            raise ValueError(
                "timeout must be greater than 0."
            )

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

        Calling start() multiple times is safe.
        The existing browser instance is reused.
        """

        if self._browser is not None:
            return self

        try:
            self._playwright = sync_playwright().start()

            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
            )

            return self

        except Exception:
            # If startup fails, clean up anything that may
            # have been partially initialized.
            self.close()
            raise

    # ========================================================
    # CONTEXT
    # ========================================================

    def create_context(self) -> BrowserContext:
        """
        Create or reuse the active browser context.

        The context is reused for the lifetime of the
        BrowserManager session.

        This preserves cookies, local storage, and session
        state between pages.
        """

        if self._browser is None:
            raise RuntimeError(
                "BrowserManager is not started. "
                "Call start() first."
            )

        if self._context is None:
            self._context = self._browser.new_context()

            self._context.set_default_timeout(
                self.timeout,
            )

            self._context.set_default_navigation_timeout(
                self.timeout,
            )

        return self._context

    # ========================================================
    # PAGE
    # ========================================================

    def new_page(self) -> Page:
        """
        Create a new page inside the active browser context.

        Multiple pages can now coexist during one session.
        """

        context = self.create_context()

        self._page = context.new_page()

        return self._page

    # ========================================================
    # CURRENT PAGE
    # ========================================================

    @property
    def page(self) -> Optional[Page]:
        """
        Return the most recently created page.
        """

        return self._page

    # ========================================================
    # BROWSER
    # ========================================================

    @property
    def browser(self) -> Optional[Browser]:
        """
        Return the active browser instance.
        """

        return self._browser

    # ========================================================
    # CONTEXT
    # ========================================================

    @property
    def context(self) -> Optional[BrowserContext]:
        """
        Return the active browser context.
        """

        return self._context

    # ========================================================
    # URL VALIDATION
    # ========================================================

    @staticmethod
    def _validate_url(url: str) -> None:
        """
        Validate that a URL is a usable HTTP/HTTPS URL.
        """

        if not isinstance(url, str):
            raise ValueError(
                "URL must be a string."
            )

        url = url.strip()

        if not url:
            raise ValueError(
                "URL cannot be empty."
            )

        parsed = urlparse(url)

        if parsed.scheme not in {
            "http",
            "https",
        }:
            raise ValueError(
                "URL must use http:// or https://."
            )

        if not parsed.netloc:
            raise ValueError(
                "URL must contain a valid hostname."
            )

    # ========================================================
    # NAVIGATION
    # ========================================================

    def open(self, url: str) -> Page:
        """
        Open a URL in a new page.

        The browser is started automatically if necessary.
        """

        self._validate_url(url)

        if self._browser is None:
            self.start()

        page = self.new_page()

        page.goto(
            url.strip(),
            wait_until="domcontentloaded",
        )

        return page

    # ========================================================
    # CLOSE PAGE
    # ========================================================

    def close_page(self, page: Optional[Page] = None) -> None:
        """
        Close one page without shutting down the entire
        browser session.

        If no page is supplied, close the current page.
        """

        target = page or self._page

        if target is None:
            return

        try:
            target.close()
        except Exception:
            pass

        if target is self._page:
            self._page = None

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self) -> None:
        """
        Safely close all Playwright resources.

        Cleanup order:

            page
              ↓
            context
              ↓
            browser
              ↓
            Playwright
        """

        self.close_page()

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
        """
        Start the browser when entering a with-block.
        """

        return self.start()

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        """
        Always clean up browser resources.
        """

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
            page = browser.open(
                "https://example.com"
            )

    The browser is automatically closed when the block ends.
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