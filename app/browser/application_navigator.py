from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page


@dataclass(frozen=True)
class PageState:
    url: str
    title: str
    has_application_form: bool
    has_success_signal: bool
    has_apply_control: bool
    has_careers_signal: bool
    has_job_search: bool
    company_site: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ApplicationNavigator:
    """
    Adaptive browser navigation.

    The navigator repeatedly performs:

        OBSERVE
            ↓
        UNDERSTAND PAGE
            ↓
        CHOOSE ACTION
            ↓
        ACT
            ↓
        OBSERVE AGAIN

    It never bypasses:
        CAPTCHA
        OTP
        login
        identity verification
    """

    APPLY_RE = re.compile(
        r"\bapply"
        r"(?: now| here"
        r"| for (?:this )?(?:job|position))?"
        r"\b",
        re.I,
    )

    EXCLUDE_APPLY_RE = re.compile(
        r"\bapply\s+filters?\b",
        re.I,
    )

    CAREERS_RE = re.compile(
        r"\b(?:career|careers|jobs|"
        r"job openings|openings|vacancies|"
        r"join us|work with us|"
        r"opportunities)\b",
        re.I,
    )

    LOGIN_RE = re.compile(
        r"\b(?:sign in|log in|login|"
        r"verify your identity|two[- ]factor|"
        r"2fa|one[- ]time password|otp)\b",
        re.I,
    )

    CAPTCHA_RE = re.compile(
        r"\b(?:captcha|recaptcha|"
        r"verify you are human|"
        r"i'm not a robot)\b",
        re.I,
    )

    SUCCESS_RE = re.compile(
        r"(?:application "
        r"(?:submitted|received)|"
        r"thank you for applying|"
        r"successfully applied|"
        r"application complete|"
        r"we received your application)",
        re.I,
    )

    def __init__(
        self,
        page: Page,
        timeout: int = 7000,
        max_hops: int = 8,
    ):
        self.page = page
        self.timeout = timeout
        self.max_hops = max(
            1,
            int(max_hops),
        )

    # ============================================================
    # PAGE REASONING
    # ============================================================

    def analyze_page(
        self,
        job: Optional[
            dict[str, Any]
        ] = None,
    ) -> dict[str, Any]:

        state = self._observe(
            job
        )

        text = self._body_text()

        if self.CAPTCHA_RE.search(
            text
        ):
            action = "human_captcha"

        elif (
            self.LOGIN_RE.search(text)
            and not state.has_application_form
        ):
            action = "human_login"

        elif state.has_success_signal:
            action = "stop_submitted"

        elif state.has_application_form:
            action = "fill_application"

        elif state.has_apply_control:
            action = "click_apply"

        elif (
            state.company_site
            and state.has_careers_signal
        ):
            action = "find_careers_or_job"

        elif (
            state.company_site
            and state.has_job_search
        ):
            action = "search_company_jobs"

        else:
            action = "inspect_or_stop"

        return {
            "state": state.to_dict(),
            "next_action": action,
        }

    # ============================================================
    # ADAPTIVE LOOP
    # ============================================================

    def navigate(
        self,
        job: Optional[
            dict[str, Any]
        ] = None,
    ) -> dict[str, Any]:

        history: list[
            dict[str, Any]
        ] = []

        for hop in range(
            self.max_hops
        ):

            analysis = (
                self.analyze_page(
                    job
                )
            )

            analysis["hop"] = (
                hop + 1
            )

            history.append(
                analysis
            )

            action = (
                analysis[
                    "next_action"
                ]
            )

            if action == (
                "stop_submitted"
            ):
                return self._result(
                    "submitted",
                    history,
                )

            if action == (
                "human_captcha"
            ):
                return self._result(
                    "human_captcha_required",
                    history,
                )

            if action == (
                "human_login"
            ):
                return self._result(
                    "login_required",
                    history,
                )

            if action == (
                "fill_application"
            ):
                return self._result(
                    "form_detected",
                    history,
                )

            if action == (
                "click_apply"
            ):

                control = (
                    self.find_apply_control()
                )

                if (
                    control is not None
                    and self._click_and_wait(
                        control
                    )
                ):
                    continue

                return self._result(
                    "apply_control_failed",
                    history,
                )

            if action in {
                "find_careers_or_job",
                "search_company_jobs",
            }:

                if self._open_careers_link():
                    continue

                if self._search_company_jobs(
                    job
                ):
                    continue

                return self._result(
                    "application_route_not_found",
                    history,
                )

            return self._result(
                "application_route_not_found",
                history,
            )

        return self._result(
            "navigation_limit_reached",
            history,
        )

    # ============================================================
    # APPLY CONTROL
    # ============================================================

    def find_apply_control(self):

        candidates = self.page.locator(
            'a,button,input[type="submit"],'
            'input[type="button"]'
        )

        for index in range(
            candidates.count()
        ):

            element = (
                candidates.nth(index)
            )

            label = self._label(
                element
            )

            if not label:
                continue

            if self.EXCLUDE_APPLY_RE.search(
                label
            ):
                continue

            if self.APPLY_RE.search(
                label
            ):

                try:
                    if element.is_visible(
                        timeout=500
                    ):
                        return element
                except Exception:
                    pass

        return None

    # ============================================================
    # CLICK
    # ============================================================

    def _click_and_wait(
        self,
        element,
    ) -> bool:

        before = self.page.url

        try:

            element.scroll_into_view_if_needed(
                timeout=1000
            )

            element.click(
                timeout=self.timeout
            )

            try:
                self.page.wait_for_load_state(
                    "domcontentloaded",
                    timeout=self.timeout,
                )
            except Exception:
                pass

            try:
                self.page.wait_for_timeout(
                    700
                )
            except Exception:
                pass

            return (
                self.page.url != before
                or self._has_form()
                or self._success_visible()
            )

        except Exception:
            return False

    # ============================================================
    # COMPANY CAREERS
    # ============================================================

    def _open_careers_link(
        self,
    ) -> bool:

        current = self.page.url

        links = self.page.locator(
            "a[href]"
        )

        candidates = []

        for index in range(
            links.count()
        ):

            link = links.nth(
                index
            )

            label = self._label(
                link
            )

            href = (
                link.get_attribute(
                    "href"
                )
                or ""
            ).strip()

            if not href:
                continue

            combined = (
                f"{label} {href}"
            )

            if not self.CAREERS_RE.search(
                combined
            ):
                continue

            target = urljoin(
                current,
                href,
            )

            if not self._same_site(
                current,
                target,
            ):
                continue

            lower = combined.lower()

            score = 0

            if "career" in lower:
                score += 4

            if "jobs" in lower:
                score += 3

            candidates.append(
                (
                    score,
                    link,
                    target,
                )
            )

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        for (
            _,
            link,
            target,
        ) in candidates:

            try:

                link.click(
                    timeout=1500
                )

                self.page.wait_for_load_state(
                    "domcontentloaded",
                    timeout=self.timeout,
                )

                return True

            except Exception:

                try:

                    self.page.goto(
                        target,
                        wait_until=(
                            "domcontentloaded"
                        ),
                        timeout=self.timeout,
                    )

                    return True

                except Exception:
                    continue

        return False

    # ============================================================
    # COMPANY JOB SEARCH
    # ============================================================

    def _search_company_jobs(
        self,
        job: Optional[
            dict[str, Any]
        ],
    ) -> bool:

        title = str(
            (job or {}).get(
                "title",
                "",
            )
        ).strip()

        if not title:
            return False

        inputs = self.page.locator(
            'input:not([type="hidden"]),textarea'
        )

        for index in range(
            inputs.count()
        ):

            element = inputs.nth(
                index
            )

            label = self._label(
                element
            ).lower()

            if not any(
                token in label
                for token in (
                    "search",
                    "keyword",
                    "job title",
                    "position",
                    "what are you looking",
                )
            ):
                continue

            try:

                if not element.is_visible(
                    timeout=500
                ):
                    continue

                element.fill(
                    title
                )

                element.press(
                    "Enter"
                )

                try:
                    self.page.wait_for_load_state(
                        "domcontentloaded",
                        timeout=self.timeout,
                    )
                except Exception:
                    pass

                return (
                    self._click_relevant_job(
                        title
                    )
                    or True
                )

            except Exception:
                continue

        return self._click_relevant_job(
            title
        )

    # ============================================================
    # RELEVANT JOB
    # ============================================================

    def _click_relevant_job(
        self,
        title: str,
    ) -> bool:

        tokens = [
            token
            for token in re.findall(
                r"[A-Za-z0-9]+",
                title.lower(),
            )
            if len(token) >= 3
        ]

        if not tokens:
            return False

        links = self.page.locator(
            "a[href]"
        )

        best = None
        best_score = 0

        for index in range(
            links.count()
        ):

            link = links.nth(
                index
            )

            text = (
                f"{self._label(link)} "
                f"{link.get_attribute('href') or ''}"
            ).lower()

            score = sum(
                2
                for token in tokens
                if token in text
            )

            if self.CAREERS_RE.search(
                text
            ):
                score += 1

            if score > best_score:
                best = link
                best_score = score

        if (
            best is None
            or best_score < 2
        ):
            return False

        try:

            best.click(
                timeout=1500
            )

            self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=self.timeout,
            )

            return True

        except Exception:

            href = (
                best.get_attribute(
                    "href"
                )
                or ""
            ).strip()

            if href:

                try:

                    self.page.goto(
                        urljoin(
                            self.page.url,
                            href,
                        ),
                        wait_until=(
                            "domcontentloaded"
                        ),
                        timeout=self.timeout,
                    )

                    return True

                except Exception:
                    pass

        return False

    # ============================================================
    # FORM DETECTION
    # ============================================================

    def _has_form(self) -> bool:

        try:

            forms = self.page.locator(
                "form"
            )

            for index in range(
                forms.count()
            ):

                form = forms.nth(
                    index
                )

                if form.locator(
                    'input[type="file"]'
                ).count() > 0:
                    return True

                text = " ".join(
                    (
                        form.inner_text(
                            timeout=1000
                        )
                        or ""
                    ).split()
                ).lower()

                if re.search(
                    r"\b(application|apply|"
                    r"applicant|candidate|resume|"
                    r"cv|cover letter|upload cv|"
                    r"upload resume|full name|"
                    r"phone number)\b",
                    text,
                ):
                    return True

        except Exception:
            pass

        return False

    # ============================================================
    # PAGE SIGNALS
    # ============================================================

    def _success_visible(
        self,
    ) -> bool:
        return bool(
            self.SUCCESS_RE.search(
                self._body_text()
            )
        )

    def _has_careers_signal(
        self,
    ) -> bool:
        return bool(
            self.CAREERS_RE.search(
                self._body_text()
            )
        )

    def _has_job_search(
        self,
    ) -> bool:

        try:

            inputs = self.page.locator(
                'input:not([type="hidden"]),textarea'
            )

            for index in range(
                inputs.count()
            ):

                label = self._label(
                    inputs.nth(index)
                ).lower()

                if any(
                    token in label
                    for token in (
                        "search",
                        "keyword",
                        "job title",
                        "position",
                    )
                ):
                    return True

        except Exception:
            pass

        return False

    def _looks_like_company_site(
        self,
    ) -> bool:

        host = (
            urlparse(
                self.page.url
            ).netloc.lower()
        )

        if not host:
            return False

        blocked = (
            "naukri.com",
            "indeed.com",
            "linkedin.com",
            "glassdoor.com",
            "foundit.in",
        )

        return not any(
            domain in host
            for domain in blocked
        )

    # ============================================================
    # HELPERS
    # ============================================================

    def _observe(
        self,
        job: Optional[
            dict[str, Any]
        ],
    ) -> PageState:

        return PageState(
            url=self.page.url,
            title=self._page_title(),
            has_application_form=(
                self._has_form()
            ),
            has_success_signal=(
                self._success_visible()
            ),
            has_apply_control=(
                self.find_apply_control()
                is not None
            ),
            has_careers_signal=(
                self._has_careers_signal()
            ),
            has_job_search=(
                self._has_job_search()
            ),
            company_site=(
                self._looks_like_company_site()
            ),
        )

    def _body_text(
        self,
    ) -> str:

        try:
            return (
                self.page.locator(
                    "body"
                ).inner_text(
                    timeout=1000
                )
                or ""
            )
        except Exception:
            return ""

    def _page_title(
        self,
    ) -> str:

        try:
            return (
                self.page.title()
                or ""
            )
        except Exception:
            return ""

    @staticmethod
    def _same_site(
        first: str,
        second: str,
    ) -> bool:

        a = (
            urlparse(first)
            .netloc.lower()
            .split(":", 1)[0]
        )

        b = (
            urlparse(second)
            .netloc.lower()
            .split(":", 1)[0]
        )

        return bool(
            a
            and b
            and (
                a == b
                or a.endswith("." + b)
                or b.endswith("." + a)
            )
        )

    @staticmethod
    def _label(
        element: Any,
    ) -> str:

        for attr in (
            "aria-label",
            "title",
            "value",
            "name",
            "placeholder",
        ):

            try:

                value = (
                    element.get_attribute(
                        attr
                    )
                    or ""
                ).strip()

                if value:
                    return value

            except Exception:
                pass

        try:

            return " ".join(
                (
                    element.inner_text()
                    or ""
                ).split()
            ).strip()

        except Exception:
            return ""

    @staticmethod
    def _result(
        status: str,
        history: list[
            dict[str, Any]
        ],
    ) -> dict[str, Any]:

        return {
            "success": status
            in {
                "submitted",
                "form_detected",
            },
            "status": status,
            "history": history,
        }


__all__ = [
    "PageState",
    "ApplicationNavigator",
]