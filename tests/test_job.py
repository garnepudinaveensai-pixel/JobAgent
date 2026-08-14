from app.jobs.job import Job


def test_job_creation():

    job = Job(
        title="Graduate Engineer Trainee",
        company="Example Engineering Ltd",
        location="India",
        description="Electrical engineering graduate trainee position.",
        url="https://example.com/job",
        source="Example",
        required_skills=[
            "Electrical Engineering",
            "Python",
        ],
        preferred_skills=[
            "Industrial Automation",
        ],
        experience_requirements="0-2 years",
    )

    assert job.title == "Graduate Engineer Trainee"
    assert job.company == "Example Engineering Ltd"
    assert job.location == "India"

    assert "Python" in job.required_skills
    assert "Industrial Automation" in job.preferred_skills

    data = job.to_dict()

    assert data["title"] == "Graduate Engineer Trainee"
    assert data["company"] == "Example Engineering Ltd"
    assert data["required_skills"] == [
        "Electrical Engineering",
        "Python",
    ]

    print("\nJob Object:")
    print(data)