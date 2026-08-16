from app.core.job_parser import (
    extract_experience_requirements,
    extract_skills,
    parse_job,
)


def test_extract_skills():
    text = """
    We are looking for an Electrical Engineer
    with Python, MATLAB, Simulink and
    predictive maintenance experience.
    """

    skills = extract_skills(text)

    assert "Python" in skills
    assert "MATLAB" in skills
    assert "Simulink" in skills
    assert "Predictive Maintenance" in skills


def test_extract_experience():
    job = {
        "title": "Electrical Engineer",
        "description": (
            "Requires 2+ years of experience "
            "in electrical maintenance."
        ),
    }

    result = extract_experience_requirements(
        job
    )

    assert "2+ years of experience" in result


def test_parse_job_preserves_fields():
    job = {
        "title": "Electrical Engineer",
        "company": "Example",
        "location": "Hyderabad",
        "url": "https://example.com/job",
        "description": (
            "Requires Python and MATLAB."
        ),
    }

    result = parse_job(job)

    assert result["title"] == (
        "Electrical Engineer"
    )

    assert result["company"] == (
        "Example"
    )

    assert "Python" in result["all_keywords"]
    assert "MATLAB" in result["all_keywords"]


def test_parse_job_preserves_existing_skills():
    job = {
        "title": "Automation Engineer",
        "description": "PLC automation role.",
        "required_skills": [
            "PLC",
        ],
        "preferred_skills": [
            "SCADA",
        ],
    }

    result = parse_job(job)

    assert result["required_skills"] == [
        "PLC"
    ]

    assert result["preferred_skills"] == [
        "SCADA"
    ]


def test_parse_invalid_job():
    assert parse_job(None) == {}
    assert parse_job("invalid") == {}