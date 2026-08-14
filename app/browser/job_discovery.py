from typing import Optional

from app.browser.browser_manager import BrowserManager
from app.browser.sites.greenhouse import GreenhouseSite


class JobDiscovery:
    """
    Coordinates job discovery across supported job sites.

    Responsible for:
    - opening a job site
    - searching for jobs
    - collecting listings
    - collecting detailed job information

    Does NOT:
    - match jobs to resumes
    - tailor resumes
    - submit applications
    """

    def __init__(
        self,
        browser: BrowserManager,
    ):
        self.browser = browser

    def discover_greenhouse(
        self,
        board_url: str,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:
        """
        Discover jobs from a public Greenhouse job board.
        """

        if not board_url or not board_url.strip():
            raise ValueError("board_url cannot be empty.")

        if not keywords or not keywords.strip():
            raise ValueError("keywords cannot be empty.")

        page = self.browser.open(board_url)

        site = GreenhouseSite(page)

        site.search_jobs(
            keywords=keywords,
            location=location,
        )

        return site.get_job_listings()

    def get_greenhouse_job_details(
        self,
        job_url: str,
    ) -> dict:
        """
        Get complete details for one Greenhouse job.
        """

        if not job_url or not job_url.strip():
            raise ValueError("job_url cannot be empty.")

        page = self.browser.open(job_url)

        site = GreenhouseSite(page)

        return site.get_job_details(job_url)