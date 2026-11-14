"""Stable application errors exposed by the CLI."""


class MviaError(Exception):
    """Expected, user-actionable failure."""


class ConfigurationError(MviaError):
    """Configuration or fixture validation failed."""


class ProviderError(MviaError):
    """A provider could not complete discovery."""
