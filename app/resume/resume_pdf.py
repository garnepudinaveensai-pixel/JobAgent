from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)


# ============================================================
# DEFAULT OUTPUT DIRECTORY
# ============================================================

DEFAULT_OUTPUT_DIR = Path("data") / "tailored_resumes"


# ============================================================
# HELPERS
# ============================================================

def _safe_text(value: Any) -> str:
    """
    Convert any value into safe displayable text.
    """
    if value is None:
        return ""

    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value if item)

    return str(value).strip()


def _escape(text: str) -> str:
    """
    Escape text for ReportLab Paragraph XML.
    """
    text = _safe_text(text)

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _normalise_list(value: Any) -> list[str]:
    """
    Convert different input formats into a clean list.
    """

    if value is None:
        return []

    if isinstance(value, str):
        lines = value.splitlines()

        result = []

        for line in lines:
            line = line.strip()

            if line:
                result.append(line)

        return result

    if isinstance(value, (list, tuple, set)):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    return [str(value).strip()]


def _get(data: dict, *keys: str, default=""):
    """
    Safely retrieve the first available key.
    """

    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]

    return default


# ============================================================
# STYLES
# ============================================================

def _create_styles():
    """
    Create professional resume styles.
    """

    styles = getSampleStyleSheet()

    return {
        "name": ParagraphStyle(
            "ResumeName",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),

        "contact": ParagraphStyle(
            "ResumeContact",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),

        "section": ParagraphStyle(
            "ResumeSection",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            alignment=TA_LEFT,
            spaceBefore=7,
            spaceAfter=4,
        ),

        "body": ParagraphStyle(
            "ResumeBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.8,
            leading=12,
            alignment=TA_LEFT,
            spaceAfter=3,
        ),

        "bullet": ParagraphStyle(
            "ResumeBullet",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.7,
            leading=11.5,
            leftIndent=10,
            firstLineIndent=-6,
            spaceAfter=2,
        ),

        "job_title": ParagraphStyle(
            "ResumeJobTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            spaceAfter=1,
        ),

        "job_meta": ParagraphStyle(
            "ResumeJobMeta",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            spaceAfter=2,
        ),
    }


# ============================================================
# SECTION HEADER
# ============================================================

def _section(title: str, styles) -> list:
    """
    Create a resume section heading.
    """

    return [
        Paragraph(
            _escape(title.upper()),
            styles["section"],
        ),

        Table(
            [[""]],
            colWidths=[170 * mm],
            rowHeights=[0.6 * mm],
            style=TableStyle(
                [
                    (
                        "LINEBELOW",
                        (0, 0),
                        (-1, -1),
                        0.6,
                        colors.black,
                    ),
                ]
            ),
        ),

        Spacer(1, 2),
    ]


# ============================================================
# BULLET LIST
# ============================================================

def _bullets(items: list[str], styles) -> list:
    """
    Create bullet points.
    """

    elements = []

    for item in items:
        elements.append(
            Paragraph(
                f"• {_escape(item)}",
                styles["bullet"],
            )
        )

    return elements


# ============================================================
# EXPERIENCE / INTERNSHIP
# ============================================================

def _experience_section(experience, styles):
    """
    Render work/internship experience.

    Supports dictionaries and strings.
    """

    elements = []

    for item in _normalise_list(experience):

        if isinstance(item, dict):
            title = _get(
                item,
                "title",
                "role",
                "position",
                "job_title",
                default="",
            )

            company = _get(
                item,
                "company",
                "organization",
                "employer",
                default="",
            )

            duration = _get(
                item,
                "duration",
                "date",
                "dates",
                "period",
                default="",
            )

            description = _normalise_list(
                _get(
                    item,
                    "description",
                    "responsibilities",
                    "details",
                    default=[],
                )
            )

            heading = " | ".join(
                part
                for part in [title, company]
                if part
            )

            block = []

            if heading:
                block.append(
                    Paragraph(
                        _escape(heading),
                        styles["job_title"],
                    )
                )

            if duration:
                block.append(
                    Paragraph(
                        _escape(duration),
                        styles["job_meta"],
                    )
                )

            block.extend(
                _bullets(
                    description,
                    styles,
                )
            )

            elements.append(
                KeepTogether(block)
            )

        else:
            elements.append(
                Paragraph(
                    f"• {_escape(item)}",
                    styles["bullet"],
                )
            )

    return elements


# ============================================================
# PROJECTS
# ============================================================

def _projects_section(projects, styles):
    """
    Render projects.
    """

    elements = []

    if isinstance(projects, dict):
        projects = [projects]

    for project in _normalise_list(projects):

        if isinstance(project, dict):

            title = _get(
                project,
                "title",
                "name",
                default="Project",
            )

            description = _normalise_list(
                _get(
                    project,
                    "description",
                    "details",
                    "responsibilities",
                    default=[],
                )
            )

            block = [
                Paragraph(
                    _escape(title),
                    styles["job_title"],
                )
            ]

            block.extend(
                _bullets(
                    description,
                    styles,
                )
            )

            elements.append(
                KeepTogether(block)
            )

        else:
            elements.append(
                Paragraph(
                    f"• {_escape(project)}",
                    styles["bullet"],
                )
            )

    return elements


# ============================================================
# MAIN PDF GENERATOR
# ============================================================

