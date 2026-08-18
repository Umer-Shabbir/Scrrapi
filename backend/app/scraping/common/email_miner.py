"""Harvests contact emails from a business website.

Legacy equivalent: EmailMiner (ExtractFirstValidEmail, IsValidEmail, GetDomainFromEmail).

`extract_first_valid_email` is the original single-address path used by the
shallow (home page only) enrichment. `extract_emails` returns every address on a
page, in confidence order, and is what the deep site crawler
(`app.scraping.common.site_crawler`) accumulates across a whole site.

Four encodings are recognised, because a business that publishes an address at
all publishes it in one of these:

1. `mailto:` links -- explicit and author-intended, so they rank first.
2. Cloudflare's email obfuscation (`data-cfemail` / `/cdn-cgi/l/email-protection#`),
   which replaces the address in the markup with a hex blob. Left undecoded, every
   Cloudflare-protected contact page reads as having no email at all.
3. Plain text in the page body.
4. Hand-rolled obfuscation -- `info [at] example [dot] com` and friends, which is
   still the most common anti-scraping measure on small business sites.
"""

import re

from email_validator import EmailNotValidError, validate_email

# `mailto:` links are the strongest signal -- if the markup names an address
# explicitly, prefer it over anything pattern-matched out of a wall of text.
# Query strings (`?subject=...&body=...`) are common on mailto hrefs and
# aren't part of the address.
MAILTO_RE = re.compile(r'href=["\']mailto:([^"\'?]+)', re.IGNORECASE)

# Deliberately permissive -- this regex just needs to find candidates in raw
# HTML/text without missing anything RFC-legal-ish. `is_valid_email` does the
# real validation on whatever it turns up.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Retina asset filenames (`logo@2x.png`, `banner@3x.jpg`) are syntactically
# indistinguishable from an email address: `name@2x.png` parses as local-part
# `name`, domain `2x.png`, which is a perfectly valid-looking domain.tld shape.
# Reject anything whose "TLD" is actually an image extension.
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp"}

# Hosts that appear in inlined config on half the web and never belong to the
# business: error-reporting DSNs (`https://<key>@o1.ingest.sentry.io/...` is
# email-shaped), site-builder infrastructure, and the placeholder domains used
# in boilerplate markup. Matched on the domain or any parent of it.
JUNK_EMAIL_DOMAINS = {
    "sentry.io",
    "ingest.sentry.io",
    "sentry-cdn.com",
    "wixpress.com",
    "sentry.wixpress.com",
    "example.com",
    "example.org",
    "domain.com",
    "yourdomain.com",
    "email.com",
    "sentry.local",
}

# A Sentry public key, a build hash, a tracking id -- long unbroken hex reads as
# a machine identifier, not as something a human would put on a contact page.
HEX_LOCAL_PART_RE = re.compile(r"^[0-9a-f]{16,}$", re.IGNORECASE)

# Cloudflare's "Email Address Obfuscation" rewrites every address on the page to
# a hex blob: the first byte is an XOR key, the rest is the encrypted address.
# It appears either as `data-cfemail="<hex>"` on the wrapping span or as the
# fragment of a `/cdn-cgi/l/email-protection#<hex>` href.
CFEMAIL_RE = re.compile(
    r'data-cfemail=["\']([0-9a-fA-F]+)["\']'
    r"|/cdn-cgi/l/email-protection#([0-9a-fA-F]+)",
    re.IGNORECASE,
)

# Hand-rolled obfuscation. Both forms below require at least one bracketed
# separator: matching a bare " at " / " dot " would turn ordinary prose
# ("meet at reception dot" ...) into email addresses on half the pages crawled.
_LOCAL = r"[A-Za-z0-9._%+\-]+"
_OPEN = r"[\[\(\{]"
_CLOSE = r"[\]\)\}]"

OBFUSCATED_RES = [
    # info [at] example [dot] com  /  info (at) example (punkt) de
    re.compile(
        rf"({_LOCAL})\s*{_OPEN}?\s*(?:@|at)\s*{_CLOSE}?\s*"
        rf"([A-Za-z0-9.\-]+)\s*{_OPEN}\s*(?:\.|dot|punkt|punto)\s*{_CLOSE}\s*([A-Za-z]{{2,}})",
        re.IGNORECASE,
    ),
    # info [at] example.com -- the domain half written out normally
    re.compile(
        rf"({_LOCAL})\s*{_OPEN}\s*(?:@|at)\s*{_CLOSE}\s*([A-Za-z0-9.\-]+\.[A-Za-z]{{2,}})",
        re.IGNORECASE,
    ),
]

