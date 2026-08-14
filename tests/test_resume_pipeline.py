from pathlib import Path

from app.parser.job_parser import parse_job
from app.resume.resume_manager import ResumeManager
from app.core.resume_selector import (
    classify_job,
    classify_resume,
    select_best_resume,
)


# ============================================================
# LOAD RESUMES
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RESUME_DIRECTORY = (
    PROJECT_ROOT / "resumes"
)


def load_resumes():

    manager = ResumeManager(
        resume_directory=RESUME_DIRECTORY
    )

    resumes = (
        manager.load_all_resumes()
    )

    print()
    print(
        f"Resume directory: "
        f"{RESUME_DIRECTORY}"
    )

    print(
        f"Found resumes: "
        f"{len(resumes)}"
    )

    for resume in resumes:

        classification = (
            classify_resume(
                resume
            )
        )

        print(
            f"  {resume['_filename']}"
            f" -> "
            f"{classification['category']}"
        )

    assert len(resumes) >= 3, (
        f"Expected at least 3 resumes, "
        f"found {len(resumes)}"
    )

    return resumes


# ============================================================
# DEBUG PRINT
# ============================================================

def print_selection_result(
    title,
    result
):

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    print(
        "Job category:",
        result["job_category"]
    )

    print(
        "Selected resume:",
        result["selected_filename"]
    )

    print(
        "Resume category:",
        result["resume_category"]
    )

    print(
        "Resume score:",
        result["resume_score"]
    )

    print(
        "Required:",
        result["matched_required_count"],
        "/",
        result["required_skill_count"]
    )

    print(
        "Matched required:",
        result[
            "matched_required_skills"
        ]
    )

    print(
        "Missing required:",
        result[
            "missing_required_skills"
        ]
    )

    print(
        "Matched preferred:",
        result[
            "matched_preferred_skills"
        ]
    )

    print()
    print("Candidate ranking:")

    for candidate in result[
        "all_candidates"
    ]:

        print(
            f"  {candidate['filename']}"
            f" | category="
            f"{candidate['resume_category']}"
            f" | score="
            f"{candidate['score']}"
            f" | skill="
            f"{candidate['skill_score']}"
            f" | required="
            f"{candidate['matched_required_count']}"
            f"/"
            f"{candidate['required_skill_count']}"
        )


# ============================================================
# SOFTWARE
# ============================================================

def test_software_job_selects_software_resume():

    resumes = load_resumes()

    job_text = """
    Software Engineer / Graduate Engineer Trainee

    Required Skills:
    Python
    SQL
    Git
    REST API
    Software Development

    Preferred Skills:
    JavaScript
    Testing
    Data Structures
    Algorithms

    Experience:
    Fresh graduates with programming projects
    are encouraged to apply.
    """

    job = parse_job(
        job_text
    )

    classification = (
        classify_job(job)
    )

    print(
        "\nSoftware classification:",
        classification
    )

    assert (
        classification["category"]
        == "SOFTWARE"
    )

    result = select_best_resume(
        resumes,
        job
    )

    print_selection_result(
        "SOFTWARE JOB",
        result
    )

    selected_file = (
        result[
            "selected_filename"
        ].lower()
    )

    assert (
        "software"
        in selected_file
    )

    assert (
        result[
            "resume_category"
        ]
        == "SOFTWARE"
    )


# ============================================================
# CORE ELECTRICAL
# ============================================================

def test_core_job_selects_technical_resume():

    resumes = load_resumes()

    job_text = """
    Electrical Engineer / Graduate Engineer Trainee

    Required Skills:
    Electrical Engineering
    Power Electronics
    Predictive Maintenance
    Condition-Based Maintenance
    Reliability Engineering

    Preferred Skills:
    Thermography
    Vibration Analysis
    Electrical Signature Analysis

    Experience:
    Fresh graduates with relevant industrial
    internship experience are encouraged to apply.
    """

    job = parse_job(
        job_text
    )

    classification = (
        classify_job(job)
    )

    print(
        "\nCore classification:",
        classification
    )

    assert (
        classification["category"]
        == "CORE"
    )

    result = select_best_resume(
        resumes,
        job
    )

    print_selection_result(
        "CORE ELECTRICAL JOB",
        result
    )

    selected_file = (
        result[
            "selected_filename"
        ].lower()
    )

    assert (
        "technical"
        in selected_file
    )

    assert (
        result[
            "resume_category"
        ]
        == "CORE"
    )


# ============================================================
# EMBEDDED / AUTOMATION
# ============================================================

def test_embedded_automation_job_selects_automation_resume():

    resumes = load_resumes()

    job_text = """
    Embedded Systems and Automation Engineer

    Required Skills:
    Embedded C
    TI C2000
    F28379D
    ESP32
    GPIO
    ADC
    PWM
    MATLAB
    Simulink

    Preferred Skills:
    Industrial Automation
    PLC
    Microcontroller
    Power Electronics

    Experience:
    Fresh graduates with embedded systems
    projects and internships are encouraged.
    """

    job = parse_job(
        job_text
    )

    classification = (
        classify_job(job)
    )

    print(
        "\nAutomation classification:",
        classification
    )

    assert (
        classification["category"]
        == "AUTOMATION"
    )

    result = select_best_resume(
        resumes,
        job
    )

    print_selection_result(
        "EMBEDDED / AUTOMATION JOB",
        result
    )

    selected_file = (
        result[
            "selected_filename"
        ].lower()
    )

    assert (
        "automation"
        in selected_file
    )

    assert (
        result[
            "resume_category"
        ]
        == "AUTOMATION"
    )


# ============================================================
# RESUME LIBRARY TEST
# ============================================================

def test_resume_library_contains_expected_profiles():

    resumes = load_resumes()

    filenames = {
        resume[
            "_filename"
        ].lower()
        for resume in resumes
    }

    assert any(
        "software"
        in filename
        for filename in filenames
    )

    assert any(
        "technical"
        in filename
        for filename in filenames
    )

    assert any(
        "automation"
        in filename
        for filename in filenames
    )