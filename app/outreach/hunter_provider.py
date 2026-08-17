from __future__ import annotations

import json
import os
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.outreach.contact_discovery import (
    ContactDiscoveryProvider,
)


class HunterProvider(
    ContactDiscoveryProvider
):
    """
    Hunter domain-search adapter.

    Configuration:

        HUNTER_API_KEY

    Optional:

        HUNTER_API_URL

    The provider only performs contact discovery.
    It does not send email.
    """

    name = "hunter"

    DEFAULT_API_URL = (
        "https://api.hunter.io/v2/domain-search"
    )

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.api_key = (
            api_key
            if api_key is not None
            else os.getenv(
                "HUNTER_API_KEY",
                "",
            )
        ).strip()

        self.api_url = (
            api_url
            if api_url is not None
            else os.getenv(
                "HUNTER_API_URL",
                self.DEFAULT_API_URL,
            )
        ).strip()

        self.timeout = float(
            timeout
        )

    def is_available(self) -> bool:
        return bool(
            self.api_key
            and self.api_url
        )

    def search(
        self,
        company: str,
        domain: Optional[str] = None,
        job: Optional[dict] = None,
        **options: Any,
    ) -> list[dict]:
        if not self.api_key:
            return []

        domain = (
            str(
                domain
                or ""
            ).strip()
        )

        if not domain:
            return []

        params = {
            "domain": domain,
            "api_key": self.api_key,
        }

        for key in (
            "limit",
            "type",
            "seniority",
            "department",
        ):
            value = options.get(
                key
            )

            if value not in (
                None,
                "",
            ):
                params[key] = value

        url = (
            self.api_url
            + "?"
            + urlencode(params)
        )

        request = Request(
            url,
            headers={
                "Accept": (
                    "application/json"
                ),
                "User-Agent": (
                    "JobAgent/1.0"
                ),
            },
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                payload = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

        except (
            HTTPError,
            URLError,
            TimeoutError,
            ValueError,
        ):
            return []

        return self._normalize_response(
            payload,
            company=company,
            domain=domain,
        )

    @staticmethod
    def _normalize_response(
        payload: Any,
        company: str,
        domain: str,
    ) -> list[dict]:
        if not isinstance(
            payload,
            dict,
        ):
            return []

        data = payload.get(
            "data",
            {},
        )

        if not isinstance(
            data,
            dict,
        ):
            return []

        emails = data.get(
            "emails",
            [],
        )

        if not isinstance(
            emails,
            list,
        ):
            return []

        results: list[dict] = []

        for item in emails:
            if not isinstance(
                item,
                dict,
            ):
                continue

            email = item.get(
                "value",
                item.get(
                    "email",
                    "",
                ),
            )

            if not email:
                continue

            results.append(
                {
                    "email": email,
                    "name": (
                        item.get(
                            "first_name",
                            "",
                        )
                        + " "
                        + item.get(
                            "last_name",
                            "",
                        )
                    ).strip(),
                    "role": item.get(
                        "position",
                        "",
                    ),
                    "company": company,
                    "source": "hunter",
                    "confidence": (
                        item.get(
                            "confidence",
                            0,
                        )
                    ),
                    "verification_status": (
                        item.get(
                            "verification",
                            {}
                        ).get(
                            "status",
                            "unknown",
                        )
                        if isinstance(
                            item.get(
                                "verification"
                            ),
                            dict,
                        )
                        else "unknown"
                    ),
                    "domain": domain,
                    "phone": item.get(
                        "phone_number",
                        "",
                    ),
                    "source_url": (
                        item.get(
                            "sources",
                            [{}],
                        )[0].get(
                            "uri",
                            "",
                        )
                        if isinstance(
                            item.get(
                                "sources"
                            ),
                            list,
                        )
                        and item.get(
                            "sources"
                        )
                        and isinstance(
                            item.get(
                                "sources"
                            )[0],
                            dict,
                        )
                        else ""
                    ),
                }
            )

        return results


__all__ = [
    "HunterProvider",
]