"""Builds the Google Maps search URL from keyword + location.

Legacy equivalent: GoogleMapsScraper.BuildSearchRequest
(keyword+in+city -> google.com/maps/search/).
"""

from urllib.parse import quote_plus

BASE_URL = "https://www.google.com/maps/search/"


def build_search_url(keyword: str, location: str) -> str:
    """`keyword` + `location` -> a `google.com/maps/search/<query>` URL.

    Mirrors the legacy "<keyword> in <city>" query string, URL-encoded the
    same way a browser address bar would (spaces -> `+`). `location` is
    optional -- pass "" to search the keyword alone.
    """
    keyword = keyword.strip()
    location = location.strip()
    if not keyword:
        raise ValueError("keyword must not be empty")

    query = f"{keyword} in {location}" if location else keyword
    return BASE_URL + quote_plus(query)
