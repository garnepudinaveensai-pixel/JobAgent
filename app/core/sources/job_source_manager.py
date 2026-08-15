from __future__ import annotations

from typing import Optional

from app.core.sources.job_source import JobSource


class JobSourceManager:
    """
    Coordinates job discovery across multiple sources.

    Each source is responsible for its own access method.
    The manager combines their results into one list.
    """

    def __init__(
        self,
        sources: Optional[list[JobSource]] = None,
    ):
        self.sources = sources or []

    # ========================================================
    # SOURCE MANAGEMENT
    # ========================================================

    def add_source(
        self,
        source: JobSource,
    ) -> None:
        """
        Register a job source.
        """

        if source not in self.sources:
            self.sources.append(
                source
            )

    def get_sources(self) -> list[JobSource]:
        """
        Return all registered sources.
        """

        return list(
            self.sources
        )

    # ========================================================
    # SEARCH
    # ========================================================

    def search(
        self,
        keywords: str,
        location: Optional[str] = None,
        **source_options,
    ) -> list[dict]:
        """
        Search every registered source.

        source_options contains source-specific options.

        Example:

            board_url="https://boards.greenhouse.io/company"
        """

        if not keywords or not keywords.strip():
            raise ValueError(
                "keywords cannot be empty."
            )

        results: list[dict] = []

        for source in self.sources:

            if not source.is_available():
                continue

            try:

                jobs = source.search(
                    keywords=keywords,
                    location=location,
                    **source_options,
                )

            except Exception as exc:

                print(
                    f"Warning: {source.name} "
                    f"source failed: {exc}"
                )

                continue

            if jobs is None:
                continue

            for job in jobs:

                if not isinstance(
                    job,
                    dict,
                ):
                    continue

                normalized = dict(
                    job
                )

                normalized.setdefault(
                    "source",
                    source.name,
                )

                results.append(
                    normalized
                )

        return results