from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ComposedEmail:
    """
    Represents a fully prepared outreach email.

    This class only creates email content.
    It does not send anything.
    """

    recipient: str
    subject: str
    body: str
    resume_path: str
    job: dict
    contact: dict


class EmailComposer:
    """
    Creates professional, job-specific outreach emails.

    Responsibilities:
        - Generate recipient information.
        - Generate a professional subject.
        - Generate a personalized email body.
        - Include the resume path.
        - Produce a structured email object.

    This class NEVER sends email.
    """

    DEFAULT_RESUME_PATH = (
        "data/resumes/master_resume.pdf"
    )

    def __init__(
        self,
        default_resume_path: str = DEFAULT_RESUME_PATH,
    ):
        self.default_resume_path = (
            str(default_resume_path).strip()
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def compose(
        self,
        job: dict,
        contact: dict,
        resume_path: Optional[str] = None,
    ) -> ComposedEmail:
        """
        Compose a complete outreach email.

        Raises:
            TypeError: Invalid job/contact objects.
            ValueError: Missing recipient or resume path.
        """

        if not isinstance(job, dict):
            raise TypeError(
                "job must be a dictionary."
            )

        if not isinstance(contact, dict):
            raise TypeError(
                "contact must be a dictionary."
            )

        recipient = self._get_recipient(contact)

        final_resume_path = (
            str(resume_path).strip()
            if resume_path is not None
            else self.default_resume_path
        )

        if not final_resume_path:
            raise ValueError(
                "resume_path cannot be empty."
            )

        subject = self.build_subject(job)

        body = self.build_body(
            job=job,
            contact=contact,
        )

        return ComposedEmail(
            recipient=recipient,
            subject=subject,
            body=body,
            resume_path=final_resume_path,
            job=job,
            contact=contact,
        )

    # ========================================================
    # RECIPIENT
    # ========================================================

    @staticmethod
    def _get_recipient(
        contact: dict,
    ) -> str:
        """
        Extract and normalize the recipient email.
        """

        email = str(
            contact.get("email", "")
        ).strip().lower()

        if not email:
            raise ValueError(
                "Contact email cannot be empty."
            )

        if (
            email.count("@") != 1
            or "." not in email.split("@", 1)[1]
        ):
            raise ValueError(
                "Contact email is invalid."
            )

        return email

    # ========================================================
    # SUBJECT
    # ========================================================

    @staticmethod
    def build_subject(
        job: dict,
    ) -> str:
        """
        Build a concise professional subject.
        """

        title = str(
            job.get("title", "")
        ).strip()

        company = str(
            job.get("company", "")
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

        return "Job Application – Electrical Engineer"

    # ========================================================
    # BODY
    # ========================================================

    @staticmethod
    def build_body(
        job: dict,
        contact: Optional[dict] = None,
    ) -> str:
        """
        Build a personalized professional email body.

        Only supplied job/contact information is used.
        """

        title = str(
            job.get("title", "")
        ).strip()

        company = str(
            job.get("company", "")
        ).strip()

        location = str(
            job.get("location", "")
        ).strip()

        contact_name = ""

        if isinstance(contact, dict):
            contact_name = str(
                contact.get("name", "")
            ).strip()

        if contact_name:
            greeting = (
                f"Dear {contact_name},"
            )
        else:
            greeting = "Dear Hiring Team,"

        if title and company:
            position_reference = (
                f"the {title} position at {company}"
            )
        elif title:
            position_reference = (
                f"the {title} position"
            )
        elif company:
            position_reference = (
                f"opportunities at {company}"
            )
        else:
            position_reference = (
                "the available engineering opportunity"
            )

        location_sentence = ""

        if location:
            location_sentence = (
                f" I am particularly interested in "
                f"opportunities in {location}."
            )

        return (
            f"{greeting}\n\n"
            f"I am writing to express my interest in "
            f"{position_reference}. "
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
    # SERIALIZATION
    # ========================================================

    @staticmethod
    def to_dict(
        email: ComposedEmail,
    ) -> dict:
        """
        Convert a composed email into a plain dictionary.
        """

        if not isinstance(
            email,
            ComposedEmail,
        ):
            raise TypeError(
                "email must be a ComposedEmail."
            )

        return {
            "recipient": email.recipient,
            "subject": email.subject,
            "body": email.body,
            "resume_path": email.resume_path,
            "job": dict(email.job),
            "contact": dict(email.contact),
        }