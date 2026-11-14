# Overview

The CLI validates strict versioned YAML, discovers resources through provider adapters or fixtures, maps them into a single resource contract, sorts results deterministically, and compares full normalized resources. Provider-specific details remain in `attributes`; common identity and location fields stay queryable.

Normalization is intentionally explicit: AWS names come from the `Name` tag and CIDRs remain strings; Azure address prefixes become sorted lists and resource group is parsed from the ARM ID; Cloudflare record type/content/proxy/TTL are retained; PAN-OS address value, value type, and description are retained. Missing optional values are `null` or a documented default—never invented.

