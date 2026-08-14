"""
Resume Selection Engine

Responsibilities:

1. Classify jobs.
2. Classify resumes.
3. Match required skills.
4. Match preferred skills.
5. Strongly prefer the correct resume profile.
6. Handle OCR/parser failures gracefully.
7. Return a stable result schema.
8. Provide detailed diagnostics.

Categories:

    SOFTWARE
    CORE
    AUTOMATION
    HYBRID
"""

import re
from pathlib import Path


# ============================================================
# CATEGORY KEYWORDS
# ============================================================

SOFTWARE_KEYWORDS = {
    "python",
    "java",
    "javascript",
    "typescript",
    "sql",
    "html",
    "css",
    "react",
    "node.js",
    "nodejs",
    "django",
    "flask",
    "api",
    "rest api",
    "rest",
    "git",
    "github",
    "software development",
    "software engineering",
    "software testing",
    "automation testing",
    "selenium",
    "testing",
    "unit testing",
    "data structures",
    "algorithms",
    "machine learning",
    "artificial intelligence",
    "object oriented programming",
    "oop",
    "backend",
    "frontend",
    "full stack",
    "web development",
}


CORE_KEYWORDS = {
    "electrical engineering",
    "electrical",
    "power electronics",
    "power systems",
    "industrial electrical",
    "electrical equipment",
    "motor",
    "motors",
    "transformer",
    "switchgear",
    "condition-based maintenance",
    "condition based maintenance",
    "predictive maintenance",
    "preventive maintenance",
    "reliability engineering",
    "thermography",
    "vibration analysis",
    "electrical signature analysis",
    "energy audit",
    "power generation",
    "power transmission",
    "power distribution",
    "electrical maintenance",
    "industrial maintenance",
    "equipment monitoring",
}


AUTOMATION_KEYWORDS = {
    "industrial automation",
    "automation",
    "plc",
    "scada",
    "embedded systems",
    "embedded c",
    "microcontroller",
    "microcontrollers",
    "ti c2000",
    "tms320f28379d",
    "f28379d",
    "esp32",
    "gpio",
    "adc",
    "pwm",
    "dac",
    "matlab",
    "simulink",
    "control systems",
    "control system",
    "digital controller",
    "embedded controller",
    "robotics",
    "instrumentation",
    "industrial control",
}


# ============================================================
# ALIASES
# ============================================================

ALIASES = {

    "tms320f28379d": "f28379d",

    "tms320 f28379d": "f28379d",

    "ti f28379d": "f28379d",

    "nodejs": "node.js",

    "rest apis": "rest api",

    "restful api": "rest api",

    "restful apis": "rest api",

    "embedded system": "embedded systems",

    "microcontroller": "microcontroller",

    "microcontrollers": "microcontroller",

    "power electronic": "power electronics",

    "predictive maintenance": "predictive maintenance",

    "condition based maintenance":
        "condition-based maintenance",

    "condition-based maintenance":
        "condition-based maintenance",

    "preventive maintenance":
        "preventive maintenance",

    "electrical signature analysis":
        "electrical signature analysis",
}


# ============================================================
# NORMALIZATION
# ============================================================

def _normalise(value):

    if value is None:
        return ""

    text = str(value).lower().strip()

    text = text.replace(
        "\u2013",
        "-"
    )

    text = text.replace(
        "\u2014",
        "-"
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


def _canonical(value):

    value = _normalise(value)

    return ALIASES.get(
        value,
        value
    )


def _normalise_collection(values):

    if values is None:
        return set()

    if isinstance(values, str):

        # Parser commonly returns:
        #
        # "Python, SQL, Git, MATLAB"

        values = [
            item.strip()
            for item in values.split(",")
            if item.strip()
        ]

    result = set()

    for value in values:

        value = _canonical(value)

        if value:
            result.add(value)

    return result


# ============================================================
# TEXT MATCHING
# ============================================================

def _contains_term(text, term):

    text = _normalise(text)

    term = _normalise(term)

    if not text or not term:
        return False

    # Special handling for punctuation-containing
    # technologies such as C++, C#, Node.js.

    escaped = re.escape(term)

    pattern = (
        rf"(?<![a-z0-9])"
        rf"{escaped}"
        rf"(?![a-z0-9])"
    )

    return bool(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )
    )


