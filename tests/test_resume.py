def test_all_resumes_can_be_loaded(
    resume_files,
    loaded_resumes,
):
    """
    Verify that all expected resume PDFs are loaded.

    Resume extraction is handled by ResumeManager and
    its persistent cache.
    """

    assert len(resume_files) >= 3

    assert len(loaded_resumes) >= 3

    loaded_filenames = {
        resume.get("_filename")
        for resume in loaded_resumes
    }

    for resume_path in resume_files:

        assert resume_path.name in loaded_filenames, (
            f"Resume was not loaded: "
            f"{resume_path.name}"
        )