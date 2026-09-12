"""Harvests phone numbers from a business website.

The Maps listing already gives one number; this is what the deep site crawler
(`app.scraping.common.site_crawler`) uses to find the others -- the mobile the
owner actually answers, the branch line, the WhatsApp number -- and what decides
whether a number found on the site is the same one Maps already had.

Three sources, in confidence order:

1. `tel:` links. Machine-readable and author-intended, so they are taken as-is.
2. WhatsApp click-to-chat links (`wa.me/<number>`), which are a phone number
   wearing a URL.
3. Visible page text, which is where most small sites still put the number.

Text is the noisy one: a page is full of digit runs that are not phone numbers
(dates, prices, ZIP+4, order ids, VAT numbers). `looks_like_phone` is what keeps
those out, and it is deliberately conservative -- a missed second number costs
far less than a column full of invoice ids.

Numbers are compared on `phone_key`, not on their text: Maps writes
"+1 512-555-0100" and the site writes "(512) 555-0100", and those must not both
end up in the phone column.
"""

import re

# `tel:` may carry punctuation, an extension (`;ext=12`) and even a leading
# `//`; everything after the first `;` is stripped as dialling metadata.
TEL_HREF_RE = re.compile(r'href=["\']tel:(?://)?([^"\'?;]+)', re.IGNORECASE)

# wa.me/15125550100, api.whatsapp.com/send?phone=15125550100 -- both are just a
# number in international form with no separators.
WHATSAPP_RE = re.compile(
    r"(?:wa\.me|whatsapp\.com/send)(?:\?phone=|/)\+?(\d{7,15})",
    re.IGNORECASE,
)

# A digit run with phone-ish punctuation in it. Bounded on both sides so a
# number embedded in a longer token (a URL, an id, a hash) is not clipped out of
# the middle of it and passed off as a phone number. The optional opening
# parenthesis matters: without it "(512) 555-0100" is captured from the digit
# onwards and stored as the visibly broken "512) 555-0100".
PHONE_TEXT_RE = re.compile(r"(?<![\w@.])(\+?\(?\d[\d\s().\-–—/]{5,22}\d)(?![\w])")

# What a phone number can be once the punctuation is gone. Below 7 digits it is
# an extension or a price; above 15 it is longer than E.164 allows, so it is an
# account number that happens to be grouped like one.
MIN_DIGITS = 7
MAX_DIGITS = 15

# Bare digit runs (no `+`, no separators) are only accepted at the lengths a
# national number actually has. Anything else in that shape -- an 8-digit order
# id, a 13-digit EAN -- is far more likely to be data than a number to call.
BARE_DIGIT_LENGTHS = {10, 11}

# Dates and opening hours survive the punctuation strip as 6-8 digit runs, and
# every site has them ("since 1998", "Mon-Fri 9.00 - 17.00"). Matched before that
# strip, while the separators are still there to recognise them by.
DATE_RES = [
    re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$"),
    re.compile(r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}$"),
    re.compile(r"^\d{4}\s*[-–—]\s*\d{4}$"),  # year range: 2019 - 2024
    # Time range: 9.00 - 17.00, 09:00-17:30, 8.30 – 12.00
    re.compile(r"^\d{1,2}[.:]\d{2}\s*[-–—]\s*\d{1,2}[.:]\d{2}$"),
]


def extract_phones(html: str, text: str | None = None, *, limit: int = 15) -> list[str]:
    """Every plausible phone number on a page, best first, deduplicated.

    `html` is the raw markup (searched for `tel:` and WhatsApp links); `text` is
    the rendered text of the same page, which the caller has usually already
    produced with BeautifulSoup. Passing it is worth it -- scanning raw markup
    for text numbers matches inside inline scripts and CSS, where every other
    hit is a timestamp or a colour value. Omitting it falls back to `html`.

    Deduplication is on `phone_key`, so the same number written two ways appears
    once, in whichever form was found first (i.e. the most trustworthy source).
    """
    seen: set[str] = set()
    phones: list[str] = []

    for candidate in _candidates(html, text if text is not None else html):
        display = _tidy(candidate)
        key = phone_key(display)
        if not key or key in seen:
            continue
        seen.add(key)
        phones.append(display)
        if len(phones) >= limit:
            break
    return phones


def _candidates(html: str, text: str):
    """Raw candidates in confidence order. `tel:`/WhatsApp are trusted as-is;
    text hits have to survive `looks_like_phone` first."""
    for match in TEL_HREF_RE.finditer(html):
        value = match.group(1).strip()
        if _digits(value):
            yield value

    for match in WHATSAPP_RE.finditer(html):
        yield f"+{match.group(1)}"

    for match in PHONE_TEXT_RE.finditer(text):
        candidate = match.group(1).strip()
        if looks_like_phone(candidate):
            yield candidate


def looks_like_phone(candidate: str) -> bool:
    """Whether a digit run found in page text is worth treating as a number.

    Rejects, in order: anything shaped like a date, anything outside the 7-15
    digit range E.164 allows, and unpunctuated runs at lengths no national
    numbering plan uses.
    """
    collapsed = re.sub(r"\s+", " ", candidate).strip()
    if any(pattern.match(collapsed) for pattern in DATE_RES):
        return False

    digits = _digits(collapsed)
    if not MIN_DIGITS <= len(digits) <= MAX_DIGITS:
        return False

    unpunctuated = collapsed.lstrip("+").isdigit()
    if unpunctuated and not collapsed.startswith("+") and len(digits) not in BARE_DIGIT_LENGTHS:
        return False
    return True


def phone_key(phone: str) -> str:
    """Comparison key for "is this the same number".

    The last nine digits, because that is what survives every way a number gets
    written down: country code present or not (+1 512 555 0100 vs 512-555-0100),
    trunk prefix present or not (020 7946 0018 vs +44 20 7946 0018). Shorter
    numbers compare on everything they have. Empty string for something with no
    digits in it, which callers treat as "not a number".
    """
    digits = _digits(phone)
    if not digits:
        return ""
    return digits[-9:] if len(digits) > 9 else digits


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _tidy(value: str) -> str:
    """Collapse whitespace and trim trailing punctuation, keeping the site's own
    formatting otherwise -- a number is easier to sanity-check in the form the
    business chose to print it."""
    return re.sub(r"\s+", " ", value).strip(" .,;:-–—")
