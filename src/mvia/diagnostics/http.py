"""HTTP diagnostics restricted to validated public network targets."""

from __future__ import annotations

import time
from contextlib import nullcontext
from urllib.parse import urlsplit

import httpx

from mvia.diagnostics.models import DiagnosticStatus, HTTPRequest, HTTPResult
from mvia.diagnostics.safety import resolve_public_addresses, validate_url

SAFE_RESPONSE_HEADERS = ("content-type", "cache-control", "etag", "last-modified")
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class HTTPDiagnostic:
    def __init__(
        self,
        timeout: float = 3.0,
        redirect_limit: int = 3,
        response_size_limit: int = 262144,
        client: httpx.Client | None = None,
    ) -> None:
        self.timeout = timeout
        self.redirect_limit = redirect_limit
        self.response_size_limit = response_size_limit
        self.client = client

    def run(self, request: HTTPRequest) -> HTTPResult:
        start = time.monotonic()
        deadline = start + self.timeout
        current = request.url
        redirects = 0
        last_status: int | None = None
        safe_headers: dict[str, str] = {}
        error: str | None = None
        # Different hostnames can resolve to the same IP. Use a fresh connection so TLS
        # is verified for the hostname of this hop, and ignore environment proxy routing.
        client_context = (
            nullcontext(self.client)
            if self.client is not None
            else httpx.Client(trust_env=False, limits=httpx.Limits(max_keepalive_connections=0))
        )
        try:
            with client_context as client:
                while True:
                    scheme, hostname, port = validate_url(current)
                    addresses = resolve_public_addresses(hostname)
                    url = httpx.URL(current).copy_with(fragment=None)
                    host = (
                        hostname
                        if port == (443 if scheme == "https" else 80)
                        else f"{hostname}:{port}"
                    )
                    for address in addresses:
                        outgoing = httpx.Request(
                            request.method,
                            url.copy_with(host=address),
                            headers={"Host": host, "Accept": "*/*", "Accept-Encoding": "identity"},
                            extensions={
                                "sni_hostname": hostname,
                                "timeout": httpx.Timeout(self._remaining(deadline)).as_dict(),
                            },
                        )
                        try:
                            response = client.send(outgoing, stream=True, follow_redirects=False)
                        except (httpx.ConnectError, httpx.ConnectTimeout):
                            if address != addresses[-1]:
                                continue
                            raise
                        break
                    try:
                        self._remaining(deadline)
                        last_status = response.status_code
                        safe_headers = {
                            name: response.headers[name]
                            for name in SAFE_RESPONSE_HEADERS
                            if name in response.headers
                        }
                        location = response.headers.get("location")
                        if last_status in REDIRECT_STATUSES and location:
                            if redirects >= self.redirect_limit:
                                error = "redirect limit exceeded"
                                break
                            current = str(url.join(location))
                            redirects += 1
                            continue
                        if request.method == "GET":
                            size = 0
                            for chunk in response.iter_raw():
                                self._remaining(deadline)
                                size += len(chunk)
                                if size > self.response_size_limit:
                                    error = "response exceeds maximum size"
                                    break
                        self._remaining(deadline)
                        break
                    finally:
                        response.close()
        except httpx.TimeoutException:
            error = "HTTP request timeout"
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            error = f"HTTP request failed: {type(exc).__name__}"

        status = DiagnosticStatus.WARNING
        if error:
            status = DiagnosticStatus.ERROR
        elif last_status is not None and 200 <= last_status < 400:
            status = DiagnosticStatus.OK
        return HTTPResult(
            url=request.url,
            final_url=current,
            status=status,
            http_status=last_status,
            method=request.method,
            total_duration_ms=round((time.monotonic() - start) * 1000, 3),
            redirect_count=redirects,
            headers=safe_headers,
            content_type=safe_headers.get("content-type"),
            tls_used=urlsplit(current).scheme.lower() == "https",
            errors=[error] if error else [],
        )

    @staticmethod
    def _remaining(deadline: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise httpx.TimeoutException("diagnostic deadline exceeded")
        return remaining
