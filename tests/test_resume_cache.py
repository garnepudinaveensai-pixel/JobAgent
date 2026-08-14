from pathlib import Path

from app.resume.resume_manager import ResumeManager


def test_resume_manager_cache_directory_exists(tmp_path):

    resume_directory = Path("resumes")

    cache_directory = (
        tmp_path / "cache"
    )

    manager = ResumeManager(
        resume_directory=resume_directory,
        cache_directory=cache_directory,
    )

    resumes = manager.load_all_resumes()

    assert resumes
    assert cache_directory.exists()


def test_cached_resumes_contain_required_metadata(
    loaded_resumes,
):

    for resume in loaded_resumes:

        assert "_filename" in resume
        assert "_raw_text" in resume

        assert resume["_filename"]
        assert resume["_raw_text"].strip()