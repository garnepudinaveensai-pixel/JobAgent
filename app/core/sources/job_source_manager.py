from __future__ import annotations

from typing import Any, Optional

from app.core.sources.job_source import JobSource, SourceAccessError


class JobSourceManager:
    """Coordinates discovery across multiple job sources."""

    def __init__(self, sources: Optional[list[JobSource]] = None):
        self.sources = list(sources or [])
        self.last_diagnostics: list[dict[str, Any]] = []

    def add_source(self, source: JobSource) -> None:
        if source not in self.sources:
            self.sources.append(source)

    def get_sources(self) -> list[JobSource]:
        return list(self.sources)

    def get_diagnostics(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.last_diagnostics]

    @staticmethod
    def _get_source_options(source: JobSource, options: dict[str, Any]) -> dict[str, Any]:
        if not options:
            return {}
        supported = source.get_supported_options()
        if not supported:
            return {}
        return {key: value for key, value in options.items() if key in supported}

    def search(
        self,
        keywords: str,
        location: Optional[str] = None,
        **source_options: Any,
    ) -> list[dict]:
        if not keywords or not keywords.strip():
            raise ValueError("keywords cannot be empty.")

        results: list[dict] = []
        self.last_diagnostics = []

        for source in self.sources:
            source_name = str(getattr(source, "name", "unknown"))

            try:
                available = source.is_available()
            except Exception as exc:
                diagnostic = {
                    "source": source_name,
                    "status": "availability_failed",
                    "jobs": 0,
                    "error": str(exc),
                    "code": "availability_failed",
                    "requires_human_action": False,
                }
                self.last_diagnostics.append(diagnostic)
                print(f"Warning: {source_name} availability check failed: {exc}")
                continue

            if not available:
                self.last_diagnostics.append({
                    "source": source_name,
                    "status": "unavailable",
                    "jobs": 0,
                    "error": "Source is unavailable.",
                    "code": "source_unavailable",
                    "requires_human_action": False,
                })
                continue

            options = self._get_source_options(source, source_options)

            try:
                jobs = source.search(
                    keywords=keywords.strip(),
                    location=location,
                    **options,
                )
            except SourceAccessError as exc:
                diagnostic = {
                    "source": source_name,
                    "status": "blocked",
                    "jobs": 0,
                    "error": str(exc),
                    "code": exc.code,
                    "requires_human_action": exc.requires_human_action,
                }
                self.last_diagnostics.append(diagnostic)
                print(f"Warning: {source_name} source blocked: {exc}")
                continue
            except Exception as exc:
                diagnostic = {
                    "source": source_name,
                    "status": "failed",
                    "jobs": 0,
                    "error": str(exc),
                    "code": "source_failed",
                    "requires_human_action": False,
                }
                self.last_diagnostics.append(diagnostic)
                print(f"Warning: {source_name} source failed: {exc}")
                continue

            if jobs is None:
                jobs = []

            valid_count = 0
            for job in jobs:
                if not isinstance(job, dict):
                    continue

                normalized = dict(job)
                normalized.setdefault("source", source_name)

                for field in ("title", "company", "location", "url", "description"):
                    normalized[field] = str(normalized.get(field, "") or "").strip()

                results.append(normalized)
                valid_count += 1

            source_diagnostic = getattr(source, "last_diagnostic", None)
            if isinstance(source_diagnostic, dict):
                diagnostic = dict(source_diagnostic)
                diagnostic.setdefault("source", source_name)
                diagnostic["jobs"] = valid_count
            else:
                diagnostic = {
                    "source": source_name,
                    "status": "ok" if valid_count else "no_results",
                    "jobs": valid_count,
                    "error": None if valid_count else "No usable job listings were extracted.",
                    "code": "ok" if valid_count else "no_results",
                    "requires_human_action": False,
                }

            self.last_diagnostics.append(diagnostic)

        return results
