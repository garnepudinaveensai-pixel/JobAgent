import re
from typing import Dict, List


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    """
    Normalize text for reliable keyword matching.
    """

    if not text:
        return ""

    text = text.lower()

    # Normalize common separators
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = text.replace("-", " ")

    # Remove extra punctuation
    text = re.sub(r"[^a-z0-9+#.\s]", " ", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# KEYWORD MATCHING
# ============================================================

def keyword_matches(
    job_text: str,
    keywords: List[str],
) -> List[str]:
    """
    Find which keywords occur in the job description.

    Uses word-boundary matching where possible.
    """

    normalized_job = normalize_text(job_text)

    matched = []

    for keyword in keywords:

        normalized_keyword = normalize_text(keyword)

        if not normalized_keyword:
            continue

        # Special handling for very short keywords
        if normalized_keyword in {"c", "c++", "r"}:

            pattern = rf"(?<![a-z0-9+#]){re.escape(normalized_keyword)}(?![a-z0-9+#])"

            if re.search(pattern, normalized_job):
                matched.append(keyword)

        else:

            # Flexible whitespace between words
            keyword_pattern = re.escape(normalized_keyword)
            keyword_pattern = keyword_pattern.replace(r"\ ", r"\s+")

            pattern = rf"(?<![a-z0-9]){keyword_pattern}(?![a-z0-9])"

            if re.search(pattern, normalized_job):
                matched.append(keyword)

    return matched


# ============================================================
# RESUME KEYWORD EXTRACTION
# ============================================================

def get_resume_keywords(resume: Dict) -> List[str]:
    """
    Combine technical skills and core competencies.

    IMPORTANT:
    Core competencies are treated as additional skills
    that the candidate is familiar with.
    """

    keywords = []

    # --------------------------------------------------------
    # Technical skills
    # --------------------------------------------------------

    skills = resume.get("skills", "")

    if isinstance(skills, str):

        for skill in skills.split(","):

            skill = skill.strip()

            if skill:
                keywords.append(skill)

    elif isinstance(skills, list):

        keywords.extend(
            skill.strip()
            for skill in skills
            if skill and skill.strip()
        )

    # --------------------------------------------------------
    # Core competencies
    # --------------------------------------------------------

    core_competencies = resume.get(
        "core_competencies",
        "",
    )

    if isinstance(core_competencies, str):

        for competency in core_competencies.split(","):

            competency = competency.strip()

            if competency:
                keywords.append(competency)

    elif isinstance(core_competencies, list):

        keywords.extend(
            competency.strip()
            for competency in core_competencies
            if competency and competency.strip()
        )

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique_keywords = []

    seen = set()

    for keyword in keywords:

        normalized = normalize_text(keyword)

        if normalized not in seen:

            seen.add(normalized)
            unique_keywords.append(keyword)

    return unique_keywords


# ============================================================
# JOB MATCHER
# ============================================================

def match_job(
    resume: Dict,
    job: Dict,
) -> Dict:
    """
    Compare a parsed resume against a parsed job description.

    Technical skills AND core competencies are considered
    candidate capabilities.

    Required skills receive higher importance than
    preferred skills.
    """

    # --------------------------------------------------------
    # Get job information
    # --------------------------------------------------------

    required_skills = job.get(
        "required_skills",
        [],
    )

    preferred_skills = job.get(
        "preferred_skills",
        [],
    )

    experience_requirements = job.get(
        "experience_requirements",
        "",
    )

    # --------------------------------------------------------
    # Convert strings to lists if necessary
    # --------------------------------------------------------

    if isinstance(required_skills, str):

        required_skills = [
            skill.strip()
            for skill in required_skills.split(",")
            if skill.strip()
        ]

    if isinstance(preferred_skills, str):

        preferred_skills = [
            skill.strip()
            for skill in preferred_skills.split(",")
            if skill.strip()
        ]

    # --------------------------------------------------------
    # Build candidate skill set
    # --------------------------------------------------------

    resume_keywords = get_resume_keywords(resume)

    # --------------------------------------------------------
    # Build searchable resume text
    # --------------------------------------------------------

    resume_text = ", ".join(resume_keywords)

    # --------------------------------------------------------
    # Required skill matching
    # --------------------------------------------------------

    matched_required = keyword_matches(
        resume_text,
        required_skills,
    )

    missing_required = [
        skill
        for skill in required_skills
        if normalize_text(skill)
        not in {
            normalize_text(item)
            for item in matched_required
        }
    ]

    # --------------------------------------------------------
    # Preferred skill matching
    # --------------------------------------------------------

    matched_preferred = keyword_matches(
        resume_text,
        preferred_skills,
    )

    missing_preferred = [
        skill
        for skill in preferred_skills
        if normalize_text(skill)
        not in {
            normalize_text(item)
            for item in matched_preferred
        }
    ]

    # --------------------------------------------------------
    # Calculate skill scores
    # --------------------------------------------------------

    required_count = len(required_skills)
    preferred_count = len(preferred_skills)

    required_score = (
        len(matched_required) / required_count
        if required_count
        else 1.0
    )

    preferred_score = (
        len(matched_preferred) / preferred_count
        if preferred_count
        else 1.0
    )

    # --------------------------------------------------------
    # Required skills are more important
    # --------------------------------------------------------

    if required_count and preferred_count:

        score = (
            required_score * 0.75
            + preferred_score * 0.25
        ) * 100

    elif required_count:

        score = required_score * 100

    elif preferred_count:

        score = preferred_score * 100

    else:

        score = 0.0

    score = round(score, 2)

    # --------------------------------------------------------
    # Eligibility
    # --------------------------------------------------------

    # A job is considered eligible when all explicitly
    # required skills are present.

    eligible = (
        len(missing_required) == 0
        if required_count
        else True
    )

    # --------------------------------------------------------
    # Recommendation
    # --------------------------------------------------------

    if eligible:

        recommendation = "APPLY"

    elif score >= 60:

        recommendation = "CONSIDER"

    else:

        recommendation = "SKIP"

    # --------------------------------------------------------
    # Return complete result
    # --------------------------------------------------------

    return {
        "match_score": score,
        "eligible": eligible,

        "matched_required_skills": matched_required,
        "missing_required_skills": missing_required,

        "matched_preferred_skills": matched_preferred,
        "missing_preferred_skills": missing_preferred,

        "experience_requirements": experience_requirements,

        "resume_keywords": resume_keywords,

        "recommendation": recommendation,
    }