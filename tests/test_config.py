from app.main import load_settings


def test_load_settings():
    settings = load_settings()

    assert settings["app"]["name"] == "JobAgent"
    assert settings["app"]["environment"] == "development"
    assert settings["job_search"]["location"] == "India"
    assert settings["job_search"]["max_results"] == 20