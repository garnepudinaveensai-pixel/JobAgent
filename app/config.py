from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


# ============================================================
# JOB SEARCH CONFIGURATION
# ============================================================


@dataclass
class JobSearchConfig:
    """Configuration for job discovery and job matching."""

    keywords: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    minimum_match_score: float = 60.0
    auto_select_eligible: bool = False


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================


@dataclass
class ApplicationConfig:
    """Configuration controlling job applications."""

    resume_path: str = "data/resumes/master_resume.pdf"
    tailored_resume_directory: str = "data/resumes/tailored"

    # ``confirm=True`` is still required by the execution router.
    require_confirmation: bool = True

    # CLI --execute is the explicit live-execution switch. This field is
    # retained for compatibility with the existing configuration model.
    auto_submit: bool = False


# ============================================================
# BROWSER CONFIGURATION
# ============================================================


@dataclass
class BrowserConfig:
    """
    Configuration for the shared Playwright browser.

    A persistent profile is enabled for normal JobAgent runs. This lets
    Naukri, Indeed and supported employer sites retain cookies/local storage
    between JobAgent launches. The user must still complete login/OTP/CAPTCHA
    manually whenever a site requests it.
    """

    persistent: bool = True
    profile_directory: str = "data/browser-profile"
    headless: bool = False
    timeout: int = 30000


# ============================================================
# NOTIFICATION CONFIGURATION
# ============================================================


@dataclass
class NotificationConfig:
    """Configuration for application notifications."""

    email: str = ""
    enabled: bool = True
    notify_on_shortlist: bool = True
    notify_on_rejection: bool = True
    notify_on_interview: bool = True
    notify_on_assessment: bool = True
    notify_on_walk_in: bool = True
    notify_on_status_change: bool = True


# ============================================================
# STORAGE CONFIGURATION
# ============================================================


@dataclass
class StorageConfig:
    """Locations used for persistent JobAgent data."""

    jobs_file: str = "data/jobs/jobs.json"
    applications_file: str = "data/jobs/applications.json"
    application_history_file: str = "data/jobs/application_history.json"


# ============================================================
# MAIN JOBAGENT CONFIGURATION
# ============================================================


@dataclass
class JobAgentConfig:
    """Central configuration for JobAgent."""

    search: JobSearchConfig = field(default_factory=JobSearchConfig)
    application: ApplicationConfig = field(default_factory=ApplicationConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)

    # ========================================================
    # DIRECTORY MANAGEMENT
    # ========================================================

    def ensure_directories(self) -> None:
        """Create directories required by JobAgent."""

        paths = [
            self.application.tailored_resume_directory,
            self.browser.profile_directory
            if self.browser.persistent
            else None,
            Path(self.storage.jobs_file).parent,
            Path(self.storage.applications_file).parent,
            Path(self.storage.application_history_file).parent,
        ]

        for path in paths:
            if not path:
                continue
            Path(path).mkdir(parents=True, exist_ok=True)

    # ========================================================
    # CONFIGURATION VALIDATION
    # ========================================================

    def validate(self) -> None:
        """Validate all configuration values."""

        score = self.search.minimum_match_score
        if not isinstance(score, (int, float)):
            raise ValueError("minimum_match_score must be numeric.")
        if not 0.0 <= score <= 100.0:
            raise ValueError("minimum_match_score must be between 0 and 100.")

        if not str(self.application.resume_path or "").strip():
            raise ValueError("resume_path cannot be empty.")

        if not str(self.application.tailored_resume_directory or "").strip():
            raise ValueError("tailored_resume_directory cannot be empty.")

        if self.application.auto_submit and not self.application.require_confirmation:
            raise ValueError(
                "Automatic submission requires confirmation protection to remain enabled."
            )

        if self.browser.persistent:
            if not str(self.browser.profile_directory or "").strip():
                raise ValueError("browser profile_directory cannot be empty.")

        if self.browser.timeout <= 0:
            raise ValueError("browser timeout must be greater than zero.")

        email = self.notification.email.strip()
        if self.notification.enabled and not email:
            raise ValueError(
                "Notification email must be provided when notifications are enabled."
            )

    # ========================================================
    # SERIALIZATION
    # ========================================================

    def to_dict(self) -> dict:
        """Return the configuration as a plain dictionary."""

        return {
            "search": {
                "keywords": list(self.search.keywords),
                "locations": list(self.search.locations),
                "minimum_match_score": self.search.minimum_match_score,
                "auto_select_eligible": self.search.auto_select_eligible,
            },
            "application": {
                "resume_path": self.application.resume_path,
                "tailored_resume_directory": self.application.tailored_resume_directory,
                "require_confirmation": self.application.require_confirmation,
                "auto_submit": self.application.auto_submit,
            },
            "browser": {
                "persistent": self.browser.persistent,
                "profile_directory": self.browser.profile_directory,
                "headless": self.browser.headless,
                "timeout": self.browser.timeout,
            },
            "notification": {
                "email": self.notification.email,
                "enabled": self.notification.enabled,
                "notify_on_shortlist": self.notification.notify_on_shortlist,
                "notify_on_rejection": self.notification.notify_on_rejection,
                "notify_on_interview": self.notification.notify_on_interview,
                "notify_on_assessment": self.notification.notify_on_assessment,
                "notify_on_walk_in": self.notification.notify_on_walk_in,
                "notify_on_status_change": self.notification.notify_on_status_change,
            },
            "storage": {
                "jobs_file": self.storage.jobs_file,
                "applications_file": self.storage.applications_file,
                "application_history_file": self.storage.application_history_file,
            },
        }


# ============================================================
# DEFAULT CONFIGURATION FACTORY
# ============================================================


def create_default_config() -> JobAgentConfig:
    """
    Create a default JobAgent configuration.

    Directory creation remains explicit through ``ensure_directories()``.
    """

    return JobAgentConfig()