def generate_resume_pdf(
    resume_data: dict,
    output_path: str | Path,
) -> Path:
    """
    Generate a professional tailored resume PDF.

    The function accepts the dictionary produced by the
    resume tailoring pipeline.
    """

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    styles = _create_styles()

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=_safe_text(
            _get(
                resume_data,
                "name",
                default="Resume",
            )
        ),
        author="JobAgent",
    )

    story = []

    # ========================================================
    # HEADER
    # ========================================================

    name = _get(
        resume_data,
        "name",
        "full_name",
        default="Candidate",
    )

    email = _get(
        resume_data,
        "email",
        default="",
    )

    phone = _get(
        resume_data,
        "phone",
        "mobile",
        default="",
    )

    location = _get(
        resume_data,
        "location",
        "address",
        default="",
    )

    linkedin = _get(
        resume_data,
        "linkedin",
        "linkedin_url",
        default="",
    )

    github = _get(
        resume_data,
        "github",
        "github_url",
        default="",
    )

    story.append(
        Paragraph(
            _escape(name),
            styles["name"],
        )
    )

    contact_parts = [
        email,
        phone,
        location,
        linkedin,
        github,
    ]

    contact_parts = [
        _escape(item)
        for item in contact_parts
        if item
    ]

    if contact_parts:
        story.append(
            Paragraph(
                " | ".join(contact_parts),
                styles["contact"],
            )
        )

    # ========================================================
    # PROFESSIONAL SUMMARY
    # ========================================================

    summary = _get(
        resume_data,
        "professional_summary",
        "summary",
        "profile",
        "objective",
        default="",
    )

    if summary:
        story.extend(
            _section(
                "Professional Summary",
                styles,
            )
        )

        story.append(
            Paragraph(
                _escape(summary),
                styles["body"],
            )
        )

    # ========================================================
    # EDUCATION
    # ========================================================

    education = resume_data.get(
        "education",
        [],
    )

    if education:
        story.extend(
            _section(
                "Education",
                styles,
            )
        )

        for item in _normalise_list(education):

            if isinstance(item, dict):

                degree = _get(
                    item,
                    "degree",
                    "qualification",
                    "title",
                    default="",
                )

                institution = _get(
                    item,
                    "institution",
                    "college",
                    "university",
                    default="",
                )

                duration = _get(
                    item,
                    "duration",
                    "year",
                    "dates",
                    default="",
                )

                heading = " — ".join(
                    part
                    for part in [
                        degree,
                        institution,
                    ]
                    if part
                )

                if heading:
                    story.append(
                        Paragraph(
                            _escape(heading),
                            styles["job_title"],
                        )
                    )

                if duration:
                    story.append(
                        Paragraph(
                            _escape(duration),
                            styles["job_meta"],
                        )
                    )

            else:
                story.append(
                    Paragraph(
                        _escape(item),
                        styles["body"],
                    )
                )

    # ========================================================
    # SKILLS
    # ========================================================

    skills = _normalise_list(
        resume_data.get(
            "skills",
            [],
        )
    )

    if skills:

        story.extend(
            _section(
                "Technical Skills",
                styles,
            )
        )

        story.append(
            Paragraph(
                _escape(
                    " • ".join(skills)
                ),
                styles["body"],
            )
        )

    # ========================================================
    # EXPERIENCE
    # ========================================================

    experience = resume_data.get(
        "experience",
        resume_data.get(
            "internships",
            [],
        ),
    )

    if experience:

        story.extend(
            _section(
                "Experience",
                styles,
            )
        )

        story.extend(
            _experience_section(
                experience,
                styles,
            )
        )

    # ========================================================
    # PROJECTS
    # ========================================================

    projects = resume_data.get(
        "projects",
        [],
    )

    if projects:

        story.extend(
            _section(
                "Projects",
                styles,
            )
        )

        story.extend(
            _projects_section(
                projects,
                styles,
            )
        )

    # ========================================================
    # CERTIFICATIONS
    # ========================================================

    certifications = _normalise_list(
        resume_data.get(
            "certifications",
            [],
        )
    )

    if certifications:

        story.extend(
            _section(
                "Certifications",
                styles,
            )
        )

        story.extend(
            _bullets(
                certifications,
                styles,
            )
        )

    # ========================================================
    # ACHIEVEMENTS
    # ========================================================

    achievements = _normalise_list(
        resume_data.get(
            "achievements",
            [],
        )
    )

    if achievements:

        story.extend(
            _section(
                "Achievements",
                styles,
            )
        )

        story.extend(
            _bullets(
                achievements,
                styles,
            )
        )

    # ========================================================
    # BUILD
    # ========================================================

    document.build(story)

    return output_path


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def generate_tailored_resume(
    resume_data: dict,
    job_id: str | None = None,
) -> Path:
    """
    Generate a uniquely named tailored resume.

    Example:

        data/tailored_resumes/
            tailored_resume_12345.pdf
    """

    DEFAULT_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if job_id:
        safe_job_id = "".join(
            character
            if character.isalnum() or character in "-_"
            else "_"
            for character in str(job_id)
        )

        filename = (
            f"tailored_resume_{safe_job_id}.pdf"
        )

    else:
        filename = "tailored_resume.pdf"

    output_path = (
        DEFAULT_OUTPUT_DIR / filename
    )

    return generate_resume_pdf(
        resume_data,
        output_path,
    )