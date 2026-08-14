import json
from pathlib import Path
from typing import Optional

from app.jobs.job import Job


class JobStore:
    """
    Persistent local storage for discovered jobs and their
    application lifecycle.

    Storage format:
        data/jobs/jobs.json
    """

    VALID_STATUSES = {
        "discovered",
        "matched",
        "selected",
        "application_started",
        "applied",
        "application_failed",
        "shortlisted",
        "rejected",
        "interview",
        "assessment",
        "walk_in",
        "status_changed",
    }

    def __init__(
        self,
        storage_path: str = "data/jobs/jobs.json",
    ):
        self.storage_path = Path(storage_path)

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._data = self._load()

    # ========================================================
    # LOAD / SAVE
    # ========================================================

    def _load(self) -> dict:
        if not self.storage_path.exists():
            return {"jobs": {}}

        try:
            with open(
                self.storage_path,
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            if not isinstance(data, dict):
                return {"jobs": {}}

            if not isinstance(
                data.get("jobs"),
                dict,
            ):
                data["jobs"] = {}

            return data

        except (
            json.JSONDecodeError,
            OSError,
        ):
            return {"jobs": {}}

    def _save(self) -> None:
        temporary_path = self.storage_path.with_suffix(
            ".tmp"
        )

        with open(
            temporary_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                self._data,
                file,
                indent=2,
                ensure_ascii=False,
            )

        temporary_path.replace(
            self.storage_path
        )

    # ========================================================
    # JOB ID
    # ========================================================

    @staticmethod
    def _job_id(job: Job | dict) -> str:
        """
        Generate a stable identifier.

        URL is preferred because it normally uniquely identifies
        a job posting.
        """

        if isinstance(job, Job):
            url = job.url
            title = job.title
            company = job.company
        else:
            url = job.get("url", "")
            title = job.get("title", "")
            company = job.get("company", "")

        if url:
            return url.strip()

        return (
            f"{company.strip()}|"
            f"{title.strip()}"
        ).lower()

    # ========================================================
    # ADD / UPDATE
    # ========================================================

    def add_job(
        self,
        job: Job | dict,
        status: str = "discovered",
    ) -> str:
        """
        Add a job if it doesn't already exist.

        Returns:
            Stable job ID.
        """

        if status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid job status: {status}"
            )

        job_id = self._job_id(job)

        if not job_id:
            raise ValueError(
                "Job must contain a URL or "
                "title/company combination."
            )

        if isinstance(job, Job):
            job_data = job.to_dict()
        else:
            job_data = dict(job)

        existing = self._data["jobs"].get(
            job_id,
            {},
        )

        record = {
            **existing,
            **job_data,
            "job_id": job_id,
            "status": existing.get(
                "status",
                status,
            ),
        }

        self._data["jobs"][job_id] = record

        self._save()

        return job_id

    # ========================================================
    # GET
    # ========================================================

    def get_job(
        self,
        job_id: str,
    ) -> Optional[dict]:
        """
        Return one stored job.
        """

        return self._data["jobs"].get(
            job_id
        )

    def get_all_jobs(self) -> list[dict]:
        """
        Return every stored job.
        """

        return list(
            self._data["jobs"].values()
        )

    # ========================================================
    # STATUS
    # ========================================================

    def update_status(
        self,
        job_id: str,
        status: str,
    ) -> bool:
        """
        Update application status.

        Returns False if the job does not exist.
        """

        if status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid job status: {status}"
            )

        job = self.get_job(job_id)

        if job is None:
            return False

        job["status"] = status

        self._save()

        return True

    def get_status(
        self,
        job_id: str,
    ) -> Optional[str]:
        """
        Return current status of a job.
        """

        job = self.get_job(job_id)

        if job is None:
            return None

        return job.get("status")

    # ========================================================
    # DUPLICATE CHECK
    # ========================================================

    def has_job(
        self,
        job_id: str,
    ) -> bool:
        """
        Check whether a job already exists.
        """

        return job_id in self._data["jobs"]

    # ========================================================
    # FILTER BY STATUS
    # ========================================================

    def get_jobs_by_status(
        self,
        status: str,
    ) -> list[dict]:
        """
        Return jobs currently having the requested status.
        """

        if status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid job status: {status}"
            )

        return [
            job
            for job in self.get_all_jobs()
            if job.get("status") == status
        ]

    # ========================================================
    # COUNT
    # ========================================================

    def count(self) -> int:
        """
        Return total number of stored jobs.
        """

        return len(
            self._data["jobs"]
        )