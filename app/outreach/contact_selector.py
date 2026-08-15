from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class ContactSelection:
    """
    Ranked contact selection result.

    Attributes:
        email:
            Normalized email address.

        score:
            Relevance score. Higher is better.

        reason:
            Human-readable explanation of the score.

        contact:
            Original contact dictionary.
    """

    email: str
    score: int
    reason: str
    contact: dict


class ContactSelector:
    """
    Select and rank the most relevant outreach contacts.

    Priority:

        1. Recruiter
        2. Talent Acquisition
        3. Recruiting / Recruitment
        4. Hiring
        5. Human Resources / HR
        6. Careers / Jobs mailbox
        7. Generic company mailbox

    This class ONLY selects/ranks contacts.

    It never:
        - sends email
        - accesses Gmail
        - submits applications
        - modifies contact storage
    """

    # ========================================================
    # SCORING CONFIGURATION
    # ========================================================

    ROLE_KEYWORDS: dict[str, int] = {
        "recruiter": 100,
        "talent acquisition": 95,
        "talent acquisition specialist": 95,
        "talent": 90,
        "recruiting": 90,
        "recruitment": 90,
        "hiring": 85,
        "hiring manager": 85,
        "human resources": 80,
        "hr": 75,
    }

    EMAIL_KEYWORDS: dict[str, int] = {
        "recruiter": 90,
        "recruit": 90,
        "talent": 85,
        "hiring": 80,
        "hr": 75,
        "careers": 70,
        "career": 65,
        "jobs": 65,
        "recruitment": 90,
    }

    GENERIC_PREFIXES: set[str] = {
        "info",
        "contact",
        "support",
        "admin",
        "hello",
        "office",
        "sales",
        "enquiries",
        "enquiry",
        "help",
    }

    PROFESSIONAL_SOURCES: set[str] = {
        "linkedin",
        "professional",
        "professional_network",
    }

    OFFICIAL_SOURCES: set[str] = {
        "company",
        "company website",
        "official",
        "company_website",
    }

    def __init__(
        self,
        minimum_score: int = 50,
    ):
        """
        Create a contact selector.

        Args:
            minimum_score:
                Contacts below this score are excluded from
                rank_contacts().

                Use 0 when you specifically want to inspect
                all valid contacts, including generic mailboxes.
        """

        if not isinstance(
            minimum_score,
            int,
        ):
            raise TypeError(
                "minimum_score must be an integer."
            )

        if not 0 <= minimum_score <= 200:
            raise ValueError(
                "minimum_score must be between 0 and 200."
            )

        self.minimum_score = minimum_score

    # ========================================================
    # PUBLIC API
    # ========================================================

    def rank_contacts(
        self,
        contacts: Iterable[dict],
        job: Optional[dict] = None,
    ) -> list[ContactSelection]:
        """
        Rank valid contacts from most to least relevant.

        Invalid contacts are ignored.

        Contacts below minimum_score are excluded.
        """

        if contacts is None:
            return []

        results: list[ContactSelection] = []

        for contact in contacts:
            if not isinstance(
                contact,
                dict,
            ):
                continue

            email = self._normalize_email(
                contact.get("email")
            )

            if not self._valid_email(email):
                continue

            score, reason = self._score_contact(
                contact,
                email=email,
                job=job,
            )

            if score < self.minimum_score:
                continue

            results.append(
                ContactSelection(
                    email=email,
                    score=score,
                    reason=reason,
                    contact=contact,
                )
            )

        results.sort(
            key=lambda item: (
                -item.score,
                item.email,
            )
        )

        return results

    def select_best_contact(
        self,
        contacts: Iterable[dict],
        job: Optional[dict] = None,
    ) -> Optional[ContactSelection]:
        """
        Select the highest-ranked relevant contact.

        Returns:
            ContactSelection or None.
        """

        ranked = self.rank_contacts(
            contacts,
            job=job,
        )

        if not ranked:
            return None

        return ranked[0]

    # ========================================================
    # SCORING
    # ========================================================

    def _score_contact(
        self,
        contact: dict,
        email: str,
        job: Optional[dict] = None,
    ) -> tuple[int, str]:
        """
        Calculate a relevance score for one contact.
        """

        score = 0
        reasons: list[str] = []

        role = self._normalize_text(
            contact.get("role")
        )

        name = self._normalize_text(
            contact.get("name")
        )

        source = self._normalize_text(
            contact.get("source")
        )

        local_part = email.split(
            "@",
            1,
        )[0]

        domain = email.split(
            "@",
            1,
        )[1]

        # ----------------------------------------------------
        # Role
        # ----------------------------------------------------

        role_score = self._keyword_score(
            role,
            self.ROLE_KEYWORDS,
        )

        if role_score:
            score += role_score
            reasons.append(
                "recruiting/HR role"
            )

        # ----------------------------------------------------
        # Contact name / title
        # ----------------------------------------------------

        name_score = self._keyword_score(
            name,
            self.ROLE_KEYWORDS,
        )

        if name_score:
            score += min(
                name_score // 2,
                40,
            )

            reasons.append(
                "recruiting/HR title"
            )

        # ----------------------------------------------------
        # Email local part
        # ----------------------------------------------------

        email_score = self._keyword_score(
            local_part,
            self.EMAIL_KEYWORDS,
        )

        if email_score:
            score += email_score
            reasons.append(
                "recruiting-related email"
            )

        # ----------------------------------------------------
        # Source quality
        # ----------------------------------------------------

        if source in self.OFFICIAL_SOURCES:
            score += 15
            reasons.append(
                "official company source"
            )

        elif source in self.PROFESSIONAL_SOURCES:
            score += 10
            reasons.append(
                "professional source"
            )

        # ----------------------------------------------------
        # Generic mailbox penalty
        # ----------------------------------------------------

        if local_part in self.GENERIC_PREFIXES:
            score -= 35
            reasons.append(
                "generic mailbox"
            )

        # ----------------------------------------------------
        # Explicit company domain
        #
        # We prefer job["company_domain"] when available.
        # This is much safer than guessing a domain from
        # the company name.
        # ----------------------------------------------------

        company_domain = self._get_company_domain(
            job
        )

        if company_domain:
            if domain == company_domain:
                score += 10
                reasons.append(
                    "company-domain match"
                )

        # ----------------------------------------------------
        # Explicit contact relevance supplied by finder
        # ----------------------------------------------------

        if contact.get("verified") is True:
            score += 10
            reasons.append(
                "verified contact"
            )

        if contact.get("is_company_domain") is True:
            score += 10
            reasons.append(
                "company-domain contact"
            )

        # ----------------------------------------------------
        # Final bounds
        # ----------------------------------------------------

        score = max(
            0,
            min(score, 200),
        )

        reason = (
            ", ".join(reasons)
            if reasons
            else "general email relevance"
        )

        return score, reason

    # ========================================================
    # TEXT / EMAIL HELPERS
    # ========================================================

    @staticmethod
    def _normalize_text(
        value: object,
    ) -> str:
        """
        Safely normalize arbitrary values to lowercase text.
        """

        if value is None:
            return ""

        return str(value).strip().lower()

    @classmethod
    def _normalize_email(
        cls,
        value: object,
    ) -> str:
        """
        Normalize an email address.
        """

        return cls._normalize_text(
            value
        )

    @staticmethod
    def _valid_email(
        email: str,
    ) -> bool:
        """
        Perform basic email validation.

        This intentionally does not attempt full RFC validation.
        """

        if not email:
            return False

        if email.count("@") != 1:
            return False

        local, domain = email.split(
            "@",
            1,
        )

        if not local or not domain:
            return False

        if local.startswith("."):
            return False

        if local.endswith("."):
            return False

        if ".." in local:
            return False

        if "." not in domain:
            return False

        if domain.startswith("."):
            return False

        if domain.endswith("."):
            return False

        if ".." in domain:
            return False

        return True

    @staticmethod
    def _keyword_score(
        text: str,
        keywords: dict[str, int],
    ) -> int:
        """
        Return the highest matching keyword score.
        """

        if not text:
            return 0

        best_score = 0

        for keyword, value in keywords.items():
            if keyword in text:
                best_score = max(
                    best_score,
                    value,
                )

        return best_score

    @staticmethod
    def _get_company_domain(
        job: Optional[dict],
    ) -> str:
        """
        Extract an explicitly supplied company domain.

        Expected examples:

            company_domain = "example.com"
            company_domain = "@example.com"

        We intentionally do NOT guess a company's domain
        from its name.
        """

        if not isinstance(
            job,
            dict,
        ):
            return ""

        value = str(
            job.get(
                "company_domain",
                "",
            )
        ).strip().lower()

        if value.startswith("@"):
            value = value[1:]

        return value