"""Provider adapter factory."""

from mvia.models import ProviderConfig, ProviderName
from mvia.providers.base import Provider


def create_provider(name: ProviderName, config: ProviderConfig, *, offline: bool) -> Provider:
    if offline:
        from mvia.providers.fixture import FixtureProvider

        return FixtureProvider(name, config)
    if name is ProviderName.AWS:
        from mvia.providers.aws import AwsProvider

        return AwsProvider(config)
    if name is ProviderName.AZURE:
        from mvia.providers.azure import AzureProvider

        return AzureProvider(config)
    if name is ProviderName.CLOUDFLARE:
        from mvia.providers.cloudflare import CloudflareProvider

        return CloudflareProvider(config)
    from mvia.providers.palo_alto import PaloAltoProvider

    return PaloAltoProvider(config)
