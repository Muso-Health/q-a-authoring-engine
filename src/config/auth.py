from __future__ import annotations

from typing import TYPE_CHECKING

from qa_authoring.infrastructure.auth.dev import DevIdentityProvider
from qa_authoring.infrastructure.auth.iap import IapIdentityProvider

if TYPE_CHECKING:
    from config.settings import Settings
    from qa_authoring.application.ports.identity import IdentityProvider


def identity_provider_from_settings(settings: Settings) -> IdentityProvider:
    if settings.auth_provider == "dev":
        return DevIdentityProvider()
    return IapIdentityProvider(settings.auth_iap_audience)
