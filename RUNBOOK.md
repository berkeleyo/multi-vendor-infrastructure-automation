# Runbook

## Operate

Run `mvia validate` before discovery. Validation checks schema and provider names; it does not contact providers or prove that credentials work. Capture stdout as an artifact; it is valid JSON. Schedule read-only discovery from a trusted runner, then run `drift`. Treat exit `2` as drift requiring review, not a runtime failure. Treat exit `1` as an input, authentication, permission, transport, or provider-response failure.

Use environment-backed credentials. Never put tokens in YAML or command arguments. For live AWS/Azure install their extras. Keep TLS verification enabled; `verify_tls: false` exists only for explicitly controlled lab appliances and should not be used in production.

Live mode remains integration-unverified until an owner-approved, least-privilege smoke test is run.
Mocked tests verify request selection, pagination/retry handling, normalization, and failure mapping;
they cannot establish provider tenancy policy, network reachability, or upstream API compatibility.

## Incident triage

1. Validate YAML and inspect the structured error type.
2. Confirm clock, DNS, egress, provider status, credential expiry, and read permissions.
3. Re-run once after provider recovery; retries are already bounded.
4. If normalization changed following an API change, retain the raw provider response outside this tool only under approved secure logging controls.
5. Fall back to the last successful inventory; do not interpret fixture output as live state.

No command mutates infrastructure. Rollback guidance is in `docs/ROLLBACK.md`.

