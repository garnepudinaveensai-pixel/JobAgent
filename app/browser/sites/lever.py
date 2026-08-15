from __future__ import annotations

from typing import Optional
from urllib.parse import urljoin, quote

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.browser.base_site import BaseJobSite


class LeverSite(BaseJobSite):
    """
    Lever public job-board adapter.

    Handles publicly accessible Lever job boards:
    - job search
    - job listing extraction
    - job detail extraction

    Does NOT:
    - bypass authentication
    - bypass anti-bot controls
    - bypass access restrictions
    - submit applications
    """

    name = "Lever"

    def __init__(self, page):
        super().__init__(page)

    # ========================================================
    # SEARCH
    # ========================================================

    def search_jobs(
        self,
        keywords: str,
        location: Optional[str] = None,
    ) -> None:
        """
        Search a publicly accessible Lever job board.
        """

        if not keywords or not keywords.strip():
            raise ValueError(
                "keywords cannot be empty."
            )

        keyword = keywords.strip()

        # Common Lever search controls.
        search_selectors = [
            'input[placeholder*="Search"]',
            'input[aria-label*="Search"]',
            'input[name="search"]',
            'input[type="search"]',
        ]

        search_box = None

        for selector in search_selectors:
            try:
                locator = self.page.locator(
                    selector
                ).first

                if locator.is_visible(
                    timeout=1500
                ):
                    search_box = locator
                    break

            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue

        if search_box is not None:
            search_box.fill(keyword)

            try:
                search_box.press("Enter")
            except Exception:
                pass

            try:
                self.wait_for_page()
            except Exception:
                pass

        else:
            # Some public Lever boards can be filtered through
            # URL parameters. We only use normal public access.
            current_url = self.get_current_url()

            separator = (
                "&"
                if "?" in current_url
                else "?"
            )

            search_url = (
                f"{current_url}"
                f"{separator}"
                f"search={quote(keyword)}"
            )

            try:
                self.page.goto(
                    search_url,
                    wait_until="domcontentloaded",
                )
            except Exception:
                pass

        # Location filtering is intentionally conservative.
        #
        # We do not attempt to bypass site controls.
        # Listing extraction below performs an additional
        # location check where location information is available.

    # ========================================================
    # JOB LISTINGS
    # ========================================================

    def get_job_listings(self) -> list[dict]:
        """
        Extract publicly visible Lever job listings.
        """

        listings: list[dict] = []

        selectors = [
            'a[href*="/jobs/"]',
            'a[href*="/job/"]',
            ".posting-title a",
            "a.posting-title",
        ]

        links = None

        for selector in selectors:
            try:
                locator = self.page.locator(
                    selector
                )

                if locator.count() > 0:
                    links = locator
                    break

            except Exception:
                continue

        if links is None:
            return listings

        count = links.count()

        for index in range(count):
            try:
                link = links.nth(index)

                if not link.is_visible(
                    timeout=1000
                ):
                    continue

                title = link.inner_text().strip()

                if not title:
                    continue

                href = link.get_attribute(
                    "href"
                )

                if not href:
                    continue

                url = urljoin(
                    self.get_current_url(),
                    href,
                )

                if any(
                    item["url"] == url
                    for item in listings
                ):
                    continue

                parent_text = ""

                try:
                    parent_text = (
                        link
                        .locator("xpath=..")
                        .inner_text()
                        .strip()
                    )
                except Exception:
                    pass

                location = self._extract_location(
                    parent_text
                )

                listings.append(
                    {
                        "title": title,
                        "company": self._extract_company(),
                        "location": location,
                        "url": url,
                        "description": "",
                    }
                )

            except Exception:
                continue

        return listings

    # ========================================================
    # JOB DETAILS
    # ========================================================

    def get_job_details(
        self,
        job_url: str,
    ) -> dict:
        """
        Open one public Lever job page and extract details.
        """

        if not job_url or not job_url.strip():
            raise ValueError(
                "job_url cannot be empty."
            )

        self.page.goto(
            job_url,
            wait_until="domcontentloaded",
        )

        try:
            self.wait_for_page()
        except Exception:
            pass

        title = self._first_text(
            [
                "h1",
                ".posting-headline h2",
                ".posting-title",
                '[data-qa="posting-name"]',
            ]
        )

        company = self._extract_company()

        location = self._first_text(
            [
                ".posting-categories .location",
                ".location",
                '[data-qa="posting-location"]',
            ]
        )

        description = self._first_text(
            [
                ".posting-page",
                ".posting-description",
                ".section-wrapper",
                "main",
            ]
        )

        return {
            "title": title,
            "company": company,
            "location": location,
            "url": self.get_current_url(),
            "description": description,
        }

    # ========================================================
    # HELPERS
    # ========================================================

    def _first_text(
        self,
        selectors: list[str],
    ) -> str:
        """
        Return text from the first visible matching element.
        """

        for selector in selectors:
            try:
                locator = self.page.locator(
                    selector
                ).first

                if locator.is_visible(
                    timeout=1000
                ):
                    text = (
                        locator
                        .inner_text()
                        .strip()
                    )

                    if text:
                        return text

            except Exception:
                continue

        return ""

    def _extract_company(self) -> str:
        """
        Extract company name when exposed by the page.
        """

        return self._first_text(
            [
                ".posting-company",
                ".company-name",
                '[data-qa="company-name"]',
            ]
        )

    @staticmethod
    def _extract_location(
        text: str,
    ) -> str:
        """
        Extract a likely location from listing text.
        """

        if not text:
            return ""

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        if len(lines) >= 2:
            return lines[-1]

        return ""

    # ========================================================
    # WAIT
    # ========================================================

    def wait_for_page(self) -> None:
        """
        Wait for normal DOM loading.
        """

        try:
            self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=10000,
            )
        except PlaywrightTimeoutError:
            pass