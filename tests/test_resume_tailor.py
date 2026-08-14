from app.resume.resume_tailor import tailor_resume


def test_tailor_resume():

    resume = {
        "name": "GARNEPUDI NAVEEN SAI",
        "email": "garnepudinaveensai@gmail.com",
        "degree": "B.Tech",
        "skills": [
            "Python",
            "C",
            "Embedded C",
            "MATLAB",
            "Simulink",
            "Code Composer Studio",
            "TI C2000 F28379D",
            "ESP32",
            "GPIO",
            "ADC",
            "PWM",
            "DAC",
        ],
        "core_competencies": [
            "Power Electronics",
            "Electrical Engineering",
            "Electrical Equipment Monitoring",
            "Condition-Based Maintenance",
            "Predictive Maintenance",
            "Preventive Maintenance",
            "Reliability Engineering",
            "Thermography",
            "Vibration Analysis",
            "Industrial Automation",
            "Automation",
            "Energy Efficiency",
            "Technical Documentation",
        ],
    }

    job = {
        "title": "Graduate Engineer Trainee - Electrical",

        "required_skills": [
            "Python",
            "Electrical Engineering",
            "Predictive Maintenance",
            "TI C2000",
        ],

        "preferred_skills": [
            "Vibration Analysis",
            "Industrial Automation",
            "PLC",
        ],
    }

    result = tailor_resume(
        resume,
        job,
    )

    # --------------------------------------------------------
    # Basic validation
    # --------------------------------------------------------

    assert result["name"] == "GARNEPUDI NAVEEN SAI"

    assert (
        result["tailored_for"]
        == "Graduate Engineer Trainee - Electrical"
    )

    # --------------------------------------------------------
    # Supported required keywords
    # --------------------------------------------------------

    assert (
        "Python"
        in result["supported_required_keywords"]
    )

    assert (
        "Electrical Engineering"
        in result["supported_required_keywords"]
    )

    assert (
        "Predictive Maintenance"
        in result["supported_required_keywords"]
    )

    assert (
        "TI C2000"
        in result["supported_required_keywords"]
    )

    # --------------------------------------------------------
    # Supported preferred keywords
    # --------------------------------------------------------

    assert (
        "Vibration Analysis"
        in result["supported_preferred_keywords"]
    )

    assert (
        "Industrial Automation"
        in result["supported_preferred_keywords"]
    )

    # --------------------------------------------------------
    # Unsupported keyword must NOT be invented
    # --------------------------------------------------------

    assert (
        "PLC"
        in result["unsupported_preferred_keywords"]
    )

    # --------------------------------------------------------
    # Skills still come from original resume
    # --------------------------------------------------------

    for skill in result["tailored_skills"]:
        assert skill in resume["skills"]

    print("\nTailored Resume:")
    print(result)