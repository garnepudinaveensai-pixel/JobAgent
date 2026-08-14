import json
from pathlib import Path


def load_settings():
    settings_path = Path("config/settings.json")

    with open(settings_path, "r", encoding="utf-8") as file:
        return json.load(file)


def main():
    settings = load_settings()

    print("=" * 50)
    print("JobAgent started successfully!")
    print("=" * 50)

    print(f"Application: {settings['app']['name']}")
    print(f"Environment: {settings['app']['environment']}")
    print(f"Job Location: {settings['job_search']['location']}")
    print(f"Maximum Results: {settings['job_search']['max_results']}")
    print("=" * 50)


if __name__ == "__main__":
    main()