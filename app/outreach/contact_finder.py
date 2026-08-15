from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv


# ============================================================
# CONTACT MODEL
# ============================================================


@dataclass
class Contact:
    """
    Represents a professional contact discovered for a company.
    """

    email: str
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    position: str = ""
    department: str = ""
    company: str = ""
    confidence: float = 0.0
    source: str = ""
    verification_status: str = "unknown"

    def to_dict(self) -> dict:
        """
        Convert the contact to a plain dictionary.
        """

        return asdict(self)


# ============================================================
# CONTACT FINDER
# ============================================================


class ContactFinder:
    """
    Finds relevant professional contacts for job opportunities.

    The finder is intentionally separated from email sending.

    Responsibilities:
        - determine company/domain
        - query contact providers
        - identify relevant HR/recruiting contacts
        - rank contacts
        - return structured contact data

    It does NOT:
        - send emails
        - attach resumes
        - submit applications
        - expose API credentials
    """

    HR_KEYWORDS = {
        "hr",
        "human resources",
        "recruiter",
        "recruiting",
        "talent acquisition",
        "talent",
        "recruitment",
        "people operations",
        "people ops",
        "hiring",
        "staffing",
        "campus recruitment",
        "campus recruiter",
        "technical recruiter",
        "talent partner",
        "hr business partner",
    }

    RELEVANT_DEPARTMENTS = {
        "human resources",
        "hr",
        "recruiting",
        "recruitment",
        "talent acquisition",
        "people",
    }

    def __init__(
        self,
        hunter_api_key: Optional[str] = None,
        timeout: int = 15,
    ):
        """
        Initialize ContactFinder.

        Hunter API key can be supplied directly or through:

            HUNTER_API_KEY

        from the environment / .env file.
        """

        load_dotenv()

        self.hunter_api_key = (
            hunter_api_key
            or os.getenv("HUNTER_API_KEY", "")
        ).strip()

        self.timeout = timeout

    # ========================================================
    # COMPANY / DOMAIN
    # ========================================================

    @staticmethod
    def extract_domain(
        value: str,
    ) -> str:
        """
        Extract a normalized domain from a company website,
        URL, email address, or domain string.

        Examples:

            https://www.example.com/jobs/123
                -> example.com

            recruiter@example.com
                -> example.com

            example.com
                -> example.com
        """

        if not value or not value.strip():
            return ""

        value = value.strip().lower()

        # Email address
        if "@" in value and "://" not in value:
            value = value.rsplit("@", 1)[1]

        # Add scheme temporarily so URL parsing is reliable.
        if not value.startswith(
            ("http://", "https://")
        ):
            value = "https://" + value

        from urllib.parse import urlparse

        parsed = urlparse(value)

        domain = parsed.netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        # Remove optional port.
        domain = domain.split(":", 1)[0]

        return domain.strip()

    # ========================================================
    # JOB DOMAIN
    # ========================================================

    def get_job_domain(
        self,
        job: dict[str, Any],
    ) -> str:
        """
        Determine the company domain from a stored job.

        Priority:

            1. company_domain
            2. company_website
            3. website
            4. company_url
            5. email
            6. job URL

        This does not guess domains from company names.
        """

        fields = (
            "company_domain",
            "company_website",
            "website",
            "company_url",
            "email",
            "url",
        )

        for field in fields:
            value = job.get(field)

            if not value:
                continue

            domain = self.extract_domain(
                str(value)
            )

            if domain:
                return domain

        return ""

    # ========================================================
    # HUNTER
    # ========================================================

    def search_hunter(
        self,
        domain: str,
    ) -> list[Contact]:
        """
        Search Hunter Domain Search for contacts.

        The API key must be configured through:

            HUNTER_API_KEY

        Returns:
            List of Contact objects.

        Raises:
            ValueError:
                If the domain or API key is missing.

            RuntimeError:
                If Hunter cannot be reached or returns
                an invalid response.
        """

        domain = self.extract_domain(domain)

        if not domain:
            raise ValueError(
                "A valid company domain is required."
            )

        if not self.hunter_api_key:
            raise ValueError(
                "HUNTER_API_KEY is not configured."
            )

        params = urlencode(
            {
                "domain": domain,
                "api_key": self.hunter_api_key,
            }
        )

        url = (
            "https://api.hunter.io/v2/domain-search?"
            f"{params}"
        )

        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "JobAgent/1.0",
            },
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                payload = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

        except HTTPError as exc:
            raise RuntimeError(
                f"Hunter API request failed "
                f"with HTTP {exc.code}."
            ) from exc

        except URLError as exc:
            raise RuntimeError(
                "Unable to connect to Hunter API."
            ) from exc

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Hunter returned invalid JSON."
            ) from exc

        return self._parse_hunter_response(
            payload
        )

    # ========================================================
    # HUNTER RESPONSE
    # ========================================================

    def _parse_hunter_response(
        self,
        payload: dict[str, Any],
    ) -> list[Contact]:
        """
        Convert Hunter's response into Contact objects.
        """

        data = payload.get("data", {})

        if not isinstance(data, dict):
            return []

        domain = str(
            data.get("domain", "")
        ).strip()

        company = str(
            data.get("organization", "")
        ).strip()

        raw_emails = data.get(
            "emails",
            [],
        )

        if not isinstance(
            raw_emails,
            list,
        ):
            return []

        contacts: list[Contact] = []

        for item in raw_emails:
            if not isinstance(item, dict):
                continue

            email = str(
                item.get("value", "")
            ).strip().lower()

            if not self._valid_email(email):
                continue

            first_name = str(
                item.get("first_name", "")
                or ""
            ).strip()

            last_name = str(
                item.get("last_name", "")
                or ""
            ).strip()

            full_name = str(
                item.get("full_name", "")
                or ""
            ).strip()

            position = str(
                item.get("position", "")
                or ""
            ).strip()

            department = str(
                item.get("department", "")
                or ""
            ).strip()

            confidence = item.get(
                "confidence",
                0,
            )

            try:
                confidence = float(
                    confidence
                )
            except (
                TypeError,
                ValueError,
            ):
                confidence = 0.0

            verification = item.get(
                "verification",
                {}
            )

            verification_status = (
                "unknown"
            )

            if isinstance(
                verification,
                dict,
            ):
                verification_status = str(
                    verification.get(
                        "status",
                        "unknown",
                    )
                )

            contact = Contact(
                email=email,
                first_name=first_name,
                last_name=last_name,
                full_name=full_name,
                position=position,
                department=department,
                company=company,
                confidence=confidence,
                source="hunter",
                verification_status=(
                    verification_status
                ),
            )

            contacts.append(contact)

        return contacts

    # ========================================================
    # FILTER
    # ========================================================

    def find_relevant_contacts(
        self,
        contacts: list[Contact],
        minimum_confidence: float = 0.0,
    ) -> list[Contact]:
        """
        Filter and rank contacts that are relevant to hiring.

        HR/recruiting contacts are prioritized.

        Contacts are never fabricated.
        """

        filtered: list[
            tuple[int, Contact]
        ] = []

        for contact in contacts:

            if not self._valid_email(
                contact.email
            ):
                continue

            if (
                contact.confidence
                < minimum_confidence
            ):
                continue

            score = self._relevance_score(
                contact
            )

            filtered.append(
                (
                    score,
                    contact,
                )
            )

        filtered.sort(
            key=lambda item: (
                item[0],
                item[1].confidence,
            ),
            reverse=True,
        )

        return [
            contact
            for _, contact
            in filtered
        ]

    # ========================================================
    # JOB CONTACT SEARCH
    # ========================================================

    def find_for_job(
        self,
        job: dict[str, Any],
        minimum_confidence: float = 0.0,
    ) -> list[Contact]:
        """
        Find relevant professional contacts for a job.

        The job must contain enough information to determine
        the company domain.
        """

        domain = self.get_job_domain(
            job
        )

        if not domain:
            return []

        contacts = self.search_hunter(
            domain
        )

        return self.find_relevant_contacts(
            contacts,
            minimum_confidence=minimum_confidence,
        )

    # ========================================================
    # RELEVANCE
    # ========================================================

    def _relevance_score(
        self,
        contact: Contact,
    ) -> int:
        """
        Calculate an internal relevance score.

        Higher score = more likely to be useful
        for professional job outreach.
        """

        text = " ".join(
            [
                contact.position,
                contact.department,
                contact.full_name,
            ]
        ).lower()

        score = 0

        # Strong HR/recruiting signals.
        for keyword in self.HR_KEYWORDS:
            if keyword in text:
                score += 30

        # Department signal.
        department = (
            contact.department
            .strip()
            .lower()
        )

        if department in self.RELEVANT_DEPARTMENTS:
            score += 40

        # Generic professional contact.
        if contact.full_name:
            score += 5

        if contact.position:
            score += 5

        # Verified contact.
        if contact.verification_status.lower() in {
            "valid",
            "accept_all",
        }:
            score += 10

        return score

    # ========================================================
    # EMAIL VALIDATION
    # ========================================================

    @staticmethod
    def _valid_email(
        email: str,
    ) -> bool:
        """
        Basic email format validation.

        This does not claim that an address exists.
        """

        if not email:
            return False

        pattern = (
            r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        )

        return bool(
            re.match(
                pattern,
                email,
            )
        )