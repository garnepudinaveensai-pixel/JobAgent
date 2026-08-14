import re
from typing import Dict, List


# ============================================================
# JOB DESCRIPTION PARSER
# ============================================================

def parse_job_description(text: str) -> dict:
    """
    Parse a job description into structured fields.

    Extracts:
    - Job title
    - Degree requirements
    - Required skills
    - Preferred skills
    - Experience requirements
    - All detected keywords

    This parser is intentionally keyword-based for now.
    The matching logic will be implemented separately.
    """

    # ========================================================
    # EMPTY TEXT
    # ========================================================

    if not text or not text.strip():
        return {
            "job_title": "",
            "degree_requirements": [],
            "required_skills": [],
            "preferred_skills": [],
            "experience_requirements": [],
            "all_keywords": [],
        }

    # ========================================================
    # NORMALIZE TEXT
    # ========================================================

    text = text.strip()

    # Normalize whitespace while preserving the original
    # text structure enough for section detection.
    normalized_text = re.sub(r"[ \t]+", " ", text)

    text_lower = normalized_text.lower()

    # ========================================================
    # KEYWORD DATABASE
    # ========================================================

    # These are the technologies/technical areas that your
    # JobAgent should recognize from job descriptions.

    technical_keywords = [
        # Programming
        "Python",
        "C",
        "C++",
        "C#",
        "Java",
        "JavaScript",
        "Embedded C",
        "SQL",

        # Engineering software
        "MATLAB",
        "Simulink",
        "AutoCAD",
        "AutoCAD Electrical",
        "Code Composer Studio",
        "VS Code",
        "Git",

        # TI / Embedded
        "TI C2000",
        "F28379D",
        "ESP32",
        "Arduino",

        # Embedded concepts
        "GPIO",
        "ADC",
        "PWM",
        "DAC",
        "Microcontrollers",
        "Embedded Systems",
        "Embedded Systems Development",

        # Electrical / Electronics
        "Electrical Engineering",
        "Electrical Systems",
        "Power Electronics",
        "Power Systems",
        "Control Systems",
        "Industrial Electronics",

        # Automation
        "Industrial Automation",
        "Automation",
        "PLC",
        "SCADA",
        "HMI",
        "Instrumentation",

        # Maintenance / Reliability
        "Condition-Based Maintenance",
        "Predictive Maintenance",
        "Preventive Maintenance",
        "Reliability Engineering",
        "Reliability Analysis",
        "Equipment Monitoring",
        "Electrical Equipment Monitoring",
        "Industrial Electrical Equipment Monitoring",

        # Condition monitoring
        "Thermography",
        "Vibration Analysis",
        "Vibration Monitoring",
        "Electrical Signature Analysis",
        "ESA",
        "CRO",

        # Engineering / analysis
        "Root Cause Analysis",
        "Troubleshooting",
        "Technical Documentation",
        "Energy Efficiency",
        "Energy Management",
        "Renewable Energy",

        # General engineering
        "Mechanical Engineering",
        "Manufacturing",
        "Maintenance Engineering",
        "Production Engineering",
    ]

    # ========================================================
    # DEGREE KEYWORDS
    # ========================================================

    degree_keywords = [
        "B.Tech",
        "B.E.",
        "BE",
        "Bachelor of Technology",
        "Bachelor of Engineering",
        "M.Tech",
        "M.E.",
        "ME",
        "Master of Technology",
        "Master of Engineering",
        "MBA",
        "MCA",
        "BCA",
        "BBA",
    ]

    # ========================================================
    # JOB TITLE DETECTION
    # ========================================================

    job_title = ""

    title_patterns = [
        r"(?:job\s*title|position|role)\s*[:\-]\s*([^\n\r]+)",
        r"(?:designation)\s*[:\-]\s*([^\n\r]+)",
    ]

    for pattern in title_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            job_title = match.group(1).strip()
            break

    # ========================================================
    # FALLBACK JOB TITLE DETECTION
    # ========================================================

    if not job_title:

        title_words = [
            "engineer",
            "developer",
            "analyst",
            "technician",
            "intern",
            "trainee",
            "manager",
            "designer",
            "consultant",
            "specialist",
            "associate",
        ]

        for line in text.splitlines():

            line = line.strip()

            if not line:
                continue

            lower_line = line.lower()

            if any(
                word in lower_line
                for word in title_words
            ):

                if len(line) <= 100:

                    job_title = re.sub(
                        r"^[\s\-:]+|[\s\-:]+$",
                        "",
                        line,
                    )

                    break

    # ========================================================
    # FIND KEYWORD SAFELY
    # ========================================================

    def keyword_found(keyword: str) -> bool:
        """
        Check whether a keyword exists in the JD.

        Uses word boundaries for short/technical terms
        where substring matching could produce false positives.
        """

        escaped = re.escape(keyword.lower())

        # Short keywords need boundaries.
        boundary_keywords = {
            "c",
            "be",
            "me",
            "esa",
            "cro",
            "adc",
            "pwm",
            "dac",
            "git",
            "sql",
        }

        if keyword.lower() in boundary_keywords:

            pattern = rf"\b{escaped}\b"

            return bool(
                re.search(
                    pattern,
                    text_lower,
                )
            )

        return keyword.lower() in text_lower

    # ========================================================
    # EXTRACT TECHNICAL KEYWORDS
    # ========================================================

    found_keywords = []

    for keyword in technical_keywords:

        if keyword_found(keyword):
            found_keywords.append(keyword)

    # ========================================================
    # EXTRACT DEGREE REQUIREMENTS
    # ========================================================

    degree_requirements = []

    for degree in degree_keywords:

        if degree.lower() in text_lower:

            if degree not in degree_requirements:
                degree_requirements.append(degree)

    # ========================================================
    # REQUIRED / PREFERRED SECTION DETECTION
    # ========================================================

    required_section_text = ""
    preferred_section_text = ""

    lines = text.splitlines()

    current_section = ""

    required_headers = [
        "requirements",
        "required skills",
        "required qualifications",
        "qualifications",
        "must have",
        "must-have",
        "what you need",
        "key requirements",
        "essential skills",
        "essential qualifications",
    ]

    preferred_headers = [
        "preferred skills",
        "preferred qualifications",
        "preferred",
        "nice to have",
        "nice-to-have",
        "good to have",
        "desirable",
        "additional skills",
    ]

    required_lines = []
    preferred_lines = []

    for line in lines:

        stripped = line.strip()

        if not stripped:
            continue

        lower_line = stripped.lower()

        # ----------------------------------------------
        # Detect required section
        # ----------------------------------------------

        if any(
            header in lower_line
            for header in required_headers
        ):
            current_section = "required"
            continue

        # ----------------------------------------------
        # Detect preferred section
        # ----------------------------------------------

        if any(
            header in lower_line
            for header in preferred_headers
        ):
            current_section = "preferred"
            continue

        # ----------------------------------------------
        # Detect common section endings
        # ----------------------------------------------

        if any(
            header in lower_line
            for header in [
                "responsibilities",
                "responsibility",
                "about the role",
                "about us",
                "what you will do",
                "what you'll do",
                "benefits",
                "location",
                "salary",
                "about the company",
            ]
        ):
            current_section = ""

        # ----------------------------------------------
        # Store lines
        # ----------------------------------------------

        if current_section == "required":
            required_lines.append(stripped)

        elif current_section == "preferred":
            preferred_lines.append(stripped)

    required_section_text = " ".join(required_lines).lower()
    preferred_section_text = " ".join(preferred_lines).lower()

    # ========================================================
    # REQUIRED SKILLS
    # ========================================================

    required_skills = []

    if required_section_text:

        for keyword in technical_keywords:

            escaped = re.escape(keyword.lower())

            if keyword.lower() in {
                "c",
                "be",
                "me",
                "esa",
                "cro",
                "adc",
                "pwm",
                "dac",
                "git",
                "sql",
            }:

                pattern = rf"\b{escaped}\b"

                found = bool(
                    re.search(
                        pattern,
                        required_section_text,
                    )
                )

            else:

                found = (
                    keyword.lower()
                    in required_section_text
                )

            if found:
                required_skills.append(keyword)

    # ========================================================
    # PREFERRED SKILLS
    # ========================================================

    preferred_skills = []

    if preferred_section_text:

        for keyword in technical_keywords:

            escaped = re.escape(keyword.lower())

            if keyword.lower() in {
                "c",
                "be",
                "me",
                "esa",
                "cro",
                "adc",
                "pwm",
                "dac",
                "git",
                "sql",
            }:

                pattern = rf"\b{escaped}\b"

                found = bool(
                    re.search(
                        pattern,
                        preferred_section_text,
                    )
                )

            else:

                found = (
                    keyword.lower()
                    in preferred_section_text
                )

            if found:
                preferred_skills.append(keyword)

    # ========================================================
    # EXPERIENCE REQUIREMENTS
    # ========================================================

    experience_requirements = []

    experience_patterns = [
        r"\b\d+\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience\b",
        r"\b\d+\s*-\s*\d+\s*(?:years?|yrs?)\s+(?:of\s+)?experience\b",
        r"\bfresher\b",
        r"\bentry[- ]level\b",
        r"\bgraduate\s+trainee\b",
        r"\b0\s*[-–]\s*1\s*years?\b",
        r"\b1\s*[-–]\s*2\s*years?\b",
        r"\b2\s*[-–]\s*3\s*years?\b",
        r"\b3\s*[-–]\s*5\s*years?\b",
    ]

    for pattern in experience_patterns:

        matches = re.findall(
            pattern,
            text,
            re.IGNORECASE,
        )

        for match in matches:

            if isinstance(match, tuple):
                value = " ".join(
                    part
                    for part in match
                    if part
                )
            else:
                value = match

            value = value.strip()

            if value and value not in experience_requirements:
                experience_requirements.append(value)

    # ========================================================
    # FALLBACK REQUIRED SKILLS
    # ========================================================

    # If the JD doesn't have an explicit requirements
    # section, use all detected technical keywords.
    #
    # The matcher will later decide how strongly each
    # keyword should affect eligibility.

    if not required_skills:

        required_skills = list(found_keywords)

    # ========================================================
    # REMOVE DUPLICATES WHILE PRESERVING ORDER
    # ========================================================

    def unique(items: List[str]) -> List[str]:

        result = []

        seen = set()

        for item in items:

            normalized = item.lower()

            if normalized not in seen:

                seen.add(normalized)
                result.append(item)

        return result

    found_keywords = unique(found_keywords)
    required_skills = unique(required_skills)
    preferred_skills = unique(preferred_skills)
    degree_requirements = unique(degree_requirements)
    experience_requirements = unique(
        experience_requirements
    )

    # ========================================================
    # RETURN STRUCTURED DATA
    # ========================================================

    return {
        "job_title": job_title,
        "degree_requirements": degree_requirements,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "experience_requirements": experience_requirements,
        "all_keywords": found_keywords,
    }

# ============================================================
# COMPATIBILITY ALIAS
# ============================================================

parse_job = parse_job_description