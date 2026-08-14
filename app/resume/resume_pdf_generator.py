from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


class ResumePDFGenerator:
    """
    Generates a professional PDF resume from the structured
    resume data produced by the resume tailoring system.

    Important:
    This class does not invent qualifications.
    It only renders information supplied in the resume data.
    """

    def __init__(
        self,
        output_dir: str = "data/resumes",
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _clean(value) -> str:
        if value is None:
            return ""

        return str(value).strip()

    @staticmethod
    def _list(value) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            return [
                item.strip()
                for item in value.split(",")
                if item.strip()
            ]

        if isinstance(value, (list, tuple, set)):
            return [
                str(item).strip()
                for item in value
                if str(item).strip()
            ]

        return []

    @staticmethod
    def _safe_filename(value: str) -> str:
        """
        Convert a job title into a filesystem-safe filename.
        """

        cleaned = "".join(
            character
            if character.isalnum() or character in " -_"
            else "_"
            for character in value
        )

        cleaned = "_".join(
            cleaned.split()
        )

        return cleaned[:100] or "tailored_resume"

    # ========================================================
    # STYLES
    # ========================================================

    @staticmethod
    def _styles():
        styles = getSampleStyleSheet()

        return {
            "name": ParagraphStyle(
                "ResumeName",
                parent=styles["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=18,
                leading=22,
                alignment=TA_CENTER,
                spaceAfter=4,
            ),

            "contact": ParagraphStyle(
                "Contact",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=12,
                alignment=TA_CENTER,
                textColor=colors.grey,
                spaceAfter=10,
            ),

            "section": ParagraphStyle(
                "Section",
                parent=styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=11,
                leading=14,
                spaceBefore=8,
                spaceAfter=4,
            ),

            "body": ParagraphStyle(
                "Body",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=9.5,
                leading=13,
                spaceAfter=3,
            ),

            "bullet": ParagraphStyle(
                "Bullet",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=9.5,
                leading=13,
                leftIndent=12,
                firstLineIndent=-7,
                spaceAfter=2,
            ),
        }

    # ========================================================
    # BUILD
    # ========================================================

    def build(
        self,
        resume: dict,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate a PDF resume.

        Args:
            resume:
                Structured resume dictionary.

            output_path:
                Optional explicit PDF path.

        Returns:
            Path to generated PDF.
        """

        if not isinstance(resume, dict):
            raise TypeError(
                "resume must be a dictionary"
            )

        if output_path:
            pdf_path = Path(output_path)
        else:
            job_title = self._clean(
                resume.get(
                    "tailored_for",
                    "",
                )
            )

            filename = (
                f"tailored_resume_"
                f"{self._safe_filename(job_title)}.pdf"
            )

            pdf_path = self.output_dir / filename

        pdf_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        styles = self._styles()

        document = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
            title="Tailored Resume",
            author=self._clean(
                resume.get("name", "")
            ),
        )

        story = []

        # ====================================================
        # HEADER
        # ====================================================

        name = self._clean(
            resume.get("name", "")
        )

        if name:
            story.append(
                Paragraph(
                    name,
                    styles["name"],
                )
            )

        contact_parts = []

        for field in (
            "email",
            "phone",
            "location",
            "linkedin",
            "github",
        ):
            value = self._clean(
                resume.get(field, "")
            )

            if value:
                contact_parts.append(value)

        if contact_parts:
            story.append(
                Paragraph(
                    " | ".join(contact_parts),
                    styles["contact"],
                )
            )

        # ====================================================
        # TARGET
        # ====================================================

        tailored_for = self._clean(
            resume.get(
                "tailored_for",
                "",
            )
        )

        if tailored_for:
            story.append(
                Paragraph(
                    "Target Role",
                    styles["section"],
                )
            )

            story.append(
                Paragraph(
                    tailored_for,
                    styles["body"],
                )
            )

        # ====================================================
        # SUMMARY
        # ====================================================

        summary = self._clean(
            resume.get(
                "summary",
                "",
            )
        )

        if summary:
            story.append(
                Paragraph(
                    "Professional Summary",
                    styles["section"],
                )
            )

            story.append(
                Paragraph(
                    summary,
                    styles["body"],
                )
            )

        # ====================================================
        # EDUCATION
        # ====================================================

        education = self._clean(
            resume.get(
                "education",
                "",
            )
        )

        degree = self._clean(
            resume.get(
                "degree",
                "",
            )
        )

        if education or degree:
            story.append(
                Paragraph(
                    "Education",
                    styles["section"],
                )
            )

            if degree:
                story.append(
                    Paragraph(
                        degree,
                        styles["body"],
                    )
                )

            if education:
                story.append(
                    Paragraph(
                        education,
                        styles["body"],
                    )
                )

        # ====================================================
        # SKILLS
        # ====================================================

        skills = self._list(
            resume.get(
                "tailored_skills",
                resume.get(
                    "skills",
                    [],
                ),
            )
        )

        if skills:
            story.append(
                Paragraph(
                    "Technical Skills",
                    styles["section"],
                )
            )

            story.append(
                Paragraph(
                    " • ".join(skills),
                    styles["body"],
                )
            )

        # ====================================================
        # CORE COMPETENCIES
        # ====================================================

        competencies = self._list(
            resume.get(
                "tailored_core_competencies",
                resume.get(
                    "core_competencies",
                    [],
                ),
            )
        )

        if competencies:
            story.append(
                Paragraph(
                    "Core Competencies",
                    styles["section"],
                )
            )

            story.append(
                Paragraph(
                    " • ".join(competencies),
                    styles["body"],
                )
            )

        # ====================================================
        # EXPERIENCE
        # ====================================================

        experience = resume.get(
            "experience",
            [],
        )

        if experience:
            story.append(
                Paragraph(
                    "Experience",
                    styles["section"],
                )
            )

            if isinstance(
                experience,
                str,
            ):
                story.append(
                    Paragraph(
                        experience,
                        styles["body"],
                    )
                )

            elif isinstance(
                experience,
                list,
            ):
                for item in experience:

                    if isinstance(
                        item,
                        dict,
                    ):
                        role = self._clean(
                            item.get(
                                "role",
                                item.get(
                                    "title",
                                    "",
                                ),
                            )
                        )

                        company = self._clean(
                            item.get(
                                "company",
                                "",
                            )
                        )

                        duration = self._clean(
                            item.get(
                                "duration",
                                "",
                            )
                        )

                        heading = " | ".join(
                            part
                            for part in (
                                role,
                                company,
                                duration,
                            )
                            if part
                        )

                        if heading:
                            story.append(
                                Paragraph(
                                    heading,
                                    styles["body"],
                                )
                            )

                        description = self._clean(
                            item.get(
                                "description",
                                "",
                            )
                        )

                        if description:
                            story.append(
                                Paragraph(
                                    description,
                                    styles["body"],
                                )
                            )

                        responsibilities = self._list(
                            item.get(
                                "responsibilities",
                                [],
                            )
                        )

                        for responsibility in responsibilities:
                            story.append(
                                Paragraph(
                                    f"• {responsibility}",
                                    styles["bullet"],
                                )
                            )

                    elif isinstance(
                        item,
                        str,
                    ):
                        story.append(
                            Paragraph(
                                item,
                                styles["body"],
                            )
                        )

        # ====================================================
        # PROJECTS
        # ====================================================

        projects = resume.get(
            "projects",
            [],
        )

        if projects:
            story.append(
                Paragraph(
                    "Projects",
                    styles["section"],
                )
            )

            if isinstance(
                projects,
                str,
            ):
                story.append(
                    Paragraph(
                        projects,
                        styles["body"],
                    )
                )

            elif isinstance(
                projects,
                list,
            ):
                for project in projects:

                    if isinstance(
                        project,
                        dict,
                    ):
                        title = self._clean(
                            project.get(
                                "title",
                                project.get(
                                    "name",
                                    "",
                                ),
                            )
                        )

                        description = self._clean(
                            project.get(
                                "description",
                                "",
                            )
                        )

                        if title:
                            story.append(
                                Paragraph(
                                    title,
                                    styles["body"],
                                )
                            )

                        if description:
                            story.append(
                                Paragraph(
                                    description,
                                    styles["body"],
                                )
                            )

                    elif isinstance(
                        project,
                        str,
                    ):
                        story.append(
                            Paragraph(
                                project,
                                styles["body"],
                            )
                        )

        # ====================================================
        # CERTIFICATIONS
        # ====================================================

        certifications = self._list(
            resume.get(
                "certifications",
                [],
            )
        )

        if certifications:
            story.append(
                Paragraph(
                    "Certifications",
                    styles["section"],
                )
            )

            for certification in certifications:
                story.append(
                    Paragraph(
                        f"• {certification}",
                        styles["bullet"],
                    )
                )

        # ====================================================
        # FINAL BUILD
        # ====================================================

        document.build(story)

        return str(pdf_path)


def generate_resume_pdf(
    resume: dict,
    output_path: Optional[str] = None,
) -> str:
    """
    Convenience function for generating a tailored resume PDF.
    """

    generator = ResumePDFGenerator()

    return generator.build(
        resume,
        output_path=output_path,
    )