from __future__ import annotations

from typing import Iterable
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)


class JobDeduplicator:
    """
    Deduplicate jobs collected from multiple job sources.

    The same underlying job may appear on:
        - Greenhouse
        - Lever
        - Indeed
        - Naukri
        - Workday
        - Company career pages

    Deduplication strategy:

        1. Canonical URL
        2. Company + title + location
        3. Company + title

    Source is intentionally NOT part of the identity because
    the same job may appear on multiple sources.
    """

    TRACKING_PARAMETERS = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "gclid",
        "fbclid",
        "ref",
        "source",
    }

    def deduplicate(
        self,
        jobs: Iterable[dict],
    ) -> list[dict]:
        """
        Return unique jobs while preserving input order.

        When duplicate jobs are found, the richer record is
        retained and source information is combined.
        """

        unique: list[dict] = []

        # Identity indexes.
        url_index: dict[str, int] = {}
        detailed_index: dict[str, int] = {}
        basic_index: dict[str, int] = {}

        for job in jobs:
            if not isinstance(job, dict):
                continue

            normalized = self._normalize_job(job)

            if not self._has_identity(normalized):
                continue

            url_key = self.canonicalize_url(
                normalized.get("url", "")
            )

            detailed_key = self._detailed_key(
                normalized
            )

            basic_key = self._basic_key(
                normalized
            )

            existing_index = None

            # ------------------------------------------------
            # URL identity
            # ------------------------------------------------

            if url_key:
                existing_index = url_index.get(
                    url_key
                )

            # ------------------------------------------------
            # Company + title + location identity
            # ------------------------------------------------

            if existing_index is None and detailed_key:
                existing_index = detailed_index.get(
                    detailed_key
                )

            # ------------------------------------------------
            # Company + title fallback
            # ------------------------------------------------

            if existing_index is None and basic_key:
                existing_index = basic_index.get(
                    basic_key
                )

            # ------------------------------------------------
            # New job
            # ------------------------------------------------

            if existing_index is None:
                index = len(unique)

                unique.append(normalized)

                if url_key:
                    url_index[url_key] = index

                if detailed_key:
                    detailed_index[detailed_key] = index

                if basic_key:
                    basic_index[basic_key] = index

                continue

            # ------------------------------------------------
            # Duplicate job
            # ------------------------------------------------

            merged = self._merge_jobs(
                unique[existing_index],
                normalized,
            )

            unique[existing_index] = merged

            # Add any newly discovered identities.
            merged_url = self.canonicalize_url(
                merged.get("url", "")
            )

            if merged_url:
                url_index[merged_url] = existing_index

            merged_detailed_key = self._detailed_key(
                merged
            )

            if merged_detailed_key:
                detailed_index[
                    merged_detailed_key
                ] = existing_index

            merged_basic_key = self._basic_key(
                merged
            )

            if merged_basic_key:
                basic_index[
                    merged_basic_key
                ] = existing_index

        return unique

    # ========================================================
    # NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_job(
        job: dict,
    ) -> dict:
        """
        Normalize the common job fields without destroying
        source-specific fields.
        """

        normalized = dict(job)

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

        return normalized

    # ========================================================
    # URL
    # ========================================================

    @classmethod
    def canonicalize_url(
        cls,
        url: str,
    ) -> str:
        """
        Canonicalize a job URL.

        Removes common tracking parameters while preserving
        the actual job identifier.
        """

        url = str(
            url or ""
        ).strip()

        if not url:
            return ""

        try:
            parts = urlsplit(url)

            scheme = parts.scheme.lower()
            netloc = parts.netloc.lower()

            path = parts.path.rstrip("/")

            query_pairs = [
                (key, value)
                for key, value in parse_qsl(
                    parts.query,
                    keep_blank_values=True,
                )
                if key.lower()
                not in cls.TRACKING_PARAMETERS
            ]

            query_pairs.sort()

            query = urlencode(
                query_pairs
            )

            return urlunsplit(
                (
                    scheme,
                    netloc,
                    path,
                    query,
                    "",
                )
            ).lower()

        except Exception:
            return url.lower().rstrip("/")

    # ========================================================
    # IDENTITY
    # ========================================================

    @staticmethod
    def _clean_identity_value(
        value: str,
    ) -> str:
        """
        Normalize a value used for duplicate detection.
        """

        value = str(
            value or ""
        ).strip().lower()

        return " ".join(
            value.split()
        )

    def _detailed_key(
        self,
        job: dict,
    ) -> str:
        """
        Company + title + location identity.
        """

        company = self._clean_identity_value(
            job.get("company", "")
        )

        title = self._clean_identity_value(
            job.get("title", "")
        )

        location = self._clean_identity_value(
            job.get("location", "")
        )

        if not company or not title:
            return ""

        return (
            f"{company}|"
            f"{title}|"
            f"{location}"
        )

    def _basic_key(
        self,
        job: dict,
    ) -> str:
        """
        Company + title fallback identity.
        """

        company = self._clean_identity_value(
            job.get("company", "")
        )

        title = self._clean_identity_value(
            job.get("title", "")
        )

        if not company or not title:
            return ""

        return (
            f"{company}|"
            f"{title}"
        )

    @staticmethod
    def _has_identity(
        job: dict,
    ) -> bool:
        """
        Return whether a job contains enough information
        to participate safely in deduplication.
        """

        return bool(
            job.get("url")
            or (
                job.get("company")
                and job.get("title")
            )
        )

    # ========================================================
    # MERGING
    # ========================================================

    @staticmethod
    def _merge_jobs(
        existing: dict,
        incoming: dict,
    ) -> dict:
        """
        Merge duplicate records.

        Prefer non-empty/richer values from the incoming
        record while preserving existing information.
        """

        merged = dict(existing)

        for key, value in incoming.items():

            if key == "source":
                continue

            if (
                key not in merged
                or not merged[key]
            ):
                merged[key] = value

        # Prefer the longer description.
        existing_description = str(
            merged.get(
                "description",
                "",
            )
        )

        incoming_description = str(
            incoming.get(
                "description",
                "",
            )
        )

        if len(incoming_description) > len(
            existing_description
        ):
            merged["description"] = (
                incoming_description
            )

        # ----------------------------------------------------
        # Preserve all sources
        # ----------------------------------------------------

        sources = []

        for record in (
            existing,
            incoming,
        ):
            source = record.get(
                "source"
            )

            if source:
                if isinstance(
                    source,
                    list,
                ):
                    sources.extend(
                        source
                    )
                else:
                    sources.append(
                        str(source)
                    )

        # Remove duplicates while preserving order.
        unique_sources = []

        for source in sources:
            if source not in unique_sources:
                unique_sources.append(
                    source
                )

        if unique_sources:
            merged["source"] = (
                unique_sources[0]
                if len(unique_sources) == 1
                else unique_sources
            )

        return merged