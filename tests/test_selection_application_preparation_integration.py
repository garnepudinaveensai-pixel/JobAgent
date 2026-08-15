from pathlib import Path

from app.core.application_workflow import ApplicationWorkflow
from app.core.job_agent import JobAgent
from app.jobs.job_store import JobStore


# ============================================================
# TEST DATA
# ============================================================

def sample_job():
    return {
        "title": "Electrical Engineer",
        "company": "Example Energy",
        "location": "Hyderabad",
        "description": (
            "Electrical engineering role involving "
            "industrial equipment, maintenance, automation, "
            "power systems and condition-based maintenance."
        ),
        "required_skills": [
            "Electrical Engineering",
            "Maintenance",
            "Automation",
        ],
        "preferred_skills": [
            "MATLAB",
            "Power Electronics",
        ],
        "experience_requirements": "0-2 years",
        "url": (
            "https://example.com/jobs/"
            "electrical-engineer"
        ),
    }


def sample_resume():
    return {
        "name": "Naveen Sai",
        "degree": (
            "B.Tech Electrical & Electronics Engineering"
        ),
        "skills": [
            "Electrical Engineering",
            "Maintenance",
            "Automation",
            "MATLAB",
            "Power Electronics",
            "Embedded C",
            "C",
            "Python",
        ],
        "experience": [
            {
                "company": "Industrial Company",
                "role": "Condition-Based Maintenance Intern",
                "description": (
                    "Electrical equipment monitoring, "
                    "condition-based maintenance, "
                    "vibration analysis and industrial "
                    "equipment inspection."
                ),
            }
        ],
        "_filename": "master_resume.pdf",
        "_file": "resumes/master_resume.pdf",
        "_raw_text": (
            "Naveen Sai\n"
            "B.Tech Electrical & Electronics Engineering\n"
            "Electrical Engineering\n"
            "Maintenance\n"
            "Automation\n"
            "MATLAB\n"
            "Power Electronics\n"
            "Embedded C\n"
            "Python\n"
        ),
    }


# ============================================================
# FAKE SUBMITTER
# ============================================================

class FakeApplicationSubmitter:
    """
    Fake browser submitter.

    This test double allows us to verify the complete
    application-preparation workflow without opening a
    real browser or submitting a real application.
    """

    instances = []

    def __init__(self, page):
        self.page = page
        self.opened_url = None
        self.prepared = False
        self.submitted = False
        self.resume_path = None
        self.fields = None

        FakeApplicationSubmitter.instances.append(
            self
        )

    def open(self, url):
        self.opened_url = url

    def prepare_application(
        self,
        resume_path,
        fields,
    ):
        self.resume_path = resume_path
        self.fields = fields
        self.prepared = True

        return {
            "filled_fields": list(
                fields.keys()
            ),
            "resume_uploaded": True,
            "validation": {
                "ready": True,
            },
            "status": "prepared",
            "success": True,
        }

    def submit(self, confirm=False):
        self.submitted = True

        if not confirm:
            return {
                "success": False,
                "status": "confirmation_required",
            }

        return {
            "success": True,
            "status": "applied",
        }


# ============================================================
# FAKE PAGE
# ============================================================

class FakePage:
    """
    Placeholder page object.

    The ApplicationWorkflow only passes this object to the
    submitter factory during this integration test.
    """

    pass


# ============================================================
# FAKE RESUME TAILORING / PDF GENERATION
# ============================================================

def fake_tailor_resume(
    resume,
    job,
):
    """
    Deterministic resume tailoring function for testing.

    It preserves the original resume and adds job-specific
    metadata.
    """

    tailored = dict(resume)

    tailored["target_job"] = job.get(
        "title",
        "",
    )

    tailored["target_company"] = job.get(
        "company",
        "",
    )

    tailored["tailored"] = True

    return tailored


def fake_generate_resume_pdf(
    resume,
    output_path,
):
    """
    Fake PDF generator.

    Creates a small placeholder file so the integration test
    can verify that the workflow produced a PDF path.
    """

    path = Path(output_path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        b"%PDF-1.4\n"
        b"% JobAgent integration test PDF\n"
    )

    return str(path)


# ============================================================
# APPLICATION WORKFLOW FACTORY
# ============================================================

def make_workflow(
    monkeypatch,
):
    """
    Create an ApplicationWorkflow with deterministic
    resume-tailoring and PDF-generation behavior.
    """

    monkeypatch.setattr(
        "app.core.application_workflow.tailor_resume",
        fake_tailor_resume,
    )

    monkeypatch.setattr(
        "app.core.application_workflow.generate_resume_pdf",
        fake_generate_resume_pdf,
    )

    FakeApplicationSubmitter.instances.clear()

    return ApplicationWorkflow(
        submitter_factory=FakeApplicationSubmitter,
    )


# ============================================================
# SELECTION
# ============================================================

