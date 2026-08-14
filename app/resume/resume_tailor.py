from copy import deepcopy

from app.core.matcher import (
    keyword_matches,
    normalize_text,
)


# ============================================================
# INPUT NORMALIZATION
# ============================================================

def _to_list(value):
    """
    Convert supported input formats into a clean list of strings.

    Supported:
    - None
    - ""
    - comma-separated strings
    - lists / tuples / sets

    Empty values are removed.
    """

    if value is None:
        return []

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return []

        return [
            item.strip()
            for item in value.split(",")
            if item.strip()
        ]

    if isinstance(value, (list, tuple, set)):
        result = []

        for item in value:
            if isinstance(item, str):
                item = item.strip()

                if item:
                    result.append(item)

        return result

    return []


# ============================================================
# UNIQUE VALUES
# ============================================================

def _unique_preserve_order(items):
    """
    Remove duplicate values while preserving original order.

    Duplicate detection is case-insensitive and normalization-aware.
    """

    result = []
    seen = set()

    for item in items:

        if not isinstance(item, str):
            continue

        item = item.strip()

        if not item:
            continue

        normalized = normalize_text(item)

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(item)

    return result


# ============================================================
# RESUME KEYWORDS
# ============================================================

def _get_resume_keywords(resume):
    """
    Build the complete set of genuine candidate capabilities.

    Technical skills and core competencies are both considered
    when determining whether the candidate supports a job keyword.
    """

    skills = _to_list(
        resume.get("skills", [])
    )

    competencies = _to_list(
        resume.get("core_competencies", [])
    )

    return _unique_preserve_order(
        skills + competencies
    )


# ============================================================
# KEYWORD SUPPORT
# ============================================================

def _find_supported_keywords(
    resume_keywords,
    job_keywords,
):
    """
    Determine which job keywords are supported by the resume.

    Uses the application's keyword matcher instead of exact
    string equality.

    Examples:

        Resume:
            TI C2000 F28379D

        Job:
            TI C2000

        Result:
            TI C2000 -> supported

    Also handles case and formatting differences.
    """

    resume_keywords = _unique_preserve_order(
        resume_keywords
    )

    job_keywords = _unique_preserve_order(
        job_keywords
    )

    if not resume_keywords or not job_keywords:
        return []

    # Convert genuine resume capabilities into searchable text.
    resume_text = ", ".join(
        resume_keywords
    )

    return keyword_matches(
        resume_text,
        job_keywords,
    )


# ============================================================
# UNSUPPORTED KEYWORDS
# ============================================================

def _find_unsupported_keywords(
    resume_keywords,
    job_keywords,
):
    """
    Return job keywords that are not supported by the resume.
    """

    supported = _find_supported_keywords(
        resume_keywords,
        job_keywords,
    )

    supported_normalized = {
        normalize_text(keyword)
        for keyword in supported
    }

    return [
        keyword
        for keyword in _unique_preserve_order(job_keywords)
        if normalize_text(keyword)
        not in supported_normalized
    ]


# ============================================================
# MATCH ORIGINAL RESUME SKILLS
# ============================================================

def _find_matching_resume_items(
    resume_items,
    supported_keywords,
):
    """
    Find original resume items that support the matched job
    keywords.

    Importantly, the ORIGINAL wording is preserved.

    Example:

        Job keyword:
            TI C2000

        Resume skill:
            TI C2000 F28379D

        Returned:
            TI C2000 F28379D
    """

    resume_items = _unique_preserve_order(
        resume_items
    )

    supported_keywords = _unique_preserve_order(
        supported_keywords
    )

    if not resume_items or not supported_keywords:
        return []

    matching_items = []

    for resume_item in resume_items:

        matches = keyword_matches(
            resume_item,
            supported_keywords,
        )

        if matches:
            matching_items.append(
                resume_item
            )

    return matching_items


# ============================================================
# RESUME TAILOR
# ============================================================

