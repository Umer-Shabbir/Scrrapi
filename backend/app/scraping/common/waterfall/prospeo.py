"""Prospeo.io API adapter for verified direct B2B email and direct mobile phone enrichment."""

import logging

import httpx

from app.scraping.common.email_miner import is_valid_email
from app.scraping.common.mobile_miner import is_mobile_number
from app.scraping.common.waterfall.base import EnrichmentProvider, WaterfallResult

logger = logging.getLogger(__name__)


class ProspeoProvider(EnrichmentProvider):
    """Adapter for Prospeo.io Email and Phone Finder APIs."""

    DOMAIN_SEARCH_URL = "https://api.prospeo.io/domain-search"
    EMAIL_FINDER_URL = "https://api.prospeo.io/email-finder"

    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        super().__init__(name="prospeo", api_key=api_key, timeout=timeout)

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
        headers = {"X-KEY": self.api_key, "Content-Type": "application/json"}

        async def _fetch(c: httpx.AsyncClient) -> None:
            # 1. Try Domain Search
            payload_body = {"company": clean_domain}
            try:
                resp = await c.post(
                    self.DOMAIN_SEARCH_URL,
                    json=payload_body,
                    headers=headers,
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    payload = resp.json()
                    raw_data["domain_search"] = payload
                    response_obj = payload.get("response") or {}
                    for item in response_obj.get("emails") or []:
                        email_val = item.get("email")
                        if email_val and is_valid_email(email_val) and email_val not in emails:
                            emails.append(email_val)

                        first = item.get("first_name") or ""
                        last = item.get("last_name") or ""
                        pos = item.get("title") or item.get("position") or ""
                        phone_val = item.get("phone") or item.get("mobile_phone")
                        if phone_val and is_mobile_number(phone_val, context="mobile direct"):
                            if phone_val not in mobiles:
                                mobiles.append(phone_val)
                        elif phone_val and phone_val not in mobiles:
                            mobiles.append(phone_val)

                        if first or last:
                            name = f"{first} {last}".strip()
                            dms.append({"name": name, "title": pos or "Decision Maker"})
                else:
                    logger.warning(
                        "Prospeo domain search status %s: %s",
                        resp.status_code,
                        resp.text[:200],
                        extra={"domain": clean_domain, "status": resp.status_code},
                    )
            except Exception as e:
                logger.warning("Prospeo API request failed: %s", e, extra={"domain": clean_domain})

            # 2. If decision maker is known, query email finder
            if decision_makers:
                top_dm = decision_makers[0].get("name", "").strip()
                if top_dm:
                    try:
                        finder_payload = {"full_name": top_dm, "company": clean_domain}
                        resp_finder = await c.post(
                            self.EMAIL_FINDER_URL,
                            json=finder_payload,
                            headers=headers,
                            timeout=self.timeout,
                        )
                        if resp_finder.status_code == 200:
                            f_data = resp_finder.json().get("response") or {}
                            f_email = f_data.get("email")
                            if f_email and is_valid_email(f_email) and f_email not in emails:
                                emails.insert(0, f_email)
                            f_phone = f_data.get("phone") or f_data.get("mobile_phone")
                            if f_phone and f_phone not in mobiles:
                                mobiles.append(f_phone)
                    except Exception:
                        pass

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
