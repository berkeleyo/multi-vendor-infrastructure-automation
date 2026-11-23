"""Server-controlled network target safety policy and hostname validation."""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit

from mvia.errors import UnsafeTargetError

_HOSTNAME_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def validate_hostname(hostname: str) -> str:
    value = hostname.strip().rstrip(".").lower()
    if not value or len(value) > 253:
        raise UnsafeTargetError("hostname is empty or exceeds 253 characters")
    if len(value.split(".")) < 2:
        raise UnsafeTargetError("hostname must be a fully qualified name")
    if any(not _HOSTNAME_LABEL.fullmatch(label) for label in value.split(".")):
        raise UnsafeTargetError("hostname contains invalid characters")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        raise UnsafeTargetError("IP literals are not accepted")
    return value


def validate_url(url: str) -> tuple[str, str, int]:
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeTargetError("only HTTP and HTTPS URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeTargetError("URLs with embedded credentials are not allowed")
    if not parsed.hostname:
        raise UnsafeTargetError("URL does not contain a valid hostname")
    hostname = validate_hostname(parsed.hostname)
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    return parsed.scheme.lower(), hostname, port


def is_blocked_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def resolve_public_addresses(hostname: str) -> list[str]:
    try:
        entries = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeTargetError("hostname could not be resolved safely") from exc
    addresses = sorted({str(entry[4][0]) for entry in entries})
    if not addresses:
        raise UnsafeTargetError("hostname resolved to no addresses")
    blocked = [address for address in addresses if is_blocked_ip(address)]
    if blocked:
        raise UnsafeTargetError("hostname resolves to a blocked address")
    return addresses
