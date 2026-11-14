"""HTTP client with bounded retries and explicit errors."""

import time
from collections.abc import Iterator
from typing import Any

import httpx

from mvia.errors import ProviderError


class ApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        headers: dict[str, str],
        verify: bool = True,
        timeout: float = 15.0,
        retries: int = 3,
    ) -> None:
        self.client = httpx.Client(
            base_url=base_url, headers=headers, verify=verify, timeout=httpx.Timeout(timeout)
        )
        self.retries = retries

    def close(self) -> None:
        self.client.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        for attempt in range(self.retries + 1):
            try:
                response = self.client.get(path, params=params)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < self.retries:
                    try:
                        delay = float(response.headers.get("Retry-After", 2**attempt))
                    except ValueError:
                        delay = float(2**attempt)
                    delay = min(max(delay, 0.0), 8.0)
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                return response
            except httpx.HTTPError as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    raise ProviderError(
                        f"API request failed after {attempt + 1} attempts: {type(exc).__name__}"
                    ) from exc
                if attempt == self.retries:
                    raise ProviderError(
                        f"API request failed after {attempt + 1} attempts: {type(exc).__name__}"
                    ) from exc
                time.sleep(min(2**attempt, 8))
        raise ProviderError("unreachable retry state")

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._get(path, params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("API returned malformed JSON") from exc
        if not isinstance(payload, dict):
            raise ProviderError("API returned a non-object JSON response")
        return payload

    def get_text(self, path: str, params: dict[str, Any] | None = None) -> str:
        return self._get(path, params).text

    def cloudflare_pages(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Iterator[dict[str, Any]]:
        page = 1
        while True:
            payload = self.get_json(path, {**(params or {}), "page": page, "per_page": 100})
            if not payload.get("success", False):
                raise ProviderError("Cloudflare API reported failure")
            result = payload.get("result", [])
            if not isinstance(result, list):
                raise ProviderError("Cloudflare result was not a list")
            yield from (item for item in result if isinstance(item, dict))
            info = payload.get("result_info", {})
            if not isinstance(info, dict):
                raise ProviderError("Cloudflare result_info was not an object")
            try:
                total_pages = int(info.get("total_pages", 1))
            except (TypeError, ValueError) as exc:
                raise ProviderError("Cloudflare total_pages was invalid") from exc
            if total_pages < 1:
                raise ProviderError("Cloudflare total_pages was invalid")
            if page >= total_pages:
                return
            page += 1
