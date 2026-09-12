import httpx

from app.scraping.common.website_finder import get_website, search_website_on_startpage

STARTPAGE_RESULTS_HTML = """
<html><body>
<div class="w-gl__result">
  <a class="w-gl__result-title" href="https://www.facebook.com/joesplumbing"
     >Joe's Plumbing - Facebook</a>
</div>
<div class="w-gl__result">
  <a class="w-gl__result-title" href="https://joesplumbing.com/">Joe's Plumbing | Official Site</a>
</div>
<div class="w-gl__result">
  <a class="w-gl__result-title" href="https://www.yelp.com/biz/joes-plumbing"
     >Joe's Plumbing - Yelp</a>
</div>
</body></html>
"""


def _transport(handler):
    return httpx.MockTransport(handler)


async def test_get_website_returns_final_url_after_redirect() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(301, headers={"Location": "https://www.example.com/"})
        return httpx.Response(200, text="<html>ok</html>")

    async with httpx.AsyncClient(transport=_transport(handler), follow_redirects=True) as client:
        result = await get_website("example.com", client=client)

    assert result == "https://www.example.com/"


async def test_get_website_normalizes_missing_scheme() -> None:
    seen_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, text="ok")

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        await get_website("www.example.com", client=client)

    assert seen_urls == ["https://www.example.com"]


async def test_get_website_returns_none_on_4xx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        result = await get_website("https://dead-domain.example", client=client)

    assert result is None


async def test_get_website_returns_none_on_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        result = await get_website("https://unreachable.example", client=client)

    assert result is None


async def test_get_website_returns_none_for_blank_candidate() -> None:
    assert await get_website("") is None
    assert await get_website("   ") is None


async def test_search_website_on_startpage_skips_directory_sites() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.startpage.com":
            return httpx.Response(200, text=STARTPAGE_RESULTS_HTML)
        # Every candidate the search surfaces resolves fine.
        return httpx.Response(200, text="<html>ok</html>")

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        result = await search_website_on_startpage("Joe's Plumbing", "Austin, TX", client=client)

    assert result == "https://joesplumbing.com/"


async def test_search_website_on_startpage_falls_through_dead_links() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.startpage.com":
            return httpx.Response(200, text=STARTPAGE_RESULTS_HTML)
        if request.url.host == "joesplumbing.com":
            return httpx.Response(404, text="gone")
        return httpx.Response(200, text="<html>ok</html>")

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        result = await search_website_on_startpage("Joe's Plumbing", "Austin, TX", client=client)

    # Only the directory sites and the dead joesplumbing.com were candidates,
    # and directory sites are filtered before ever being fetched.
    assert result is None


async def test_search_website_on_startpage_returns_none_for_blank_query() -> None:
    assert await search_website_on_startpage("", "") is None


async def test_search_website_on_startpage_skips_subdomains_of_directory_sites() -> None:
    """`app.startpage.com` is not `startpage.com` to an exact-match check, and it
    is the first link on every results page -- so it used to win outright."""
    html = """
    <html><body>
      <a href="https://app.startpage.com?source=home-hamburger">Get the app</a>
      <a href="https://m.facebook.com/joesplumbing">Joe's Plumbing</a>
      <a href="https://joesplumbing.com/">Joe's Plumbing | Official Site</a>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.startpage.com":
            return httpx.Response(200, text=html)
        return httpx.Response(200, text="<html>ok</html>")

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        result = await search_website_on_startpage("Joe's Plumbing", "Austin, TX", client=client)

    assert result == "https://joesplumbing.com/"


async def test_search_website_on_startpage_treats_a_captcha_page_as_no_results() -> None:
    """The challenge page answers 200 and carries its own outbound links; mining
    them hands back a website that has nothing to do with the business."""
    captcha_html = (
        '<html><body><a href="https://www.reddit.com/r/StartpageSearch/">help</a></body></html>'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sp/search":
            return httpx.Response(
                302, headers={"Location": "https://www.startpage.com/sp/captcha-block?bc=PK"}
            )
        return httpx.Response(200, text=captcha_html)

    async with httpx.AsyncClient(transport=_transport(handler), follow_redirects=True) as client:
        result = await search_website_on_startpage("Joe's Plumbing", "Austin, TX", client=client)

    assert result is None
