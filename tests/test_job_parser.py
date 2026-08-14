from app.parser.job_parser import parse_job_description


def test_parse_job_description():

    job_description = """
    Job Title: Graduate Engineer Trainee

    Requirements:
    - B.Tech in Electrical Engineering
    - Python
    - C
    - MATLAB
    - Industrial Automation
    - Power Electronics
    - TI C2000

    Preferred Skills:
    - Predictive Maintenance
    - Vibration Analysis

    Experience:
    0-1 years of experience
    """

    job = parse_job_description(job_description)

    assert job["job_title"]

    assert job["degree_requirements"]

    assert "Python" in job["required_skills"]

    assert "C" in job["required_skills"]

    assert "MATLAB" in job["required_skills"]

    assert "Industrial Automation" in job["required_skills"]

    assert "Power Electronics" in job["required_skills"]

    assert "TI C2000" in job["required_skills"]

    assert "Predictive Maintenance" in job["preferred_skills"]

    assert "Vibration Analysis" in job["preferred_skills"]

    assert job["experience_requirements"]

    assert job["all_keywords"]

    print("\nParsed Job Description:")
    print(job)