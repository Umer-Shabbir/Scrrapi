"""Wires the website + email mining steps onto a scraped place record.

Connects 3.4 (place detail scraper) -> 4.1/4.2 (website_finder) -> 4.3
(email_miner) into one call: place data in, `website`/`email` fields filled
in the result. Source-agnostic (works on Google's `PlaceData` and, later,
Bing's mirror of it) -- it only ever touches the contact keys on whatever
mapping it's handed, and passes every other field through untouched.

With the deep crawler on (`deep_crawl=True`, driven by the Settings page), the
website isn't just fetched -- it's walked, and everything found across its pages
is merged in:

- `email` gains the site's other addresses, appended to whatever Maps had rather
  than replacing it,
- `phone` likewise gains the numbers printed on the site,
- `socials` appears, keyed by network.

Merging is on identity, not on text: the Maps listing writes a number as
"+1 512-555-0100" and the site writes "(512) 555-0100", so a naive append would
put the same number in the column twice. `phone_key` and a lowercased address are
what decide "same". Maps' own values always come first, because they are the ones
attached to the map pin the user searched for.
"""

import logging

import httpx

from app.scraping.common.email_miner import extract_first_valid_email, is_valid_email
from app.scraping.common.phone_miner import phone_key
from app.scraping.common.site_crawler import CrawlBudget, SiteContacts, crawl_site
from app.scraping.common.website_finder import get_website, search_website_on_startpage

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10.0

# What fits in the widened `results.email` / `results.phone` columns with room to
# spare once joined with ", ". A lead with fifteen addresses on it is a directory
# page, not a business.
MAX_EMAILS = 15
MAX_PHONES = 10

# How the multi-value columns are joined. Chosen over ";" because every
# spreadsheet splits on it and the CSV writer quotes the field anyway.
VALUE_SEPARATOR = ", "


async def enrich_place_data[T: dict](
    place: T,
    location: str = "",
    *,
    client: httpx.AsyncClient | None = None,
    deep_crawl: bool = False,
    budget: CrawlBudget | None = None,
    on_crawl=None,
) -> T:
    """Fill in the contact fields on a place-data dict returned by a place scraper.

    - If `place["website"]` is already set (the listing had one), validate/
      normalize it (4.1). If it's missing or dead, fall back to a Startpage
      search on the place's name + `location` (4.2).
    - Whichever website survives that, mine contact details off it: the home
      page only (4.3) by default, or the whole site when `deep_crawl` is on.

    `on_crawl` is called with the `SiteContacts` a deep crawl produced, so the
    caller can report it on the live activity feed; it never fires when the
    crawler is off or there was no website to crawl.

    Mutates and returns the same `place` mapping it was given. Fields end up
    `None`/absent if nothing panned out (no name to search with, no live website,
    no contact details on it) rather than raising.
    """
    name = place.get("name") or ""
    candidate = place.get("website")

    website = await get_website(candidate, client=client) if candidate else None
    if website is None and name:
        website = await search_website_on_startpage(name, location, client=client)

    place["website"] = website

    if not website:
        _apply_contacts(place, SiteContacts())
        return place

    if not deep_crawl:
        # Shallow path unchanged: one GET, first valid address, no crawl.
        place["email"] = await _mine_email(website, client=client)
        place["emails"] = [place["email"]] if place["email"] else []
        place["phones"] = _split_existing(place.get("phone"))
        return place

    contacts = await crawl_site(website, budget=budget, client=client)
    _apply_contacts(place, contacts)
    if on_crawl is not None:
        on_crawl(contacts)
    return place


def _apply_contacts(place: dict, contacts: SiteContacts) -> None:
    """Merge crawl output into the place's contact fields.

    The scalar `email`/`phone` keys stay the ones the rest of the pipeline writes
    to the database, so they become the joined, deduplicated lists; `emails`/
    `phones` carry the same data unjoined for anything that wants to count or
    render them (the activity feed does).
    """
    emails = _merge(
        _split_existing(place.get("email")),
        [value for value in contacts.emails if is_valid_email(value)],
        key=str.lower,
        cap=MAX_EMAILS,
    )
    phones = _merge(
        _split_existing(place.get("phone")),
        contacts.phones,
        key=phone_key,
        cap=MAX_PHONES,
    )

    place["emails"] = emails
    place["phones"] = phones
    place["email"] = VALUE_SEPARATOR.join(emails) or None
    place["phone"] = VALUE_SEPARATOR.join(phones) or None
    place["socials"] = contacts.socials
    place["crawled_pages"] = contacts.pages_crawled


def _merge(existing: list[str], found: list[str], *, key, cap: int) -> list[str]:
    """`existing` first (those are Maps' own), then whatever `found` adds that
    isn't already there under `key`."""
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


def _split_existing(value: str | None) -> list[str]:
    """Read a scalar contact field back as a list.

    The place scrapers set one value, but a re-run over an already-merged record
    would see the joined form, so this parses both.
    """
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


async def _mine_email(website: str, *, client: httpx.AsyncClient | None = None) -> str | None:
    if client is not None:
        return await _fetch_and_mine(website, client)

    async with httpx.AsyncClient(follow_redirects=True, timeout=REQUEST_TIMEOUT) as owned_client:
        return await _fetch_and_mine(website, owned_client)


async def _fetch_and_mine(website: str, client: httpx.AsyncClient) -> str | None:
    try:
        response = await client.get(website)
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    return extract_first_valid_email(response.text)
