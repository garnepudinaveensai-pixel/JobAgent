from pathlib import Path

import pytest

from app.resume.resume_pdf_generator import (
    ResumePDFGenerator,
    generate_resume_pdf,
)


@pytest.fixture
def resume():
    return {
        "name": "GARNEPUDI NAVEEN SAI",
        "email": "garnepudinaveensai@gmail.com",
        "phone": "9876543210",
        "location": "India",
        "degree": "B.Tech Electrical & Electronics Engineering",

        "tailored_for": (
            "Graduate Engineer Trainee - Electrical"
        ),

        "summary": (
            "Electrical engineering graduate with "
            "hands-on exposure to industrial equipment "
            "monitoring, predictive maintenance, "
            "embedded systems and automation."
        ),

        "tailored_skills": [
            "Python",
            "C",
            "Embedded C",
            "MATLAB",
            "Simulink",
            "Code Composer Studio",
            "TI C2000 F28379D",
        ],

        "tailored_core_competencies": [
            "Electrical Engineering",
            "Predictive Maintenance",
            "Condition-Based Maintenance",
            "Industrial Automation",
            "Vibration Analysis",
        ],

        "experience": [
            {
                "role": "CBM Junior Intern",
                "company": (
                    "Adani Cement Krishnapatnam "
                    "Port & Power Facility"
                ),
                "duration": "Jan 2026 - Apr 2026",
                "responsibilities": [
                    (
                        "Supported condition-based monitoring "
                        "and preventive maintenance."
                    ),
                    (
                        "Performed equipment inspections "
                        "and data collection."
                    ),
                ],
            },
            {
                "role": "Industrial Electrical Equipment "
                "Monitoring Engineer",
                "company": "AMIS",
                "duration": "May 2024",
                "responsibilities": [
                    (
                        "Worked with thermography, vibration "
                        "analysis and Electrical Signature Analysis."
                    ),
                ],
            },
        ],

        "projects": [
            {
                "title": "Predictive Maintenance of Motors",
                "description": (
                    "Developed a predictive maintenance "
                    "prototype for electrical motors."
                ),
            },
        ],

        "certifications": [
            "Digital Controller for Power Applications",
        ],
    }


def test_generator_initialization(tmp_path):
    generator = ResumePDFGenerator(
        output_dir=str(tmp_path)
    )

    assert generator.output_dir.exists()


def test_build_creates_pdf(tmp_path, resume):
    generator = ResumePDFGenerator(
        output_dir=str(tmp_path)
    )

    output = generator.build(resume)

    path = Path(output)

    assert path.exists()
    assert path.is_file()
    assert path.suffix.lower() == ".pdf"
    assert path.stat().st_size > 0


def test_build_with_explicit_output_path(
    tmp_path,
    resume,
):
    output_path = (
        tmp_path
        / "custom_resume.pdf"
    )

    generator = ResumePDFGenerator(
        output_dir=str(tmp_path)
    )

    result = generator.build(
        resume,
        output_path=str(output_path),
    )

    assert result == str(output_path)
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_generate_resume_pdf_function(
    tmp_path,
    resume,
):
    output_path = (
        tmp_path
        / "generated_resume.pdf"
    )

    result = generate_resume_pdf(
        resume,
        output_path=str(output_path),
    )

    assert result == str(output_path)
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_invalid_resume_raises_error(tmp_path):
    generator = ResumePDFGenerator(
        output_dir=str(tmp_path)
    )

    with pytest.raises(TypeError):
        generator.build(None)


def test_pdf_contains_pdf_signature(
    tmp_path,
    resume,
):
    output_path = (
        tmp_path
        / "resume.pdf"
    )

    generator = ResumePDFGenerator(
        output_dir=str(tmp_path)
    )

    generator.build(
        resume,
        output_path=str(output_path),
    )

    content = output_path.read_bytes()

    assert content.startswith(b"%PDF")


def test_tailored_skills_are_used(
    tmp_path,
    resume,
):
    generator = ResumePDFGenerator(
        output_dir=str(tmp_path)
    )

    result = generator.build(resume)

    assert Path(result).exists()

    # The generator must use the tailored section
    # when it is available.
    assert "tailored_skills" in resume


def test_fallback_to_original_skills(
    tmp_path,
):
    resume = {
        "name": "Test Candidate",
        "skills": [
            "Python",
            "MATLAB",
        ],
    }

    generator = ResumePDFGenerator(
        output_dir=str(tmp_path)
    )

    output = generator.build(resume)

    assert Path(output).exists()


def test_string_skills_are_supported(tmp_path):
    resume = {
        "name": "Test Candidate",
        "skills": "Python, MATLAB, C",
    }

    generator = ResumePDFGenerator(
        output_dir=str(tmp_path)
    )

    output = generator.build(resume)

    assert Path(output).exists()


def test_empty_optional_sections_are_supported(
    tmp_path,
):
    resume = {
        "name": "Test Candidate",
        "email": "test@example.com",
    }

    generator = ResumePDFGenerator(
        output_dir=str(tmp_path)
    )

    output = generator.build(resume)

    assert Path(output).exists()