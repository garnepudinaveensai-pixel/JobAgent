def test_all_resumes_can_be_parsed(
    resume_files,
    parsed_resumes,
):
    """
    Verify that every resume was successfully parsed.

    ResumeManager already performs extraction and parsing,
    so this test does not repeat expensive work.
    """

    assert len(resume_files) >= 3

    assert len(parsed_resumes) >= 3

    for resume_path in resume_files:

        filename = resume_path.name

        assert filename in parsed_resumes, (
            f"Resume was not parsed: "
            f"{filename}"
        )

        parsed_resume = parsed_resumes[
            filename
        ]

        assert parsed_resume, (
            f"Parser returned empty result "
            f"for {filename}"
        )