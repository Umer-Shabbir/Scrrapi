"""Findymail API adapter for direct verified email and decision-maker discovery."""

import logging

import httpx

from app.scraping.common.email_miner import is_valid_email
from app.scraping.common.waterfall.base import EnrichmentProvider, WaterfallResult

logger = logging.getLogger(__name__)


class FindymailProvider(EnrichmentProvider):
    """Adapter for Findymail Contact Search API."""

    SEARCH_BY_NAME_URL = "https://app.findymail.com/api/search/name"

    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        super().__init__(name="findymail", api_key=api_key, timeout=timeout)

    async def enrich(
        self,
        domain: str,
        company_name: str = "",
        location: str = "",
        decision_makers: list[dict[str, str]] | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> WaterfallResult:
        if not self.is_configured or not domain:
            return WaterfallResult(provider_used=self.name)

        emails: list[str] = []
        mobiles: list[str] = []
        dms: list[dict[str, str]] = []
        raw_data: dict = {}

        clean_domain = domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async def _fetch(c: httpx.AsyncClient) -> None:
            # Query by top decision maker name if available
            dm_name = decision_makers[0].get("name", "") if decision_makers else ""
            if not dm_name and company_name:
                dm_name = "Owner"

            body = {"domain": clean_domain}
            if dm_name:
                body["name"] = dm_name

            try:
                resp = await c.post(
                    self.SEARCH_BY_NAME_URL,
                    json=body,
                    headers=headers,
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    payload = resp.json()
                    raw_data["search"] = payload
                    contact = payload.get("contact") or payload.get("data") or payload

                    email_val = contact.get("email")
                    if email_val and is_valid_email(email_val) and email_val not in emails:
                        emails.append(email_val)

                    phone_val = contact.get("phone") or contact.get("mobile")
                    if phone_val and phone_val not in mobiles:
                        mobiles.append(phone_val)

                    full_name = contact.get("name") or contact.get("full_name")
                    title = contact.get("title") or contact.get("position") or "Decision Maker"
                    if full_name:
                        dms.append({"name": full_name, "title": title})
                else:
                    logger.warning(
                        "Findymail API returned status %s: %s",
                        resp.status_code,
                        resp.text[:200],
                        extra={"domain": clean_domain, "status": resp.status_code},
                    )
            except Exception as e:
                logger.warning(
                    "Findymail API request failed: %s", e, extra={"domain": clean_domain}
                )

        if client is not None:
            await _fetch(client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as new_client:
                await _fetch(new_client)

        return WaterfallResult(
            emails=emails,
            mobile_phones=mobiles,
            decision_makers=dms,
            provider_used=self.name,
            raw=raw_data,
        )
