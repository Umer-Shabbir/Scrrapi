import httpx

from app.scraping.common.site_crawler import CrawlBudget, crawl_site

HOME = """
<html><body>
  <nav>
    <a href="/about">About</a>
    <a href="/contact">Contact</a>
    <a href="/blog/2019/why-we-love-pipes">Blog post</a>
    <a href="https://facebook.com/joesplumbing">Facebook</a>
  </nav>
  <p>Call us on (512) 555-0100.</p>
</body></html>
"""

CONTACT = """
<html><body>
  <a href="mailto:office@joesplumbing.com">Email the office</a>
  <p>Emergencies: <a href="tel:+15125550188">+1 512-555-0188</a></p>
  <a href="https://instagram.com/joesplumbing">Instagram</a>
</body></html>
"""

ABOUT = """
<html><body>
  <p>Founded 1998. Reach the owner at joe [at] joesplumbing [dot] com.</p>
</body></html>
"""

BLOG = "<html><body><p>Pipes are great. Written 2019-07-04.</p></body></html>"

PAGES = {
    "/": HOME,
    "/about": ABOUT,
    "/contact": CONTACT,
    "/blog/2019/why-we-love-pipes": BLOG,
}


def _site(pages: dict[str, str] | None = None, *, robots: str | None = None, sitemap: str = ""):
    """A mock transport serving one site. Missing paths 404, which is what a real
    crawl mostly gets when it guesses."""
    served = PAGES if pages is None else pages

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            if robots is None:
                return httpx.Response(404)
            return httpx.Response(200, text=robots, headers={"content-type": "text/plain"})
        if path in ("/sitemap.xml", "/sitemap_index.xml"):
            if not sitemap:
                return httpx.Response(404)
            return httpx.Response(200, text=sitemap, headers={"content-type": "application/xml"})
        if path in served:
            return httpx.Response(
                200, text=served[path], headers={"content-type": "text/html; charset=utf-8"}
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _client(transport: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, follow_redirects=True)


BUDGET = CrawlBudget(max_pages=10, max_depth=2, total_timeout_s=10.0)


async def test_crawls_past_the_home_page_and_merges_contacts() -> None:
    async with _client(_site()) as client:
        contacts = await crawl_site("https://joesplumbing.com", budget=BUDGET, client=client)

    assert contacts.pages_crawled >= 3
    assert contacts.emails == ["office@joesplumbing.com", "joe@joesplumbing.com"]
    # The home page number and the contact page's emergency line, both kept, in
    # the order the pages were read.
    assert contacts.phones == ["(512) 555-0100", "+15125550188"]
    assert contacts.socials == {
        "facebook": ["https://facebook.com/joesplumbing"],
        "instagram": ["https://instagram.com/joesplumbing"],
    }


async def test_contact_page_is_visited_before_the_blog() -> None:
    """With a budget of two pages, the one page that gets crawled after the home
    page has to be /contact -- ordering is the whole reason a page budget works."""
    async with _client(_site()) as client:
        contacts = await crawl_site(
            "https://joesplumbing.com",
            budget=CrawlBudget(max_pages=2, max_depth=2, total_timeout_s=10.0),
            client=client,
        )

    assert contacts.pages_crawled == 2
    assert "office@joesplumbing.com" in contacts.emails
    assert contacts.truncated is True


async def test_sitemap_finds_a_page_nothing_links_to() -> None:
    pages = {
        "/": "<html><body><p>Nothing links anywhere.</p></body></html>",
        "/kontakt": '<html><body><a href="mailto:hallo@joesplumbing.com">Mail</a></body></html>',
    }
    sitemap = """<?xml version="1.0"?>
    <urlset><url><loc>https://joesplumbing.com/kontakt</loc></url></urlset>
    """

    async with _client(_site(pages, sitemap=sitemap)) as client:
        contacts = await crawl_site("https://joesplumbing.com", budget=BUDGET, client=client)

    assert contacts.emails == ["hallo@joesplumbing.com"]


async def test_robots_disallow_is_honoured() -> None:
    robots = "User-agent: *\nDisallow: /contact\n"

    async with _client(_site(robots=robots)) as client:
        contacts = await crawl_site("https://joesplumbing.com", budget=BUDGET, client=client)

    assert "office@joesplumbing.com" not in contacts.emails
    # The rest of the site is still crawled.
    assert "joe@joesplumbing.com" in contacts.emails


async def test_offsite_links_are_not_followed() -> None:
    pages = {
        "/": '<html><body><a href="https://competitor.com/contact">Them</a></body></html>',
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "competitor.com":
            raise AssertionError("crawled off-site")
        if request.url.path == "/":
            return httpx.Response(200, text=pages["/"], headers={"content-type": "text/html"})
        return httpx.Response(404)

    async with _client(httpx.MockTransport(handler)) as client:
        contacts = await crawl_site("https://joesplumbing.com", budget=BUDGET, client=client)

    assert contacts.pages_crawled == 1


async def test_the_business_own_domain_ranks_first_among_emails() -> None:
    pages = {
        "/": """<html><body>
            <p>Site by hello@webagency.io</p>
            <a href="mailto:office@joesplumbing.com">Us</a>
        </body></html>""",
    }

    async with _client(_site(pages)) as client:
        contacts = await crawl_site("https://joesplumbing.com", budget=BUDGET, client=client)

    assert contacts.emails[0] == "office@joesplumbing.com"


async def test_dead_site_returns_empty_rather_than_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    async with _client(httpx.MockTransport(handler)) as client:
        contacts = await crawl_site("https://gone.example", budget=BUDGET, client=client)

    assert contacts.is_empty()
    assert contacts.pages_crawled == 0


async def test_assets_and_state_changing_paths_are_skipped() -> None:
    pages = {
        "/": """<html><body>
            <a href="/brochure.pdf">Brochure</a>
            <a href="/cart">Cart</a>
            <a href="/contact">Contact</a>
        </body></html>""",
        "/contact": CONTACT,
    }
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if request.url.path in pages:
            return httpx.Response(
                200, text=pages[request.url.path], headers={"content-type": "text/html"}
            )
        return httpx.Response(404)

    async with _client(httpx.MockTransport(handler)) as client:
        await crawl_site("https://joesplumbing.com", budget=BUDGET, client=client)

    assert "/brochure.pdf" not in requested
    assert "/cart" not in requested
    assert "/contact" in requested
