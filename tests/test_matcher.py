from app.parser.resume_parser import parse_resume
from app.parser.job_parser import parse_job
from app.core.matcher import match_job


# ============================================================
# HELPER
# ============================================================

def run_match(resume_text, job_text):
    resume = parse_resume(resume_text)
    job = parse_job(job_text)

    return match_job(resume, job)


# ============================================================
# TEST 1 — STRONG MATCH
# ============================================================

def test_strong_match():

    resume_text = """
    GARNEPUDI NAVEEN SAI

    B.Tech Electrical Engineering

    Skills:
    Python, C, Embedded C, MATLAB, Simulink,
    Code Composer Studio, TI C2000 F28379D,
    Electrical Engineering, Predictive Maintenance,
    Vibration Analysis, Industrial Automation
    """

    job_text = """
    Electrical Engineer / Graduate Engineer Trainee

    Required Skills:
    Python
    C
    Electrical Engineering
    Predictive Maintenance
    TI C2000

    Preferred Skills:
    Vibration Analysis
    Industrial Automation
    PLC

    Experience:
    Fresh graduates are encouraged to apply.
    """

    result = run_match(resume_text, job_text)

    assert result["eligible"] is True

    assert "Python" in result["matched_required_skills"]
    assert "C" in result["matched_required_skills"]
    assert "Electrical Engineering" in result["matched_required_skills"]
    assert "Predictive Maintenance" in result["matched_required_skills"]
    assert "TI C2000" in result["matched_required_skills"]

    assert "Vibration Analysis" in result["matched_preferred_skills"]
    assert "Industrial Automation" in result["matched_preferred_skills"]

    assert "PLC" in result["missing_preferred_skills"]

    assert result["recommendation"] == "APPLY"
    assert result["match_score"] > 0


# ============================================================
# TEST 2 — MISSING REQUIRED SKILLS
# ============================================================

def test_missing_required_skills():

    resume_text = """
    B.Tech Electrical Engineering

    Skills:
    Python
    C
    MATLAB
    Electrical Engineering
    """

    job_text = """
    Electrical Engineer

    Required Skills:
    Python
    C
    Electrical Engineering
    Predictive Maintenance
    TI C2000

    Preferred Skills:
    PLC
    SCADA
    """

    result = run_match(resume_text, job_text)

    assert "Python" in result["matched_required_skills"]
    assert "C" in result["matched_required_skills"]

    assert "Predictive Maintenance" in result["missing_required_skills"]
    assert "TI C2000" in result["missing_required_skills"]

    assert result["eligible"] is False


# ============================================================
# TEST 3 — UNRELATED JOB
# ============================================================

def test_unrelated_job():

    resume_text = """
    B.Tech Electrical Engineering

    Skills:
    Electrical Engineering
    Power Electronics
    MATLAB
    Embedded C
    """

    job_text = """
    Full Stack Software Developer

    Required Skills:
    Java
    Spring Boot
    React
    Node.js
    MongoDB

    Preferred Skills:
    AWS
    Docker
    Kubernetes
    """

    result = run_match(resume_text, job_text)

    assert result["match_score"] < 50

    assert result["recommendation"] in [
        "SKIP",
        "MAYBE",
    ]


# ============================================================
# TEST 4 — PREFERRED SKILL MISSING
# ============================================================

def test_missing_preferred_skill_does_not_fail_required_match():

    resume_text = """
    B.Tech Electrical Engineering

    Skills:
    Python
    C
    Electrical Engineering
    Predictive Maintenance
    TI C2000
    """

    job_text = """
    Graduate Engineer Trainee

    Required Skills:
    Python
    C
    Electrical Engineering
    Predictive Maintenance
    TI C2000

    Preferred Skills:
    PLC
    SCADA
    Industrial Automation
    """

    result = run_match(resume_text, job_text)

    assert result["eligible"] is True

    assert result["recommendation"] == "APPLY"

    assert "PLC" in result["missing_preferred_skills"]
    assert "SCADA" in result["missing_preferred_skills"]

    assert "Industrial Automation" in result["missing_preferred_skills"]


# ============================================================
# TEST 5 — CASE DIFFERENCE
# ============================================================

