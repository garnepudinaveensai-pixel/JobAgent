from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Iterable, Optional
from urllib.parse import urlparse


EMAIL_PATTERN = re.compile(
    r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class DiscoveredContact:
    """
    Normalized professional contact discovered from a provider.

    The object deliberately contains only professional contact
    information relevant to recruitment outreach.
    """

    email: str
    name: str = ""
    role: str = ""
    company: str = ""
    source: str = ""
    confidence: float = 0.0
    verification_status: str = "unknown"
    domain: str = ""
    phone: str = ""
    source_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContactDiscoveryProvider:
    """
    Base interface for contact-discovery providers.

    Providers should return normalized dictionaries or
    DiscoveredContact instances.

    This abstraction allows providers such as Hunter to be
    added without coupling the rest of JobAgent to one vendor.
    """

    name = "unknown"

    def is_available(self) -> bool:
        return True

    def search(
        self,
        company: str,
        domain: Optional[str] = None,
        job: Optional[dict] = None,
        **options: Any,
    ) -> list[dict]:
        raise NotImplementedError


class StaticContactProvider(ContactDiscoveryProvider):
    """
    Deterministic provider useful for tests, local development,
    and manually configured contacts.
    """

    name = "static"

    def __init__(
        self,
        contacts: Optional[Iterable[dict]] = None,
    ):
        self.contacts = list(contacts or [])

    def search(
        self,
        company: str,
        domain: Optional[str] = None,
        job: Optional[dict] = None,
        **options: Any,
    ) -> list[dict]:
        return [
            dict(contact)
            for contact in self.contacts
            if isinstance(contact, dict)
        ]


class ContactDiscovery:
    """
    Coordinates contact discovery across providers.

    Flow:

        Job
         ↓
        Company/domain extraction
         ↓
        Provider discovery
         ↓
        Validation
         ↓
        Normalization
         ↓
        Deduplication
         ↓
        Ranked contact candidates

    This class does not send emails.
    """

    def __init__(
        self,
        providers: Optional[
            Iterable[ContactDiscoveryProvider]
        ] = None,
    ):
        self.providers = list(providers or [])

    # ========================================================
    # PROVIDER MANAGEMENT
    # ========================================================

    def add_provider(
        self,
        provider: ContactDiscoveryProvider,
    ) -> None:
        if provider is None:
            raise ValueError(
                "provider cannot be None."
            )

        if provider not in self.providers:
            self.providers.append(provider)

    def get_providers(
        self,
    ) -> list[ContactDiscoveryProvider]:
        return list(self.providers)

    # ========================================================
    # DISCOVERY
    # ========================================================

    def discover(
        self,
        company: str,
        domain: Optional[str] = None,
        job: Optional[dict] = None,
        **options: Any,
    ) -> list[dict]:
        """
        Discover professional contacts.

        Provider failures are isolated so one unavailable
        provider does not break the complete discovery flow.
        """

        company = self._clean(company)

        if not company:
            raise ValueError(
                "company cannot be empty."
            )

        resolved_domain = self.resolve_domain(
            domain=domain,
            job=job,
        )

        results: list[dict] = []

        for provider in self.providers:
            if provider is None:
                continue

            try:
                if not provider.is_available():
                    continue
            except Exception:
                continue

            try:
                contacts = provider.search(
                    company=company,
                    domain=resolved_domain,
                    job=job,
                    **options,
                )
            except Exception:
                continue

            if not contacts:
                continue

            for contact in contacts:
                normalized = self.normalize_contact(
                    contact,
                    default_company=company,
                    default_domain=resolved_domain,
                    default_source=getattr(
                        provider,
                        "name",
                        "unknown",
                    ),
                )

                if normalized is not None:
                    results.append(normalized)

        return self.deduplicate(
            results
        )

    # ========================================================
    # DOMAIN
    # ========================================================

    @classmethod
    def resolve_domain(
        cls,
        domain: Optional[str] = None,
        job: Optional[dict] = None,
    ) -> str:
        """
        Resolve a company domain from an explicit domain or
        common job fields.

        No external lookup is performed here.
        """

        if domain:
            value = cls.extract_domain(
                domain
            )

            if value:
                return value

        if isinstance(job, dict):
            for field in (
                "company_domain",
                "domain",
                "company_url",
                "website",
            ):
                value = job.get(field)

                if value:
                    extracted = cls.extract_domain(
                        str(value)
                    )

                    if extracted:
                        return extracted

            url = job.get("url")

            if url:
                extracted = cls.extract_domain(
                    str(url)
                )

                if extracted:
                    return extracted

        return ""

    @staticmethod
    def extract_domain(
        value: str,
    ) -> str:
        """
        Extract a normalized hostname from a URL/domain.
        """

        value = str(
            value or ""
        ).strip()

        if not value:
            return ""

        candidate = value

        if "://" not in candidate:
            candidate = (
                "https://"
                + candidate
            )

        try:
            parsed = urlparse(
                candidate
            )

            hostname = (
                parsed.hostname
                or ""
            ).lower()

        except Exception:
            return ""

        hostname = hostname.strip(
            "."
        )

        if hostname.startswith(
            "www."
        ):
            hostname = hostname[4:]

        return hostname

    # ========================================================
    # NORMALIZATION
    # ========================================================

    @classmethod
    def normalize_contact(
        cls,
        contact: Any,
        default_company: str = "",
        default_domain: str = "",
        default_source: str = "",
    ) -> Optional[dict]:
        """
        Normalize provider output into the common contact schema.
        """

        if isinstance(
            contact,
            DiscoveredContact,
        ):
            data = contact.to_dict()
        elif isinstance(
            contact,
            dict,
        ):
            data = dict(contact)
        else:
            return None

        email = cls._clean(
            data.get(
                "email",
                data.get(
                    "address",
                    "",
                ),
            )
        ).lower()

        if not cls.is_valid_email(
            email
        ):
            return None

        domain = cls.extract_domain(
            data.get(
                "domain",
                "",
            )
        )

        if not domain:
            domain = default_domain

        result = {
            "email": email,
            "name": cls._clean(
                data.get(
                    "name",
                    data.get(
                        "full_name",
                        "",
                    ),
                )
            ),
            "role": cls._clean(
                data.get(
                    "role",
                    data.get(
                        "position",
                        data.get(
                            "title",
                            "",
                        ),
                    ),
                )
            ),
            "company": cls._clean(
                data.get(
                    "company",
                    default_company,
                )
            ),
            "source": cls._clean(
                data.get(
                    "source",
                    default_source,
                )
            ),
            "confidence": cls._confidence(
                data.get(
                    "confidence",
                    0.0,
                )
            ),
            "verification_status": cls._clean(
                data.get(
                    "verification_status",
                    data.get(
                        "status",
                        "unknown",
                    ),
                )
            ).lower() or "unknown",
            "domain": domain,
            "phone": cls._clean(
                data.get(
                    "phone",
                    "",
                )
            ),
            "source_url": cls._clean(
                data.get(
                    "source_url",
                    data.get(
                        "url",
                        "",
                    ),
                )
            ),
        }

        return result

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def is_valid_email(
        email: str,
    ) -> bool:
        email = str(
            email or ""
        ).strip()

        if not email:
            return False

        return bool(
            EMAIL_PATTERN.match(
                email
            )
        )

    @staticmethod
    def _confidence(
        value: Any,
    ) -> float:
        try:
            score = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0.0

        # Support both 0-1 and 0-100 provider conventions.
        if score > 1:
            score /= 100.0

        return max(
            0.0,
            min(
                1.0,
                score,
            ),
        )

    # ========================================================
    # DEDUPLICATION
    # ========================================================

    @classmethod
    def deduplicate(
        cls,
        contacts: Iterable[dict],
    ) -> list[dict]:
        """
        Deduplicate contacts by normalized email.

        If multiple providers return the same address, retain
        the richest/highest-confidence representation.
        """

        by_email: dict[str, dict] = {}

        for contact in contacts:
            if not isinstance(
                contact,
                dict,
            ):
                continue

            email = cls._clean(
                contact.get(
                    "email",
                    "",
                )
            ).lower()

            if not cls.is_valid_email(
                email
            ):
                continue

            current = by_email.get(
                email
            )

            if current is None:
                by_email[email] = dict(
                    contact
                )
                continue

            current_score = cls.contact_quality(
                current
            )

            new_score = cls.contact_quality(
                contact
            )

            if new_score > current_score:
                by_email[email] = dict(
                    contact
                )
            else:
                # Merge missing fields from the newer record.
                merged = dict(
                    current
                )

                for key, value in contact.items():
                    if not merged.get(
                        key
                    ) and value:
                        merged[key] = value

                by_email[email] = merged

        return list(
            by_email.values()
        )

    # ========================================================
    # QUALITY
    # ========================================================

    @classmethod
    def contact_quality(
        cls,
        contact: dict,
    ) -> float:
        if not isinstance(
            contact,
            dict,
        ):
            return 0.0

        score = 0.0

        score += (
            cls._confidence(
                contact.get(
                    "confidence",
                    0.0,
                )
            )
            * 60.0
        )

        status = cls._clean(
            contact.get(
                "verification_status",
                "",
            )
        ).lower()

        if status in {
            "verified",
            "valid",
            "deliverable",
        }:
            score += 30.0

        elif status in {
            "risky",
            "unknown",
        }:
            score += 5.0

        if contact.get(
            "name"
        ):
            score += 3.0

        if contact.get(
            "role"
        ):
            score += 5.0

        if contact.get(
            "company"
        ):
            score += 2.0

        return score

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _clean(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        return str(
            value
        ).strip()


__all__ = [
    "DiscoveredContact",
    "ContactDiscoveryProvider",
    "StaticContactProvider",
    "ContactDiscovery",
]