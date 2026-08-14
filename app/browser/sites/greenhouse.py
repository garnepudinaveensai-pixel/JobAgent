from typing import Optional
from urllib.parse import quote

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.browser.base_site import BaseJobSite


class GreenhouseSite(BaseJobSite):
    """
    Greenhouse job-board adapter.

    Handles public Greenhouse-hosted job boards:
    - job search
    - job listing extraction
    - job detail extraction

    Does NOT submit applications.
    """

    name = "Greenhouse"

    def __init__(self, page):
        super().__init__(page)
        self._search_url: Optional[str] = None

    # ========================================================
    # SEARCH
    # ========================================================

    def search_jobs(
        self,
        keywords: str,
        location: Optional[str] = None,
    ) -> None:
        """
        Search a Greenhouse job board.

        Greenhouse boards differ between companies, so this
        method supports the common search/filter controls
        without depending on one specific company.
        """

        if not keywords or not keywords.strip():
            raise ValueError("keywords cannot be empty")

        keyword = keywords.strip()

        # Try the common Greenhouse search input.
        search_selectors = [
            'input[placeholder*="Search"]',
            'input[aria-label*="Search"]',
            'input[name="q"]',
            'input[type="search"]',
        ]

        search_box = None

        for selector in search_selectors:
            try:
                locator = self.page.locator(selector).first

                if locator.is_visible(timeout=1500):
                    search_box = locator
                    break

            except PlaywrightTimeoutError:
                continue

        if search_box is not None:
            search_box.fill(keyword)
            search_box.press("Enter")

            try:
                self.wait_for_page()
            except Exception:
                pass

        else:
            # Some Greenhouse boards expose search through
            # URL parameters rather than a visible input.
            current_url = self.get_current_url()

            separator = "&" if "?" in current_url else "?"

            search_url = (
                f"{current_url}"
                f"{separator}query={quote(keyword)}"
            )

            self.page.goto(
                search_url,
                wait_until="domcontentloaded",
            )

        self._search_url = self.get_current_url()

    # ========================================================
    # JOB LISTINGS
    # ========================================================

    def get_job_listings(self) -> list[dict]:
        """
        Extract currently visible Greenhouse job listings.

        Returns normalized dictionaries containing:
        title, company, location, URL, description.
        """

        listings: list[dict] = []

        # Greenhouse commonly exposes job links through
        # links containing /jobs/.
        links = self.page.locator('a[href*="/jobs/"]')

        count = links.count()

        for index in range(count):
            try:
                link = links.nth(index)

                if not link.is_visible(timeout=1000):
                    continue

                title = link.inner_text().strip()

                if not title:
                    continue

                href = link.get_attribute("href")

                if not href:
                    continue

                url = self.page.url

                if href.startswith("http"):
                    url = href
                elif href.startswith("/"):
                    base = self.page.url.split("/", 3)

                    if len(base) >= 3:
                        url = f"{base[0]}//{base[2]}{href}"

                # Avoid duplicate URLs.
                if any(item["url"] == url for item in listings):
                    continue

                listings.append(
                    {
                        "title": title,
                        "company": self._extract_company(),
                        "location": self._extract_listing_location(link),
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

    def get_job_details(self, job_url: str) -> dict:
        """
        Open one Greenhouse job page and extract normalized
        job information.
        """

        if not job_url or not job_url.strip():
            raise ValueError("job_url cannot be empty")

        self.page.goto(
            job_url,
            wait_until="domcontentloaded",
        )

        self.wait_for_page()

        title = self._first_text(
            [
                "h1",
                '[data-testid="job-title"]',
                ".job-title",
            ]
        )

        company = self._extract_company()

        location = self._first_text(
            [
                '[data-testid="location"]',
                ".location",
                ".job-location",
            ]
        )

        description = self._first_text(
            [
                "#content",
                ".job__description",
                ".job-description",
                '[data-testid="job-description"]',
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

    def _first_text(self, selectors: list[str]) -> str:
        """Return text from the first visible matching element."""

        for selector in selectors:
            try:
                locator = self.page.locator(selector).first

                if locator.is_visible(timeout=1000):
                    text = locator.inner_text().strip()

                    if text:
                        return text

            except Exception:
                continue

        return ""

    def _extract_company(self) -> str:
        """Try common Greenhouse/company name selectors."""

        return self._first_text(
            [
                '[data-testid="company-name"]',
                ".company-name",
                '[class*="company-name"]',
            ]
        )

    def _extract_listing_location(self, link) -> str:
        """
        Try to extract location associated with a job listing.
        """

        try:
            parent = link.locator("xpath=..")

            text = parent.inner_text().strip()

            if text:
                lines = [
                    line.strip()
                    for line in text.splitlines()
                    if line.strip()
                ]

                # Usually the title is the first line.
                if len(lines) > 1:
                    return lines[1]

        except Exception:
            pass

        return ""

    # ========================================================
    # WAIT
    # ========================================================

    def wait_for_page(self) -> None:
        """Wait until the current page finishes loading."""

        try:
            self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=10000,
            )
        except PlaywrightTimeoutError:
            pass