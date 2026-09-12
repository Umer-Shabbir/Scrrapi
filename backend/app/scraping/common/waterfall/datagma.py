"""Datagma API adapter for B2B direct email and direct mobile line enrichment."""

import logging

import httpx

from app.scraping.common.email_miner import is_valid_email
from app.scraping.common.waterfall.base import EnrichmentProvider, WaterfallResult

logger = logging.getLogger(__name__)


class DatagmaProvider(EnrichmentProvider):
    """Adapter for Datagma findEmail / findPhone API."""

    INGRESS_URL = "https://gateway.datagma.com/api/v1/ingress/findEmail"

    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        super().__init__(name="datagma", api_key=api_key, timeout=timeout)

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

        async def _fetch(c: httpx.AsyncClient) -> None:
            name_param = ""
            if decision_makers:
                name_param = decision_makers[0].get("name", "")

            params = {
                "apiKey": self.api_key,
                "domain": clean_domain,
            }
            if name_param:
                params["fullName"] = name_param
            elif company_name:
                params["companyName"] = company_name

            try:
                resp = await c.get(self.INGRESS_URL, params=params, timeout=self.timeout)
                if resp.status_code == 200:
                    payload = resp.json()
                    raw_data["ingress"] = payload
                    data = payload.get("data") or payload

                    # Direct email
                    email_val = data.get("email") or data.get("workEmail")
                    if email_val and is_valid_email(email_val) and email_val not in emails:
                        emails.append(email_val)

                    # Mobile / direct phone
                    mobile_val = data.get("mobilePhone") or data.get("directPhone")
                    if mobile_val and mobile_val not in mobiles:
                        mobiles.append(mobile_val)

                    # Additional emails in array if present
                    for extra in data.get("emails") or []:
                        ev = extra.get("email") if isinstance(extra, dict) else str(extra)
                        if ev and is_valid_email(ev) and ev not in emails:
                            emails.append(ev)

                    # Decision maker
                    fn = data.get("firstName") or ""
                    ln = data.get("lastName") or ""
                    job_title = data.get("jobTitle") or data.get("title") or "Decision Maker"
                    if fn or ln:
                        dms.append({"name": f"{fn} {ln}".strip(), "title": job_title})
                else:
                    logger.warning(
                        "Datagma API returned status %s: %s",
                        resp.status_code,
                        resp.text[:200],
                        extra={"domain": clean_domain, "status": resp.status_code},
                    )
            except Exception as e:
                logger.warning("Datagma API request failed: %s", e, extra={"domain": clean_domain})

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
