"""Hunter.io API adapter for domain search and verified email discovery."""

import logging

import httpx

from app.scraping.common.email_miner import is_valid_email
from app.scraping.common.waterfall.base import EnrichmentProvider, WaterfallResult

logger = logging.getLogger(__name__)


class HunterProvider(EnrichmentProvider):
    """Adapter for Hunter.io Domain Search & Email Finder APIs."""

    DOMAIN_SEARCH_URL = "https://api.hunter.io/v2/domain-search"
    EMAIL_FINDER_URL = "https://api.hunter.io/v2/email-finder"

    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        super().__init__(name="hunter", api_key=api_key, timeout=timeout)

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
            # 1. Domain Search
            params = {
                "domain": clean_domain,
                "api_key": self.api_key,
                "limit": 10,
                "type": "personal",  # focus on direct/personal emails
            }
            if company_name:
                params["company"] = company_name

            try:
                resp = await c.get(self.DOMAIN_SEARCH_URL, params=params, timeout=self.timeout)
                if resp.status_code == 200:
                    payload = resp.json()
                    raw_data["domain_search"] = payload
                    data = payload.get("data") or {}
                    for item in data.get("emails") or []:
                        email_val = item.get("value")
                        if email_val and is_valid_email(email_val) and email_val not in emails:
                            emails.append(email_val)

                        # Decision maker / person info if available
                        first = item.get("first_name") or ""
                        last = item.get("last_name") or ""
                        pos = item.get("position") or ""
                        phone_val = item.get("phone_number")
                        if phone_val and phone_val not in mobiles:
                            mobiles.append(phone_val)

                        if first and last:
                            name = f"{first} {last}".strip()
                            dms.append({"name": name, "title": pos or "Decision Maker"})
                else:
                    logger.warning(
                        "Hunter domain search returned status %s: %s",
                        resp.status_code,
                        resp.text[:200],
                        extra={"domain": clean_domain, "status": resp.status_code},
                    )
            except Exception as e:
                logger.warning("Hunter API request failed: %s", e, extra={"domain": clean_domain})

            # 2. If decision makers were passed and no direct email was found yet,
            # try Email Finder for top DM
            if not emails and decision_makers:
                top_dm = decision_makers[0].get("name", "").strip()
                dm_parts = top_dm.split()
                if len(dm_parts) >= 2:
                    finder_params = {
                        "domain": clean_domain,
                        "first_name": dm_parts[0],
                        "last_name": " ".join(dm_parts[1:]),
                        "api_key": self.api_key,
                    }
                    try:
                        resp_finder = await c.get(
                            self.EMAIL_FINDER_URL, params=finder_params, timeout=self.timeout
                        )
                        if resp_finder.status_code == 200:
                            f_data = (resp_finder.json().get("data") or {}).get("email")
                            if f_data and is_valid_email(f_data) and f_data not in emails:
                                emails.append(f_data)
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
