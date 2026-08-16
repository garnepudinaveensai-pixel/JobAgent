from __future__ import annotations

from typing import Optional
from urllib.parse import quote, urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.browser.base_site import BaseJobSite


class IndeedSite(BaseJobSite):
    """
    Indeed public job-search adapter.

    Uses normal publicly accessible browser functionality.

    Does NOT:
        - bypass authentication
        - bypass CAPTCHA
        - bypass anti-bot protections
        - bypass access restrictions
        - submit applications
    """

    name = "Indeed"

    # ========================================================
    # SEARCH
    # ========================================================

    def search_jobs(
        self,
        keywords: str,
        location: Optional[str] = None,
    ) -> None:
        """
        Search Indeed using the public search interface.

        Falls back to Indeed's public search URL if the
        visible search controls are unavailable.
        """

        if not keywords or not keywords.strip():
            raise ValueError(
                "keywords cannot be empty."
            )

        keyword = keywords.strip()
        location_value = (
            location.strip()
            if location
            else ""
        )

        keyword_selectors = [
            'input[name="q"]',
            'input[placeholder*="What"]',
            'input[placeholder*="what"]',
            'input[aria-label*="What"]',
            'input[type="search"]',
        ]

        location_selectors = [
            'input[name="l"]',
            'input[name="location"]',
            'input[placeholder*="Where"]',
            'input[placeholder*="where"]',
            'input[aria-label*="Where"]',
        ]

        search_box = self._first_visible(
            keyword_selectors
        )

        if search_box is not None:
            try:
                search_box.fill(
                    keyword
                )

                if location_value:
                    location_box = self._first_visible(
                        location_selectors
                    )

                    if location_box is not None:
                        location_box.fill(
                            location_value
                        )

                search_box.press("Enter")

                self.wait_for_page()
                return

            except Exception:
                pass

        # Public URL fallback.
        search_url = (
            "https://www.indeed.com/jobs"
            f"?q={quote(keyword)}"
        )

        if location_value:
            search_url += (
                f"&l={quote(location_value)}"
            )

        self.page.goto(
            search_url,
            wait_until="domcontentloaded",
        )

        self.wait_for_page()

    # ========================================================
    # LISTINGS
    # ========================================================

    def get_job_listings(self) -> list[dict]:
        """
        Extract currently visible public Indeed job listings.
        """

        listings: list[dict] = []

        card_selectors = [
            "div.job_seen_beacon",
            "div.cardOutline",
            "td.resultContent",
            "[data-jk]",
        ]

        cards = None

        for selector in card_selectors:
            try:
                locator = self.page.locator(
                    selector
                )

                if locator.count() > 0:
                    cards = locator
                    break

            except Exception:
                continue

        if cards is not None:
            for index in range(
                cards.count()
            ):
                try:
                    card = cards.nth(index)

                    if not card.is_visible(
                        timeout=1000
                    ):
                        continue

                    job = self._extract_card(
                        card
                    )

                    if not job["title"]:
                        continue

                    if not job["url"]:
                        continue

                    if any(
                        item["url"] == job["url"]
                        for item in listings
                    ):
                        continue

                    listings.append(job)

                except Exception:
                    continue

            if listings:
                return listings

        # Generic public Indeed job links.
        links = self.page.locator(
            'a[href*="/viewjob"]'
        )

        for index in range(
            links.count()
        ):
            try:
                link = links.nth(index)

                if not link.is_visible(
                    timeout=1000
                ):
                    continue

                title = (
                    link.inner_text()
                    .strip()
                )

                href = (
                    link.get_attribute(
                        "href"
                    )
                    or ""
                )

                url = self._absolute_url(
                    href
                )

                if not title or not url:
                    continue

                if any(
                    item["url"] == url
                    for item in listings
                ):
                    continue

                listings.append(
                    {
                        "title": title,
                        "company": "",
                        "location": "",
                        "url": url,
                        "description": "",
                    }
                )

            except Exception:
                continue

        return listings

    def _extract_card(
        self,
        card,
    ) -> dict:
        """
        Extract one Indeed job card.
        """

        title = self._first_text_from(
            card,
            [
                "h2.jobTitle",
                "h2",
                ".jobTitle",
                '[data-testid="jobTitle"]',
            ],
        )

        company = self._first_text_from(
            card,
            [
                '[data-testid="company-name"]',
                ".companyName",
                ".company",
            ],
        )

        location = self._first_text_from(
            card,
            [
                '[data-testid="text-location"]',
                ".companyLocation",
                ".location",
            ],
        )

        description = self._first_text_from(
            card,
            [
                ".job-snippet",
                ".jobSnippet",
                ".underShelfFooter",
            ],
        )

        url = ""

        link_selectors = [
            "h2.jobTitle a",
            "a[href*='/viewjob']",
            "a[href*='jk=']",
            "a[href]",
        ]

        for selector in link_selectors:
            try:
                link = card.locator(
                    selector
                ).first

                if link.count() == 0:
                    continue

                href = (
                    link.get_attribute(
                        "href"
                    )
                    or ""
                )

                if href:
                    url = self._absolute_url(
                        href
                    )
                    break

            except Exception:
                continue

        return {
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "description": description,
        }

    # ========================================================
    # DETAILS
    # ========================================================

    def get_job_details(
        self,
        job_url: str,
    ) -> dict:
        """
        Open and extract details from a public Indeed job page.
        """

        if not job_url or not job_url.strip():
            raise ValueError(
                "job_url cannot be empty."
            )

        self.page.goto(
            job_url.strip(),
            wait_until="domcontentloaded",
        )

        self.wait_for_page()

        title = self._first_text(
            [
                "h1",
                '[data-testid="jobsearch-JobInfoHeader-title"]',
                ".jobsearch-JobInfoHeader-title",
            ]
        )

        company = self._first_text(
            [
                '[data-testid="inlineHeader-companyName"]',
                '[data-testid="companyName"]',
                ".jobsearch-InlineCompanyRating-companyHeader",
            ]
        )

        location = self._first_text(
            [
                '[data-testid="inlineHeader-companyLocation"]',
                '[data-testid="job-location"]',
                ".jobsearch-JobInfoHeader-subtitle",
            ]
        )

        description = self._first_text(
            [
                "#jobDescriptionText",
                '[data-testid="jobDescriptionText"]',
                ".jobsearch-jobDescriptionText",
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

    def _first_visible(
        self,
        selectors: list[str],
    ):
        for selector in selectors:
            try:
                locator = self.page.locator(
                    selector
                ).first

                if locator.is_visible(
                    timeout=1000
                ):
                    return locator

            except Exception:
                continue

        return None

    def _first_text(
        self,
        selectors: list[str],
    ) -> str:
        for selector in selectors:
            try:
                locator = self.page.locator(
                    selector
                ).first

                if locator.is_visible(
                    timeout=1000
                ):
                    text = (
                        locator.inner_text()
                        .strip()
                    )

                    if text:
                        return text

            except Exception:
                continue

        return ""

    def _first_text_from(
        self,
        parent,
        selectors: list[str],
    ) -> str:
        for selector in selectors:
            try:
                locator = parent.locator(
                    selector
                ).first

                if locator.count() == 0:
                    continue

                text = (
                    locator.inner_text()
                    .strip()
                )

                if text:
                    return text

            except Exception:
                continue

        return ""

    @staticmethod
    def _absolute_url(
        href: str,
    ) -> str:
        if not href:
            return ""

        href = href.strip()

        if href.startswith(
            "http://"
        ) or href.startswith(
            "https://"
        ):
            return href

        return urljoin(
            "https://www.indeed.com",
            href,
        )

    # ========================================================
    # WAIT
    # ========================================================

    def wait_for_page(self) -> None:
        try:
            self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=10000,
            )
        except PlaywrightTimeoutError:
            pass