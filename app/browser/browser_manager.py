from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
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

    The manager supports two modes:

    1. Ephemeral browser context (default for tests and isolated runs).
    2. Persistent Chromium profile when ``persistent_profile_dir`` is set.

    A persistent profile is the important part for real JobAgent use:
    cookies, local storage and site sessions survive browser restarts.
    The user logs in manually once; later JobAgent runs reuse the same
    profile instead of asking for credentials every time.

    JobAgent never stores site passwords and never attempts to bypass
    CAPTCHA, OTP or other human-verification mechanisms.
    """

    def __init__(
        self,
        headless: bool = False,
        timeout: int = 30000,
        persistent_profile_dir: Optional[str] = None,
    ):
        if timeout <= 0:
            raise ValueError("timeout must be greater than 0.")

        self.headless = bool(headless)
        self.timeout = timeout
        self.persistent_profile_dir = (
            str(persistent_profile_dir).strip()
            if persistent_profile_dir is not None
            else None
        ) or None

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._persistent_context = False

    # ========================================================
    # START
    # ========================================================

    def start(self) -> "BrowserManager":
        """Start Playwright and create the configured browser context."""

        if self._context is not None:
            return self

        try:
            self._playwright = sync_playwright().start()

            if self.persistent_profile_dir:
                profile = Path(self.persistent_profile_dir).expanduser()
                profile.mkdir(parents=True, exist_ok=True)

                self._context = self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile.resolve()),
                    headless=self.headless,
                )
                self._persistent_context = True
                self._browser = getattr(self._context, "browser", None)
            else:
                self._browser = self._playwright.chromium.launch(
                    headless=self.headless,
                )
                self._persistent_context = False

            if self._context is not None:
                self._configure_context(self._context)

            return self

        except Exception:
            self.close()
            raise

    # ========================================================
    # CONTEXT
    # ========================================================

    def _configure_context(self, context: BrowserContext) -> None:
        context.set_default_timeout(self.timeout)
        context.set_default_navigation_timeout(self.timeout)

    def create_context(self) -> BrowserContext:
        """Create or reuse the active browser context."""

        if self._context is None:
            if self._playwright is None and self._browser is None:
                raise RuntimeError(
                    "BrowserManager is not started. Call start() first."
                )

            # Defensive compatibility path for unusual callers that provide
            # a browser object without going through start().
            if self._browser is None:
                raise RuntimeError(
                    "BrowserManager is not started. Call start() first."
                )

            self._context = self._browser.new_context()
            self._persistent_context = False
            self._configure_context(self._context)

        return self._context

    # ========================================================
    # PAGE
    # ========================================================

    def new_page(self) -> Page:
        """Create a new page inside the active browser context."""

        context = self.create_context()
        self._page = context.new_page()
        return self._page

    # ========================================================
    # CURRENT PAGE
    # ========================================================

    @property
    def page(self) -> Optional[Page]:
        return self._page

    # ========================================================
    # BROWSER
    # ========================================================

    @property
    def browser(self) -> Optional[Browser]:
        return self._browser

    # ========================================================
    # CONTEXT
    # ========================================================

    @property
    def context(self) -> Optional[BrowserContext]:
        return self._context

    # ========================================================
    # PROFILE
    # ========================================================

    @property
    def is_persistent(self) -> bool:
        return self._persistent_context

    @property
    def profile_directory(self) -> Optional[str]:
        if not self.persistent_profile_dir:
            return None
        return str(Path(self.persistent_profile_dir).expanduser().resolve())

    # ========================================================
    # URL VALIDATION
    # ========================================================

    @staticmethod
    def _validate_url(url: str) -> None:
        if not isinstance(url, str):
            raise ValueError("URL must be a string.")

        url = url.strip()
        if not url:
            raise ValueError("URL cannot be empty.")

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("URL must use http:// or https://.")

        if not parsed.netloc:
            raise ValueError("URL must contain a valid hostname.")

    # ========================================================
    # NAVIGATION
    # ========================================================

    def open(self, url: str) -> Page:
        """Open a URL in a new page using the active session/profile."""

        self._validate_url(url)

        if self._context is None:
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
        """Safely close Playwright resources."""

        self.close_page()

        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None

        # A persistent context owns the Chromium instance. Do not call
        # browser.close() separately in that mode.
        if self._browser is not None and not self._persistent_context:
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

        self._persistent_context = False

    # ========================================================
    # CONTEXT MANAGER
    # ========================================================

    def __enter__(self) -> "BrowserManager":
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


@contextmanager
def browser_session(
    headless: bool = False,
    timeout: int = 30000,
    persistent_profile_dir: Optional[str] = None,
) -> Generator[BrowserManager, None, None]:
    """Convenience context manager for a complete browser session."""

    manager = BrowserManager(
        headless=headless,
        timeout=timeout,
        persistent_profile_dir=persistent_profile_dir,
    )

    try:
        manager.start()
        yield manager
    finally:
        manager.close()
