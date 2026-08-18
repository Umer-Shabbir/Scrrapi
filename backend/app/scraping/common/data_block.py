"""Parses Google's packed JSON-array response format for map results.

Legacy equivalent: DataBlock.Parse (the "],[" token parsing).

Decision (3.5): the feed/place scrapers (3.3/3.4) scrape the rendered DOM
(div[role="feed"] + a.hfpxzc, per-field locators on the place page) rather than
intercepting the underlying XHR JSON, so this parser is not currently wired into
the scraping pipeline. It's kept as a tested, standalone utility for if/when the
feed or place scrapers get swapped over to Playwright `page.on("response")`
network interception -- Google's packed payloads are XSSI-protected JSON, so
that interception path would feed response bodies straight into this function.
"""

import json

# Google prefixes many JSON XHR bodies with this token so the raw response can't
# be `eval`'d if pulled in as a <script> src (a general anti-JSON-hijacking
# convention, not specific to Maps).
XSSI_PREFIX = ")]}'"


def parse_packed_response(raw: str) -> list:
    """Strip Google's XSSI prefix (if present) and decode the packed JSON array.

    Raises ValueError if the body isn't valid JSON, or isn't a top-level array,
    once the prefix is stripped.
    """
    text = raw.strip()
    if text.startswith(XSSI_PREFIX):
        text = text[len(XSSI_PREFIX) :].lstrip("\n")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("could not parse packed response as JSON") from exc

    if not isinstance(data, list):
        # ValueError, not TypeError: this rejects malformed *data* (a validation
        # failure on an external response body), not a bad argument type.
        raise ValueError("expected a top-level JSON array")  # noqa: TRY004

    return data
