"""Wires the website + email, decision-maker, mobile phone, and review sentiment mining
steps onto a scraped place record.

Connects place detail scraping (Google/Bing) -> website finding/validation ->
email/mobile/decision-maker/review mining into one pipeline: place data in, enriched
fields filled in the result.

With the deep crawler on (`deep_crawl=True`, driven by the Settings page), the
website is walked, and everything found across its pages is merged in:
- `email` gains the site's other addresses,
- `phone` gains the numbers printed on the site,
- `mobile_phone` identifies direct mobile / personal lines,
- `decision_maker` finds owners, founders, CEOs, and key executives,
- `socials` appears, keyed by network,
- customer reviews undergo sentiment analysis and pain-point extraction.
"""

import logging

import httpx

from app.scraping.common.decision_maker_miner import extract_decision_makers, format_decision_makers
from app.scraping.common.email_miner import extract_emails, is_valid_email
from app.scraping.common.email_verify import has_mx_record
from app.scraping.common.generic_email import has_only_generic_emails
from app.scraping.common.mobile_miner import extract_mobile_phones
from app.scraping.common.phone_miner import extract_phones, phone_key
from app.scraping.common.review_sentiment import analyze_reviews
from app.scraping.common.site_crawler import CrawlBudget, SiteContacts, crawl_site
from app.scraping.common.structured_data import extract_structured_contacts
from app.scraping.common.waterfall.engine import run_waterfall_cascade
from app.scraping.common.website_finder import get_website, search_website_on_startpage

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10.0

MAX_EMAILS = 15
MAX_PHONES = 10
MAX_MOBILES = 5
MAX_DECISION_MAKERS = 5

VALUE_SEPARATOR = ", "


async def enrich_place_data(
    place: dict,
    location: str = "",
    *,
    client: httpx.AsyncClient | None = None,
    deep_crawl: bool = False,
    budget: CrawlBudget | None = None,
    on_crawl=None,
    email_verification_mode: str = "off",
    waterfall_enabled: bool = False,
    waterfall_providers: list[str] | None = None,
    waterfall_keys: dict[str, str] | None = None,
) -> dict:
    """Fill in contact, decision-maker, mobile, and sentiment fields on a place-data dict."""
    name = place.get("name") or ""
    candidate = place.get("website")

    website = await get_website(candidate, client=client) if candidate else None
    if website is None and name:
        website = await search_website_on_startpage(name, location, client=client)

    place["website"] = website

    # Perform review sentiment & pain-point extraction on Maps review snippets
    raw_reviews = list(place.get("reviews") or [])
    review_count = place.get("reviews_count")

    if not website:
        contacts = SiteContacts()
        _apply_contacts(place, contacts, email_verification_mode=email_verification_mode)
        _apply_review_analysis(place, raw_reviews, review_count)
    elif not deep_crawl:
        # Shallow path: fetch home page for email, mobile, decision makers, and structured data
        shallow_contacts = await _mine_shallow_page(
            website, client=client, email_verification_mode=email_verification_mode
        )
        _apply_contacts(place, shallow_contacts, email_verification_mode=email_verification_mode)
        all_reviews = raw_reviews + shallow_contacts.reviews
        _apply_review_analysis(place, all_reviews, review_count)
    else:
        contacts = await crawl_site(website, budget=budget, client=client)
        _apply_contacts(place, contacts, email_verification_mode=email_verification_mode)
        all_reviews = raw_reviews + contacts.reviews
        _apply_review_analysis(place, all_reviews, review_count)
        if on_crawl is not None:
            on_crawl(contacts)

    # Waterfall Email & Mobile Phone Enrichment
    # Trigger condition:
    # 1. Internal website mining/crawl found no emails, OR
    # 2. Internal website mining/crawl only found generic role-based emails (info@, contact@, etc.)
    current_emails = place.get("emails") or []
    if waterfall_enabled and (not current_emails or has_only_generic_emails(current_emails)):
        domain = ""
        if website:
            domain = website.lower().replace("https://", "").replace("http://", "").split("/")[0]

        if domain:
            waterfall_res = await run_waterfall_cascade(
                domain=domain,
                company_name=name,
                location=location,
                existing_emails=place.get("emails") or [],
                existing_mobiles=place.get("mobile_phones") or [],
                decision_makers=place.get("decision_makers") or [],
                provider_keys=waterfall_keys,
                provider_order=waterfall_providers or ("hunter", "prospeo", "datagma", "findymail"),
                client=client,
            )

            # Apply enriched emails & mobiles
            if waterfall_res.emails:
                place["emails"] = waterfall_res.emails
                place["email"] = VALUE_SEPARATOR.join(waterfall_res.emails)
                if waterfall_res.provider_used:
                    place["email_source"] = f"waterfall:{waterfall_res.provider_used}"

            if waterfall_res.mobile_phones:
                place["mobile_phones"] = waterfall_res.mobile_phones
                place["mobile_phone"] = VALUE_SEPARATOR.join(waterfall_res.mobile_phones)
                if waterfall_res.provider_used:
                    place["phone_source"] = f"waterfall:{waterfall_res.provider_used}"

            if waterfall_res.decision_makers:
                place["decision_makers"] = waterfall_res.decision_makers
                place["decision_maker"] = format_decision_makers(waterfall_res.decision_makers)

    return place


