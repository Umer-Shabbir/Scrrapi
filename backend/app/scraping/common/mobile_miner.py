"""Identifies and extracts direct personal mobile phone numbers.

Distinguishes direct mobile / cell numbers from general store / switchboard lines
using two signals:
1. Contextual labels in HTML and page text ("Mobile:", "Cell:", "Direct:", "WhatsApp:", etc.).
2. Number plan heuristics (e.g. WhatsApp wa.me links, UK 07xxx, DE 015/016/017, FR 06/07, etc.).
"""

import re

from app.scraping.common.phone_miner import _digits, _tidy, looks_like_phone, phone_key

# Mobile context prefixes in various languages
MOBILE_LABEL_RES = [
    re.compile(
        r"(?:mobile|cell|cellular|direct(?:\s+dial)?|personal|whatsapp|sms|text(?:\s+us)?|"
        r"handy|mobil|móvil|portátil|celular)\s*[:–—\-]?\s*(\+?\(?\d[\d\s().\-–—/]{5,22}\d)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\+?\(?\d[\d\s().\-–—/]{5,22}\d)\s*(?:\((?:mobile|cell|direct|whatsapp|sms|handy|mobil)\)|"
        r"\[(?:mobile|cell|direct)\])",
        re.IGNORECASE,
    ),
]

# wa.me and sms: hrefs are direct mobile numbers
SMS_HREF_RE = re.compile(r'href=["\']sms:(?://)?([^"\'?;]+)', re.IGNORECASE)
WA_HREF_RE = re.compile(r"(?:wa\.me|whatsapp\.com/send)(?:\?phone=|/)\+?(\d{7,15})", re.IGNORECASE)


# International mobile prefix ranges
# Formatted after stripping non-digits
def is_international_mobile_pattern(digits: str) -> bool:
    """Check if normalized digits match known international mobile number allocations."""
    # UK: +44 7xxx or 07xxx
    if digits.startswith("447") and len(digits) == 12:
        return True
    if digits.startswith("07") and len(digits) == 11:
        return True

    # Germany: +49 15x / 16x / 17x or 015x / 016x / 017x
    if (
        digits.startswith("4915") or digits.startswith("4916") or digits.startswith("4917")
    ) and len(digits) in (12, 13):
        return True
    if (digits.startswith("015") or digits.startswith("016") or digits.startswith("017")) and len(
        digits
    ) in (11, 12):
        return True

    # France: +33 6 / 7 or 06 / 07
    if (digits.startswith("336") or digits.startswith("337")) and len(digits) == 11:
        return True
    if (digits.startswith("06") or digits.startswith("07")) and len(digits) == 10:
        return True

    # Spain: +34 6 / 7 or 6xx / 7xx (9 digits)
    if (digits.startswith("346") or digits.startswith("347")) and len(digits) == 11:
        return True
    if (digits.startswith("6") or digits.startswith("7")) and len(digits) == 9:
        return True

    # Italy: +39 3xx or 3xx (10 digits)
    if digits.startswith("393") and len(digits) in (11, 12):
        return True
    if digits.startswith("3") and len(digits) == 10:
        return True

    # Australia: +61 4xx or 04xx
    if digits.startswith("614") and len(digits) == 11:
        return True
    if digits.startswith("04") and len(digits) == 10:
        return True

    return False


def is_mobile_number(candidate: str, context: str = "") -> bool:
    """Determine whether a phone string is likely a direct mobile phone number."""
    if not looks_like_phone(candidate):
        return False
    digits = _digits(candidate)
    if not digits:
        return False

    # Check context keywords
    lowered_context = context.lower()
    if any(
        k in lowered_context
        for k in (
            "mobile",
            "cell",
            "cellular",
            "direct",
            "whatsapp",
            "sms",
            "handy",
            "mobil",
            "móvil",
        )
    ):
        return True

    # Check numbering plan rules
    if is_international_mobile_pattern(digits):
        return True

    return False


def extract_mobile_phones(html: str, text: str | None = None, limit: int = 5) -> list[str]:
    """Extract direct mobile phone numbers from page HTML and text.

    Returns deduplicated list of mobile phone numbers in formatted display form.
    """
    seen_keys: set[str] = set()
    mobiles: list[str] = []

    def add_mobile(candidate: str) -> None:
        display = _tidy(candidate)
        key = phone_key(display)
        if not key or key in seen_keys:
            return
        seen_keys.add(key)
        mobiles.append(display)

    # 1. WhatsApp links are explicit mobile numbers
    for match in WA_HREF_RE.finditer(html):
        add_mobile(f"+{match.group(1)}")

    # 2. sms: links
    for match in SMS_HREF_RE.finditer(html):
        val = match.group(1).strip()
        if looks_like_phone(val):
            add_mobile(val)

    # 3. Labelled mobile numbers in text / HTML
    content = text if text is not None else html
    for pattern in MOBILE_LABEL_RES:
        for match in pattern.finditer(content):
            num = match.group(1).strip()
            if looks_like_phone(num):
                add_mobile(num)

    # 4. Any numbers in page that match mobile numbering plan heuristics
    from app.scraping.common.phone_miner import extract_phones

    all_phones = extract_phones(html, text)
    for phone in all_phones:
        digits = _digits(phone)
        if is_international_mobile_pattern(digits):
            add_mobile(phone)

    return mobiles[:limit]
