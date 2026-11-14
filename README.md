# Multi-Vendor Infrastructure Automation

An independent, read-only infrastructure inventory and drift-analysis portfolio project by **berkeleyo**. It discovers a deliberately narrow resource set across AWS, Azure, Cloudflare, and Palo Alto, normalizes it, and compares it with a typed desired state. Offline mode is credential-free and deterministic.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/mvia validate --config examples/offline.yaml
.venv/bin/mvia discover --config examples/offline.yaml
.venv/bin/mvia drift --config examples/offline.yaml --desired examples/desired.yaml
```

Exit codes are `0` for success/in-sync, `1` for configuration or provider errors, and `2` when drift exists. Operational commands write a JSON document to stdout; conventional `--help` and `--version` output is plain text.

## Supported live discovery

The adapters below are implemented against their documented public interfaces and tested with
mocked SDK/API boundaries. **This repository has not been tested against a live cloud account or
firewall.** Offline fixture discovery and comparison are the only end-to-end tested operating mode.

| Provider | Resources | Interface | Authentication |
|---|---|---|---|
| AWS | VPCs, subnets | boto3 EC2 paginators | standard AWS credential chain |
| Azure | virtual networks, subnets | Azure Network SDK | `DefaultAzureCredential` |
| Cloudflare | zones, DNS records | API v4 with pagination/retry | `CLOUDFLARE_API_TOKEN` |
| Palo Alto | shared address objects | PAN-OS XML config `get` | `PANOS_API_KEY` |

Live integrations only read. Creation, update, deletion, deployment, and Palo Alto commit operations are unsupported. Cloudflare and PAN-OS rate-limit responses, transport failures, and transient HTTP errors receive bounded retries. AWS/Azure authentication and pagination behavior is supplied by their SDKs; the adapters set bounded SDK retries and connection/read timeouts and consume SDK paginators/pageables. PAN-OS sends its key in the `X-PAN-KEY` header rather than the URL.

Install provider extras only when needed: `pip install -e '.[aws,azure]'`. See [RUNBOOK.md](RUNBOOK.md), [architecture](docs/ARCHITECTURE.md), and [security](docs/SECURITY.md).

CI installs and audits the reviewed base, AWS, and Azure Python resolution in `constraints-ci.txt`. Runtime dependency ranges remain
in `pyproject.toml` so downstream users can receive compatible security fixes; update the constraints
file deliberately after testing and auditing.

## Engineering lifecycle

**Plan → Build → Test → Deploy → Operate → Improve**: define normalized contracts and least privilege; implement isolated adapters; verify offline and mocked boundaries; package without deploying infrastructure; run observable read-only discovery; then improve coverage and supported resources from operational evidence.

All sample infrastructure is invented. Domains use `.example`; IP addresses use RFC 5737 documentation ranges; identifiers are synthetic.

