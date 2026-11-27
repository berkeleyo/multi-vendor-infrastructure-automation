"""Bounded provider-neutral TLS diagnostics."""

from __future__ import annotations

import socket
import ssl
import time

from mvia.diagnostics.models import DiagnosticStatus, TLSRequest, TLSResult
from mvia.diagnostics.safety import resolve_public_addresses, validate_hostname


class TLSDiagnostic:
    def __init__(self, timeout: float = 3.0) -> None:
        self.timeout = timeout

    def run(self, request: TLSRequest) -> TLSResult:
        hostname = validate_hostname(request.hostname)
        start = time.monotonic()
        addresses = resolve_public_addresses(hostname)
        deadline = start + self.timeout
        context = ssl.create_default_context()
        try:
            for address in addresses:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError
                try:
                    raw_socket = socket.create_connection(
                        (address, request.port), timeout=remaining
                    )
                except OSError:
                    if address != addresses[-1]:
                        continue
                    raise
                break
            with raw_socket as raw:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError
                raw.settimeout(remaining)
                with context.wrap_socket(raw, server_hostname=hostname) as tls:
                    certificate_raw = tls.getpeercert()
                    certificate = certificate_raw if isinstance(certificate_raw, dict) else {}
                    cipher = tls.cipher()
                    version = tls.version()
                    subject_raw = certificate.get("subject", ()) if certificate else ()
                    issuer_raw = certificate.get("issuer", ()) if certificate else ()
                    subject: dict[str, object] = {}
                    issuer: dict[str, object] = {}
                    if isinstance(subject_raw, tuple):
                        for group in subject_raw:
                            if isinstance(group, tuple):
                                for item in group:
                                    if isinstance(item, tuple) and len(item) == 2:
                                        subject[str(item[0])] = str(item[1])
                    if isinstance(issuer_raw, tuple):
                        for group in issuer_raw:
                            if isinstance(group, tuple):
                                for item in group:
                                    if isinstance(item, tuple) and len(item) == 2:
                                        issuer[str(item[0])] = str(item[1])
                    san_entries = certificate.get("subjectAltName", ()) if certificate else ()
                    san: list[str] = []
                    if isinstance(san_entries, tuple):
                        for entry in san_entries:
                            if isinstance(entry, tuple) and len(entry) == 2:
                                kind, value = entry
                                if kind == "DNS" and isinstance(value, str):
                                    san.append(value)
                    not_before_raw = certificate.get("notBefore") if certificate else None
                    not_after_raw = certificate.get("notAfter") if certificate else None
                    not_before = not_before_raw if isinstance(not_before_raw, str) else None
                    not_after = not_after_raw if isinstance(not_after_raw, str) else None
                    duration = (time.monotonic() - start) * 1000
                    return TLSResult(
                        hostname=hostname,
                        port=request.port,
                        status=DiagnosticStatus.OK,
                        handshake_success=True,
                        tls_version=version,
                        cipher=cipher[0] if cipher else None,
                        subject=subject,
                        issuer=issuer,
                        san=san,
                        not_before=not_before,
                        not_after=not_after,
                        hostname_valid=True,
                        chain_validation="valid",
                        duration_ms=round(duration, 3),
                    )
        except TimeoutError:
            error = "TLS or TCP connection timeout"
        except ssl.CertificateError as exc:
            error = f"Certificate validation failed: {type(exc).__name__}"
        except ssl.SSLError as exc:
            error = f"TLS handshake failed: {type(exc).__name__}"
        except OSError as exc:
            error = f"Connection failed: {type(exc).__name__}"
        duration = (time.monotonic() - start) * 1000
        return TLSResult(
            hostname=hostname,
            port=request.port,
            status=DiagnosticStatus.ERROR,
            handshake_success=False,
            chain_validation="unknown",
            duration_ms=round(duration, 3),
            errors=[error],
        )
