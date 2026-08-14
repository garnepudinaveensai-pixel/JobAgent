from pathlib import Path

from app.resume.resume_pdf import generate_resume_pdf


def test_generate_resume_pdf(tmp_path):

    resume_data = {
        "name": "GARNEPUDI NAVEEN SAI",
        "email": "garnepudinaveensai@gmail.com",
        "phone": "+91 8688042159",
        "location": "India",

        "professional_summary": (
            "Electrical Engineering graduate with hands-on "
            "experience in predictive maintenance, electrical "
            "equipment monitoring, automation and embedded systems."
        ),

        "education": [
            {
                "degree": "B.Tech Electrical Engineering",
                "institution": "University College of Engineering, Kakinada",
                "duration": "2022 - 2026",
            }
        ],

        "skills": [
            "Python",
            "C",
            "Embedded C",
            "MATLAB",
            "Simulink",
            "Code Composer Studio",
            "TI C2000 F28379D",
            "Industrial Automation",
            "Predictive Maintenance",
            "Vibration Analysis",
        ],

        "experience": [
            {
                "title": "CBM Junior Intern",
                "company": "Adani Cement",
                "duration": "Jan 2026 - Apr 2026",
                "description": [
                    "Supported condition-based monitoring.",
                    "Performed equipment inspections.",
                    "Assisted with reliability analysis.",
                ],
            }
        ],

        "projects": [
            {
                "title": "Predictive Maintenance of Motors",
                "description": [
                    "Developed a prototype approach for motor condition monitoring.",
                    "Analysed equipment parameters for predictive maintenance.",
                ],
            }
        ],

        "certifications": [
            "Digital Controller for Power Applications - IIT Bhubaneswar",
        ],
    }

    output_path = (
        tmp_path / "test_tailored_resume.pdf"
    )

    result = generate_resume_pdf(
        resume_data,
        output_path,
    )

    assert result.exists()
    assert result.suffix.lower() == ".pdf"
    assert result.stat().st_size > 0

    print(
        f"\nGenerated resume: {result}"
    )