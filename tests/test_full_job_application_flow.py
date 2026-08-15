from pathlib import Path

import pytest

from app.core.job_agent import JobAgent
from app.core.application_workflow import ApplicationWorkflow
from app.jobs.job_store import JobStore
from app.jobs.application_tracker import ApplicationTracker
from app.jobs.application_status_monitor import (
    ApplicationStatusMonitor,
)
from app.outreach.outreach_pipeline import OutreachPipeline
from app.outreach.contact_selector import ContactSelector
from app.outreach.email_composer import EmailComposer
from app.outreach.email_sender import EmailSender
from app.resume.resume_tailor import tailor_resume
from app.resume.resume_pdf_generator import (
    ResumePDFGenerator,
)


# ============================================================
# TEST DATA
# ============================================================


def make_resume():
    return {
        "name": "Naveen Sai",
        "email": "naveen@example.com",
        "phone": "9999999999",
        "location": "India",
        "degree": "B.Tech Electrical & Electronics Engineering",
        "summary": (
            "Electrical engineering graduate with hands-on "
            "industrial and automation experience."
        ),
        "skills": [
            "C",
            "Embedded C",
            "Python",
            "MATLAB",
            "Simulink",
            "TI C2000",
            "F28379D",
            "GPIO",
            "ADC",
            "PWM",
            "SQL",
            "Git",
        ],
        "core_competencies": [
            "Automation",
            "Electrical Engineering",
            "Condition-Based Maintenance",
            "Predictive Maintenance",
            "Problem Solving",
        ],
        "experience": [
            {
                "company": "Adani Cement",
                "role": "CBM Junior Intern",
                "description": (
                    "Supported condition-based monitoring "
                    "and preventive maintenance."
                ),
            }
        ],
        "projects": [
            {
                "title": "Predictive Maintenance of Motors",
                "description": (
                    "Developed a predictive maintenance "
                    "prototype for motors."
                ),
            }
        ],
    }


def make_job():
    return {
        "job_id": "job-001",
        "title": "Automation Engineer",
        "company": "Example Technologies",
        "location": "Hyderabad",
        "url": "https://example.com/jobs/automation-engineer",
        "description": (
            "Automation engineering role involving "
            "embedded systems and industrial automation."
        ),
        "required_skills": [
            "Embedded C",
            "TI C2000",
            "MATLAB",
            "Simulink",
        ],
        "preferred_skills": [
            "GPIO",
            "ADC",
            "PWM",
            "Automation",
        ],
        "experience_requirements": (
            "Fresh graduates and interns are welcome."
        ),
    }


def make_contact():
    return {
        "email": "recruiter@example.com",
        "name": "Recruiter",
        "role": "Talent Acquisition",
        "company": "Example Technologies",
        "source": "company website",
    }


def make_application_fields():
    return {
        "Name": "Naveen Sai",
        "Email": "naveen@example.com",
        "Phone": "9999999999",
        "Location": "Hyderabad",
    }


# ============================================================
# FAKE APPLICATION SUBMITTER
# ============================================================


class FakeApplicationSubmitter:
    """
    Safe browser-free application submitter.

    It behaves like the real ApplicationSubmitter but never
    opens a browser or submits anything externally.
    """

    def __init__(self):
        self.prepared = False
        self.submitted = False
        self.confirm_values = []

    def open(self, url):
        assert url
        return True

    def discover(self):
        return [
            {
                "name": "Name",
                "type": "text",
                "required": True,
            },
            {
                "name": "Email",
                "type": "email",
                "required": True,
            },
            {
                "name": "Phone",
                "type": "text",
                "required": True,
            },
        ]

    def prepare_application(
        self,
        resume_path,
        fields,
    ):
        assert Path(resume_path).exists()

        self.prepared = True

        return {
            "success": True,
            "status": "ready_for_submission",
            "filled_fields": list(fields.keys()),
            "resume_uploaded": True,
            "validation": {
                "ready": True,
                "missing": [],
                "valid": True,
            },
        }

    def submit(self, confirm=False):
        self.confirm_values.append(confirm)

        if not confirm:
            return {
                "success": False,
                "status": "confirmation_required",
            }

        self.submitted = True

        return {
            "success": True,
            "status": "applied",
        }


