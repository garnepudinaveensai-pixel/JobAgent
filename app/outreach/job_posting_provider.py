from __future__ import annotations

import re
from typing import Any, Optional

from app.outreach.contact_discovery import ContactDiscoveryProvider


_EMAIL_RE = re.compile(
    r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])",
    re.IGNORECASE,
)

_GENERIC_RECRUITING_MAILBOXES = {
    "hr",
    "hiring",
    "recruiting",
    "recruitment",
    "careers",
    "career",
    "jobs",
    "job",
    "talent",
    "people",
    "staffing",
    "resumes",
    "resume",
}


class JobPostingContactProvider(ContactDiscoveryProvider):
    """
    Discover professional recruitment contacts that are already
    publicly present in a job posting.

    This provider never guesses addresses and never scrapes private
    contact information. It only extracts email addresses from
    fields already supplied by the job source.

    Typical fields:
        description
        application_email
        recruiter_email
        contact_email
        email
        contact_emails
    """

    name = "job_posting"

    def search(
        self,
        company: str,
        domain: Optional[str] = None,
        job: Optional[dict] = None,
        **options: Any,
    ) -> list[dict]:
        if not isinstance(job, dict):
            return []

        candidates: list[tuple[str, str]] = []

        explicit_fields = (
            "application_email",
            "recruiter_email",
            "contact_email",
            "email",
        )

        for field in explicit_fields:
            value = job.get(field)
            if isinstance(value, str):
                candidates.append((value, f"job:{field}"))

        values = job.get("contact_emails")
        if isinstance(values, (list, tuple, set)):
            for value in values:
                if isinstance(value, str):
                    candidates.append((value, "job:contact_emails"))

        description = job.get("description", "")
        if isinstance(description, str):
            for email in _EMAIL_RE.findall(description):
                candidates.append((email, "job:description"))

        result: list[dict] = []
        seen: set[str] = set()

        for raw, source in candidates:
            for email in _EMAIL_RE.findall(raw):
                normalized = email.strip().lower()
                if normalized in seen:
                    continue

                local, _, email_domain = normalized.partition("@")
                if not local or not email_domain:
                    continue

                # Prefer recruitment-oriented published mailboxes.
                local_base = local.split("+", 1)[0]
                role = (
                    "recruiting"
                    if local_base in _GENERIC_RECRUITING_MAILBOXES
                    else "recruiter/contact"
                )

                seen.add(normalized)
                result.append(
                    {
                        "email": normalized,
                        "name": "",
                        "role": role,
                        "company": company,
                        "source": self.name,
                        "confidence": 0.95 if local_base in _GENERIC_RECRUITING_MAILBOXES else 0.80,
                        "verification_status": "published",
                        "domain": email_domain,
                        "source_url": str(
                            job.get("url", "")
                            or job.get("source_url", "")
                        ).strip(),
                    }
                )

        return result


__all__ = ["JobPostingContactProvider"]
