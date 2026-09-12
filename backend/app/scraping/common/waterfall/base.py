"""Base classes and contracts for third-party waterfall enrichment providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx


@dataclass
class WaterfallResult:
    """Standardized result returned by enrichment providers in the waterfall."""

    emails: list[str] = field(default_factory=list)
    mobile_phones: list[str] = field(default_factory=list)
    decision_makers: list[dict[str, str]] = field(default_factory=list)
    provider_used: str | None = None
    raw: dict = field(default_factory=dict)

    def has_direct_email(self) -> bool:
        """Check if any personal/direct email was discovered."""
        from app.scraping.common.generic_email import is_generic_email

        return any(not is_generic_email(e) for e in self.emails)

    def has_mobile(self) -> bool:
        """Check if any mobile phone was discovered."""
        return len(self.mobile_phones) > 0


class EnrichmentProvider(ABC):
    """Abstract interface for third-party B2B contact and phone enrichment APIs."""

    def __init__(self, name: str, api_key: str | None = None, timeout: float = 8.0):
        self.name = name
        self.api_key = api_key
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        """Check whether this provider has a non-empty API key."""
        return bool(self.api_key and self.api_key.strip())

    @abstractmethod
    async def enrich(
        self,
        domain: str,
        company_name: str = "",
        location: str = "",
        decision_makers: list[dict[str, str]] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> WaterfallResult:
        """Query the provider API to find direct emails, mobile phones, and key decision makers.

        Must return a WaterfallResult (empty on failure/not-found) without raising uncaught
        exceptions.
        """
        pass