def _text_contains_any(
    text,
    terms
):

    return any(
        _contains_term(
            text,
            term
        )
        for term in terms
    )


# ============================================================
# JOB DATA
# ============================================================

def _job_text(job):

    if not isinstance(job, dict):
        return ""

    parts = []

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

        if isinstance(value, (list, tuple, set)):

            parts.extend(
                str(item)
                for item in value
            )

        else:

            parts.append(
                str(value)
            )

    return " ".join(parts)


def _collect_job_keywords(job):

    keywords = set()

    for field in (
        "required_skills",
        "preferred_skills",
        "all_keywords",
    ):

        values = job.get(
            field,
            []
        )

        keywords.update(
            _normalise_collection(
                values
            )
        )

    return keywords


def _collect_required_skills(job):

    return _normalise_collection(
        job.get(
            "required_skills",
            []
        )
    )


def _collect_preferred_skills(job):

    return _normalise_collection(
        job.get(
            "preferred_skills",
            []
        )
    )


# ============================================================
# JOB CLASSIFICATION
# ============================================================

def _score_category_from_text(
    text,
    keywords
):

    score = 0

    for keyword in keywords:

        if _contains_term(
            text,
            keyword
        ):
            score += 1

    return score


def classify_job(job):

    keywords = _collect_job_keywords(
        job
    )

    text = _job_text(job)

    software_score = (
        _score_category_from_text(
            text,
            SOFTWARE_KEYWORDS
        )
    )

    core_score = (
        _score_category_from_text(
            text,
            CORE_KEYWORDS
        )
    )

    automation_score = (
        _score_category_from_text(
            text,
            AUTOMATION_KEYWORDS
        )
    )

    scores = {
        "SOFTWARE": software_score,
        "CORE": core_score,
        "AUTOMATION": automation_score,
    }

    ordered = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    highest_category, highest_score = (
        ordered[0]
    )

    second_score = ordered[1][1]

    if highest_score == 0:

        category = "HYBRID"

    elif highest_score == second_score:

        category = "HYBRID"

    elif (
        highest_score - second_score <= 1
        and highest_score < 4
    ):

        category = "HYBRID"

    else:

        category = highest_category

    return {
        "category": category,
        "software_score": software_score,
        "core_score": core_score,
        "automation_score": automation_score,
        "classification_scores": scores,
    }


# ============================================================
# RESUME DATA
# ============================================================

def _resume_filename(resume):

    filename = resume.get(
        "_filename",
        ""
    )

    if not filename:

        filename = Path(
            resume.get(
                "_file",
                ""
            )
        ).name

    return _normalise(
        filename
    )


def _resume_raw_text(resume):

    return _normalise(
        resume.get(
            "_raw_text",
            ""
        )
    )


def _resume_combined_text(resume):

    parts = []

    raw_text = resume.get(
        "_raw_text",
        ""
    )

    if raw_text:
        parts.append(
            str(raw_text)
        )

    for field in (
        "name",
        "degree",
        "skills",
        "core_competencies",
        "technical_skills",
        "all_keywords",
        "projects",
        "experience",
        "internships",
        "summary",
    ):

        value = resume.get(
            field
        )

        if value is None:
            continue

        if isinstance(
            value,
            (list, tuple, set)
        ):

            parts.extend(
                str(item)
                for item in value
            )

        else:

            parts.append(
                str(value)
            )

    return _normalise(
        " ".join(parts)
    )


def _resume_keywords(resume):

    keywords = set()

    # --------------------------------------------------------
    # Parsed fields
    # --------------------------------------------------------

    for field in (
        "skills",
        "core_competencies",
        "technical_skills",
        "all_keywords",
    ):

        values = resume.get(
            field,
            []
        )

        keywords.update(
            _normalise_collection(
                values
            )
        )

    # --------------------------------------------------------
    # Raw text
    # --------------------------------------------------------

    raw_text = _resume_raw_text(
        resume
    )

    if raw_text:

        all_known_keywords = (
            SOFTWARE_KEYWORDS
            | CORE_KEYWORDS
            | AUTOMATION_KEYWORDS
        )

        for keyword in all_known_keywords:

            if _contains_term(
                raw_text,
                keyword
            ):

                keywords.add(
                    _canonical(keyword)
                )

    return keywords


# ============================================================
# RESUME CATEGORY
# ============================================================

