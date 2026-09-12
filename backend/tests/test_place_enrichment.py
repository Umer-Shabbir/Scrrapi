import httpx

from app.scraping.common.place_enrichment import enrich_place_data
from app.scraping.common.site_crawler import CrawlBudget


def _transport(handler):
    return httpx.MockTransport(handler)


DEEP_BUDGET = CrawlBudget(max_pages=5, max_depth=2, total_timeout_s=10.0)


async def test_enrich_place_data_validates_existing_website_and_mines_email() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "joesplumbing.com":
            return httpx.Response(200, text='<a href="mailto:owner@joesplumbing.com">Email</a>')
        return httpx.Response(200, text="ok")

    place = {"name": "Joe's Plumbing", "website": "joesplumbing.com", "phone": "555-1234"}

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        result = await enrich_place_data(place, "Austin, TX", client=client)

    assert result["website"] == "https://joesplumbing.com"
    assert result["email"] == "owner@joesplumbing.com"
    # Untouched fields pass through.
    assert result["phone"] == "555-1234"
    assert result["name"] == "Joe's Plumbing"


async def test_enrich_place_data_falls_back_to_startpage_when_website_missing() -> None:
    startpage_html = """
    <a class="w-gl__result-title" href="https://joesplumbing.com/">Joe's Plumbing</a>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.startpage.com":
            return httpx.Response(200, text=startpage_html)
        if request.url.host == "joesplumbing.com":
            return httpx.Response(200, text="<p>contact@joesplumbing.com</p>")
        return httpx.Response(200, text="ok")

    place = {"name": "Joe's Plumbing", "website": None}

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        result = await enrich_place_data(place, "Austin, TX", client=client)

    assert result["website"] == "https://joesplumbing.com/"
    assert result["email"] == "contact@joesplumbing.com"


async def test_enrich_place_data_falls_back_when_listed_website_is_dead() -> None:
    startpage_html = '<a class="w-gl__result-title" href="https://real-site.com/">Real Site</a>'

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "dead-site.com":
            return httpx.Response(404, text="gone")
        if request.url.host == "www.startpage.com":
            return httpx.Response(200, text=startpage_html)
        return httpx.Response(200, text="ok")

    place = {"name": "Joe's Plumbing", "website": "https://dead-site.com"}

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        result = await enrich_place_data(place, "Austin, TX", client=client)

    assert result["website"] == "https://real-site.com/"


async def test_enrich_place_data_leaves_both_fields_none_when_nothing_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="gone")

    place = {"name": "Ghost Business", "website": "https://dead-site.com"}

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        result = await enrich_place_data(place, "Nowhere, TX", client=client)

    assert result["website"] is None
    assert result["email"] is None


async def test_enrich_place_data_skips_startpage_when_no_name_and_no_website() -> None:
    place = {"phone": "555-0000"}

    result = await enrich_place_data(place, "Austin, TX")

    assert result["website"] is None
    assert result["email"] is None
    # Maps' own phone survives a run that found no website to crawl.
    assert result["phone"] == "555-0000"


# --------------------------------------------------------------------------- #
# Deep crawl
# --------------------------------------------------------------------------- #

DEEP_SITE = {
    "/": """<html><body>
        <a href="/contact">Contact</a>
        <a href="https://facebook.com/joesplumbing">Facebook</a>
        <p>Joe's Plumbing — (512) 555-0100</p>
    </body></html>""",
    "/contact": """<html><body>
        <a href="mailto:office@joesplumbing.com">Office</a>
        <a href="mailto:accounts@joesplumbing.com">Accounts</a>
        <a href="tel:+15125550188">Emergencies</a>
    </body></html>""",
}


def _deep_handler(request: httpx.Request) -> httpx.Response:
    if request.url.host != "joesplumbing.com":
        return httpx.Response(404)
    path = request.url.path
    if path in DEEP_SITE:
        return httpx.Response(200, text=DEEP_SITE[path], headers={"content-type": "text/html"})
    return httpx.Response(404)


async def test_deep_crawl_appends_site_contacts_to_the_maps_ones() -> None:
    place = {
        "name": "Joe's Plumbing",
        "website": "https://joesplumbing.com",
        "phone": "+1 512-555-0100",
    }

    async with httpx.AsyncClient(transport=_transport(_deep_handler)) as client:
        result = await enrich_place_data(
            place, "Austin, TX", client=client, deep_crawl=True, budget=DEEP_BUDGET
        )

    # Maps' number first, the site's second -- and the site's copy of Maps'
    # number, written "(512) 555-0100", is not a third entry.
    assert result["phone"] == "+1 512-555-0100, +15125550188"
    assert result["email"] == "office@joesplumbing.com, accounts@joesplumbing.com"
    assert result["emails"] == ["office@joesplumbing.com", "accounts@joesplumbing.com"]
    assert result["socials"]["facebook"] == ["https://facebook.com/joesplumbing"]


async def test_deep_crawl_reports_what_it_crawled() -> None:
    seen = []
    place = {"name": "Joe's Plumbing", "website": "https://joesplumbing.com"}

    async with httpx.AsyncClient(transport=_transport(_deep_handler)) as client:
        await enrich_place_data(
            place,
            client=client,
            deep_crawl=True,
            budget=DEEP_BUDGET,
            on_crawl=seen.append,
        )

    assert len(seen) == 1
    assert seen[0].pages_crawled == 2


async def test_shallow_run_does_not_crawl_beyond_the_home_page() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return _deep_handler(request)

    place = {"name": "Joe's Plumbing", "website": "https://joesplumbing.com"}

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        result = await enrich_place_data(place, client=client)

    assert "/contact" not in requested
    # Nothing on the home page, and no crawl to find the contact page's address.
    assert result["email"] is None


async def test_enrich_place_data_depth_capabilities() -> None:
    html = """<html><body>
        <h1>Joe's Plumbing</h1>
        <p>Founder & CEO: Joe Schmoe</p>
        <p>Direct Mobile: (512) 555-0999</p>
        <a href="mailto:[EMAIL_REDACTED]">Email</a>
    </body></html>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    place = {
        "name": "Joe's Plumbing",
        "website": "https://joesplumbing.com",
        "phone": "(512) 555-0100",
        "reviews": [
            "Great service, Joe was very prompt and affordable!",
            "Fast same day repair, highly recommended.",
        ],
        "reviews_count": 25,
    }

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        result = await enrich_place_data(place, client=client)

    assert result["decision_maker"] == "Joe Schmoe (Founder & CEO)"
    assert "(512) 555-0999" in result["mobile_phone"]
    assert result["sentiment_label"] == "Positive"
    assert result["sentiment_score"] is not None and result["sentiment_score"] >= 0.7
    assert (
        "Fast response & punctual" in result["positive_highlights"]
        or "Fair & affordable pricing" in result["positive_highlights"]
    )


