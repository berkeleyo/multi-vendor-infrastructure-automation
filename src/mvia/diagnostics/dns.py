"""Bounded provider-neutral DNS diagnostics."""

from __future__ import annotations

import time

import dns.exception
import dns.resolver

from mvia.diagnostics.models import DiagnosticStatus, DNSRecord, DNSRequest, DNSResult
from mvia.diagnostics.safety import resolve_public_addresses, validate_hostname


class DNSDiagnostic:
    def __init__(self, timeout: float = 3.0, lifetime: float = 3.0) -> None:
        self.resolver = dns.resolver.Resolver(configure=True)
        self.resolver.timeout = timeout
        self.resolver.lifetime = lifetime

    def run(self, request: DNSRequest) -> DNSResult:
        hostname = validate_hostname(request.hostname)
        resolve_public_addresses(hostname)
        start = time.monotonic()
        records: list[DNSRecord] = []
        errors: list[str] = []
        for record_type in request.record_types:
            try:
                answer = self.resolver.resolve(hostname, record_type, lifetime=3.0)
                ttl = getattr(answer.rrset, "ttl", None)
                for item in answer:
                    records.append(DNSRecord(record_type=record_type, value=str(item), ttl=ttl))
            except dns.resolver.NXDOMAIN:
                errors.append(f"{record_type}: name does not exist")
            except dns.resolver.NoAnswer:
                errors.append(f"{record_type}: no answer")
            except dns.exception.Timeout:
                errors.append(f"{record_type}: query timeout")
            except dns.resolver.NoNameservers:
                errors.append(f"{record_type}: no nameservers responded")
        duration = (time.monotonic() - start) * 1000
        status = (
            DiagnosticStatus.ERROR
            if errors and not records
            else DiagnosticStatus.OK
            if not errors
            else DiagnosticStatus.WARNING
        )
        return DNSResult(
            hostname=hostname,
            status=status,
            records=records,
            duration_ms=round(duration, 3),
            errors=errors,
        )