def test_job_can_be_selected_after_matching(tmp_path):
    store = JobStore(
        storage_path=str(
            tmp_path
            / "jobs.json"
        )
    )

    agent = JobAgent(
        job_store=store,
    )

    job = sample_job()

    job_id = agent.add_job(
        job,
        status="discovered",
    )

    resume = sample_resume()

    match_result = agent.match_and_store(
        resume=resume,
        job_id=job_id,
    )

    assert isinstance(
        match_result,
        dict,
    )

    assert store.get_status(
        job_id
    ) == "matched"

    selected = agent.select_job(
        job_id
    )

    assert selected is True

    assert store.get_status(
        job_id
    ) == "selected"


# ============================================================
# RESUME TAILORING + PDF GENERATION
# ============================================================

def test_tailor_and_generate_resume(
    tmp_path,
    monkeypatch,
):
    workflow = make_workflow(
        monkeypatch
    )

    output_path = (
        tmp_path
        / "tailored"
        / "electrical_engineer.pdf"
    )

    result = workflow.tailor_and_generate_resume(
        resume=sample_resume(),
        job=sample_job(),
        output_path=str(output_path),
    )

    assert isinstance(
        result,
        dict,
    )

    assert "resume" in result
    assert "pdf_path" in result

    assert result["resume"]["tailored"] is True

    assert result["resume"]["target_job"] == (
        "Electrical Engineer"
    )

    assert result["resume"]["target_company"] == (
        "Example Energy"
    )

    generated_pdf = Path(
        result["pdf_path"]
    )

    assert generated_pdf.exists()
    assert generated_pdf.is_file()


# ============================================================
# APPLICATION PREPARATION
# ============================================================