def _filename_category_hint(
    resume
):

    filename = _resume_filename(
        resume
    )

    scores = {
        "SOFTWARE": 0,
        "CORE": 0,
        "AUTOMATION": 0,
    }

    # Filename is a profile hint,
    # NOT proof of skills.

    if "software" in filename:
        scores["SOFTWARE"] += 100

    if "technical" in filename:
        scores["CORE"] += 100

    if "core" in filename:
        scores["CORE"] += 100

    if "automation" in filename:
        scores["AUTOMATION"] += 100

    if "embedded" in filename:
        scores["AUTOMATION"] += 100

    return scores


def classify_resume(resume):

    filename_scores = (
        _filename_category_hint(
            resume
        )
    )

    text = _resume_combined_text(
        resume
    )

    content_scores = {
        "SOFTWARE":
            _score_category_from_text(
                text,
                SOFTWARE_KEYWORDS
            ),

        "CORE":
            _score_category_from_text(
                text,
                CORE_KEYWORDS
            ),

        "AUTOMATION":
            _score_category_from_text(
                text,
                AUTOMATION_KEYWORDS
            ),
    }

    # Filename is deliberately strong,
    # because these are user-defined resume profiles.

    total_scores = {
        category:
            filename_scores[category]
            + content_scores[category]
        for category in filename_scores
    }

    best_category = max(
        total_scores,
        key=total_scores.get
    )

    if total_scores[best_category] == 0:

        best_category = "HYBRID"

    return {
        "category": best_category,

        "filename_scores":
            filename_scores,

        "content_scores":
            content_scores,

        "total_scores":
            total_scores,
    }


# ============================================================
# SKILL MATCHING
# ============================================================

def _resume_has_skill(
    resume_text,
    resume_keywords,
    skill
):

    canonical_skill = _canonical(
        skill
    )

    # Exact parsed skill match
    if canonical_skill in resume_keywords:
        return True

    # Raw text fallback
    if _contains_term(
        resume_text,
        canonical_skill
    ):
        return True

    # Alias fallback
    for alias, target in ALIASES.items():

        if target == canonical_skill:

            if _contains_term(
                resume_text,
                alias
            ):
                return True

    return False


def score_resume_for_job(
    resume,
    job
):

    resume_keywords = (
        _resume_keywords(
            resume
        )
    )

    resume_text = (
        _resume_combined_text(
            resume
        )
    )

    required = (
        _collect_required_skills(
            job
        )
    )

    preferred = (
        _collect_preferred_skills(
            job
        )
    )

    matched_required = sorted(
        skill
        for skill in required
        if _resume_has_skill(
            resume_text,
            resume_keywords,
            skill
        )
    )

    missing_required = sorted(
        required
        - set(matched_required)
    )

    matched_preferred = sorted(
        skill
        for skill in preferred
        if _resume_has_skill(
            resume_text,
            resume_keywords,
            skill
        )
    )

    # --------------------------------------------------------
    # SCORING
    # --------------------------------------------------------

    required_score = (
        len(matched_required)
        * 100
    )

    preferred_score = (
        len(matched_preferred)
        * 20
    )

    # Completion ratio matters.
    #
    # 5/5 required is significantly
    # better than 5/10 required.

    if required:

        required_ratio = (
            len(matched_required)
            / len(required)
        )

    else:

        required_ratio = 0.0

    completeness_bonus = int(
        required_ratio * 100
    )

    skill_score = (
        required_score
        + preferred_score
        + completeness_bonus
    )

    return {
        "score": skill_score,

        "skill_score": skill_score,

        "matched_required_skills":
            matched_required,

        "missing_required_skills":
            missing_required,

        "matched_preferred_skills":
            matched_preferred,

        "required_skill_count":
            len(required),

        "matched_required_count":
            len(matched_required),

        "preferred_skill_count":
            len(preferred),

        "matched_preferred_count":
            len(matched_preferred),

        "required_match_ratio":
            required_ratio,
    }


# ============================================================
# CATEGORY COMPATIBILITY
# ============================================================

