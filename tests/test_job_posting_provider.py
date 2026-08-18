from app.outreach.job_posting_provider import JobPostingContactProvider


def test_extracts_published_recruitment_email_from_job_description():
    provider = JobPostingContactProvider()

    result = provider.search(
        company="Example Energy",
        job={
            "title": "Electrical Engineer",
            "url": "https://example.com/jobs/1",
            "description": (
                "For questions contact careers@example.com "
                "or call the office."
            ),
        },
    )

    assert len(result) == 1
    assert result[0]["email"] == "careers@example.com"
    assert result[0]["verification_status"] == "published"
    assert result[0]["source"] == "job_posting"


def test_deduplicates_explicit_and_description_email():
    provider = JobPostingContactProvider()

    result = provider.search(
        company="Example Energy",
        job={
            "recruiter_email": "hr@example.com",
            "description": "Send resumes to HR@EXAMPLE.COM.",
            "url": "https://example.com/jobs/1",
        },
    )

    emails = [item["email"] for item in result]
    assert emails == ["hr@example.com"]


def test_does_not_guess_email_addresses():
    provider = JobPostingContactProvider()

    result = provider.search(
        company="Example Energy",
        domain="example.com",
        job={
            "title": "Electrical Engineer",
            "url": "https://example.com/jobs/1",
            "description": "Apply through our website.",
        },
    )

    assert result == []
