# Changelog

## v0.2.0 — 2026-11-23

### Added

- FastAPI control-plane interface under versioned `/api/v1` endpoints.
- Shared application service used by the CLI and REST API for discovery and drift operations.
- Provider capability discovery and fixture-based discovery/drift API access.
- Provider-neutral DNS, TLS and HTTP diagnostics.
- SSRF protections for IP literals, private, loopback, link-local, multicast, reserved and unspecified targets.
- Bounded diagnostic timeouts, redirects and response sizes.
- Correlation IDs for API requests and sanitized structured error responses.
- Container runtime support with a non-root user and health check.
- Documentation for API use, diagnostics, security boundaries and Docker operation.

### Preserved

- Existing CLI commands and JSON envelopes.
- Existing provider discovery and normalized drift behaviour.
- Read-only provider integrations and explicit opt-in live verification.
- Fixture/offline demonstrations and deterministic provider coverage.

### Validation

- 66 tests passing.
- 82.33% coverage.
- Ruff passing.
- mypy passing.
- Dependency security checks passing.
- Secret scanning passing.
- Docker build passing in GitHub Actions.

### Not included

- Provider mutation or infrastructure deployment.
- Terraform execution.
- Kubernetes deployment.
- AI-driven remediation or autonomous infrastructure changes.
