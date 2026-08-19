from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


class ApplicationNavigator:
    """Adaptive, bounded browser navigation for application routes."""

    APPLY_RE = re.compile(
        r"^(apply|apply now|apply here|apply on company site|"
        r"apply on employer site|apply on company website|"
        r"apply at company|apply externally|apply for this position|"
        r"apply for this job)$",
        re.I,
    )
    CAREERS_RE = re.compile(
        r"(career|careers|jobs|job openings|openings|vacancies|join us|work with us)",
        re.I,
    )
    SUCCESS_RE = re.compile(
        r"(application (?:submitted|received)|thank you for applying|"
        r"successfully applied|application complete|we received your application)",
        re.I,
    )

    def __init__(self, page: Page, timeout: int = 7000, max_hops: int = 4):
        self.page = page
        self.timeout = timeout
        self.max_hops = max(1, int(max_hops))

    def navigate(self, job: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        history: list[str] = []
        for _ in range(self.max_hops):
            history.append(str(self.page.url))
            if self._has_form():
                return self._result("form_detected", history)
            if self._success_visible():
                return self._result("submitted", history)

            apply_control = self.find_apply_control()
            if apply_control is not None:
                label = self._label(apply_control).lower()
                if self._is_external_apply_label(label):
                    before = self.page.url
                    if self._click_and_wait(apply_control):
                        if self._has_form() or self._success_visible():
                            return self._result("form_detected" if self._has_form() else "submitted", history)
                        if self.page.url != before:
                            continue
                else:
                    return self._result("ready_to_apply", history)

            if self._looks_like_company_site() or self._has_company_site_signal():
                if self._open_careers_link():
                    continue
                if self._search_company_jobs(job):
                    continue

            return self._result("application_route_not_found", history)

        return self._result("navigation_limit_reached", history)

    def find_apply_control(self):
        candidates = self.page.locator(
            'a,button,input[type="submit"],input[type="button"]'
        )
        for index in range(candidates.count()):
            element = candidates.nth(index)
            label = self._label(element)
            if label and self.APPLY_RE.match(label):
                try:
                    if element.is_visible(timeout=500):
                        return element
                except Exception:
                    continue
        return None

    @staticmethod
    def _is_external_apply_label(label: str) -> bool:
        return any(token in label for token in (
            "company site", "employer site", "company website", "extern"
        ))

    def _click_and_wait(self, element) -> bool:
        try:
            old_url = self.page.url
            element.scroll_into_view_if_needed(timeout=1000)
            element.click(timeout=self.timeout)
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=self.timeout)
            except Exception:
                pass
            try:
                self.page.wait_for_timeout(800)
            except Exception:
                pass
            return self.page.url != old_url or self._has_form() or self._success_visible()
        except Exception:
            return False

    def _open_careers_link(self) -> bool:
        links = self.page.locator('a[href]')
        current = self.page.url
        for index in range(links.count()):
            link = links.nth(index)
            label = self._label(link)
            href = (link.get_attribute("href") or "").strip()
            if not href or not self.CAREERS_RE.search(f"{label} {href}"):
                continue
            target = urljoin(current, href)
            if not self._same_site(current, target):
                continue
            try:
                link.click(timeout=1500)
                self.page.wait_for_load_state("domcontentloaded", timeout=self.timeout)
                return True
            except Exception:
                try:
                    self.page.goto(target, wait_until="domcontentloaded", timeout=self.timeout)
                    return True
                except Exception:
                    continue
        return False

    def _search_company_jobs(self, job: Optional[dict[str, Any]]) -> bool:
        if not isinstance(job, dict):
            return False
        title = str(job.get("title", "")).strip()
        if not title:
            return False

        inputs = self.page.locator('input:not([type="hidden"]),textarea')
        for index in range(inputs.count()):
            element = inputs.nth(index)
            label = self._label(element).lower()
            if not any(token in label for token in ("search", "keyword", "job title", "position")):
                continue
            try:
                if not element.is_visible(timeout=500):
                    continue
                element.fill(title)
                element.press("Enter")
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=self.timeout)
                except Exception:
                    pass
                return self._click_relevant_job(title)
            except Exception:
                continue
        return self._click_relevant_job(title)

    def _click_relevant_job(self, title: str) -> bool:
        tokens = [x for x in re.findall(r"[A-Za-z0-9]+", title.lower()) if len(x) >= 3]
        links = self.page.locator('a[href]')
        best = None
        best_score = 0
        for index in range(links.count()):
            link = links.nth(index)
            label = self._label(link)
            href = (link.get_attribute("href") or "").strip()
            text = f"{label} {href}".lower()
            if not self.CAREERS_RE.search(text) and not any(t in text for t in tokens):
                continue
            score = sum(1 for token in tokens if token in text)
            if score > best_score:
                best = link
                best_score = score
        if best is None or best_score == 0:
            return False
        try:
            best.click(timeout=1500)
            self.page.wait_for_load_state("domcontentloaded", timeout=self.timeout)
            return True
        except Exception:
            href = (best.get_attribute("href") or "").strip()
            if href:
                try:
                    self.page.goto(urljoin(self.page.url, href), wait_until="domcontentloaded", timeout=self.timeout)
                    return True
                except Exception:
                    pass
        return False

    def _has_form(self) -> bool:
        """Return True only for a form that looks application-related.

        Company homepages often contain newsletter/contact forms. Treating
        every <form> as an application form can stop navigation prematurely.
        A file upload or application-specific wording is a much stronger
        signal.
        """
        try:
            forms = self.page.locator("form")
            count = forms.count()
        except Exception:
            return False

        for index in range(count):
            form = forms.nth(index)
            try:
                if form.locator('input[type="file"]').count() > 0:
                    return True

                text = " ".join(
                    (form.inner_text(timeout=1000) or "").split()
                ).lower()

                if re.search(
                    r"\b(application|apply|applicant|candidate|resume|"
                    r"cv|cover letter|upload cv|upload resume|"
                    r"full name|phone number)\b",
                    text,
                    re.I,
                ):
                    return True
            except Exception:
                continue

        return False

    def _success_visible(self) -> bool:
        try:
            text = self.page.locator("body").inner_text(timeout=1000)
        except Exception:
            return False
        return bool(self.SUCCESS_RE.search(text or ""))

    def _looks_like_company_site(self) -> bool:
        host = urlparse(self.page.url).netloc.lower()
        return bool(host and not any(x in host for x in ("naukri.com", "indeed.com", "linkedin.com")))

    def _has_company_site_signal(self) -> bool:
        try:
            text = self.page.locator("body").inner_text(timeout=1000).lower()
        except Exception:
            text = ""
        return bool(self.CAREERS_RE.search(text))

    @staticmethod
    def _same_site(first: str, second: str) -> bool:
        a = urlparse(first).netloc.lower().split(":", 1)[0]
        b = urlparse(second).netloc.lower().split(":", 1)[0]
        if not a or not b:
            return False
        return a == b or a.endswith("." + b) or b.endswith("." + a)

    @staticmethod
    def _label(element: Any) -> str:
        for attr in ("aria-label", "title", "value", "name", "placeholder"):
            try:
                value = (element.get_attribute(attr) or "").strip()
                if value:
                    return value
            except Exception:
                pass
        try:
            return " ".join((element.inner_text() or "").split()).strip()
        except Exception:
            return ""

    @staticmethod
    def _result(status: str, history: list[str]) -> dict[str, Any]:
        return {
            "success": status in {"form_detected", "submitted", "ready_to_apply"},
            "status": status,
            "url": str(history[-1]) if history else str(self.page.url),
            "navigation_history": list(history),
            "requires_human_action": status == "navigation_limit_reached",
        }