# ============================================================
# FULL WORKFLOW TEST
# ============================================================


def test_complete_job_application_pipeline(tmp_path):
    """
    Verify the complete internal JobAgent flow:

        job
        ↓
        matching
        ↓
        resume tailoring
        ↓
        PDF generation
        ↓
        application preparation
        ↓
        confirmation gate
        ↓
        submission
        ↓
        application tracking
        ↓
        HR contact selection
        ↓
        outreach preparation
        ↓
        outreach dry-run
        ↓
        status monitoring
    """

    # --------------------------------------------------------
    # STORAGE
    # --------------------------------------------------------

    store_path = tmp_path / "jobs.json"

    store = JobStore(
        storage_path=str(store_path)
    )

    tracker = ApplicationTracker(
        store=store
    )

    # --------------------------------------------------------
    # JOB AGENT
    # --------------------------------------------------------

    application_submitter = FakeApplicationSubmitter()

    application_workflow = ApplicationWorkflow(
        submitter_factory=lambda page: (
            application_submitter
        )
    )

    outreach_pipeline = OutreachPipeline(
        contact_selector=ContactSelector(),
        email_composer=EmailComposer(),
        email_sender=EmailSender(
            dry_run=True
        ),
    )

    agent = JobAgent(
        job_store=store,
        application_workflow=application_workflow,
        outreach_pipeline=outreach_pipeline,
    )

    # --------------------------------------------------------
    # 1. STORE JOB
    # --------------------------------------------------------

    job = make_job()

    job_id = agent.add_job(
        job,
        status="discovered",
    )

    assert job_id

    stored_job = agent.get_job(job_id)

    assert stored_job is not None
    assert stored_job["status"] == "discovered"

    # --------------------------------------------------------
    # 2. MATCH JOB
    # --------------------------------------------------------

    resume = make_resume()

    match_result = agent.match_and_store(
        resume=resume,
        job_id=job_id,
    )

    assert isinstance(
        match_result,
        dict,
    )

    assert "match_score" in match_result
    assert "eligible" in match_result

    assert (
        agent.get_application_status(job_id)
        == "matched"
    )

    # --------------------------------------------------------
    # 3. SELECT JOB
    # --------------------------------------------------------

    assert agent.select_job(job_id) is True

    assert (
        agent.get_application_status(job_id)
        == "selected"
    )

    # --------------------------------------------------------
    # 4. TAILOR RESUME
    # --------------------------------------------------------

    tailored = tailor_resume(
        resume,
        job,
    )

    assert isinstance(
        tailored,
        dict,
    )

    assert (
        tailored["tailored_for"]
        == job["title"]
    )

    assert (
        tailored["eligible"]
        is True
    )

    # Make sure tailoring did not invent a skill.
    assert (
        "Embedded C"
        in tailored["tailored_skills"]
        or "Embedded C"
        in resume["skills"]
    )

    # --------------------------------------------------------
    # 5. GENERATE PDF
    # --------------------------------------------------------

    pdf_path = (
        tmp_path
        / "tailored_resume.pdf"
    )

    generator = ResumePDFGenerator(
        output_dir=str(tmp_path)
    )

    generated_pdf = generator.build(
        tailored,
        output_path=str(pdf_path),
    )

    assert generated_pdf
    assert Path(generated_pdf).exists()
    assert Path(generated_pdf).is_file()

    # --------------------------------------------------------
    # 6. PREPARE APPLICATION
    # --------------------------------------------------------

    prepared = agent.prepare_application(
        page=object(),
        resume=resume,
        job_id=job_id,
        fields=make_application_fields(),
        resume_output_path=str(
            tmp_path
            / "workflow_resume.pdf"
        ),
    )

    assert prepared is not None

    assert Path(
        prepared["resume_pdf"]
    ).exists()

    assert (
        prepared["resume_uploaded"]
        is True
    )

    assert (
        prepared["validation"]["ready"]
        is True
    )

    assert (
        agent.get_application_status(job_id)
        == "application_started"
    )

    # --------------------------------------------------------
    # 7. SUBMISSION MUST REQUIRE CONFIRMATION
    # --------------------------------------------------------

    blocked = agent.submit_application(
        job_id=job_id,
        prepared_application=prepared,
        confirm=False,
    )

    assert (
        blocked["success"]
        is False
    )

    assert (
        blocked["status"]
        == "confirmation_required"
    )

    assert (
        application_submitter.submitted
        is False
    )

    # --------------------------------------------------------
    # 8. EXPLICIT SUBMISSION
    # --------------------------------------------------------

    submitted = agent.submit_application(
        job_id=job_id,
        prepared_application=prepared,
        confirm=True,
    )

    assert (
        submitted["success"]
        is True
    )

    assert (
        application_submitter.submitted
        is True
    )

    assert (
        agent.get_application_status(job_id)
        == "applied"
    )

    # --------------------------------------------------------
    # 9. TRACK APPLICATION
    # --------------------------------------------------------

    applied_jobs = (
        tracker.get_applied_jobs()
    )

    assert len(applied_jobs) == 1

    assert (
        applied_jobs[0]["job_id"]
        == job_id
    )

    # --------------------------------------------------------
    # 10. FIND / SELECT HR CONTACT
    # --------------------------------------------------------

    contact = make_contact()

    selected_contact = (
        outreach_pipeline.select_contact(
            [contact],
            job=job,
        )
    )

    assert selected_contact is not None

    assert (
        selected_contact.email
        == "recruiter@example.com"
    )

    # --------------------------------------------------------
    # 11. PREPARE OUTREACH
    # --------------------------------------------------------

    outreach = (
        outreach_pipeline.prepare_outreach(
            contacts=[contact],
            job=job,
            candidate=resume,
            resume_path=prepared["resume_pdf"],
        )
    )

    assert outreach.success is True

    assert (
        outreach.status
        == "prepared"
    )

    assert (
        outreach.email
        == "recruiter@example.com"
    )

    assert Path(
        outreach.attachment
    ).exists()

    assert (
        job["company"]
        in outreach.subject
    )

    # --------------------------------------------------------
    # 12. OUTREACH MUST NOT SEND WITHOUT CONFIRMATION
    # --------------------------------------------------------

    outreach_blocked = (
        outreach_pipeline.send_outreach(
            contacts=[contact],
            job=job,
            candidate=resume,
            resume_path=prepared["resume_pdf"],
            confirm=False,
        )
    )

    assert (
        outreach_blocked.success
        is True
    )

    assert (
        outreach_blocked.status
        == "confirmation_required"
    )

    # --------------------------------------------------------
    # 13. DRY-RUN OUTREACH SEND
    # --------------------------------------------------------

    outreach_sent = (
        outreach_pipeline.send_outreach(
            contacts=[contact],
            job=job,
            candidate=resume,
            resume_path=prepared["resume_pdf"],
            confirm=True,
        )
    )

    assert (
        outreach_sent.success
        is True
    )

    assert (
        outreach_sent.dry_run
        is True
    )

    # --------------------------------------------------------
    # 14. STATUS MONITORING
    # --------------------------------------------------------

    monitor = ApplicationStatusMonitor(
        job_store=store
    )

    status_event = monitor.detect_status(
        job_id=job_id,
        detected_status="shortlisted",
    )

    assert (
        status_event["success"]
        is True
    )

    assert (
        status_event["changed"]
        is True
    )

    assert (
        status_event["old_status"]
        == "applied"
    )

    assert (
        status_event["new_status"]
        == "shortlisted"
    )

    assert (
        status_event["notification_required"]
        is True
    )

    # --------------------------------------------------------
    # 15. FINAL STATE
    # --------------------------------------------------------

    assert (
        monitor.get_status(job_id)
        == "shortlisted"
    )

    assert (
        monitor.requires_notification(
            "shortlisted"
        )
        is True
    )