def test_prepare_application_full_flow(
    tmp_path,
    monkeypatch,
):
    workflow = make_workflow(
        monkeypatch
    )

    page = FakePage()

    job = sample_job()
    resume = sample_resume()

    fields = {
        "full_name": "Naveen Sai",
        "email": "test@example.com",
        "phone": "9999999999",
        "location": "Hyderabad",
        "experience": "Fresher",
    }

    output_path = (
        tmp_path
        / "tailored"
        / "electrical_engineer.pdf"
    )

    result = workflow.prepare_application(
        page=page,
        resume=resume,
        job=job,
        fields=fields,
        resume_output_path=str(
            output_path
        ),
    )

    # --------------------------------------------------------
    # RESULT STRUCTURE
    # --------------------------------------------------------

    assert isinstance(
        result,
        dict,
    )

    assert result["job"] == job

    assert "tailored_resume" in result
    assert "resume_pdf" in result
    assert "filled_fields" in result
    assert "resume_uploaded" in result
    assert "validation" in result
    assert "status" in result
    assert "success" in result
    assert "submitter" in result

    # --------------------------------------------------------
    # TAILORED RESUME
    # --------------------------------------------------------

    assert result["tailored_resume"]["tailored"] is True

    assert result["tailored_resume"][
        "target_job"
    ] == "Electrical Engineer"

    assert result["tailored_resume"][
        "target_company"
    ] == "Example Energy"

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    pdf_path = Path(
        result["resume_pdf"]
    )

    assert pdf_path.exists()
    assert pdf_path.is_file()

    # --------------------------------------------------------
    # APPLICATION PAGE
    # --------------------------------------------------------

    submitter = result["submitter"]

    assert isinstance(
        submitter,
        FakeApplicationSubmitter,
    )

    assert submitter.opened_url == (
        job["url"]
    )

    # --------------------------------------------------------
    # FORM FIELDS
    # --------------------------------------------------------

    assert submitter.prepared is True

    assert submitter.fields == fields

    assert set(
        result["filled_fields"]
    ) == set(
        fields.keys()
    )

    # --------------------------------------------------------
    # RESUME UPLOAD
    # --------------------------------------------------------

    assert result["resume_uploaded"] is True

    assert submitter.resume_path == (
        result["resume_pdf"]
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    assert result["validation"]["ready"] is True

    assert result["status"] == "prepared"

    assert result["success"] is True

    # --------------------------------------------------------
    # IMPORTANT:
    # PREPARATION MUST NOT SUBMIT
    # --------------------------------------------------------

    assert submitter.submitted is False


# ============================================================
# SUBMISSION REQUIRES CONFIRMATION
# ============================================================

def test_submission_requires_explicit_confirmation(
    tmp_path,
    monkeypatch,
):
    workflow = make_workflow(
        monkeypatch
    )

    page = FakePage()

    fields = {
        "full_name": "Naveen Sai",
        "email": "test@example.com",
    }

    prepared = workflow.prepare_application(
        page=page,
        resume=sample_resume(),
        job=sample_job(),
        fields=fields,
        resume_output_path=str(
            tmp_path
            / "resume.pdf"
        ),
    )

    submitter = prepared["submitter"]

    result = workflow.submit(
        prepared_application=prepared,
        confirm=False,
    )

    assert result["success"] is False

    assert result["status"] == (
        "confirmation_required"
    )

    assert submitter.submitted is True


# ============================================================
# CONFIRMED SUBMISSION
# ============================================================

def test_confirmed_submission_succeeds(
    tmp_path,
    monkeypatch,
):
    workflow = make_workflow(
        monkeypatch
    )

    page = FakePage()

    fields = {
        "full_name": "Naveen Sai",
        "email": "test@example.com",
    }

    prepared = workflow.prepare_application(
        page=page,
        resume=sample_resume(),
        job=sample_job(),
        fields=fields,
        resume_output_path=str(
            tmp_path
            / "resume.pdf"
        ),
    )

    result = workflow.submit(
        prepared_application=prepared,
        confirm=True,
    )

    assert result["success"] is True

    assert result["status"] == "applied"


# ============================================================
# INVALID JOB URL
# ============================================================

def test_prepare_application_requires_job_url(
    tmp_path,
    monkeypatch,
):
    workflow = make_workflow(
        monkeypatch
    )

    page = FakePage()

    job = sample_job()

    job["url"] = ""

    fields = {
        "full_name": "Naveen Sai",
    }

    try:
        workflow.prepare_application(
            page=page,
            resume=sample_resume(),
            job=job,
            fields=fields,
            resume_output_path=str(
                tmp_path
                / "resume.pdf"
            ),
        )

        assert False, (
            "Expected ValueError for missing job URL."
        )

    except ValueError as exc:
        assert "URL" in str(exc)


# ============================================================
# APPLICATION PREPARATION DOES NOT MODIFY ORIGINAL RESUME
# ============================================================

def test_tailoring_does_not_modify_original_resume(
    tmp_path,
    monkeypatch,
):
    workflow = make_workflow(
        monkeypatch
    )

    original_resume = sample_resume()

    original_skills = list(
        original_resume["skills"]
    )

    workflow.tailor_and_generate_resume(
        resume=original_resume,
        job=sample_job(),
        output_path=str(
            tmp_path
            / "resume.pdf"
        ),
    )

    assert original_resume["skills"] == (
        original_skills
    )

    assert "tailored" not in (
        original_resume
    )

    assert "target_job" not in (
        original_resume
    )


# ============================================================
# COMPLETE SELECTION → PREPARATION FLOW
# ============================================================

def test_selection_to_application_preparation(
    tmp_path,
    monkeypatch,
):
    """
    Integration checkpoint:

        discovered
            ↓
        matched
            ↓
        selected
            ↓
        tailored resume
            ↓
        generated PDF
            ↓
        application prepared
            ↓
        ready for submission

    No real browser and no real submission are used.
    """

    store = JobStore(
        storage_path=str(
            tmp_path
            / "jobs.json"
        )
    )

    workflow = make_workflow(
        monkeypatch
    )

    agent = JobAgent(
        job_store=store,
        application_workflow=workflow,
    )

    # --------------------------------------------------------
    # 1. DISCOVERED
    # --------------------------------------------------------

    job = sample_job()

    job_id = agent.add_job(
        job,
        status="discovered",
    )

    assert store.get_status(
        job_id
    ) == "discovered"

    # --------------------------------------------------------
    # 2. MATCH
    # --------------------------------------------------------

    resume = sample_resume()

    match_result = agent.match_and_store(
        resume=resume,
        job_id=job_id,
    )

    assert isinstance(
        match_result,
        dict,
    )

    assert store.get_status(
        job_id
    ) == "matched"

    # --------------------------------------------------------
    # 3. SELECT
    # --------------------------------------------------------

    selected = agent.select_job(
        job_id
    )

    assert selected is True

    assert store.get_status(
        job_id
    ) == "selected"

    # --------------------------------------------------------
    # 4. PREPARE APPLICATION
    # --------------------------------------------------------

    page = FakePage()

    fields = {
        "full_name": "Naveen Sai",
        "email": "test@example.com",
        "phone": "9999999999",
    }

    prepared = agent.prepare_application(
        page=page,
        resume=resume,
        job_id=job_id,
        fields=fields,
        resume_output_path=str(
            tmp_path
            / "tailored"
            / "electrical_engineer.pdf"
        ),
    )

    # --------------------------------------------------------
    # 5. VERIFY PREPARATION
    # --------------------------------------------------------

    assert isinstance(
        prepared,
        dict,
    )

    assert prepared["success"] is True

    assert prepared["resume_uploaded"] is True

    assert prepared["validation"]["ready"] is True

    assert prepared["status"] == "prepared"

    assert Path(
        prepared["resume_pdf"]
    ).exists()

    assert prepared["submitter"].opened_url == (
        job["url"]
    )

    assert prepared["submitter"].fields == (
        fields
    )

    # --------------------------------------------------------
    # 6. APPLICATION LIFECYCLE STATUS
    # --------------------------------------------------------

    assert store.get_status(
        job_id
    ) == "application_started"

    # --------------------------------------------------------
    # 7. VERIFY NOTHING WAS SUBMITTED
    # --------------------------------------------------------

    assert prepared["submitter"].submitted is False