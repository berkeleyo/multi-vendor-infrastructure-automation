# Architecture

```mermaid
flowchart LR
  YAML[Versioned YAML] --> CLI[Python CLI]
  CLI --> V[Typed validation]
  V --> F[Provider factory]
  F --> OFF[Offline fixtures]
  F --> AWS[AWS EC2 SDK]
  F --> AZ[Azure Network SDK]
  F --> CF[Cloudflare API v4]
  F --> PAN[PAN-OS XML API]
  OFF & AWS & AZ & CF & PAN --> N[Normalized inventory]
  N --> JSON[Structured JSON]
  N --> D[Drift engine]
  DES[Desired inventory] --> D
  D --> REPORT[Drift report + exit code]
```

Adapters have one read-only contract: return normalized resources or raise an explicit provider error. Secret-bearing headers and API keys never enter output models. Deterministic sorting occurs after aggregation. The drift key is `provider/kind/id`; identity matches are then compared field-by-field.

