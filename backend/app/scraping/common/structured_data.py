"""Reads contact details, leadership, and reviews out of schema.org JSON-LD blocks.

Most site builders (Wix, Squarespace, WordPress SEO plugins, Shopify) emit a
`LocalBusiness`/`Organization` block with the business's own phone, email,
decision makers, and social profiles in it, and it is the most reliable contact data on the page --
hand-typed once by the owner, not scattered through the markup.

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
DECISION_MAKER_KEYS = {
    "founder",
    "founders",
    "employee",
    "employees",
    "alumni",
    "member",
    "members",
    "director",
    "officer",
}
REVIEW_KEYS = {"review", "reviews"}

# Guards against a pathological document (a product feed with thousands of
# nodes) turning one page into a long walk.
MAX_NODES = 2000


def extract_structured_contacts(
    html: str, *, include_extended: bool = False
) -> dict[str, list[Any]]:
    """`{"emails": [...], "phones": [...], "socials": [...]}` from every JSON-LD
    block on the page, in document order and deduplicated.

    When `include_extended=True`, also returns `decision_makers` and `reviews`.
    """
    emails: list[str] = []
    phones: list[str] = []
    socials: list[str] = []
    decision_makers: list[dict[str, str]] = []
    reviews: list[str] = []

    for match in JSON_LD_RE.finditer(html):
        document = _load(match.group(1))
        if document is None:
            continue
        _walk(document, emails, phones, socials, decision_makers, reviews, budget=[MAX_NODES])

    res = {
        "emails": _dedupe(emails),
        "phones": _dedupe(phones),
        "socials": _dedupe(socials),
    }
    if include_extended:
        res["decision_makers"] = _dedupe_decision_makers(decision_makers)
        res["reviews"] = _dedupe(reviews)
    return res


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
    decision_makers: list[dict[str, str]],
    reviews: list[str],
    *,
    budget: list[int],
) -> None:
    if budget[0] <= 0:
        return
    budget[0] -= 1

    if isinstance(node, list):
        for item in node:
            _walk(item, emails, phones, socials, decision_makers, reviews, budget=budget)
        return
    if not isinstance(node, dict):
        return

    # Check if this node itself is a Person
    node_type = str(node.get("@type", "")).lower()
    if "person" in node_type or "founder" in node_type:
        name = _extract_name(node)
        job_title = node.get("jobTitle") or node.get("roleName") or "Decision Maker"
        if isinstance(job_title, dict):
            job_title = job_title.get("name") or "Decision Maker"
        if name:
            decision_makers.append({"name": str(name).strip(), "title": str(job_title).strip()})

    # Check if this node is a Review
    if "review" in node_type:
        review_body = node.get("reviewBody") or node.get("description") or node.get("text")
        if review_body and isinstance(review_body, str):
            reviews.append(review_body.strip())

    for key, value in node.items():
        lowered = key.lower()
        if lowered in EMAIL_KEYS:
            emails.extend(_strings(value, strip_prefix="mailto:"))
        elif lowered in PHONE_KEYS:
            phones.extend(_strings(value, strip_prefix="tel:"))
        elif lowered in SOCIAL_KEYS:
            socials.extend(_strings(value))
        elif lowered in DECISION_MAKER_KEYS:
            if isinstance(value, dict):
                name = _extract_name(value)
                job_title = value.get("jobTitle") or lowered.rstrip("s").capitalize()
                if name:
                    decision_makers.append(
                        {"name": str(name).strip(), "title": str(job_title).strip()}
                    )
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        name = _extract_name(item)
                        job_title = item.get("jobTitle") or lowered.rstrip("s").capitalize()
                        if name:
                            decision_makers.append(
                                {"name": str(name).strip(), "title": str(job_title).strip()}
                            )
                    elif isinstance(item, str):
                        decision_makers.append(
                            {"name": item.strip(), "title": lowered.rstrip("s").capitalize()}
                        )
            elif isinstance(value, str):
                decision_makers.append(
                    {"name": value.strip(), "title": lowered.rstrip("s").capitalize()}
                )
            _walk(value, emails, phones, socials, decision_makers, reviews, budget=budget)
        elif lowered in REVIEW_KEYS:
            if isinstance(value, list):
                for r in value:
                    if isinstance(r, dict):
                        body = r.get("reviewBody") or r.get("description") or r.get("text")
                        if body and isinstance(body, str):
                            reviews.append(body.strip())
            elif isinstance(value, dict):
                body = value.get("reviewBody") or value.get("description") or value.get("text")
                if body and isinstance(body, str):
                    reviews.append(body.strip())
            _walk(value, emails, phones, socials, decision_makers, reviews, budget=budget)
        else:
            _walk(value, emails, phones, socials, decision_makers, reviews, budget=budget)


def _extract_name(node: dict) -> str | None:
    name_val = node.get("name")
    if isinstance(name_val, str):
        return name_val
    if isinstance(name_val, dict):
        return name_val.get("@value") or name_val.get("value")
    return None


def _strings(value: Any, *, strip_prefix: str = "") -> list[str]:
    """Coerce a JSON-LD value into a list of strings -- it may legally be a bare
    string, a list of them, or a `{"@value": ...}` wrapper."""
    if isinstance(value, str):
        cleaned = value.strip()
        if strip_prefix and cleaned.lower().startswith(strip_prefix):
            cleaned = cleaned[len(strip_prefix) :].strip()
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


def _dedupe_decision_makers(dms: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for dm in dms:
        name = dm.get("name", "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(dm)
    return out
