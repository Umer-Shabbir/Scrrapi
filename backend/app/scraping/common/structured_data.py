"""Reads contact details out of a page's schema.org JSON-LD block.

Most site builders (Wix, Squarespace, WordPress SEO plugins, Shopify) emit a
`LocalBusiness`/`Organization` block with the business's own phone, email and
social profiles in it, and it is the most reliable contact data on the page --
hand-typed once by the owner, not scattered through the markup.

It matters most for phone numbers. Emails and profile URLs survive a plain text
scan of the markup anyway, but a JSON-LD `telephone` sits inside a `<script>`,
which the crawler strips before scanning text (script bodies are full of
timestamps and ids that read as phone numbers). Without this the number in the
structured block is the one number on the page that gets missed.

Everything here is defensive: real-world JSON-LD is routinely malformed, doubly
encoded, or an `@graph` of thirty nodes. A block that doesn't parse is skipped,
never raised on.
"""

import json
import re
from typing import Any

JSON_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)

# Keys worth pulling out of any node, at any depth. `contactPoint`/`address`
# nodes nest their own telephone, which is why this walks rather than reading
# the top level.
EMAIL_KEYS = {"email"}
PHONE_KEYS = {"telephone", "phone", "faxnumber"}
SOCIAL_KEYS = {"sameas"}

# Guards against a pathological document (a product feed with thousands of
# nodes) turning one page into a long walk.
MAX_NODES = 2000


def extract_structured_contacts(html: str) -> dict[str, list[str]]:
    """`{"emails": [...], "phones": [...], "socials": [...]}` from every JSON-LD
    block on the page, in document order and deduplicated.

    Values are returned raw -- validation belongs to `email_miner`/`phone_miner`,
    which the caller runs over them anyway.
    """
    emails: list[str] = []
    phones: list[str] = []
    socials: list[str] = []

    for match in JSON_LD_RE.finditer(html):
        document = _load(match.group(1))
        if document is None:
            continue
        _walk(document, emails, phones, socials, budget=[MAX_NODES])

    return {
        "emails": _dedupe(emails),
        "phones": _dedupe(phones),
        "socials": _dedupe(socials),
    }


def _load(raw: str) -> Any | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _walk(
    node: Any,
    emails: list[str],
    phones: list[str],
    socials: list[str],
    *,
    budget: list[int],
) -> None:
    if budget[0] <= 0:
        return
    budget[0] -= 1

    if isinstance(node, list):
        for item in node:
            _walk(item, emails, phones, socials, budget=budget)
        return
    if not isinstance(node, dict):
        return

    for key, value in node.items():
        lowered = key.lower()
        if lowered in EMAIL_KEYS:
            emails.extend(_strings(value, strip_prefix="mailto:"))
        elif lowered in PHONE_KEYS:
            phones.extend(_strings(value, strip_prefix="tel:"))
        elif lowered in SOCIAL_KEYS:
            socials.extend(_strings(value))
        else:
            _walk(value, emails, phones, socials, budget=budget)


def _strings(value: Any, *, strip_prefix: str = "") -> list[str]:
    """Coerce a JSON-LD value into a list of strings -- it may legally be a bare
    string, a list of them, or a `{"@value": ...}` wrapper."""
    if isinstance(value, str):
        cleaned = value.strip()
        if strip_prefix and cleaned.lower().startswith(strip_prefix):
            cleaned = cleaned[len(strip_prefix):].strip()
        return [cleaned] if cleaned else []
    if isinstance(value, list):
        return [item for entry in value for item in _strings(entry, strip_prefix=strip_prefix)]
    if isinstance(value, dict):
        return _strings(value.get("@value") or value.get("value") or "", strip_prefix=strip_prefix)
    return []


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out
