from __future__ import annotations

import re
from typing import Any


# ============================================================
# KNOWN JOB SKILLS
# ============================================================

KNOWN_SKILLS = [
    # Software
    "Python",
    "C",
    "C++",
    "C#",
    "Java",
    "JavaScript",
    "TypeScript",
    "SQL",
    "HTML",
    "CSS",
    "React",
    "Node.js",
    "Django",
    "Flask",
    "REST API",
    "Git",
    "GitHub",
    "Selenium",
    "Testing",
    "Unit Testing",
    "Machine Learning",
    "Artificial Intelligence",
    "Data Structures",
    "Algorithms",

    # Electrical / Core
    "Electrical Engineering",
    "Electrical",
    "Power Electronics",
    "Power Systems",
    "Industrial Electrical",
    "Electrical Equipment",
    "Motor",
    "Motors",
    "Transformer",
    "Switchgear",
    "Condition-Based Maintenance",
    "Predictive Maintenance",
    "Preventive Maintenance",
    "Reliability Engineering",
    "Thermography",
    "Vibration Analysis",
    "Electrical Signature Analysis",
    "Energy Audit",
    "Power Generation",
    "Power Transmission",
    "Power Distribution",
    "Electrical Maintenance",
    "Industrial Maintenance",
    "Equipment Monitoring",

    # Automation / Embedded
    "Industrial Automation",
    "Automation",
    "PLC",
    "SCADA",
    "Embedded Systems",
    "Embedded C",
    "Microcontroller",
    "TI C2000",
    "TMS320F28379D",
    "F28379D",
    "GPIO",
    "ADC",
    "PWM",
    "DAC",
    "MATLAB",
    "Simulink",
    "Control Systems",
    "Digital Controller",
    "Embedded Controller",
    "Robotics",
    "Instrumentation",
    "Industrial Control",
]


# ============================================================
# NORMALIZATION
# ============================================================


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).lower()

    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _contains(text: str, term: str) -> bool:
    text = normalize_text(text)
    term = normalize_text(term)

    if not text or not term:
        return False

    pattern = (
        rf"(?<![a-z0-9])"
        rf"{re.escape(term)}"
        rf"(?![a-z0-9])"
    )

    return bool(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
    )


# ============================================================
# JOB TEXT
# ============================================================


def build_job_text(job: dict) -> str:
    if not isinstance(job, dict):
        return ""

    parts: list[str] = []

    for field in (
        "title",
        "job_title",
        "description",
        "summary",
        "required_skills",
        "preferred_skills",
        "all_keywords",
    ):
        value = job.get(field)

        if value is None:
            continue

        if isinstance(
            value,
            (list, tuple, set),
        ):
            parts.extend(
                str(item)
                for item in value
                if item is not None
            )
        else:
            parts.append(str(value))

    return normalize_text(
        " ".join(parts)
    )


# ============================================================
# SKILL EXTRACTION
# ============================================================


def extract_skills(
    text: str,
) -> list[str]:
    """
    Extract known technical skills from job text.
    """

    normalized = normalize_text(text)

    found: list[str] = []

    for skill in KNOWN_SKILLS:
        if _contains(
            normalized,
            skill,
        ):
            found.append(skill)

    return found


# ============================================================
# REQUIRED / PREFERRED SKILLS
# ============================================================


def _extract_skill_section(
    text: str,
    start_patterns: list[str],
    end_patterns: list[str],
) -> str:
    normalized = normalize_text(text)

    start_match = None

    for pattern in start_patterns:
        match = re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        )

        if match:
            start_match = match
            break

    if start_match is None:
        return ""

    section = normalized[
        start_match.end():
    ]

    end_positions = []

    for pattern in end_patterns:
        match = re.search(
            pattern,
            section,
            flags=re.IGNORECASE,
        )

        if match:
            end_positions.append(
                match.start()
            )

    if end_positions:
        section = section[
            :min(end_positions)
        ]

    return section


def extract_required_skills(
    job: dict,
) -> list[str]:
    """
    Extract skills from explicitly required sections.

    If no explicit required section exists,
    use the complete job text as a fallback.
    """

    text = build_job_text(job)

    section = _extract_skill_section(
        text,
        start_patterns=[
            r"\brequired skills?\b",
            r"\brequired qualifications?\b",
            r"\bminimum qualifications?\b",
            r"\bmust have\b",
            r"\bwhat you(?:'|’)ll need\b",
            r"\bqualifications\b",
            r"\brequirements\b",
        ],
        end_patterns=[
            r"\bpreferred skills?\b",
            r"\bpreferred qualifications?\b",
            r"\bnice to have\b",
            r"\bdesired skills?\b",
            r"\bresponsibilities\b",
            r"\babout the role\b",
        ],
    )

    if not section:
        return []

    return extract_skills(section)


def extract_preferred_skills(
    job: dict,
) -> list[str]:
    text = build_job_text(job)

    section = _extract_skill_section(
        text,
        start_patterns=[
            r"\bpreferred skills?\b",
            r"\bpreferred qualifications?\b",
            r"\bnice to have\b",
            r"\bdesired skills?\b",
            r"\bplus\b",
        ],
        end_patterns=[
            r"\bresponsibilities\b",
            r"\babout the role\b",
            r"\brequired skills?\b",
            r"\brequirements\b",
        ],
    )

    if not section:
        return []

    return extract_skills(section)


# ============================================================
# EXPERIENCE
# ============================================================


def extract_experience_requirements(
    job: dict,
) -> str:
    text = build_job_text(job)

    patterns = [
        r"\b\d+\+?\s*(?:years?|yrs?)\s*(?:of)?\s*experience\b",
        r"\b(?:fresher|freshers|entry[- ]level|graduate|graduates)\b",
        r"\b(?:no experience required|experience not required)\b",
    ]

    matches: list[str] = []

    for pattern in patterns:
        for match in re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):
            value = match.group(0).strip()

            if value not in matches:
                matches.append(value)

    return ", ".join(matches)


# ============================================================
# PARSER
# ============================================================


def parse_job(
    job: dict,
) -> dict:
    """
    Parse and enrich a discovered job.

    Existing discovered fields are preserved.
    """

    if not isinstance(job, dict):
        return {}

    parsed = dict(job)

    text = build_job_text(job)

    existing_required = job.get(
        "required_skills",
        [],
    )

    existing_preferred = job.get(
        "preferred_skills",
        [],
    )

    required = (
        list(existing_required)
        if isinstance(
            existing_required,
            (list, tuple, set),
        )
        else []
    )

    preferred = (
        list(existing_preferred)
        if isinstance(
            existing_preferred,
            (list, tuple, set),
        )
        else []
    )

    if not required:
        required = extract_required_skills(
            job
        )

    if not preferred:
        preferred = extract_preferred_skills(
            job
        )

    all_keywords = extract_skills(
        text
    )

    parsed["required_skills"] = required
    parsed["preferred_skills"] = preferred
    parsed["all_keywords"] = all_keywords
    parsed["experience_requirements"] = (
        job.get(
            "experience_requirements",
            "",
        )
        or extract_experience_requirements(
            job
        )
    )

    return parsed


__all__ = [
    "KNOWN_SKILLS",
    "normalize_text",
    "build_job_text",
    "extract_skills",
    "extract_required_skills",
    "extract_preferred_skills",
    "extract_experience_requirements",
    "parse_job",
]