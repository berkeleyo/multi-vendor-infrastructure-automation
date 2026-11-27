# Security

Use least-privilege, short-lived identities. Required eventual live permissions are: AWS `ec2:DescribeVpcs` and `ec2:DescribeSubnets`; Azure subscription/resource-group scope `Microsoft.Network/virtualNetworks/read` (Reader is broader but sufficient); Cloudflare token permissions `Zone:Read` and `DNS:Read` restricted to selected zones; PAN-OS an API administrator role restricted to configuration read access for `/config/shared/address`.

Secrets are accepted only through standard AWS/Azure credential chains or `CLOUDFLARE_API_TOKEN` / `PANOS_API_KEY`. PAN-OS authentication uses the `X-PAN-KEY` header. Structured values and common unstructured credential patterns are redacted, validation errors hide input values, and provider exception messages are reduced to exception types. Do not enable debug HTTP logging. TLS verification defaults on. Dependency and secret scanning run in CI.

Report vulnerabilities privately to the repository owner. This portfolio repository contains no production credentials or real infrastructure identifiers.

## v0.2 control-plane controls

Network diagnostics reject IP literals and addresses that are not globally routable unicast. HTTP and TLS connect directly to a validated address, with the original hostname used for HTTP Host and TLS certificate verification. HTTP ignores environment proxies, validates each redirect, and limits bytes read from the final response. The HTTP request budget is shared across redirects and checked during streaming. The operating system handles the initial DNS resolution. Containers run as a dedicated non-root user, and the documented Docker command publishes the API to loopback on the host.