def test_case_insensitive_matching():

    resume_text = """
    B.Tech Electrical Engineering

    Skills:
    python
    c
    electrical engineering
    predictive maintenance
    ti c2000
    """

    job_text = """
    Electrical Engineer

    Required Skills:
    Python
    C
    Electrical Engineering
    Predictive Maintenance
    TI C2000
    """

    result = run_match(resume_text, job_text)

    assert result["eligible"] is True

    assert "Python" in result["matched_required_skills"]
    assert "C" in result["matched_required_skills"]
    assert "Electrical Engineering" in result["matched_required_skills"]
    assert "Predictive Maintenance" in result["matched_required_skills"]
    assert "TI C2000" in result["matched_required_skills"]


# ============================================================
# TEST 6 — PARTIAL MATCH
# ============================================================

def test_partial_match():

    resume_text = """
    B.Tech Electrical Engineering

    Skills:
    Python
    C
    MATLAB
    Electrical Engineering
    """

    job_text = """
    Electrical Engineer

    Required Skills:
    Python
    C
    Electrical Engineering
    MATLAB
    Predictive Maintenance
    TI C2000
    """

    result = run_match(resume_text, job_text)

    assert "Python" in result["matched_required_skills"]
    assert "C" in result["matched_required_skills"]
    assert "Electrical Engineering" in result["matched_required_skills"]
    assert "MATLAB" in result["matched_required_skills"]

    assert "Predictive Maintenance" in result["missing_required_skills"]
    assert "TI C2000" in result["missing_required_skills"]

    assert result["match_score"] > 0


# ============================================================
# TEST 7 — AUTOMATION JOB
# ============================================================

def test_automation_job():

    resume_text = """
    B.Tech Electrical Engineering

    Skills:
    Electrical Engineering
    Industrial Automation
    Automation
    Predictive Maintenance
    Vibration Analysis
    Python
    MATLAB
    """

    job_text = """
    Automation Engineer

    Required Skills:
    Electrical Engineering
    Industrial Automation
    Python

    Preferred Skills:
    Predictive Maintenance
    Vibration Analysis
    PLC
    """

    result = run_match(resume_text, job_text)

    assert result["eligible"] is True

    assert "Electrical Engineering" in result["matched_required_skills"]
    assert "Industrial Automation" in result["matched_required_skills"]
    assert "Python" in result["matched_required_skills"]

    assert "Predictive Maintenance" in result["matched_preferred_skills"]
    assert "Vibration Analysis" in result["matched_preferred_skills"]

    assert "PLC" in result["missing_preferred_skills"]

    assert result["recommendation"] == "APPLY"


# ============================================================
# TEST 8 — COMPLETELY EMPTY SKILL MATCH
# ============================================================

def test_no_skill_match():

    resume_text = """
    B.Tech Electrical Engineering

    Skills:
    Electrical Engineering
    MATLAB
    Power Electronics
    """

    job_text = """
    Software Engineer

    Required Skills:
    Java
    React
    Node.js
    MongoDB
    """

    result = run_match(resume_text, job_text)

    assert len(result["matched_required_skills"]) == 0

    assert len(result["missing_required_skills"]) > 0

    assert result["eligible"] is False

    assert result["recommendation"] == "SKIP"


# ============================================================
# TEST 9 — RESULT STRUCTURE
# ============================================================

def test_matcher_result_structure():

    resume_text = """
    B.Tech Electrical Engineering

    Skills:
    Python
    C
    Electrical Engineering
    """

    job_text = """
    Electrical Engineer

    Required Skills:
    Python
    Electrical Engineering

    Preferred Skills:
    MATLAB
    """

    result = run_match(resume_text, job_text)

    required_keys = {
        "eligible",
        "matched_required_skills",
        "missing_required_skills",
        "matched_preferred_skills",
        "missing_preferred_skills",
        "match_score",
        "recommendation",
    }

    assert required_keys.issubset(result.keys())


# ============================================================
# TEST 10 — SCORE IS VALID
# ============================================================

def test_score_range():

    resume_text = """
    B.Tech Electrical Engineering

    Skills:
    Python
    C
    Electrical Engineering
    """

    job_text = """
    Electrical Engineer

    Required Skills:
    Python
    C
    Electrical Engineering
    """

    result = run_match(resume_text, job_text)

    assert isinstance(result["match_score"], (int, float))

    assert 0 <= result["match_score"] <= 100