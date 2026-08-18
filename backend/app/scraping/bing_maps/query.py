"""Bing Maps search URL builder. Mirrors google_maps/query.py's interface so the job
runner can be source-agnostic (cboDataSource toggle in the legacy app)."""

from urllib.parse import quote_plus

BASE_URL = "https://www.bing.com/maps?q="


def build_search_url(keyword: str, location: str) -> str:
    """`keyword` + `location` -> a `bing.com/maps?q=<query>` URL.

    Same "<keyword> in <city>" query shape as google_maps.query.build_search_url,
    URL-encoded the same way (spaces -> `+`). `location` is optional -- pass ""
    to search the keyword alone.
    """
    keyword = keyword.strip()
    location = location.strip()
    if not keyword:
        raise ValueError("keyword must not be empty")

    query = f"{keyword} in {location}" if location else keyword
    return BASE_URL + quote_plus(query)