def _apply_contacts(
    place: dict, contacts: SiteContacts, email_verification_mode: str = "off"
) -> None:
    """Merge crawl / extraction output into the place's contact and leadership fields."""
    valid_emails = []
    mx_cache = {}
    for value in contacts.emails:
        if not is_valid_email(value):
            continue
        if email_verification_mode == "syntax_mx":
            domain = value.split("@")[-1].lower()
            if domain not in mx_cache:
                mx_cache[domain] = has_mx_record(domain)
            if not mx_cache[domain]:
                continue
        valid_emails.append(value)

    emails = _merge(
        _split_existing(place.get("email")),
        valid_emails,
        key=str.lower,
        cap=MAX_EMAILS,
    )
    phones = _merge(
        _split_existing(place.get("phone")),
        contacts.phones,
        key=phone_key,
        cap=MAX_PHONES,
    )
    mobiles = _merge(
        _split_existing(place.get("mobile_phone")),
        contacts.mobile_phones,
        key=phone_key,
        cap=MAX_MOBILES,
    )

    # Decision makers merge
    existing_dms = place.get("decision_makers") or []
    all_dms = _merge_dms(existing_dms, contacts.decision_makers, cap=MAX_DECISION_MAKERS)

    place["emails"] = emails
    place["phones"] = phones
    place["mobile_phones"] = mobiles
    place["decision_makers"] = all_dms

    place["email"] = VALUE_SEPARATOR.join(emails) or None
    place["phone"] = VALUE_SEPARATOR.join(phones) or None
    place["mobile_phone"] = VALUE_SEPARATOR.join(mobiles) or None
    place["decision_maker"] = format_decision_makers(all_dms)
    place["socials"] = contacts.socials
    place["crawled_pages"] = contacts.pages_crawled


def _apply_review_analysis(place: dict, reviews: list[str], review_count: int | None) -> None:
    analysis = analyze_reviews(reviews, review_count=review_count)
    place["sentiment_score"] = analysis.get("sentiment_score")
    place["sentiment_label"] = analysis.get("sentiment_label")
    place["pain_points"] = analysis.get("pain_points") or []
    place["pain_points_summary"] = analysis.get("pain_points_summary")
    place["positive_highlights"] = analysis.get("positive_highlights") or []


def _merge(existing: list[str], found: list[str], *, key, cap: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in [*existing, *found]:
        identity = key(value)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        out.append(value)
        if len(out) >= cap:
            break
    return out


def _merge_dms(
    existing: list[dict[str, str]], found: list[dict[str, str]], cap: int
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for dm in [*existing, *found]:
        name = dm.get("name", "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(dm)
        if len(out) >= cap:
            break
    return out


def _split_existing(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


async def _mine_shallow_page(
    website: str,
    *,
    client: httpx.AsyncClient | None = None,
    email_verification_mode: str = "off",
) -> SiteContacts:
    contacts = SiteContacts(pages_crawled=1)
    try:
        if client is not None:
            response = await client.get(website, timeout=REQUEST_TIMEOUT)
        else:
            async with httpx.AsyncClient(follow_redirects=True, timeout=REQUEST_TIMEOUT) as c:
                response = await c.get(website)
    except Exception:
        return contacts

    if response.status_code >= 400:
        return contacts

    html = response.text[:400_000]
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)

    # Emails
    raw_emails = extract_emails(html)
    contacts.emails = raw_emails

    # Phones & Mobiles
    contacts.phones = extract_phones(html, text)
    contacts.mobile_phones = extract_mobile_phones(html, text)

    # Decision makers
    contacts.decision_makers = extract_decision_makers(html, text)

    # Structured data
    structured = extract_structured_contacts(html, include_extended=True)
    for email in structured.get("emails", []):
        if is_valid_email(email) and email.lower() not in [e.lower() for e in contacts.emails]:
            contacts.emails.append(email)
    for phone in structured.get("phones", []):
        if phone_key(phone) not in [phone_key(p) for p in contacts.phones]:
            contacts.phones.append(phone)
    for dm in structured.get("decision_makers", []):
        if dm.get("name", "").lower() not in [
            d.get("name", "").lower() for d in contacts.decision_makers
        ]:
            contacts.decision_makers.append(dm)
    contacts.reviews = structured.get("reviews", [])

    return contacts
