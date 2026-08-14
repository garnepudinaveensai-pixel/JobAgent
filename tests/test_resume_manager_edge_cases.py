import json
from pathlib import Path

import pytest

from app.resume.resume_manager import ResumeManager


def test_discover_resumes_missing_directory(tmp_path):

    manager = ResumeManager(
        resume_directory=tmp_path / "does_not_exist",
        cache_directory=tmp_path / "cache",
    )

    with pytest.raises(FileNotFoundError):
        manager.discover_resumes()


def test_discover_resumes_only_pdf(tmp_path):

    resume_dir = tmp_path / "resumes"
    cache_dir = tmp_path / "cache"

    resume_dir.mkdir()

    (resume_dir / "resume1.pdf").write_bytes(b"pdf")
    (resume_dir / "resume2.pdf").write_bytes(b"pdf")
    (resume_dir / "notes.txt").write_text("not a resume")

    manager = ResumeManager(
        resume_directory=resume_dir,
        cache_directory=cache_dir,
    )

    resumes = manager.discover_resumes()

    assert len(resumes) == 2
    assert all(path.suffix.lower() == ".pdf" for path in resumes)


def test_cache_path(tmp_path):

    resume_dir = tmp_path / "resumes"
    cache_dir = tmp_path / "cache"

    resume_dir.mkdir()

    resume_path = resume_dir / "technical_resume.pdf"
    resume_path.write_bytes(b"test")

    manager = ResumeManager(
        resume_directory=resume_dir,
        cache_directory=cache_dir,
    )

    cache_path = manager._cache_path(resume_path)

    assert cache_path == (
        cache_dir / "technical_resume.json"
    )


def test_file_signature(tmp_path):

    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"test resume")

    manager = ResumeManager(
        resume_directory=tmp_path,
        cache_directory=tmp_path / "cache",
    )

    signature = manager._file_signature(resume_path)

    assert "size" in signature
    assert "mtime_ns" in signature
    assert signature["size"] == len(b"test resume")


def test_load_cached_resume_when_cache_missing(tmp_path):

    resume_dir = tmp_path / "resumes"
    cache_dir = tmp_path / "cache"

    resume_dir.mkdir()

    resume_path = resume_dir / "resume.pdf"
    resume_path.write_bytes(b"test")

    manager = ResumeManager(
        resume_directory=resume_dir,
        cache_directory=cache_dir,
    )

    result = manager._load_cached_resume(resume_path)

    assert result is None


def test_save_and_load_cached_resume(tmp_path):

    resume_dir = tmp_path / "resumes"
    cache_dir = tmp_path / "cache"

    resume_dir.mkdir()

    resume_path = resume_dir / "resume.pdf"
    resume_path.write_bytes(b"test resume")

    manager = ResumeManager(
        resume_directory=resume_dir,
        cache_directory=cache_dir,
    )

    resume = {
        "name": "Test Candidate",
        "skills": ["Python"],
        "core_competencies": ["Electrical Engineering"],
    }

    manager._save_cached_resume(
        resume_path,
        resume,
    )

    cache_path = manager._cache_path(resume_path)

    assert cache_path.exists()

    loaded = manager._load_cached_resume(
        resume_path
    )

    assert loaded == resume


def test_stale_cache_returns_none(tmp_path):

    resume_dir = tmp_path / "resumes"
    cache_dir = tmp_path / "cache"

    resume_dir.mkdir()

    resume_path = resume_dir / "resume.pdf"
    resume_path.write_bytes(b"original")

    manager = ResumeManager(
        resume_directory=resume_dir,
        cache_directory=cache_dir,
    )

    resume = {
        "name": "Test Candidate",
        "skills": ["Python"],
    }

    manager._save_cached_resume(
        resume_path,
        resume,
    )

    # Modify PDF after cache creation
    resume_path.write_bytes(
        b"modified resume content"
    )

    result = manager._load_cached_resume(
        resume_path
    )

    assert result is None


