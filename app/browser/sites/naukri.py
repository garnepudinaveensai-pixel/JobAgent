from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote, urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.browser.base_site import BaseJobSite


class NaukriSite(BaseJobSite):
    """
    Public Naukri job-search adapter.

    The adapter intentionally uses the normal public job-search page and
    ordinary DOM extraction. It does not bypass CAPTCHA/Cloudflare,
    authentication, or other access controls, and it never submits an
    application from the discovery layer.

    Naukri's search-result DOM changes periodically. For that reason the
    listing extractor uses several generations of selectors plus a generic
    public-job-link fallback instead of depending on one CSS class.
    """

    name = "Naukri"
    BASE_URL = "https://www.naukri.com/"

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
        if not keywords or not keywords.strip():
            raise ValueError("keywords cannot be empty.")

        keyword = keywords.strip()
        location_value = (location or "").strip()

        # Prefer the public search URL. Naukri may redirect this URL to its
        # current SEO search route, which is exactly what a normal browser
        # search does and is more reliable than depending on the current
        # search-box implementation.
        search_url = (
            f"{self.BASE_URL}jobs-in-india"
            f"?k={quote(keyword)}"
        )
        if location_value:
            search_url += f"&l={quote(location_value)}"

        try:
            self.page.goto(
                search_url,
                wait_until="domcontentloaded",
            )
            self.wait_for_page()
            self._wait_for_results()
            return
        except Exception:
            # Fall back to the visible search controls if direct navigation
            # was interrupted by a browser/navigation issue.
            pass

        self._search_using_controls(keyword, location_value)
        self._wait_for_results()

    def _search_using_controls(
        self,
        keyword: str,
        location: str,
    ) -> None:
        keyword_selectors = [
            'input[placeholder*="skills"]',
            'input[placeholder*="Skills"]',
            'input[placeholder*="designations"]',
            'input[placeholder*="companies"]',
            'input[placeholder*="Search"]',
            'input[placeholder*="search"]',
            'input[name="keyword"]',
            'input[name="keywords"]',
            'input[type="search"]',
        ]

        for selector in keyword_selectors:
            try:
                locator = self.page.locator(selector).first
                if not locator.is_visible(timeout=1000):
                    continue

                locator.fill(keyword)
                if location:
                    self._fill_location(location)

                if not self._click_search_button():
                    locator.press("Enter")

                self.wait_for_page()
                return
            except Exception:
                continue

        # Last resort: direct URL again, without relying on page controls.
        search_url = (
            f"{self.BASE_URL}jobs-in-india"
            f"?k={quote(keyword)}"
        )
        if location:
            search_url += f"&l={quote(location)}"

        self.page.goto(
            search_url,
            wait_until="domcontentloaded",
        )
        self.wait_for_page()

    def _click_search_button(self) -> bool:
        selectors = [
            'button:has-text("Search")',
            'button[type="submit"]',
            'input[type="submit"]',
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

    def _fill_location(self, location: str) -> bool:
        selectors = [
            'input[placeholder*="Location"]',
            'input[placeholder*="location"]',
            'input[placeholder*="Enter location"]',
            'input[name="location"]',
            'input[name="locations"]',
        ]

        for selector in selectors:
            try:
                locator = self.page.locator(selector).first
                if locator.is_visible(timeout=1000):
                    locator.fill(location)
                    return True
            except Exception:
                continue
        return False

    def _wait_for_results(self) -> None:
        """Give Naukri's client-side result list time to render."""
        result_selectors = [
            'a[href*="/job-listings-"]',
            'a[href*="/job-listings/"]',
            "article.jobTuple",
            ".cust-job-tuple",
            ".jobTuple",
            "[data-job-id]",
        ]

        for selector in result_selectors:
            try:
                self.page.locator(selector).first.wait_for(
                    state="attached",
                    timeout=7000,
                )
                break
            except Exception:
                continue

        # Lazy-loaded result cards are common. A small number of normal
        # scrolls is enough to trigger them without attempting to defeat any
        # anti-bot mechanism.
        for _ in range(2):
            try:
                self.page.mouse.wheel(0, 900)
                self.page.wait_for_timeout(700)
            except Exception:
                break

        try:
            self.page.wait_for_timeout(800)
        except Exception:
            pass

    # ========================================================
    # ACCESS STATE
    # ========================================================

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
        matched = next(
            (term for term in verification_terms if term in text),
            None,
        )

        if matched:
            return {
                "blocked": True,
                "code": "verification_required",
                "message": (
                    "Naukri requires additional verification "
                    f"({matched})."
                ),
                "requires_human_action": True,
            }

        return {
            "blocked": False,
            "code": "ok",
            "message": "",
            "requires_human_action": False,
        }

    # ========================================================
    # LISTINGS
    # ========================================================

    def get_job_listings(self) -> list[dict]:
        """
        Extract visible public Naukri listings.

        Strategy order:
            1. Known Naukri result-card selectors.
            2. Current/legacy job-listing anchor selectors.
            3. Generic anchors whose href clearly identifies a Naukri job.

        The generic fallback is deliberately conservative: a URL must look
        like a Naukri job-listing URL before it is accepted.
        """
        listings: list[dict] = []
        seen: set[str] = set()

        # Known/current result-card selectors.
        card_selectors = [
            "article.jobTuple",
            "article.job-tuple",
            ".jobTuple.bgWhite.br4.mb-8",
            ".jobTuple",
            ".cust-job-tuple",
            "[data-job-id]",
            "div[data-job-id]",
            'article[class*="job"]',
            'div[class*="jobTuple"]',
            'div[class*="job-tuple"]',
        ]

        for selector in card_selectors:
            try:
                cards = self.page.locator(selector)
                count = cards.count()
                if count <= 0:
                    continue

                for index in range(count):
                    try:
                        card = cards.nth(index)
                        job = self._extract_card(card)
                        self._append_listing(listings, seen, job)
                    except Exception:
                        continue

                if listings:
                    return listings
            except Exception:
                continue

        # Generic public job links. This is the important fallback for the
        # current Naukri layout shown by the user.
        link_selectors = [
            'a[href*="/job-listings-"]',
            'a[href*="/job-listings/"]',
            'a[href*="naukri.com/job-listings-"]',
            'a[href*="naukri.com/job-listings/"]',
        ]

        for selector in link_selectors:
            try:
                links = self.page.locator(selector)
                count = links.count()
                for index in range(count):
                    try:
                        link = links.nth(index)
                        job = self._extract_from_job_link(link)
                        self._append_listing(listings, seen, job)
                    except Exception:
                        continue
                if listings:
                    return listings
            except Exception:
                continue

        return listings

    def _append_listing(
        self,
        listings: list[dict],
        seen: set[str],
        job: dict,
    ) -> None:
        title = str(job.get("title", "") or "").strip()
        url = str(job.get("url", "") or "").strip()
        if not title or not url:
            return

        key = self._canonical_url(url)
        if key in seen:
            return

        # Avoid accepting obvious navigation links.
        if not self._looks_like_job_url(url):
            return

        job = {
            "title": title,
            "company": str(job.get("company", "") or "").strip(),
            "location": str(job.get("location", "") or "").strip(),
            "url": url,
            "description": str(job.get("description", "") or "").strip(),
        }
        seen.add(key)
        listings.append(job)

    def _extract_card(self, card) -> dict:
        title = self._first_text_from(
            card,
            [
                "a.title",
                ".title",
                ".jobTitle",
                '[class*="jobTitle"]',
                'a[class*="title"]',
                "h2",
                "h3",
            ],
        )

        company = self._first_text_from(
            card,
            [
                "a.subTitle",
                ".comp-name",
                ".companyInfo",
                ".company-name",
                ".subTitle",
                '[class*="comp-name"]',
            ],
        )

        location = self._first_text_from(
            card,
            [
                ".loc",
                ".location",
                ".job-location",
                ".locationsContainer",
                '[class*="location"]',
            ],
        )

        description = self._first_text_from(
            card,
            [
                ".job-desc",
                ".job-description",
                ".jobDescription",
                '[class*="job-desc"]',
            ],
        )

        url = ""
        for selector in [
            "a.title",
            'a[href*="/job-listings-"]',
            'a[href*="/job-listings/"]',
            "a[href]",
        ]:
            try:
                link = card.locator(selector).first
                if link.count() == 0:
                    continue
                href = link.get_attribute("href") or ""
                if self._looks_like_job_url(href):
                    url = self._absolute_url(href)
                    break
            except Exception:
                continue

        # If class-specific selectors fail, use the card's visible text and
        # the first public job link. This keeps extraction resilient to class
        # renames.
        if not title or not url:
            try:
                link = card.locator('a[href*="/job-listings-"]').first
                if link.count() > 0:
                    href = link.get_attribute("href") or ""
                    if not url and self._looks_like_job_url(href):
                        url = self._absolute_url(href)
                    if not title:
                        title = self._link_text(link)
            except Exception:
                pass

        if not title:
            try:
                link = card.locator('a[href*="/job-listings/"]').first
                if link.count() > 0:
                    href = link.get_attribute("href") or ""
                    if not url and self._looks_like_job_url(href):
                        url = self._absolute_url(href)
                    title = self._link_text(link)
            except Exception:
                pass

        return {
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "description": description,
        }

    def _extract_from_job_link(self, link) -> dict:
        href = link.get_attribute("href") or ""
        url = self._absolute_url(href)
        title = self._link_text(link)

        # Walk up a few ancestors. We do not assume one particular Naukri
        # class because the current site changes card markup frequently.
        company = ""
        location = ""
        description = ""

        for level in range(1, 7):
            try:
                ancestor = link.locator(
                    f"xpath=ancestor::*[{level}]"
                ).first
                if ancestor.count() == 0:
                    continue

                text = self._safe_inner_text(ancestor)
                if len(text) < 20:
                    continue

                if not company:
                    company = self._first_text_from(
                        ancestor,
                        [
                            "a.subTitle",
                            ".comp-name",
                            ".companyInfo",
                            ".company-name",
                            ".subTitle",
                            '[class*="comp-name"]',
                        ],
                    )

                if not location:
                    location = self._first_text_from(
                        ancestor,
                        [
                            ".loc",
                            ".location",
                            ".job-location",
                            ".locationsContainer",
                            '[class*="location"]',
                        ],
                    )

                if not description:
                    description = self._first_text_from(
                        ancestor,
                        [
                            ".job-desc",
                            ".job-description",
                            ".jobDescription",
                            '[class*="job-desc"]',
                        ],
                    )

                # A card-like ancestor usually has enough content to serve
                # as a fallback description even if no description class is
                # available.
                if not description and len(text) > 100:
                    description = text

                # Stop once we have useful metadata.
                if company or location or description:
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

    def get_job_details(self, job_url: str) -> dict:
        if not job_url or not job_url.strip():
            raise ValueError("job_url cannot be empty.")

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
                '[class*="jd-header-title"]',
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
                '[class*="location"]',
            ]
        )
        description = self._first_text(
            [
                ".job-desc",
                ".dang-inner-html",
                ".job-description",
                '[class*="job-desc"]',
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
        for selector in selectors:
            try:
                locator = self.page.locator(selector).first
                if locator.is_visible(timeout=1000):
                    text = self._safe_inner_text(locator)
                    if text:
                        return text
            except Exception:
                continue
        return ""

    def _first_text_from(self, parent, selectors: list[str]) -> str:
        for selector in selectors:
            try:
                locator = parent.locator(selector).first
                if locator.count() == 0:
                    continue
                text = self._safe_inner_text(locator)
                if text:
                    return text
            except Exception:
                continue
        return ""

    @staticmethod
    def _safe_inner_text(locator) -> str:
        try:
            return " ".join(
                (locator.inner_text() or "").split()
            ).strip()
        except Exception:
            return ""

    @staticmethod
    def _link_text(link) -> str:
        try:
            text = " ".join(
                (link.inner_text() or "").split()
            ).strip()
        except Exception:
            text = ""

        if text:
            return text

        for attribute in ("aria-label", "title"):
            try:
                value = (link.get_attribute(attribute) or "").strip()
                if value:
                    return value
            except Exception:
                continue
        return ""

    @classmethod
    def _looks_like_job_url(cls, href: str) -> bool:
        if not href:
            return False
        value = href.strip().lower()
        return (
            "/job-listings-" in value
            or "/job-listings/" in value
        )

    def _absolute_url(self, href: str) -> str:
        if not href:
            return ""
        return urljoin(self.BASE_URL, href.strip())

    @staticmethod
    def _canonical_url(url: str) -> str:
        return url.rstrip("/").split("#", 1)[0].lower()

    def wait_for_page(self) -> None:
        try:
            self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=10000,
            )
        except PlaywrightTimeoutError:
            pass
