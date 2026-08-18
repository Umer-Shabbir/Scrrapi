"""Matching logic shared by every place a suppression rule takes effect:
deleting existing rows when a rule is added (app.api.routers.suppression),
skipping a place before it's ever written (app.workers.tasks.scrape_place),
and excluding rows from every export (app.export.*_writer).

One function per kind, all exact-match by design -- see the migration
docstring on `suppression_entries` for why: a domain rule matches its own
hostname or a bare `www.` prefix of it, nothing broader (no subdomains, no
substrings). A suppression rule deletes stored data immediately and
irreversibly, so its blast radius has to be exactly what the confirm modal's
row count promised, not a superset discovered later.
"""

from urllib.parse import urlsplit

from app.db.models.result import Result


def normalize_domain(value: str) -> str:
    """Lowercase, strip a leading `www.`, strip any scheme/path if a full URL
    was pasted instead of a bare hostname."""
    value = value.strip().lower()
    if "://" in value:
        value = urlsplit(value).hostname or value
    return value.removeprefix("www.")


def normalize_email(value: str) -> str:
    return value.strip().lower()


def website_matches_domain(website: str | None, domain: str) -> bool:
    """Whether `website` (a Result.website value, possibly a bare host, a full
    URL, or missing a scheme) is the suppressed domain or its `www.` form."""
    if not website:
        return False
    host = website.strip().lower()
    if "://" in host:
        host = urlsplit(host).hostname or ""
    host = host.removeprefix("www.")
    return host == domain


def email_field_matches(email_field: str | None, address: str) -> bool:
    """`Result.email` may hold several comma-joined addresses -- true if any
    of them is the suppressed address."""
    if not email_field:
        return False
    values = [part.strip().lower() for part in email_field.split(",") if part.strip()]
    return address in values


def result_is_suppressed(result: Result, entries: list[tuple[str, str]]) -> bool:
    """`entries` is a list of (kind, normalized_value) pairs -- the cheap
    in-Python check used by scrape_place, where pulling every suppression row
    into a SQL OR clause for one candidate result isn't worth it."""
    for kind, value in entries:
        if kind == "domain" and website_matches_domain(result.website, value):
            return True
        if kind == "email" and email_field_matches(result.email, value):
            return True
        if kind == "place" and result.place_key == value:
            return True
    return False