def _category_compatibility(
    job_category,
    resume_category
):

    if job_category == "SOFTWARE":

        if resume_category == "SOFTWARE":
            return 10000

        if resume_category == "HYBRID":
            return 2000

        return 0

    if job_category == "CORE":

        if resume_category == "CORE":
            return 10000

        if resume_category == "HYBRID":
            return 2000

        if resume_category == "AUTOMATION":
            return 1000

        return 0

    if job_category == "AUTOMATION":

        if resume_category == "AUTOMATION":
            return 10000

        if resume_category == "HYBRID":
            return 2000

        if resume_category == "CORE":
            return 1000

        return 0

    # HYBRID job

    if resume_category == "HYBRID":
        return 5000

    return 1000


# ============================================================
# BEST RESUME
# ============================================================

def select_best_resume(
    resumes,
    job
):

    if not resumes:

        raise ValueError(
            "No resumes available."
        )

    classification = classify_job(
        job
    )

    job_category = (
        classification["category"]
    )

    results = []

    for resume in resumes:

        resume_classification = (
            classify_resume(
                resume
            )
        )

        resume_category = (
            resume_classification[
                "category"
            ]
        )

        skill_data = (
            score_resume_for_job(
                resume,
                job
            )
        )

        category_score = (
            _category_compatibility(
                job_category,
                resume_category
            )
        )

        final_score = (
            category_score
            + skill_data["skill_score"]
        )

        filename = resume.get(
            "_filename"
        )

        if not filename:

            filename = Path(
                resume.get(
                    "_file",
                    ""
                )
            ).name

        candidate = {

            # Original resume
            "resume":
                resume,

            # File information
            "filename":
                filename,

            "selected_filename":
                filename,

            "_file":
                resume.get(
                    "_file"
                ),

            "_absolute_path":
                resume.get(
                    "_absolute_path"
                ),

            # Categories
            "resume_category":
                resume_category,

            "resume_category_scores":
                resume_classification,

            # Scores
            "category_score":
                category_score,

            "skill_score":
                skill_data[
                    "skill_score"
                ],

            "resume_score":
                final_score,

            "score":
                final_score,

            # Required
            "matched_required_skills":
                skill_data[
                    "matched_required_skills"
                ],

            "missing_required_skills":
                skill_data[
                    "missing_required_skills"
                ],

            "required_skill_count":
                skill_data[
                    "required_skill_count"
                ],

            "matched_required_count":
                skill_data[
                    "matched_required_count"
                ],

            # Preferred
            "matched_preferred_skills":
                skill_data[
                    "matched_preferred_skills"
                ],

            "preferred_skill_count":
                skill_data[
                    "preferred_skill_count"
                ],

            "matched_preferred_count":
                skill_data[
                    "matched_preferred_count"
                ],

            "required_match_ratio":
                skill_data[
                    "required_match_ratio"
                ],

            "matched_keywords":
                (
                    skill_data[
                        "matched_required_skills"
                    ]
                    +
                    skill_data[
                        "matched_preferred_skills"
                    ]
                ),
        }

        results.append(
            candidate
        )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    results.sort(
        key=lambda item: (
            item["resume_score"],
            item["matched_required_count"],
            item["matched_preferred_count"],
            item["required_match_ratio"],
        ),
        reverse=True
    )

    best = results[0]

    # --------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------

    return {

        "job_category":
            job_category,

        "software_score":
            classification[
                "software_score"
            ],

        "core_score":
            classification[
                "core_score"
            ],

        "automation_score":
            classification[
                "automation_score"
            ],

        "classification_scores":
            classification[
                "classification_scores"
            ],

        # Selected resume
        "selected_resume":
            best["resume"],

        "selected_filename":
            best["filename"],

        "resume_category":
            best["resume_category"],

        "resume_score":
            best["resume_score"],

        # Required
        "matched_required_skills":
            best[
                "matched_required_skills"
            ],

        "missing_required_skills":
            best[
                "missing_required_skills"
            ],

        "matched_required_count":
            best[
                "matched_required_count"
            ],

        "required_skill_count":
            best[
                "required_skill_count"
            ],

        # Preferred
        "matched_preferred_skills":
            best[
                "matched_preferred_skills"
            ],

        "matched_preferred_count":
            best[
                "matched_preferred_count"
            ],

        "preferred_skill_count":
            best[
                "preferred_skill_count"
            ],

        "required_match_ratio":
            best[
                "required_match_ratio"
            ],

        "matched_keywords":
            best[
                "matched_keywords"
            ],

        # All candidates
        "all_candidates":
            results,
    }