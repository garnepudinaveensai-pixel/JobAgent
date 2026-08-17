from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from app.outreach.contact_selector import (
    ContactSelection,
    ContactSelector,
)
from app.outreach.contact_discovery import (
    ContactDiscovery,
)


@dataclass(frozen=True)
class OutreachMessage:
    """
    Prepared outreach email.

    This object represents an email that is READY for review.
    It does not send anything.
    """

    recipient: str
    subject: str
    body: str
    resume_path: str
    contact_score: int
    contact_reason: str
    contact: dict
    job: dict


class OutreachManager:
    """
    Prepare personalized job outreach emails.

    Responsibilities:
        - Discover professional contacts when configured.
        - Select the best HR/recruiting contact.
        - Generate a job-specific subject.
        - Generate a personalized email body.
        - Attach/reference the appropriate resume path.
        - Return a structured message for later review/sending.

    This class NEVER sends email.

    Workflow:

        Job
         ↓
        Contact Discovery
         ↓
        Contact Selection
         ↓
        Subject Generation
         ↓
        Personalized Body
         ↓
        OutreachMessage
         ↓
        Review / Sending handled elsewhere
    """

    DEFAULT_RESUME_PATH = (
        "data/resumes/master_resume.pdf"
    )

    def __init__(
        self,
        contact_selector: Optional[
            ContactSelector
        ] = None,
        default_resume_path: str = DEFAULT_RESUME_PATH,
        contact_discovery: Optional[
            ContactDiscovery
        ] = None,
    ):
        """
        Initialize OutreachManager.

        Args:
            contact_selector:
                Optional contact-ranking component.

            default_resume_path:
                Resume used when no explicit resume path
                is supplied.

            contact_discovery:
                Optional contact-discovery component.

        The discovery component is injected so the manager
        remains easy to test and does not depend on a
        particular provider.
        """

        self.contact_selector = (
            contact_selector
            if contact_selector is not None
            else ContactSelector()
        )

        self.default_resume_path = (
            str(default_resume_path).strip()
        )

        self.contact_discovery = (
            contact_discovery
            if contact_discovery is not None
            else ContactDiscovery()
        )

    # ========================================================
    # CONTACT DISCOVERY
    # ========================================================

    def discover_contacts(
        self,
        company: str,
        domain: Optional[str] = None,
        job: Optional[dict] = None,
        **options: Any,
    ) -> list[dict]:
        """
        Discover professional contacts for a company.

        This method only discovers and normalizes contacts.
        It does not select a contact and does not send email.

        Args:
            company:
                Company name.

            domain:
                Optional company domain.

            job:
                Optional job dictionary.

            **options:
                Provider-specific discovery options.

        Returns:
            A list of normalized contact dictionaries.
        """

        if not isinstance(
            company,
            str,
        ):
            raise TypeError(
                "company must be a string."
            )

        company = company.strip()

        if not company:
            raise ValueError(
                "company cannot be empty."
            )

        return self.contact_discovery.discover(
            company=company,
            domain=domain,
            job=job,
            **options,
        )

    def discover_contacts_for_job(
        self,
        job: dict,
        domain: Optional[str] = None,
        **options: Any,
    ) -> list[dict]:
        """
        Discover professional contacts for a job.

        The company is extracted from:

            job["company"]

        The domain may come from:

            explicit domain
            ↓
            job["company_domain"]
            ↓
            job["domain"]
            ↓
            job["company_url"]
            ↓
            job["website"]
            ↓
            job["url"]

        Returns:
            List of normalized contact dictionaries.
        """

        if not isinstance(
            job,
            dict,
        ):
            raise TypeError(
                "job must be a dictionary."
            )

        company = str(
            job.get(
                "company",
                "",
            )
            or ""
        ).strip()

        if not company:
            raise ValueError(
                "job company cannot be empty."
            )

        return self.contact_discovery.discover(
            company=company,
            domain=domain,
            job=job,
            **options,
        )

    # ========================================================
    # CONTACT SELECTION
    # ========================================================

    def select_contact(
        self,
        contacts: Iterable[dict],
        job: Optional[dict] = None,
    ) -> Optional[ContactSelection]:
        """
        Select the best available outreach contact.

        ContactSelector is responsible for ranking contacts.
        """

        return self.contact_selector.select_best_contact(
            contacts,
            job=job,
        )

    # ========================================================
    # DISCOVER + SELECT
    # ========================================================

    def discover_and_select_contact(
        self,
        job: dict,
        domain: Optional[str] = None,
        **options: Any,
    ) -> Optional[ContactSelection]:
        """
        Discover contacts for a job and immediately select
        the best suitable contact.

        No email is generated or sent.
        """

        if not isinstance(
            job,
            dict,
        ):
            raise TypeError(
                "job must be a dictionary."
            )

        contacts = (
            self.discover_contacts_for_job(
                job=job,
                domain=domain,
                **options,
            )
        )

        return self.select_contact(
            contacts,
            job=job,
        )

    # ========================================================
    # OUTREACH PREPARATION
    # ========================================================

    def prepare_outreach(
        self,
        job: dict,
        contacts: Iterable[dict],
        resume_path: Optional[str] = None,
    ) -> Optional[OutreachMessage]:
        """
        Prepare an outreach email for a job.

        Returns:
            OutreachMessage when a suitable contact exists.
            None when no suitable contact can be selected.

        No email is sent.
        """

        if not isinstance(
            job,
            dict,
        ):
            raise TypeError(
                "job must be a dictionary."
            )

        selected = self.select_contact(
            contacts,
            job=job,
        )

        if selected is None:
            return None

        final_resume_path = (
            str(
                resume_path
            ).strip()
            if resume_path is not None
            else self.default_resume_path
        )

        if not final_resume_path:
            raise ValueError(
                "resume_path cannot be empty."
            )

        subject = self.build_subject(
            job
        )

        body = self.build_body(
            job=job,
            contact=selected.contact,
        )

        return OutreachMessage(
            recipient=selected.email,
            subject=subject,
            body=body,
            resume_path=final_resume_path,
            contact_score=selected.score,
            contact_reason=selected.reason,
            contact=selected.contact,
            job=job,
        )

    def prepare_outreach_for_job(
        self,
        job: dict,
        resume_path: Optional[str] = None,
        domain: Optional[str] = None,
        **options: Any,
    ) -> Optional[OutreachMessage]:
        """
        Complete discovery → selection → outreach preparation
        flow for a single job.

        This is the main high-level method.

        Workflow:

            job
             ↓
            discover contacts
             ↓
            select best contact
             ↓
            generate subject
             ↓
            generate body
             ↓
            return OutreachMessage

        No email is sent.
        """

        if not isinstance(
            job,
            dict,
        ):
            raise TypeError(
                "job must be a dictionary."
            )

        contacts = (
            self.discover_contacts_for_job(
                job=job,
                domain=domain,
                **options,
            )
        )

        return self.prepare_outreach(
            job=job,
            contacts=contacts,
            resume_path=resume_path,
        )

    # ========================================================
    # SUBJECT
    # ========================================================

    @staticmethod
    def build_subject(
        job: dict,
    ) -> str:
        """
        Build a professional job-outreach subject.
        """

        title = str(
            job.get(
                "title",
                "",
            )
        ).strip()

        company = str(
            job.get(
                "company",
                "",
            )
        ).strip()

        if title and company:
            return (
                f"Application for {title} "
                f"at {company}"
            )

        if title:
            return (
                f"Application for {title}"
            )

        if company:
            return (
                f"Job Application – {company}"
            )

        return (
            "Job Application – Electrical Engineer"
        )

    # ========================================================
    # BODY
    # ========================================================

    @staticmethod
    def build_body(
        job: dict,
        contact: Optional[dict] = None,
    ) -> str:
        """
        Build a concise professional outreach message.

        The message uses only information available from
        the supplied job/contact dictionaries.
        """

        title = str(
            job.get(
                "title",
                "",
            )
        ).strip()

        company = str(
            job.get(
                "company",
                "",
            )
        ).strip()

        location = str(
            job.get(
                "location",
                "",
            )
        ).strip()

        name = ""

        if isinstance(
            contact,
            dict,
        ):
            name = str(
                contact.get(
                    "name",
                    "",
                )
            ).strip()

        greeting = (
            f"Dear {name},"
            if name
            else "Dear Hiring Team,"
        )

        job_reference = title

        if company:
            if title:
                job_reference = (
                    f"{title} position at "
                    f"{company}"
                )
            else:
                job_reference = (
                    f"opportunities at "
                    f"{company}"
                )

        # If both title and company are absent,
        # avoid producing "the ."
        if not job_reference:
            job_reference = (
                "the available opportunity"
            )

        location_sentence = ""

        if location:
            location_sentence = (
                " I am particularly interested in "
                f"opportunities in {location}."
            )

        return (
            f"{greeting}\n\n"
            f"I am writing to express my interest in "
            f"the {job_reference}. "
            f"I am a B.Tech Electrical & Electronics "
            f"Engineering graduate with hands-on exposure "
            f"to industrial electrical equipment monitoring, "
            f"condition-based maintenance, automation, "
            f"embedded systems, power electronics, and "
            f"engineering projects."
            f"{location_sentence}\n\n"
            f"My experience includes industrial equipment "
            f"monitoring, predictive maintenance activities, "
            f"TI C2000 embedded development, MATLAB/Simulink, "
            f"and practical exposure to electrical and "
            f"mechanical equipment in an industrial environment."
            f"\n\n"
            f"I have attached my resume for your consideration. "
            f"I would appreciate the opportunity to discuss "
            f"how my background could contribute to your team."
            f"\n\n"
            f"Thank you for your time and consideration."
            f"\n\n"
            f"Best regards,\n"
            f"Naveen Sai"
        )

    # ========================================================
    # RESUME
    # ========================================================

    @staticmethod
    def validate_resume_path(
        resume_path: str,
    ) -> bool:
        """
        Check whether a resume path is valid and points
        to an existing file.

        This method does not create or modify the file.
        """

        if not resume_path:
            return False

        path = Path(
            resume_path
        )

        return (
            path.exists()
            and path.is_file()
        )

    def resolve_resume_path(
        self,
        resume_path: Optional[str] = None,
    ) -> str:
        """
        Resolve the resume path that should be used.

        If no explicit path is provided, the configured
        default resume path is returned.

        This method does not require the file to exist.
        """

        final_path = (
            str(
                resume_path
            ).strip()
            if resume_path is not None
            else self.default_resume_path
        )

        if not final_path:
            raise ValueError(
                "resume_path cannot be empty."
            )

        return final_path

    # ========================================================
    # SERIALIZATION
    # ========================================================

    @staticmethod
    def to_dict(
        outreach: OutreachMessage,
    ) -> dict:
        """
        Convert an OutreachMessage into a plain dictionary.

        Useful for persistence, CLI output, logging,
        previews, and future sending workflows.
        """

        if not isinstance(
            outreach,
            OutreachMessage,
        ):
            raise TypeError(
                "outreach must be an OutreachMessage."
            )

        return {
            "recipient": outreach.recipient,
            "subject": outreach.subject,
            "body": outreach.body,
            "resume_path": outreach.resume_path,
            "contact_score": outreach.contact_score,
            "contact_reason": outreach.contact_reason,
            "contact": dict(
                outreach.contact
            ),
            "job": dict(
                outreach.job
            ),
        }

    # ========================================================
    # PREVIEW
    # ========================================================

    @staticmethod
    def preview(
        outreach: OutreachMessage,
    ) -> str:
        """
        Generate a human-readable preview of a prepared
        outreach email.

        This method never sends anything.
        """

        if not isinstance(
            outreach,
            OutreachMessage,
        ):
            raise TypeError(
                "outreach must be an OutreachMessage."
            )

        return (
            "\n"
            + "=" * 70
            + "\n"
            + "OUTREACH PREVIEW"
            + "\n"
            + "=" * 70
            + "\n"
            + f"To: {outreach.recipient}\n"
            + f"Subject: {outreach.subject}\n"
            + f"Resume: {outreach.resume_path}\n"
            + f"Contact score: "
            f"{outreach.contact_score}\n"
            + f"Contact reason: "
            f"{outreach.contact_reason}\n"
            + "-" * 70
            + "\n"
            + outreach.body
            + "\n"
            + "=" * 70
        )


__all__ = [
    "OutreachMessage",
    "OutreachManager",
]