# Cutover Checklist

- Review sample-only configuration and replace only with approved scope identifiers.
- Create least-privilege read identities described in `SECURITY.md`.
- Store credentials in the runner secret store; verify no secrets exist in Git history.
- Run `validate`, offline `discover`, tests, lint, typing, dependency audit, and secret scan.
- Run each live provider separately first; review normalized output for sensitivity.
- Establish artifact retention, drift ownership, alert routing, and exit-code handling.
- Approve the combined live configuration and record the first known-good inventory.

