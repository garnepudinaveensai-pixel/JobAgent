from pathlib import Path

import pytest

from app.resume.resume_manager import ResumeManager


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RESUME_DIRECTORY = PROJECT_ROOT / "resumes"
CACHE_DIRECTORY = PROJECT_ROOT / "data" / "cache" / "resumes"


# ============================================================
# RESUME MANAGER
# ============================================================

@pytest.fixture(scope="session")
def resume_manager():
    """
    Create one ResumeManager for the entire pytest session.

    The manager uses the application's persistent resume cache.
    """

    return ResumeManager(
        resume_directory=RESUME_DIRECTORY,
        cache_directory=CACHE_DIRECTORY,
    )


# ============================================================
# RESUME FILES
# ============================================================

@pytest.fixture(scope="session")
def resume_files():
    """
    Discover resume PDFs once per pytest session.
    """

    files = sorted(
        RESUME_DIRECTORY.glob("*.pdf")
    )

    assert len(files) >= 3, (
        f"Expected at least 3 resumes, "
        f"found {len(files)}"
    )

    return files


# ============================================================
# LOADED RESUMES
# ============================================================

@pytest.fixture(scope="session")
def loaded_resumes(resume_manager):
    """
    Load every resume through ResumeManager.

    ResumeManager handles:
    - PDF extraction
    - OCR fallback
    - parsing
    - persistent cache
    """

    resumes = resume_manager.load_all_resumes()

    assert len(resumes) >= 3, (
        f"Expected at least 3 loaded resumes, "
        f"found {len(resumes)}"
    )

    return resumes


# ============================================================
# RESUME TEXTS
# ============================================================

@pytest.fixture(scope="session")
def resume_texts(loaded_resumes):
    """
    Extract raw text from already-loaded resumes.

    No PDF extraction is performed here.
    """

    texts = {}

    for resume in loaded_resumes:

        filename = resume.get("_filename")
        text = resume.get("_raw_text", "")

        assert filename, (
            "Loaded resume is missing _filename"
        )

        assert text.strip(), (
            f"No extracted text for {filename}"
        )

        texts[filename] = text

    return texts


# ============================================================
# PARSED RESUMES
# ============================================================

@pytest.fixture(scope="session")
def parsed_resumes(loaded_resumes):
    """
    Reuse resumes already parsed by ResumeManager.
    """

    return {
        resume["_filename"]: resume
        for resume in loaded_resumes
    }