def tailor_resume(resume, job):
    """
    Tailor a resume toward a specific job.

    Rules:
    - Never invent qualifications.
    - Only use information already present in the resume.
    - Required and preferred job skills are evaluated separately.
    - Technical skills and core competencies are both considered
      when determining capability.
    - Original resume skill wording is preserved.
    """

    if not isinstance(resume, dict):
        raise TypeError(
            "resume must be a dictionary"
        )

    if not isinstance(job, dict):
        raise TypeError(
            "job must be a dictionary"
        )

    # ========================================================
    # COPY ORIGINAL RESUME
    # ========================================================

    # Deep copy prevents accidental modification of nested
    # lists in the caller's original resume.
    result = deepcopy(resume)

    # ========================================================
    # RESUME DATA
    # ========================================================

    resume_skills = _unique_preserve_order(
        _to_list(
            resume.get("skills", [])
        )
    )

    resume_competencies = _unique_preserve_order(
        _to_list(
            resume.get(
                "core_competencies",
                [],
            )
        )
    )

    # Both categories represent genuine candidate capabilities.
    resume_keywords = _unique_preserve_order(
        resume_skills
        + resume_competencies
    )

    # ========================================================
    # JOB DATA
    # ========================================================

    required_skills = _unique_preserve_order(
        _to_list(
            job.get(
                "required_skills",
                [],
            )
        )
    )

    preferred_skills = _unique_preserve_order(
        _to_list(
            job.get(
                "preferred_skills",
                [],
            )
        )
    )

    # ========================================================
    # REQUIRED SKILLS
    # ========================================================

    supported_required_keywords = (
        _find_supported_keywords(
            resume_keywords,
            required_skills,
        )
    )

    unsupported_required_keywords = (
        _find_unsupported_keywords(
            resume_keywords,
            required_skills,
        )
    )

    # ========================================================
    # PREFERRED SKILLS
    # ========================================================

    supported_preferred_keywords = (
        _find_supported_keywords(
            resume_keywords,
            preferred_skills,
        )
    )

    unsupported_preferred_keywords = (
        _find_unsupported_keywords(
            resume_keywords,
            preferred_skills,
        )
    )

    # ========================================================
    # ORIGINAL TECHNICAL SKILLS TO PROMOTE
    # ========================================================

    supported_job_keywords = _unique_preserve_order(
        supported_required_keywords
        + supported_preferred_keywords
    )

    tailored_skills = _find_matching_resume_items(
        resume_skills,
        supported_job_keywords,
    )

    # ========================================================
    # ORIGINAL CORE COMPETENCIES TO PROMOTE
    # ========================================================

    tailored_core_competencies = (
        _find_matching_resume_items(
            resume_competencies,
            supported_job_keywords,
        )
    )

    # ========================================================
    # FALLBACK
    # ========================================================

    # If there are no matching job keywords, don't fabricate
    # anything and don't destroy the candidate's existing skills.
    if not tailored_skills:
        tailored_skills = list(
            resume_skills
        )

    if not tailored_core_competencies:
        tailored_core_competencies = list(
            resume_competencies
        )

    # ========================================================
    # MATCH STATISTICS
    # ========================================================

    required_count = len(
        required_skills
    )

    preferred_count = len(
        preferred_skills
    )

    matched_required_count = len(
        supported_required_keywords
    )

    matched_preferred_count = len(
        supported_preferred_keywords
    )

    required_match_percentage = (
        round(
            (
                matched_required_count
                / required_count
            ) * 100,
            2,
        )
        if required_count
        else 100.0
    )

    preferred_match_percentage = (
        round(
            (
                matched_preferred_count
                / preferred_count
            ) * 100,
            2,
        )
        if preferred_count
        else 100.0
    )

    # ========================================================
    # ELIGIBILITY
    # ========================================================

    eligible = (
        len(unsupported_required_keywords)
        == 0
    )

    # ========================================================
    # RESULT
    # ========================================================

    result.update(
        {
            "tailored_for": job.get(
                "title",
                "",
            ),

            # Required skills
            "supported_required_keywords":
                supported_required_keywords,

            "unsupported_required_keywords":
                unsupported_required_keywords,

            # Preferred skills
            "supported_preferred_keywords":
                supported_preferred_keywords,

            "unsupported_preferred_keywords":
                unsupported_preferred_keywords,

            # Tailored resume sections
            "tailored_skills":
                tailored_skills,

            "tailored_core_competencies":
                tailored_core_competencies,

            # Matching information
            "required_match_percentage":
                required_match_percentage,

            "preferred_match_percentage":
                preferred_match_percentage,

            "eligible":
                eligible,

            "supported_job_keywords":
                supported_job_keywords,
        }
    )

    return result