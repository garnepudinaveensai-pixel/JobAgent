from app.resume.resume_manager import ResumeManager


def test_resume_manager():

    manager = ResumeManager("resumes")

    resumes = manager.load_all_resumes()

    assert isinstance(resumes, list)

    for resume in resumes:

        assert resume["_filename"].endswith(".pdf")

        assert "skills" in resume

        assert "core_competencies" in resume

        print(
            f"\nLoaded resume: "
            f"{resume['_filename']}"
        )