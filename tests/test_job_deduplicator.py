from app.core.job_deduplicator import (
    JobDeduplicator,
)


def test_deduplicator_keeps_unique_jobs():

    jobs = [
        {
            "title": "Electrical Engineer",
            "company": "ABC",
            "location": "Hyderabad",
            "url": "https://example.com/job/1",
            "source": "greenhouse",
        },
        {
            "title": "Software Engineer",
            "company": "XYZ",
            "location": "Bangalore",
            "url": "https://example.com/job/2",
            "source": "lever",
        },
    ]

    result = JobDeduplicator().deduplicate(
        jobs
    )

    assert len(result) == 2


def test_deduplicates_same_url():

    jobs = [
        {
            "title": "Software Engineer",
            "company": "ABC",
            "location": "India",
            "url": "https://example.com/job/1",
            "source": "greenhouse",
        },
        {
            "title": "Software Engineer",
            "company": "ABC",
            "location": "India",
            "url": "https://example.com/job/1",
            "source": "indeed",
        },
    ]

    result = JobDeduplicator().deduplicate(
        jobs
    )

    assert len(result) == 1


def test_deduplicates_url_tracking_parameters():

    jobs = [
        {
            "title": "Software Engineer",
            "company": "ABC",
            "location": "India",
            "url": (
                "https://example.com/job/1"
                "?utm_source=indeed"
            ),
            "source": "indeed",
        },
        {
            "title": "Software Engineer",
            "company": "ABC",
            "location": "India",
            "url": (
                "https://example.com/job/1"
                "?utm_source=naukri"
            ),
            "source": "naukri",
        },
    ]

    result = JobDeduplicator().deduplicate(
        jobs
    )

    assert len(result) == 1


def test_deduplicates_across_different_urls():

    jobs = [
        {
            "title": "Software Engineer",
            "company": "ABC",
            "location": "Hyderabad",
            "url": (
                "https://boards.greenhouse.io/"
                "abc/jobs/123"
            ),
            "source": "greenhouse",
        },
        {
            "title": "Software Engineer",
            "company": "ABC",
            "location": "Hyderabad",
            "url": (
                "https://www.indeed.com/"
                "viewjob?jk=123"
            ),
            "source": "indeed",
        },
        {
            "title": "Software Engineer",
            "company": "ABC",
            "location": "Hyderabad",
            "url": (
                "https://www.naukri.com/"
                "job-listings-123"
            ),
            "source": "naukri",
        },
    ]

    result = JobDeduplicator().deduplicate(
        jobs
    )

    assert len(result) == 1


def test_deduplicates_using_company_title_location():

    jobs = [
        {
            "title": "  Software Engineer  ",
            "company": " ABC ",
            "location": " Hyderabad ",
            "source": "greenhouse",
        },
        {
            "title": "Software Engineer",
            "company": "ABC",
            "location": "Hyderabad",
            "source": "lever",
        },
    ]

    result = JobDeduplicator().deduplicate(
        jobs
    )

    assert len(result) == 1


def test_deduplicates_using_company_title_without_location():

    jobs = [
        {
            "title": "Software Engineer",
            "company": "ABC",
            "location": "Hyderabad",
            "source": "greenhouse",
        },
        {
            "title": "Software Engineer",
            "company": "ABC",
            "location": "Bangalore",
            "source": "lever",
        },
    ]

    result = JobDeduplicator().deduplicate(
        jobs
    )

    assert len(result) == 1


def test_invalid_jobs_are_ignored():

    jobs = [
        None,
        "invalid",
        123,
        {},
        {
            "title": "",
            "company": "",
            "url": "",
        },
        {
            "title": "Valid Job",
            "company": "ABC",
            "location": "India",
        },
    ]

    result = JobDeduplicator().deduplicate(
        jobs
    )

    assert len(result) == 1
    assert result[0]["title"] == "Valid Job"


def test_duplicate_sources_are_combined():

    jobs = [
        {
            "title": "Software Engineer",
            "company": "ABC",
            "location": "India",
            "url": "https://example.com/job/1",
            "description": "Short",
            "source": "greenhouse",
        },
        {
            "title": "Software Engineer",
            "company": "ABC",
            "location": "India",
            "url": "https://example.com/job/1",
            "description": (
                "Much longer and richer description."
            ),
            "source": "indeed",
        },
    ]

    result = JobDeduplicator().deduplicate(
        jobs
    )

    assert len(result) == 1

    assert set(
        result[0]["source"]
        if isinstance(
            result[0]["source"],
            list,
        )
        else [result[0]["source"]]
    ) == {
        "greenhouse",
        "indeed",
    }

    assert (
        result[0]["description"]
        == "Much longer and richer description."
    )


def test_canonicalize_url():

    deduplicator = JobDeduplicator()

    result = deduplicator.canonicalize_url(
        (
            "HTTPS://Example.COM/job/123/"
            "?utm_source=indeed"
            "&utm_medium=job"
            "&page=1"
        )
    )

    assert result == (
        "https://example.com/job/123"
        "?page=1"
    )