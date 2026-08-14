from app.resume.resume_tailor import tailor_resume


def test_specific_resume_skill_supports_general_job_keyword():

    resume = {
        "skills": [
            "TI C2000 F28379D",
        ],
        "core_competencies": [],
    }

    job = {
        "title": "Embedded Engineer",
        "required_skills": [
            "TI C2000",
        ],
        "preferred_skills": [],
    }

    result = tailor_resume(
        resume,
        job,
    )

    assert result["eligible"] is True

    assert (
        "TI C2000"
        in result["supported_required_keywords"]
    )

    assert (
        "TI C2000 F28379D"
        in result["tailored_skills"]
    )


def test_case_insensitive_matching():

    resume = {
        "skills": [
            "PYTHON",
        ],
        "core_competencies": [],
    }

    job = {
        "title": "Python Developer",
        "required_skills": [
            "python",
        ],
        "preferred_skills": [],
    }

    result = tailor_resume(
        resume,
        job,
    )

    assert result["eligible"] is True


def test_missing_required_skill():

    resume = {
        "skills": [
            "Python",
        ],
        "core_competencies": [],
    }

    job = {
        "title": "Automation Engineer",
        "required_skills": [
            "Python",
            "PLC",
        ],
        "preferred_skills": [],
    }

    result = tailor_resume(
        resume,
        job,
    )

    assert result["eligible"] is False

    assert (
        "Python"
        in result["supported_required_keywords"]
    )

    assert (
        "PLC"
        in result["unsupported_required_keywords"]
    )


def test_missing_preferred_skill_does_not_make_ineligible():

    resume = {
        "skills": [
            "Python",
        ],
        "core_competencies": [],
    }

    job = {
        "title": "Python Developer",
        "required_skills": [
            "Python",
        ],
        "preferred_skills": [
            "Django",
        ],
    }

    result = tailor_resume(
        resume,
        job,
    )

    assert result["eligible"] is True

    assert (
        "Django"
        in result["unsupported_preferred_keywords"]
    )


def test_core_competency_supports_job_requirement():

    resume = {
        "skills": [],
        "core_competencies": [
            "Predictive Maintenance",
        ],
    }

    job = {
        "title": "Reliability Engineer",
        "required_skills": [
            "Predictive Maintenance",
        ],
        "preferred_skills": [],
    }

    result = tailor_resume(
        resume,
        job,
    )

    assert result["eligible"] is True

    assert (
        "Predictive Maintenance"
        in result["supported_required_keywords"]
    )


def test_no_skill_is_invented():

    resume = {
        "skills": [
            "Python",
        ],
        "core_competencies": [],
    }

    job = {
        "title": "Software Engineer",
        "required_skills": [
            "Python",
        ],
        "preferred_skills": [
            "Django",
            "AWS",
        ],
    }

    result = tailor_resume(
        resume,
        job,
    )

    assert "Django" not in result["tailored_skills"]
    assert "AWS" not in result["tailored_skills"]

    assert "Python" in result["tailored_skills"]


def test_duplicate_resume_skills_are_removed():

    resume = {
        "skills": [
            "Python",
            "python",
            "Python",
        ],
        "core_competencies": [],
    }

    job = {
        "title": "Python Developer",
        "required_skills": [
            "Python",
        ],
        "preferred_skills": [],
    }

    result = tailor_resume(
        resume,
        job,
    )

    assert result["tailored_skills"] == [
        "Python"
    ]


def test_empty_inputs_are_safe():

    result = tailor_resume(
        {},
        {},
    )

    assert result["tailored_for"] == ""

    assert result["supported_required_keywords"] == []

    assert result["unsupported_required_keywords"] == []

    assert result["supported_preferred_keywords"] == []

    assert result["unsupported_preferred_keywords"] == []

    assert result["tailored_skills"] == []


def test_original_resume_is_not_modified():

    resume = {
        "name": "Sai",
        "skills": [
            "Python",
            "C",
        ],
        "core_competencies": [
            "Electrical Engineering",
        ],
    }

    original_skills = list(
        resume["skills"]
    )

    original_competencies = list(
        resume["core_competencies"]
    )

    job = {
        "title": "Engineer",
        "required_skills": [
            "Python",
        ],
        "preferred_skills": [
            "PLC",
        ],
    }

    tailor_resume(
        resume,
        job,
    )

    assert resume["skills"] == original_skills

    assert (
        resume["core_competencies"]
        == original_competencies
    )