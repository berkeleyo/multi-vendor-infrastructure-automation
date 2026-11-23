"""FastAPI control-plane interface over shared application and diagnostic services."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from mvia import __version__
from mvia.application import ApplicationService
from mvia.diagnostics.dns import DNSDiagnostic
from mvia.diagnostics.http import HTTPDiagnostic
from mvia.diagnostics.models import (
    DNSRequest,
    DNSResult,
    HTTPRequest,
    HTTPResult,
    TLSRequest,
    TLSResult,
)
from mvia.diagnostics.tls import TLSDiagnostic
from mvia.errors import ConfigurationError, MviaError, UnsafeTargetError
from mvia.models import DriftReport, Inventory
from mvia.redaction import redact
from mvia.settings import Settings

settings = Settings.from_env()
PROJECT_ROOT = Path(__file__).resolve().parents[3]
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("mvia")

app = FastAPI(
    title="Multi-Vendor Infrastructure Automation",
    description="Read-only infrastructure control-plane and provider-neutral diagnostics",
    version=__version__,
)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next: Any) -> Any:
    supplied = request.headers.get("x-correlation-id")
    request_id = supplied if supplied and 8 <= len(supplied) <= 128 else uuid.uuid4().hex
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("mvia request failed", extra={"request_id": request_id})
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An internal error occurred",
                    "request_id": request_id,
                }
            },
        )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(MviaError)
async def mvia_error_handler(request: Request, exc: MviaError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
    code = (
        "unsafe_target"
        if isinstance(exc, UnsafeTargetError)
        else ("configuration_error" if isinstance(exc, ConfigurationError) else "provider_error")
    )
    return JSONResponse(
        status_code=422 if isinstance(exc, UnsafeTargetError) else 400,
        headers={"X-Request-ID": request_id},
        content={
            "error": {
                "code": code,
                "message": redact(str(exc)),
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
    return JSONResponse(
        status_code=exc.status_code,
        headers={"X-Request-ID": request_id},
        content={
            "error": {
                "code": "validation_error",
                "message": str(exc.detail),
                "request_id": request_id,
            }
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "multi-vendor-infrastructure-automation",
        "version": __version__,
    }


@app.get("/api/v1/health")
def api_health() -> dict[str, object]:
    return {
        "status": "healthy",
        "service": "multi-vendor-infrastructure-automation",
        "version": __version__,
        "capabilities": [
            "discovery",
            "drift",
            "dns_diagnostics",
            "tls_diagnostics",
            "http_diagnostics",
        ],
    }


@app.get("/api/v1/providers")
def providers() -> dict[str, list[dict[str, object]]]:
    return {
        "providers": [
            {"name": "aws", "capabilities": ["discover"]},
            {"name": "azure", "capabilities": ["discover"]},
            {"name": "cloudflare", "capabilities": ["discover"]},
            {"name": "palo_alto", "capabilities": ["discover"]},
        ]
    }


@app.post("/api/v1/discovery")
def discovery() -> Inventory:
    config_path = PROJECT_ROOT / "examples/offline.yaml"
    if not config_path.is_file():
        raise ConfigurationError("offline fixture configuration is unavailable")
    return ApplicationService().discover(config_path)


@app.post("/api/v1/drift")
def drift() -> DriftReport:
    config_path = PROJECT_ROOT / "examples/offline.yaml"
    desired_path = PROJECT_ROOT / "examples/desired.yaml"
    if not config_path.is_file() or not desired_path.is_file():
        raise ConfigurationError("offline drift fixtures are unavailable")
    return ApplicationService().drift(config_path, desired_path)


@app.post("/api/v1/diagnostics/dns", response_model=DNSResult)
def diagnose_dns(request: DNSRequest) -> DNSResult:
    return DNSDiagnostic(timeout=settings.diagnostic_timeout).run(request)


@app.post("/api/v1/diagnostics/tls", response_model=TLSResult)
def diagnose_tls(request: TLSRequest) -> TLSResult:
    return TLSDiagnostic(timeout=settings.diagnostic_timeout).run(request)


@app.post("/api/v1/diagnostics/http", response_model=HTTPResult)
def diagnose_http(request: HTTPRequest) -> HTTPResult:
    return HTTPDiagnostic(
        timeout=settings.diagnostic_timeout,
        redirect_limit=settings.diagnostic_redirect_limit,
        response_size_limit=settings.diagnostic_response_size_limit,
    ).run(request)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
