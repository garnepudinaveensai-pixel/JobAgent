from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class JobSource(ABC):
    """
    Common interface for every job source.

    Every source returns normalized job dictionaries.

    Sources may declare which source-specific options they support.
    """

    name: str = "unknown"

    @abstractmethod
    def search(
        self,
        keywords: str,
        location: Optional[str] = None,
        **options: Any,
    ) -> list[dict]:
        """
        Search for jobs using this source.

        Args:
            keywords:
                Job search keywords.

            location:
                Optional location filter.

            **options:
                Source-specific search options.

        Returns:
            A list of normalized job dictionaries.
        """
        raise NotImplementedError

    def is_available(self) -> bool:
        """
        Return whether this source is currently available.
        """
        return True

    def supports_option(
        self,
        option: str,
    ) -> bool:
        """
        Return whether this source explicitly supports
        a source-specific option.

        By default, sources support no optional parameters.
        Individual sources can override this method.
        """
        return False

    def get_supported_options(self) -> set[str]:
        """
        Return the set of source-specific options supported
        by this source.
        """
        return set()