"""Bounded SSRF-safe HTTP diagnostics."""

from __future__ import annotations

import time

import httpx

from mvia.diagnostics.models import DiagnosticStatus, HTTPRequest, HTTPResult
from mvia.diagnostics.safety import resolve_public_addresses, validate_url

SAFE_RESPONSE_HEADERS = ("content-type", "cache-control", "etag", "last-modified")
SENSITIVE_HEADERS = {
    "set-cookie",
    "authorization",
    "proxy-authorization",
    "cookie",
}


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
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
            verify=True,
        )

    def close(self) -> None:
        self.client.close()

    def run(self, request: HTTPRequest) -> HTTPResult:
        start = time.monotonic()
        current = request.url
        redirects = 0
        last_status: int | None = None
        safe_headers: dict[str, str] = {}
        content_type: str | None = None

        try:
            for _ in range(self.redirect_limit + 1):
                scheme, hostname, port = validate_url(current)
                resolve_public_addresses(hostname)
                response = self.client.request(
                    request.method,
                    current,
                    headers={"Accept": "*/*"},
                )
                last_status = response.status_code
                content_type = response.headers.get("content-type")
                safe_headers = {
                    name.lower(): value
                    for name, value in response.headers.items()
                    if name.lower() in SAFE_RESPONSE_HEADERS
                    and name.lower() not in SENSITIVE_HEADERS
                }
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        break
                    if redirects >= self.redirect_limit:
                        duration = (time.monotonic() - start) * 1000
                        return HTTPResult(
                            url=request.url,
                            final_url=current,
                            status=DiagnosticStatus.ERROR,
                            http_status=last_status,
                            method=request.method,
                            total_duration_ms=round(duration, 3),
                            redirect_count=redirects,
                            headers=safe_headers,
                            content_type=content_type,
                            tls_used=scheme == "https",
                            errors=["redirect limit exceeded"],
                        )
                    current = str(httpx.URL(current).join(location))
                    redirects += 1
                    continue
                if len(response.content) > self.response_size_limit:
                    duration = (time.monotonic() - start) * 1000
                    return HTTPResult(
                        url=request.url,
                        final_url=current,
                        status=DiagnosticStatus.ERROR,
                        http_status=last_status,
                        method=request.method,
                        total_duration_ms=round(duration, 3),
                        redirect_count=redirects,
                        headers=safe_headers,
                        content_type=content_type,
                        tls_used=scheme == "https",
                        errors=["response exceeds maximum size"],
                    )
                duration = (time.monotonic() - start) * 1000
                status = (
                    DiagnosticStatus.OK if 200 <= last_status < 400 else DiagnosticStatus.WARNING
                )
                return HTTPResult(
                    url=request.url,
                    final_url=current,
                    status=status,
                    http_status=last_status,
                    method=request.method,
                    total_duration_ms=round(duration, 3),
                    redirect_count=redirects,
                    headers=safe_headers,
                    content_type=content_type,
                    tls_used=scheme == "https",
                )
            duration = (time.monotonic() - start) * 1000
            return HTTPResult(
                url=request.url,
                final_url=current,
                status=DiagnosticStatus.ERROR,
                http_status=last_status,
                method=request.method,
                total_duration_ms=round(duration, 3),
                redirect_count=redirects,
                tls_used=current.startswith("https://"),
                errors=["redirect limit exceeded"],
            )
        except httpx.TimeoutException:
            error = "HTTP request timeout"
        except httpx.TooManyRedirects:
            error = "redirect limit exceeded"
        except httpx.HTTPError as exc:
            error = f"HTTP request failed: {type(exc).__name__}"
        duration = (time.monotonic() - start) * 1000
        return HTTPResult(
            url=request.url,
            final_url=current,
            status=DiagnosticStatus.ERROR,
            http_status=last_status,
            method=request.method,
            total_duration_ms=round(duration, 3),
            redirect_count=redirects,
            tls_used=current.startswith("https://"),
            errors=[error],
        )