# `&#64;` / `&commat;` / fullwidth `＠` all render as an at sign but defeat a
# plain regex, so they are normalized before the patterns above run.
_AT_ENTITIES = {"&#64;": "@", "&#x40;": "@", "&commat;": "@", "＠": "@"}


def extract_first_valid_email(html: str) -> str | None:
    """Pull the first plausible contact email out of a page's HTML.

    Confidence order, not document order: an explicit `mailto:` anywhere on the
    page beats an address pattern-matched out of the body text. Every candidate
    is run through `is_valid_email` before being accepted, so junk matches
    (retina image filenames, Sentry DSNs, placeholder domains) are skipped
    rather than returned.
    """
    found = extract_emails(html, limit=1)
    return found[0] if found else None


def extract_emails(html: str, *, limit: int = 25) -> list[str]:
    """Every valid-looking address on the page, best first, deduplicated.

    Order is by how strong a signal the encoding is -- `mailto:`, then decoded
    Cloudflare blobs, then plain text, then hand-obfuscated text -- because the
    caller keeps the first one as the primary address and a `mailto:` on a
    contact page is far more likely to be the business's own than the first
    address that happens to appear in a paragraph.

    `limit` bounds the work done on a page that lists hundreds of staff
    addresses; the crawler applies its own cap across the whole site.
    """
    seen: set[str] = set()
    emails: list[str] = []

    for candidate in _candidates(html):
        candidate = candidate.strip().strip(".,;:")
        key = candidate.lower()
        if key in seen or not is_valid_email(candidate):
            continue
        seen.add(key)
        emails.append(candidate)
        if len(emails) >= limit:
            break
    return emails


def _candidates(html: str):
    """Raw candidate strings in confidence order (may repeat, may be invalid)."""
    for match in MAILTO_RE.finditer(html):
        yield match.group(1)

    for match in CFEMAIL_RE.finditer(html):
        decoded = decode_cfemail(match.group(1) or match.group(2))
        if decoded:
            yield decoded

    text = _normalize_at_entities(html)
    for match in EMAIL_RE.finditer(text):
        yield match.group(0)

    for pattern in OBFUSCATED_RES:
        for match in pattern.finditer(text):
            parts = [group for group in match.groups() if group]
            if len(parts) == 3:
                yield f"{parts[0]}@{parts[1]}.{parts[2]}"
            elif len(parts) == 2:
                yield f"{parts[0]}@{parts[1]}"


def decode_cfemail(blob: str) -> str | None:
    """Decode a Cloudflare `data-cfemail` hex blob back into an address.

    Byte 0 is the XOR key; every following byte is one character of the address
    XORed with it. Returns `None` for a malformed blob rather than raising --
    this runs over whatever markup a live site served.
    """
    try:
        raw = bytes.fromhex(blob)
    except ValueError:
        return None
    if len(raw) < 2:
        return None

    key = raw[0]
    try:
        return "".join(chr(byte ^ key) for byte in raw[1:]).encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return None


def _normalize_at_entities(text: str) -> str:
    for entity, replacement in _AT_ENTITIES.items():
        text = text.replace(entity, replacement)
    return text


def is_valid_email(candidate: str) -> bool:
    """RFC-shape check via `email_validator`, plus a filter for image-filename false positives.

    No DNS/deliverability check -- this only runs against candidates already
    pulled off a live page, and a network round-trip per candidate isn't worth
    the cost here.
    """
    if "@" not in candidate:
        return False

    domain = get_domain_from_email(candidate)
    if domain.rsplit(".", 1)[-1] in IMAGE_EXTENSIONS:
        return False
    if any(domain == junk or domain.endswith(f".{junk}") for junk in JUNK_EMAIL_DOMAINS):
        return False
    if HEX_LOCAL_PART_RE.match(candidate.rpartition("@")[0]):
        return False

    try:
        validate_email(candidate, check_deliverability=False)
    except EmailNotValidError:
        return False
    return True


def get_domain_from_email(email: str) -> str:
    """Return the part after `@`, lowercased. Raises `ValueError` if there's no `@`.

    Note: `str.rpartition` returns the *whole string* as the tail when the
    separator isn't found (not an empty string), so the no-`@` case has to be
    detected off the separator it found, not off the tail.
    """
    _, separator, domain = email.rpartition("@")
    if not separator:
        raise ValueError(f"not an email address: {email!r}")
    return domain.lower()
