
with open("backend/app/scraping/common/place_enrichment.py") as f:
    text = f.read()

text = text.replace(
    "from app.scraping.common.site_crawler import CrawlBudget, SiteContacts, crawl_site",
    "from app.scraping.common.email_verify import has_mx_record\nfrom app.scraping.common.site_crawler import CrawlBudget, SiteContacts, crawl_site"
)

text = text.replace(
    "    on_crawl=None,\n) -> T:",
    "    on_crawl=None,\n    email_verification_mode: str = \"off\",\n) -> T:"
)

text = text.replace(
    "        place[\"email\"] = await _mine_email(website, client=client)",
    "        place[\"email\"] = await _mine_email(website, client=client, email_verification_mode=email_verification_mode)"
)

text = text.replace(
    "    _apply_contacts(place, contacts)",
    "    _apply_contacts(place, contacts, email_verification_mode=email_verification_mode)"
)

text = text.replace(
    "def _apply_contacts(place: dict, contacts: SiteContacts) -> None:",
    "def _apply_contacts(place: dict, contacts: SiteContacts, email_verification_mode: str = \"off\") -> None:"
)

apply_repl = """    valid_emails = []
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
    )"""

text = text.replace(
    """    emails = _merge(
        _split_existing(place.get("email")),
        [value for value in contacts.emails if is_valid_email(value)],
        key=str.lower,
        cap=MAX_EMAILS,
    )""",
    apply_repl
)

text = text.replace(
    "def _mine_email(website: str, *, client: httpx.AsyncClient | None = None) -> str | None:",
    "def _mine_email(website: str, *, client: httpx.AsyncClient | None = None, email_verification_mode: str = \"off\") -> str | None:"
)

text = text.replace(
    "        return await _fetch_and_mine(website, client)",
    "        return await _fetch_and_mine(website, client, email_verification_mode)"
)

text = text.replace(
    "        return await _fetch_and_mine(website, owned_client)",
    "        return await _fetch_and_mine(website, owned_client, email_verification_mode)"
)

mine_repl = """async def _fetch_and_mine(website: str, client: httpx.AsyncClient, email_verification_mode: str = "off") -> str | None:
    try:
        response = await client.get(website)
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    
    # We want to use the email miner, but it returns the FIRST valid email. 
    # If mode is syntax_mx, we might need to check if the first string has MX record. 
    # It's better to just extract emails and find the first one that has MX record.
    from app.scraping.common.email_miner import extract_emails
    emails = extract_emails(response.text)
    if not emails:
        return None
        
    for email in emails:
        if not is_valid_email(email):
            continue
        if email_verification_mode == "syntax_mx":
            domain = email.split("@")[-1].lower()
            if not has_mx_record(domain):
                continue
        return email
        
    return None"""

text = text.replace(
    """async def _fetch_and_mine(website: str, client: httpx.AsyncClient) -> str | None:
    try:
        response = await client.get(website)
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    return extract_first_valid_email(response.text)""",
    mine_repl
)

with open("backend/app/scraping/common/place_enrichment.py", "w") as f:
    f.write(text)

