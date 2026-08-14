from app.resume.resume_manager import ResumeManager
from app.parser.job_parser import parse_job
from app.core.resume_selector import select_best_resume


def test_multiple_resume_selection():

    manager = ResumeManager(
        "resumes"
    )

    resumes = manager.load_all_resumes()

    assert len(resumes) == 3

    filenames = {
        resume["_filename"]
        for resume in resumes
    }

    assert "technical_resume.pdf" in filenames
    assert "software_resume.pdf" in filenames
    assert "automation_embedded_resume.pdf" in filenames

    # --------------------------------------------------
    # SOFTWARE JOB
    # --------------------------------------------------

    software_job_text = """
    Python Software Developer

    Required Skills:
    Python
    SQL
    Git
    Software Development
    REST API

    Preferred Skills:
    Django
    Testing
    """

    software_job = parse_job(
        software_job_text
    )

    software_result = select_best_resume(
        resumes,
        software_job,
    )

    print("\nSOFTWARE JOB RESULT:")
    print(software_result)

    assert software_result[
        "job_category"
    ] == "SOFTWARE"

    assert software_result[
        "selected_filename"
    ] == "software_resume.pdf"

    # --------------------------------------------------
    # CORE / ELECTRICAL JOB
    # --------------------------------------------------

    core_job_text = """
    Graduate Engineer Trainee - Electrical

    Required Skills:
    Electrical Engineering
    Power Electronics
    Predictive Maintenance
    Condition-Based Maintenance

    Preferred Skills:
    Thermography
    Vibration Analysis
    MATLAB
    """

    core_job = parse_job(
        core_job_text
    )

    core_result = select_best_resume(
        resumes,
        core_job,
    )

    print("\nCORE JOB RESULT:")
    print(core_result)

    assert core_result[
        "job_category"
    ] == "CORE"

    assert core_result[
        "selected_filename"
    ] == "technical_resume.pdf"

    # --------------------------------------------------
    # AUTOMATION JOB
    # --------------------------------------------------

    automation_job_text = """
    Automation Engineer

    Required Skills:
    PLC
    SCADA
    Industrial Automation
    Control Systems

    Preferred Skills:
    HMI
    VFD
    Siemens TIA Portal
    """

    automation_job = parse_job(
        automation_job_text
    )

    automation_result = select_best_resume(
        resumes,
        automation_job,
    )

    print("\nAUTOMATION JOB RESULT:")
    print(automation_result)

    assert automation_result[
        "job_category"
    ] == "AUTOMATION"

    assert automation_result[
        "selected_filename"
    ] == "automation_embedded_resume.pdf"