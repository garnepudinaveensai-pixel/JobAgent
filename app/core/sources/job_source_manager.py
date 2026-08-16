from __future__ import annotations

from typing import Any, Optional

from app.core.sources.job_source import JobSource


class JobSourceManager:
    """
    Coordinates job discovery across multiple sources.

    Responsibilities:

        Source availability
            ↓
        Source-specific options
            ↓
        Source search
            ↓
        Result validation
            ↓
        Common-field normalization
            ↓
        Combined results

    Deduplication is intentionally handled outside this
    manager by the orchestration layer.
    """

    def __init__(
        self,
        sources: Optional[list[JobSource]] = None,
    ):
        self.sources = list(
            sources or []
        )

    # ========================================================
    # SOURCE MANAGEMENT
    # ========================================================

    def add_source(
        self,
        source: JobSource,
    ) -> None:
        """
        Register a job source.

        The same source instance is not registered twice.
        """

        if source not in self.sources:
            self.sources.append(
                source
            )

    def get_sources(
        self,
    ) -> list[JobSource]:
        """
        Return a copy of registered sources.
        """

        return list(
            self.sources
        )

    # ========================================================
    # OPTION HANDLING
    # ========================================================

    @staticmethod
    def _get_source_options(
        source: JobSource,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Select only options explicitly supported by a source.
        """

        if not options:
            return {}

        supported = source.get_supported_options()

        if not supported:
            return {}

        return {
            key: value
            for key, value in options.items()
            if key in supported
        }

    # ========================================================
    # SEARCH
    # ========================================================

    def search(
        self,
        keywords: str,
        location: Optional[str] = None,
        **source_options: Any,
    ) -> list[dict]:
        """
        Search all registered sources.

        Common parameters:

            keywords
            location

        Source-specific parameters are sent only to sources
        that explicitly declare support for them.

        Deduplication is handled by the orchestration layer.
        """

        if not keywords or not keywords.strip():
            raise ValueError(
                "keywords cannot be empty."
            )

        results: list[dict] = []

        for source in self.sources:

            # ------------------------------------------------
            # AVAILABILITY
            # ------------------------------------------------

            try:
                if not source.is_available():
                    continue

            except Exception as exc:
                print(
                    f"Warning: {source.name} "
                    f"availability check failed: {exc}"
                )
                continue

            # ------------------------------------------------
            # SOURCE OPTIONS
            # ------------------------------------------------

            options = (
                self._get_source_options(
                    source,
                    source_options,
                )
            )

            # ------------------------------------------------
            # SEARCH
            # ------------------------------------------------

            try:
                jobs = source.search(
                    keywords=keywords.strip(),
                    location=location,
                    **options,
                )

            except Exception as exc:
                print(
                    f"Warning: {source.name} "
                    f"source failed: {exc}"
                )
                continue

            if jobs is None:
                continue

            # ------------------------------------------------
            # NORMALIZATION
            # ------------------------------------------------

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

                for field in (
                    "title",
                    "company",
                    "location",
                    "url",
                    "description",
                ):
                    value = normalized.get(
                        field,
                        "",
                    )

                    normalized[field] = str(
                        value or ""
                    ).strip()

                results.append(
                    normalized
                )

        return results