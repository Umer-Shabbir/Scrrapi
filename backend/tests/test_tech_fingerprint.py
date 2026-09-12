import httpx

from app.scraping.common.tech_fingerprint import detect_tech_stack, fetch_tech_stack


def test_detects_wordpress() -> None:
    html = '<link rel="stylesheet" href="/wp-content/themes/x/style.css">'
    assert detect_tech_stack(html) == ["WordPress"]


def test_detects_multiple_signatures_in_order() -> None:
    html = """
    <script src="https://www.googletagmanager.com/gtag/js?id=G-XXX"></script>
    <script src="https://js.hs-scripts.com/12345.js"></script>
    <link rel="stylesheet" href="/wp-content/themes/x/style.css">
    """
    assert detect_tech_stack(html) == ["WordPress", "Google Analytics", "HubSpot"]


def test_no_signatures_is_empty_list() -> None:
    assert detect_tech_stack("<html><body>Plain site</body></html>") == []


def test_empty_html_is_empty_list() -> None:
    assert detect_tech_stack("") == []


async def test_fetch_tech_stack_detects_from_response_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text='<link href="/wp-content/style.css">', headers={"content-type": "text/html"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await fetch_tech_stack("https://example.com", client=client) == ["WordPress"]


async def test_fetch_tech_stack_no_website_is_empty() -> None:
    assert await fetch_tech_stack(None) == []


async def test_fetch_tech_stack_network_error_is_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await fetch_tech_stack("https://example.com", client=client) == []
