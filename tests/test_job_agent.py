from app.core.job_agent import JobAgent


class FakeJobStore:
    def __init__(self):
        self.jobs = {}

    def add_job(
        self,
        job,
        status="discovered",
    ):
        job_id = job.get(
            "url"
        ) or (
            f"{job.get('company', '')}|"
            f"{job.get('title', '')}"
        )

        self.jobs[job_id] = {
            **job,
            "job_id": job_id,
            "status": status,
        }

        return job_id

    def get_job(
        self,
        job_id,
    ):
        return self.jobs.get(
            job_id
        )

    def get_all_jobs(self):
        return list(
            self.jobs.values()
        )

    def update_status(
        self,
        job_id,
        status,
    ):
        if job_id not in self.jobs:
            return False

        self.jobs[job_id]["status"] = status
        return True

    def get_status(
        self,
        job_id,
    ):
        job = self.get_job(
            job_id
        )

        if job is None:
            return None

        return job.get(
            "status"
        )


class FakeWorkflow:
    def __init__(self):
        self.prepared = False
        self.submitted = False

    def prepare_application(
        self,
        page,
        resume,
        job,
        fields,
        resume_output_path,
    ):
        self.prepared = True

        return {
            "success": True,
            "status": "ready_for_submission",
            "validation": {
                "ready": True,
            },
            "filled_fields": list(
                fields.keys()
            ),
            "resume_uploaded": True,
        }

    def submit(
        self,
        prepared_application,
        confirm=False,
    ):
        if not confirm:
            return {
                "success": False,
                "status": "confirmation_required",
            }

        self.submitted = True

        return {
            "success": True,
            "status": "submitted",
        }


def sample_job():
    return {
        "title": "Graduate Engineer Trainee",
        "company": "Example Company",
        "location": "Hyderabad",
        "url": "https://example.com/job/123",
        "description": (
            "Electrical Engineering "
            "Python Automation"
        ),
        "required_skills": [
            "Python",
            "Electrical Engineering",
        ],
        "preferred_skills": [
            "Automation",
        ],
    }


def sample_resume():
    return {
        "name": "GARNEPUDI NAVEEN SAI",
        "email": "test@example.com",
        "skills": [
            "Python",
            "C",
        ],
        "core_competencies": [
            "Electrical Engineering",
            "Automation",
        ],
    }


def create_agent():
    store = FakeJobStore()
    workflow = FakeWorkflow()

    agent = JobAgent(
        job_store=store,
        application_workflow=workflow,
    )

    return agent, store, workflow


def test_add_and_get_job():
    agent, _, _ = create_agent()

    job = sample_job()

    job_id = agent.add_job(
        job
    )

    stored = agent.get_job(
        job_id
    )

    assert stored is not None
    assert (
        stored["title"]
        == "Graduate Engineer Trainee"
    )
    assert (
        stored["status"]
        == "discovered"
    )


def test_get_jobs():
    agent, _, _ = create_agent()

    agent.add_job(
        sample_job()
    )

    jobs = agent.get_jobs()

    assert len(jobs) == 1


def test_match_job():
    agent, _, _ = create_agent()

    result = agent.match(
        sample_resume(),
        sample_job(),
    )

    assert (
        result["match_score"]
        > 0
    )

    assert (
        "Python"
        in result[
            "matched_required_skills"
        ]
    )


def test_match_and_store():
    agent, store, _ = create_agent()

    job_id = agent.add_job(
        sample_job()
    )

    result = agent.match_and_store(
        sample_resume(),
        job_id,
    )

    assert result["match_score"] > 0

    assert (
        store.get_status(job_id)
        == "matched"
    )


def test_select_job():
    agent, store, _ = create_agent()

    job_id = agent.add_job(
        sample_job()
    )

    assert agent.select_job(
        job_id
    ) is True

    assert (
        store.get_status(job_id)
        == "selected"
    )


def test_prepare_application():
    agent, store, workflow = (
        create_agent()
    )

    job_id = agent.add_job(
        sample_job()
    )

    result = agent.prepare_application(
        page="fake-page",
        resume=sample_resume(),
        job_id=job_id,
        fields={
            "First Name": "Naveen",
            "Email": "test@example.com",
        },
        resume_output_path=(
            "data/resumes/test.pdf"
        ),
    )

    assert result["success"] is True

    assert workflow.prepared is True

    assert (
        store.get_status(job_id)
        == "application_started"
    )


def test_submit_requires_confirmation():
    agent, store, workflow = (
        create_agent()
    )

    job_id = agent.add_job(
        sample_job()
    )

    prepared = {
        "validation": {
            "ready": True,
        }
    }

    result = agent.submit_application(
        job_id,
        prepared,
        confirm=False,
    )

    assert result["success"] is False

    assert (
        result["status"]
        == "confirmation_required"
    )

    assert (
        store.get_status(job_id)
        == "discovered"
    )


def test_submit_application():
    agent, store, workflow = (
        create_agent()
    )

    job_id = agent.add_job(
        sample_job()
    )

    prepared = {
        "validation": {
            "ready": True,
        }
    }

    result = agent.submit_application(
        job_id,
        prepared,
        confirm=True,
    )

    assert result["success"] is True

    assert (
        result["status"]
        == "submitted"
    )

    assert workflow.submitted is True

    assert (
        store.get_status(job_id)
        == "applied"
    )


def test_update_application_status():
    agent, store, _ = create_agent()

    job_id = agent.add_job(
        sample_job()
    )

    assert agent.update_application_status(
        job_id,
        "shortlisted",
    )

    assert (
        agent.get_application_status(
            job_id
        )
        == "shortlisted"
    )


def test_process_job():
    agent, store, _ = create_agent()

    job_id = agent.add_job(
        sample_job()
    )

    result = agent.process_job(
        sample_resume(),
        job_id,
    )

    assert "job" in result
    assert "match" in result
    assert "status" in result

    assert (
        result["status"]
        == "matched"
    )


def test_missing_job_raises_error():
    agent, _, _ = create_agent()

    try:
        agent.match_and_store(
            sample_resume(),
            "missing-job",
        )

        assert False

    except ValueError as exc:
        assert "Job not found" in str(
            exc
        )