async def test_enrich_place_data_waterfall_trigger_on_generic_email() -> None:
    # Website only contains info@joesplumbing.com -> triggers waterfall cascade
    html = """<html><body>
        <h1>Joe's Plumbing</h1>
        <a href="mailto:info@joesplumbing.com">Contact</a>
    </body></html>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "joesplumbing.com":
            return httpx.Response(200, text=html)
        if request.url.host == "api.hunter.io":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "emails": [
                            {
                                "value": "joe.plumber@joesplumbing.com",
                                "first_name": "Joe",
                                "last_name": "Plumber",
                                "position": "Owner",
                                "phone_number": "+15125550999",
                            }
                        ]
                    }
                },
            )
        return httpx.Response(404)

    place = {
        "name": "Joe's Plumbing",
        "website": "https://joesplumbing.com",
    }

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        result = await enrich_place_data(
            place,
            client=client,
            waterfall_enabled=True,
            waterfall_providers=["hunter"],
            waterfall_keys={"hunter": "test_key"},
        )

    assert result["email"] == "joe.plumber@joesplumbing.com, info@joesplumbing.com"
    assert result["email_source"] == "waterfall:hunter"
    assert result["phone_source"] == "waterfall:hunter"
    assert "+15125550999" in result["mobile_phone"]


async def test_enrich_place_data_waterfall_trigger_on_missing_email() -> None:
    # Website contains no email -> triggers waterfall cascade
    html = """<html><body>
        <h1>Joe's Plumbing</h1>
        <p>Call us at 555-0100</p>
    </body></html>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "joesplumbing.com":
            return httpx.Response(200, text=html)
        if request.url.host == "api.prospeo.io":
            return httpx.Response(
                200,
                json={
                    "response": {
                        "emails": [
                            {
                                "email": "joe@joesplumbing.com",
                                "first_name": "Joe",
                                "last_name": "Owner",
                                "mobile_phone": "+15125550888",
                            }
                        ]
                    }
                },
            )
        return httpx.Response(404)

    place = {
        "name": "Joe's Plumbing",
        "website": "https://joesplumbing.com",
    }

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        result = await enrich_place_data(
            place,
            client=client,
            waterfall_enabled=True,
            waterfall_providers=["prospeo"],
            waterfall_keys={"prospeo": "test_key"},
        )

    assert result["email"] == "joe@joesplumbing.com"
    assert result["email_source"] == "waterfall:prospeo"
    assert result["phone_source"] == "waterfall:prospeo"
    assert "+15125550888" in result["mobile_phone"]
