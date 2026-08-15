from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class JobSource(ABC):
    """
    Common interface for every job source.

    Every source must return normalized job dictionaries.
    """

    name: str = "unknown"

    @abstractmethod
    def search(
        self,
        keywords: str,
        location: Optional[str] = None,
    ) -> list[dict]:
        """
        Search for jobs using the source.
        """
        raise NotImplementedError

    def is_available(self) -> bool:
        """
        Return whether this source is currently available.
        """
        return True