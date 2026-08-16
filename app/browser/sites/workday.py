from __future__ import annotations

from typing import Optional
from urllib.parse import quote

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.browser.base_site import BaseJobSite


class WorkdaySite(BaseJobSite):
    """
    Public Workday external-career-site adapter.

    Supports normal publicly accessible Workday career pages.

    This adapter:
        - opens a public Workday career site
        - searches available jobs
        - extracts visible job listings
        - extracts job details

    It does NOT:
        - bypass authentication
        - bypass CAPTCHA
        - bypass anti-bot controls
        - bypass access restrictions
        - submit applications
    """

    name = "Workday"

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
        Search a public Workday external career site.
        """

        if not keywords or not keywords.strip():
            raise ValueError(
                "keywords cannot be empty."
            )

        keyword = keywords.strip()

        # Workday career sites have changed UI structures
        # across tenants and versions, so use several
        # common public-search selectors.
        search_selectors = [
            'input[placeholder*="Search"]',
            'input[placeholder*="search"]',
            'input[aria-label*="Search"]',
            'input[aria-label*="search"]',
            'input[name="searchText"]',
            'input[name="q"]',
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

            except Exception:
                continue

        if search_box is not None:
            search_box.fill(keyword)

            # Try Enter first. Some Workday sites search
            # immediately, while others expose a button.
            try:
                search_box.press("Enter")
            except Exception:
                pass

            self._wait_after_search()

        else:
            # Some public Workday career sites expose
            # search parameters in the URL.
            current_url = self.get_current_url()

            separator = (
                "&"
                if "?" in current_url
                else "?"
            )

            search_url = (
                f"{current_url}"
                f"{separator}"
                f"searchText={quote(keyword)}"
            )

            try:
                self.page.goto(
                    search_url,
                    wait_until="domcontentloaded",
                )
            except Exception:
                # Do not attempt any bypass if the site
                # rejects normal navigation.
                raise

            self.wait_for_page()

        self._search_url = self.get_current_url()

    # ========================================================
    # JOB LISTINGS
    # ========================================================

    def get_job_listings(self) -> list[dict]:
        """
        Extract visible job listings from a public
        Workday career site.
        """

        listings: list[dict] = []
        seen_urls: set[str] = set()

        # Workday career pages commonly expose job links
        # containing /job/ or /jobs/.
        selectors = [
            'a[href*="/job/"]',
            'a[href*="/jobs/"]',
            'a[data-automation-id="jobTitle"]',
            'a[data-automation-id="jobLink"]',
        ]

        links = []

        for selector in selectors:
            try:
                locator = self.page.locator(
                    selector
                )

                count = locator.count()

                for index in range(count):
                    links.append(
                        locator.nth(index)
                    )

            except Exception:
                continue

        for link in links:
            try:
                if not link.is_visible(
                    timeout=1000
                ):
                    continue

                title = link.inner_text().strip()

                if not title:
                    title = (
                        link.get_attribute(
                            "aria-label"
                        )
                        or ""
                    ).strip()

                if not title:
                    continue

                href = link.get_attribute(
                    "href"
                )

                if not href:
                    continue

                url = self._absolute_url(
                    href
                )

                if not url:
                    continue

                if url in seen_urls:
                    continue

                seen_urls.add(url)

                listings.append(
                    {
                        "title": title,
                        "company": self._extract_company(),
                        "location": (
                            self._extract_listing_location(
                                link
                            )
                        ),
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
        Open one public Workday job page and extract
        normalized job information.
        """

        if not job_url or not job_url.strip():
            raise ValueError(
                "job_url cannot be empty."
            )

        url = job_url.strip()

        self.page.goto(
            url,
            wait_until="domcontentloaded",
        )

        self.wait_for_page()

        title = self._first_text(
            [
                'h1[data-automation-id="jobPostingHeader"]',
                '[data-automation-id="jobPostingHeader"]',
                "h1",
            ]
        )

        company = self._extract_company()

        location = self._first_text(
            [
                '[data-automation-id="locations"]',
                '[data-automation-id="location"]',
                ".job-location",
            ]
        )

        description = self._first_text(
            [
                '[data-automation-id="jobPostingDescription"]',
                '[data-automation-id="jobPostingDescriptionContent"]',
                ".job-description",
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
        Return text from the first visible matching
        selector.
        """

        for selector in selectors:
            try:
                locator = self.page.locator(
                    selector
                ).first

                if locator.is_visible(
                    timeout=1000
                ):
                    text = locator.inner_text().strip()

                    if text:
                        return text

            except Exception:
                continue

        return ""

    def _extract_company(self) -> str:
        """
        Try to identify the company from the public page.
        """

        return self._first_text(
            [
                '[data-automation-id="company"]',
                '[data-automation-id="companyName"]',
                '[data-automation-id="jobPostingCompany"]',
                ".company-name",
            ]
        )

    def _extract_listing_location(
        self,
        link,
    ) -> str:
        """
        Attempt to identify the location associated with
        a visible job listing.
        """

        try:
            parent = link.locator(
                "xpath=.."
            )

            text = parent.inner_text().strip()

            if text:
                lines = [
                    line.strip()
                    for line in text.splitlines()
                    if line.strip()
                ]

                # Usually the title is near the beginning
                # and location appears elsewhere in the
                # same listing container.
                for line in lines[1:]:
                    if line != link.inner_text().strip():
                        return line

        except Exception:
            pass

        return ""

    def _absolute_url(
        self,
        href: str,
    ) -> str:
        """
        Convert a relative Workday link into an absolute URL.
        """

        if not href:
            return ""

        href = href.strip()

        if href.startswith("http://"):
            return href

        if href.startswith("https://"):
            return href

        if href.startswith("//"):
            current = self.page.url

            if current.startswith("https://"):
                return "https:" + href

            return "http:" + href

        if href.startswith("/"):
            current = self.page.url
            parts = current.split("/", 3)

            if len(parts) >= 3:
                return (
                    f"{parts[0]}//{parts[2]}"
                    f"{href}"
                )

        return ""

    def _wait_after_search(self) -> None:
        """
        Wait for a normal public search operation to settle.
        """

        try:
            self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=10000,
            )
        except PlaywrightTimeoutError:
            pass

        # Give client-rendered job results a short opportunity
        # to appear without introducing aggressive polling.
        try:
            self.page.wait_for_timeout(1000)
        except Exception:
            pass

    def wait_for_page(self) -> None:
        """
        Wait for the current page to finish loading.
        """

        try:
            self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=10000,
            )
        except PlaywrightTimeoutError:
            pass