def test_corrupted_cache_returns_none(tmp_path):

    resume_dir = tmp_path / "resumes"
    cache_dir = tmp_path / "cache"

    resume_dir.mkdir()

    resume_path = resume_dir / "resume.pdf"
    resume_path.write_bytes(b"test")

    manager = ResumeManager(
        resume_directory=resume_dir,
        cache_directory=cache_dir,
    )

    cache_path = manager._cache_path(resume_path)

    cache_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_path.write_text(
        "{ invalid json",
        encoding="utf-8",
    )

    result = manager._load_cached_resume(
        resume_path
    )

    assert result is None


def test_invalid_cached_resume_returns_none(tmp_path):

    resume_dir = tmp_path / "resumes"
    cache_dir = tmp_path / "cache"

    resume_dir.mkdir()

    resume_path = resume_dir / "resume.pdf"
    resume_path.write_bytes(b"test")

    manager = ResumeManager(
        resume_directory=resume_dir,
        cache_directory=cache_dir,
    )

    cache_path = manager._cache_path(resume_path)

    cache_data = {
        "file_signature": manager._file_signature(
            resume_path
        ),
        "resume": "not a dictionary",
    }

    cache_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_path.write_text(
        json.dumps(cache_data),
        encoding="utf-8",
    )

    result = manager._load_cached_resume(
        resume_path
    )

    assert result is None


def test_get_resume_count(tmp_path):

    resume_dir = tmp_path / "resumes"

    resume_dir.mkdir()

    (resume_dir / "one.pdf").write_bytes(b"1")
    (resume_dir / "two.pdf").write_bytes(b"2")
    (resume_dir / "three.pdf").write_bytes(b"3")

    manager = ResumeManager(
        resume_directory=resume_dir,
        cache_directory=tmp_path / "cache",
    )

    assert manager.get_resume_count() == 3


def test_load_all_resumes_handles_processing_error(
    tmp_path,
    monkeypatch,
):

    resume_dir = tmp_path / "resumes"

    resume_dir.mkdir()

    resume_path = resume_dir / "broken.pdf"
    resume_path.write_bytes(b"test")

    manager = ResumeManager(
        resume_directory=resume_dir,
        cache_directory=tmp_path / "cache",
    )

    def failing_process(path):
        raise RuntimeError("Processing failed")

    monkeypatch.setattr(
        manager,
        "_process_resume",
        failing_process,
    )

    result = manager.load_all_resumes()

    assert result == []


def test_process_resume_empty_text(
    tmp_path,
    monkeypatch,
):

    resume_dir = tmp_path / "resumes"

    resume_dir.mkdir()

    resume_path = resume_dir / "empty.pdf"
    resume_path.write_bytes(b"test")

    manager = ResumeManager(
        resume_directory=resume_dir,
        cache_directory=tmp_path / "cache",
    )

    monkeypatch.setattr(
        "app.resume.resume_manager.load_resume",
        lambda path: "",
    )

    result = manager._process_resume(
        resume_path
    )

    assert result is None


def test_process_resume_success(
    tmp_path,
    monkeypatch,
):

    resume_dir = tmp_path / "resumes"

    resume_dir.mkdir()

    resume_path = resume_dir / "resume.pdf"
    resume_path.write_bytes(b"test")

    manager = ResumeManager(
        resume_directory=resume_dir,
        cache_directory=tmp_path / "cache",
    )

    monkeypatch.setattr(
        "app.resume.resume_manager.load_resume",
        lambda path: "Resume text here",
    )

    monkeypatch.setattr(
        "app.resume.resume_manager.parse_resume",
        lambda text: {
            "name": "Test Candidate",
            "skills": ["Python"],
        },
    )

    result = manager._process_resume(
        resume_path
    )

    assert result["name"] == "Test Candidate"
    assert result["_filename"] == "resume.pdf"
    assert result["_file"] == str(resume_path)
    assert result["_raw_text"] == "Resume text here"