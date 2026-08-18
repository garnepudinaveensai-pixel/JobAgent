from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class SourceAccessError(RuntimeError):
    """Raised when a public source cannot be accessed safely."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "source_access_error",
        requires_human_action: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.requires_human_action = requires_human_action


class JobSource(ABC):
    """Common interface for every job source."""

    name: str = "unknown"

    @abstractmethod
    def search(
        self,
        keywords: str,
        location: Optional[str] = None,
        **options: Any,
    ) -> list[dict]:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True

    def supports_option(self, option: str) -> bool:
        return option in self.get_supported_options()

    def get_supported_options(self) -> set[str]:
        return set()
