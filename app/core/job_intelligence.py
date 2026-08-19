from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional
from urllib.parse import urlparse


class JobIntelligence:
    """
    Deterministic job-triage layer used before application execution.

    It answers four questions without inventing facts:
      1. Is this actually a technical/software role?
      2. Is it a mixed/non-target role such as sales or plumbing?
      3. Is it recent/urgent enough to prioritize?
      4. What application route should the browser investigate?

    The output is deliberately explainable so the CLI can show why a job
    was selected or rejected.
    """

    EXCLUDED_TITLE_TERMS = (
        "sales",
        "business development",
        "bd executive",
        "account executive",
        "customer success",
        "customer support",
        "inside sales",
        "field sales",
        "marketing",
        "recruiter",
        "recruitment",
        "human resources",
        "hr executive",
        "talent acquisition",
        "finance",
        "accountant",
        "accounts executive",
        "procurement",
        "purchase executive",
        "administration",
        "admin executive",
        "plumbing",
        "civil engineer",
        "mechanical engineer",
    )

    TARGET_TITLE_TERMS = (
        "electrical engineer",
        "electrical engineering",
        "electrical",
        "power engineer",
        "power systems",
        "power electronics",
        "electrical maintenance",
        "maintenance engineer",
        "reliability engineer",
        "condition based maintenance",
        "cbm",
        "automation engineer",
        "industrial automation",
        "controls engineer",
        "control engineer",
        "instrumentation engineer",
        "embedded engineer",
        "embedded systems",
        "firmware engineer",
        "software engineer",
        "software developer",
        "developer",
        "backend engineer",
        "frontend engineer",
        "full stack",
        "data engineer",
        "machine learning engineer",
        "ai engineer",
        "artificial intelligence",
        "python developer",
        "test engineer",
        "qa engineer",
        "devops engineer",
        "telecom engineer",
        "testing and commissioning",
        "commissioning engineer",
        "graduate engineer trainee",
        "engineering trainee",
    )

    URGENCY_TERMS = (
        "urgent hiring",
        "urgent requirement",
        "urgently hiring",
        "immediate hiring",
        "immediate joiner",
        "immediate joining",
        "join immediately",
        "walk-in",
        "walk in",
        "actively hiring",
        "hiring now",
        "join asap",
        "asap",
    )

    FRESHNESS_PATTERNS = (
        (re.compile(r"\btoday\b|\bjust posted\b|\bjust now\b", re.I), 100),
        (re.compile(r"\b1\s*day\s*ago\b|\byesterday\b", re.I), 90),
        (re.compile(r"\b[2-3]\s*days?\s*ago\b", re.I), 80),
        (re.compile(r"\b[4-7]\s*days?\s*ago\b", re.I), 65),
        (re.compile(r"\b[1-2]\s*weeks?\s*ago\b", re.I), 45),
        (re.compile(r"\b[3-4]\s*weeks?\s*ago\b", re.I), 25),
        (re.compile(r"\b\d+\s*months?\s*ago\b", re.I), 5),
    )

    @classmethod
    def analyze(cls, job: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(job, Mapping):
            raise TypeError("job must be a mapping.")

        title = cls._text(job.get("title") or job.get("job_title"))
        description = cls._text(job.get("description"))
        company = cls._text(job.get("company"))
        url = cls._text(job.get("url"))
        combined = f"{title} {description}".lower()
        title_lower = title.lower()

        excluded = [term for term in cls.EXCLUDED_TITLE_TERMS if term in title_lower]
        targets = [term for term in cls.TARGET_TITLE_TERMS if term in title_lower]

        technical = bool(targets) and not bool(excluded)
        if not targets:
            # A clearly technical description can still qualify when the
            # title is generic, e.g. "Engineer - Embedded Systems".
            technical_terms = (
                "plc", "scada", "embedded", "python", "matlab", "simulink",
                "electrical system", "power electronics", "microcontroller",
                "firmware", "software development", "sql", "automation",
            )
            technical = any(term in combined for term in technical_terms) and not excluded

        if excluded:
            role_class = "non_target"
        elif technical:
            role_class = cls._role_class(title_lower)
        else:
            role_class = "uncertain"

        freshness = cls._freshness_score(combined, job)
        urgency = cls._urgency_score(combined)
        target_score = 70 if technical else (20 if role_class == "uncertain" else 0)
        priority = min(100, target_score + round(freshness * 0.2) + round(urgency * 0.1))

        route = cls._application_route(url, job)

        reasons = []
        reasons.append("technical/software target" if technical else "non-target role" if excluded else "role fit uncertain")
        if freshness >= 80:
            reasons.append("very recent")
        elif freshness >= 45:
            reasons.append("recent")
        if urgency >= 80:
            reasons.append("urgent/active hiring signal")
        reasons.append(f"route={route}")

        return {
            "technical_target": technical,
            "role_class": role_class,
            "excluded_terms": excluded,
            "matched_target_terms": targets,
            "freshness_score": freshness,
            "urgency_score": urgency,
            "priority_score": priority,
            "application_route": route,
            "priority_reason": "; ".join(reasons),
            "company": company,
        }

    @classmethod
    def _role_class(cls, title: str) -> str:
        if any(x in title for x in ("software", "developer", "devops", "backend", "frontend", "full stack")):
            return "software"
        if any(x in title for x in ("embedded", "firmware", "microcontroller")):
            return "embedded"
        if any(x in title for x in ("automation", "controls", "plc", "scada", "instrumentation")):
            return "automation"
        if any(x in title for x in ("power", "electrical", "maintenance", "reliability", "commissioning")):
            return "electrical_core"
        if any(x in title for x in ("data", "machine learning", "ai")):
            return "data_ai"
        if "telecom" in title:
            return "telecom"
        return "technical"

    @classmethod
    def _freshness_score(cls, text: str, job: Mapping[str, Any]) -> int:
        explicit = cls._text(job.get("posted_date") or job.get("date_posted"))
        source_text = f"{explicit} {text}".strip()
        for pattern, score in cls.FRESHNESS_PATTERNS:
            if pattern.search(source_text):
                return score
        # ISO dates are treated conservatively.
        for key in ("posted_at", "published_at", "date_posted"):
            value = cls._text(job.get(key))
            if not value:
                continue
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                age = datetime.now(timezone.utc) - parsed
                if age <= timedelta(days=1):
                    return 90
                if age <= timedelta(days=3):
                    return 80
                if age <= timedelta(days=7):
                    return 65
                if age <= timedelta(days=14):
                    return 45
                if age <= timedelta(days=30):
                    return 25
                return 5
            except ValueError:
                continue
        return 40

    @classmethod
    def _urgency_score(cls, text: str) -> int:
        hits = sum(1 for term in cls.URGENCY_TERMS if term in text)
        return min(100, hits * 40)

    @classmethod
    def _application_route(cls, url: str, job: Mapping[str, Any]) -> str:
        explicit = cls._text(job.get("application_url") or job.get("apply_url"))
        if explicit:
            return "application_url"
        source = cls._text(job.get("source")).lower()
        if source == "naukri":
            return "job_board_or_company_site"
        if source == "indeed":
            return "job_board_or_external_site"
        if source in {"greenhouse", "lever", "workday"}:
            return "employer_ats"
        host = urlparse(url).netloc.lower()
        if host:
            return "job_page"
        return "unknown"

    @staticmethod
    def _text(value: Any) -> str:
        return " ".join(str(value or "").split()).strip()
