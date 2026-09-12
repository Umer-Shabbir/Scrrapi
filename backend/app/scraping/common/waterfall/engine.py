"""Waterfall cascade execution engine for email and mobile phone enrichment."""

import logging
from collections.abc import Sequence

import httpx

from app.scraping.common.generic_email import is_generic_email
from app.scraping.common.waterfall.base import EnrichmentProvider, WaterfallResult
from app.scraping.common.waterfall.datagma import DatagmaProvider
from app.scraping.common.waterfall.findymail import FindymailProvider
from app.scraping.common.waterfall.hunter import HunterProvider
from app.scraping.common.waterfall.prospeo import ProspeoProvider

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER_ORDER = ("hunter", "prospeo", "datagma", "findymail")

_PROVIDER_FACTORIES = {
    "hunter": HunterProvider,
    "prospeo": ProspeoProvider,
    "datagma": DatagmaProvider,
    "findymail": FindymailProvider,
}


def build_providers(
    provider_keys: dict[str, str] | None = None,
    order: Sequence[str] = DEFAULT_PROVIDER_ORDER,
) -> list[EnrichmentProvider]:
    """Construct configured provider instances in specified waterfall order."""
    keys = provider_keys or {}
    providers: list[EnrichmentProvider] = []
    for name in order:
        clean_name = name.strip().lower()
        factory = _PROVIDER_FACTORIES.get(clean_name)
        if factory is not None:
            api_key = keys.get(clean_name) or keys.get(f"{clean_name}_api_key")
            provider = factory(api_key=api_key)
            providers.append(provider)
    return providers


async def run_waterfall_cascade(
    domain: str,
    company_name: str = "",
    location: str = "",
    existing_emails: list[str] | None = None,
    existing_mobiles: list[str] | None = None,
    decision_makers: list[dict[str, str]] | None = None,
    *,
    providers: list[EnrichmentProvider] | None = None,
    provider_keys: dict[str, str] | None = None,
    provider_order: Sequence[str] = DEFAULT_PROVIDER_ORDER,
    client: httpx.AsyncClient | None = None,
) -> WaterfallResult:
    """Execute waterfall enrichment cascade across providers until direct email and mobile
    are discovered.

    Cascade flow:
    1. If providers not explicitly passed, build from provider_keys & order.
    2. Filter to configured providers (is_configured == True).
    3. Loop through providers sequentially:
       - Query provider with domain, company, location, and existing decision makers.
       - If provider finds direct/personal email, add to accumulated emails.
       - If provider finds mobile phone, add to accumulated mobiles.
       - Track which provider first delivered direct email / mobile.
       - Check if both direct email AND mobile phone have been discovered -> break cascade early.
    4. Return aggregated WaterfallResult.
    """
    accumulated_emails = list(existing_emails or [])
    accumulated_mobiles = list(existing_mobiles or [])
    accumulated_dms = list(decision_makers or [])
    last_provider_used: str | None = None

    if not domain:
        return WaterfallResult(
            emails=accumulated_emails,
            mobile_phones=accumulated_mobiles,
            decision_makers=accumulated_dms,
        )

    active_providers = providers or build_providers(provider_keys, order=provider_order)
    configured_providers = [p for p in active_providers if p.is_configured]

    if not configured_providers:
        logger.debug("No waterfall enrichment providers are configured with API keys.")
        return WaterfallResult(
            emails=accumulated_emails,
            mobile_phones=accumulated_mobiles,
            decision_makers=accumulated_dms,
        )

    for provider in configured_providers:
        # Check if we already have a direct email AND at least one mobile phone
        have_direct_email = any(not is_generic_email(e) for e in accumulated_emails)
        have_mobile = len(accumulated_mobiles) > 0

        if have_direct_email and have_mobile:
            break

        try:
            res = await provider.enrich(
                domain=domain,
                company_name=company_name,
                location=location,
                decision_makers=accumulated_dms,
                client=client,
            )
        except Exception as exc:
            logger.warning(
                "Waterfall provider %s encountered an error: %s",
                provider.name,
                exc,
                extra={"provider": provider.name, "domain": domain},
            )
            continue

        # Merge newly discovered emails
        new_direct_found = False
        for email in res.emails:
            if email.lower() not in [e.lower() for e in accumulated_emails]:
                # If it's direct, put it at the beginning; if generic, append
                if not is_generic_email(email):
                    accumulated_emails.insert(0, email)
                    new_direct_found = True
                else:
                    accumulated_emails.append(email)

        # Merge newly discovered mobiles
        new_mobile_found = False
        from app.scraping.common.phone_miner import phone_key

        for mob in res.mobile_phones:
            mob_k = phone_key(mob)
            if mob_k and mob_k not in [phone_key(m) for m in accumulated_mobiles]:
                accumulated_mobiles.append(mob)
                new_mobile_found = True

        # Merge newly discovered decision makers
        for dm in res.decision_makers:
            dm_name = dm.get("name", "").strip().lower()
            if dm_name and dm_name not in [d.get("name", "").lower() for d in accumulated_dms]:
                accumulated_dms.append(dm)

        if new_direct_found or new_mobile_found:
            last_provider_used = provider.name
            logger.info(
                "Waterfall provider %s enriched domain %s (emails=%s, mobiles=%s)",
                provider.name,
                domain,
                len(res.emails),
                len(res.mobile_phones),
                extra={"provider": provider.name, "domain": domain},
            )

    return WaterfallResult(
        emails=accumulated_emails,
        mobile_phones=accumulated_mobiles,
        decision_makers=accumulated_dms,
        provider_used=last_provider_used,
    )
