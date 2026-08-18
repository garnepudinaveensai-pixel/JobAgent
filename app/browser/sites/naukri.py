from __future__ import annotations

from typing import Optional
from urllib.parse import quote

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.browser.base_site import BaseJobSite


class NaukriSite(BaseJobSite):
    """
    Naukri public job-search adapter.

    Uses normal browser navigation and publicly accessible
    job-search functionality.

    Does NOT:
        - bypass authentication
        - bypass CAPTCHA
        - bypass anti-bot protections
        - bypass access restrictions
        - submit applications
    """

    name = "Naukri"

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
        Search Naukri using the normal public search interface.
        """

        if not keywords or not keywords.strip():
            raise ValueError(
                "keywords cannot be empty."
            )

        keyword = keywords.strip()

        # Try visible search controls first.
        keyword_selectors = [
            'input[placeholder*="Search"]',
            'input[placeholder*="search"]',
            'input[placeholder*="skills"]',
            'input[placeholder*="Skills"]',
            'input[placeholder*="designations"]',
            'input[placeholder*="companies"]',
            'input[placeholder*="Enter skills"]',
            'input[name="keyword"]',
            'input[name="keywords"]',
            'input[type="search"]',
        ]

        search_box = None

        for selector in keyword_selectors:
            try:
                locator = (
                    self.page.locator(
                        selector
                    ).first
                )

                if locator.is_visible(
                    timeout=1500
                ):
                    search_box = locator
                    break

            except Exception:
                continue

        if search_box is not None:
            try:
                search_box.fill(
                    keyword
                )

                if location and location.strip():
                    self._fill_location(
                        location.strip()
                    )

                clicked = self._click_search_button()
                if not clicked:
                    search_box.press("Enter")

                self.wait_for_page()
                self._settle_page()
                return

            except Exception:
                pass

        # Fallback to Naukri's public search URL.
        search_url = (
            "https://www.naukri.com/"
            "jobs-in-india"
            f"?k={quote(keyword)}"
        )

        if location and location.strip():
            search_url += (
                f"&l={quote(location.strip())}"
            )

        self.page.goto(
            search_url,
            wait_until="domcontentloaded",
        )

        self.wait_for_page()
        self._settle_page()

    def _click_search_button(self) -> bool:
        selectors = [
            'button:has-text("Search")',
            'input[type="submit"]',
            'button[type="submit"]',
        ]
        for selector in selectors:
            try:
                locator = self.page.locator(selector).first
                if locator.is_visible(timeout=1000):
                    locator.click()
                    return True
            except Exception:
                continue
        return False

    def _settle_page(self) -> None:
        try:
            self.page.wait_for_timeout(1200)
        except Exception:
            pass

    def get_access_state(self) -> dict:
        try:
            url = self.get_current_url().lower()
        except Exception:
            url = ""
        try:
            title = self.get_title().lower()
        except Exception:
            title = ""
        try:
            body = self.page.locator("body").inner_text(timeout=3000).lower()
        except Exception:
            body = ""
        text = f"{title} {url} {body}"
        verification_terms = (
            "captcha",
            "verify you are human",
            "access denied",
            "unusual traffic",
            "cloudflare",
            "just a moment",
            "additional verification",
        )
        matched = next((term for term in verification_terms if term in text), None)
        if matched:
            return {
                "blocked": True,
                "code": "verification_required",
                "message": f"Naukri requires additional verification ({matched}).",
                "requires_human_action": True,
            }
        return {
            "blocked": False,
            "code": "ok",
            "message": "",
            "requires_human_action": False,
        }

    def _fill_location(
        self,
        location: str,
    ) -> bool:
        """
        Try to fill the public location field.
        """

        selectors = [
            'input[placeholder*="Location"]',
            'input[placeholder*="location"]',
            'input[placeholder*="Enter location"]',
            'input[placeholder*="location"]',
            'input[name="location"]',
            'input[name="locations"]',
        ]

        for selector in selectors:
            try:
                locator = (
                    self.page.locator(
                        selector
                    ).first
                )

                if locator.is_visible(
                    timeout=1000
                ):
                    locator.fill(
                        location
                    )

                    return True

            except Exception:
                continue

        return False

    # ========================================================
    # LISTINGS
    # ========================================================

    def get_job_listings(self) -> list[dict]:
        """
        Extract visible Naukri job listings.

        Returns normalized dictionaries containing:
            title
            company
            location
            url
            description
        """

        listings: list[dict] = []

        selectors = [
            "article.jobTuple",
            "article.job-tuple",
            ".jobTuple",
            ".cust-job-tuple",
            "[data-job-id]",
            "div[data-job-id]",
            "div[class*=jobTuple]",
            "div[class*=job-tuple]",
        ]

        cards = None

        for selector in selectors:
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
            count = cards.count()

            for index in range(count):
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

            return listings

        # Generic fallback for publicly visible job links.
        links = self.page.locator(
            'a[href*="/job-listings-"], a[href*="/job-listings/"]'
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

                title = (link.inner_text() or "").strip()
                if not title:
                    title = (link.get_attribute("aria-label") or link.get_attribute("title") or "").strip()

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
        Extract one Naukri job card.
        """

        title = self._first_text_from(
            card,
            [
                ".title",
                ".jobTitle",
                "[class*=jobTitle]",
                ".jobTitle",
                "a.title",
                "h2",
                "h3",
            ],
        )

        company = self._first_text_from(
            card,
            [
                ".comp-name",
                ".companyInfo",
                ".company-name",
                ".subTitle",
            ],
        )

        location = self._first_text_from(
            card,
            [
                ".loc",
                ".location",
                ".job-location",
                ".locationsContainer",
            ],
        )

        description = self._first_text_from(
            card,
            [
                ".job-desc",
                ".job-description",
                ".jobDescription",
            ],
        )

        url = ""

        for selector in [
            "a.title",
            'a[href*="/job-listings-"]',
            "a[href]",
        ]:
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
        Open and extract details from a public Naukri job page.
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
                ".jd-header-title",
                ".jd-header h1",
                ".styles_jd-header-title__",
            ]
        )

        company = self._first_text(
            [
                ".jd-header-comp-name",
                ".jd-header-comp-name a",
                ".company-name",
            ]
        )

        location = self._first_text(
            [
                ".loc",
                ".location",
                ".jd-job-meta",
            ]
        )

        description = self._first_text(
            [
                ".job-desc",
                ".dang-inner-html",
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
        for selector in selectors:
            try:
                locator = (
                    self.page.locator(
                        selector
                    ).first
                )

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
                locator = (
                    parent.locator(
                        selector
                    ).first
                )

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

    def _absolute_url(
        self,
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

        if href.startswith("/"):
            return (
                "https://www.naukri.com"
                f"{href}"
            )

        return ""

    def wait_for_page(self) -> None:
        try:
            self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=10000,
            )
        except PlaywrightTimeoutError:
            pass