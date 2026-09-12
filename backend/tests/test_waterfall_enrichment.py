import httpx
import pytest

from app.scraping.common.generic_email import (
    has_only_generic_emails,
    is_generic_email,
)
from app.scraping.common.waterfall.datagma import DatagmaProvider
from app.scraping.common.waterfall.engine import build_providers, run_waterfall_cascade
from app.scraping.common.waterfall.findymail import FindymailProvider
from app.scraping.common.waterfall.hunter import HunterProvider
from app.scraping.common.waterfall.prospeo import ProspeoProvider


def _mock_transport(handler):
    return httpx.MockTransport(handler)


# --------------------------------------------------------------------------- #
# Generic Email Detection Tests
# --------------------------------------------------------------------------- #


def test_is_generic_email_identifies_standard_role_inboxes():
    assert is_generic_email("info@acmeplumbing.com") is True
    assert is_generic_email("contact@acmeplumbing.com") is True
    assert is_generic_email("sales@acmeplumbing.com") is True
    assert is_generic_email("support@acmeplumbing.com") is True
    assert is_generic_email("hello@acmeplumbing.com") is True
    assert is_generic_email("admin@acmeplumbing.com") is True
    assert is_generic_email("office@acmeplumbing.com") is True
    assert is_generic_email("billing@acmeplumbing.com") is True
    assert is_generic_email("help@acmeplumbing.com") is True
    assert is_generic_email("inquiries@acmeplumbing.com") is True
    assert is_generic_email("press@acmeplumbing.com") is True
    assert is_generic_email("contact-us@acmeplumbing.com") is True
    assert is_generic_email("info.austin@acmeplumbing.com") is True


def test_is_generic_email_identifies_personal_inboxes():
    assert is_generic_email("john.doe@acmeplumbing.com") is False
    assert is_generic_email("sarah_smith@acmeplumbing.com") is False
    assert is_generic_email("david@acmeplumbing.com") is False
    assert is_generic_email("dr.miller@acmeplumbing.com") is False
    assert is_generic_email("ceo.janesmith@acmeplumbing.com") is False


def test_has_only_generic_emails():
    # Empty list
    assert has_only_generic_emails([]) is True

    # Only generic emails
    assert has_only_generic_emails(["info@acmeplumbing.com", "contact@acmeplumbing.com"]) is True

    # Mixed list containing a personal email
    assert has_only_generic_emails(["info@acmeplumbing.com", "john.doe@acmeplumbing.com"]) is False

    # Only personal emails
    assert has_only_generic_emails(["john.doe@acmeplumbing.com"]) is False


# --------------------------------------------------------------------------- #
# Provider Tests (Hunter, Prospeo, Datagma, Findymail)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_hunter_provider_domain_search():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.hunter.io"
        assert request.url.params["api_key"] == "test_hunter_key"
        assert request.url.params["domain"] == "acmeplumbing.com"
        return httpx.Response(
            200,
            json={
                "data": {
                    "emails": [
                        {
                            "value": "john.acme@acmeplumbing.com",
                            "first_name": "John",
                            "last_name": "Acme",
                            "position": "Owner",
                            "phone_number": "+15125550199",
                        }
                    ]
                }
            },
        )

    provider = HunterProvider(api_key="test_hunter_key")
    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        res = await provider.enrich("acmeplumbing.com", client=client)

    assert res.emails == ["john.acme@acmeplumbing.com"]
    assert res.mobile_phones == ["+15125550199"]
    assert len(res.decision_makers) == 1
    assert res.decision_makers[0]["name"] == "John Acme"
    assert res.decision_makers[0]["title"] == "Owner"
    assert res.provider_used == "hunter"


@pytest.mark.asyncio
async def test_prospeo_provider():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.prospeo.io"
        assert request.headers["X-KEY"] == "test_prospeo_key"
        return httpx.Response(
            200,
            json={
                "response": {
                    "emails": [
                        {
                            "email": "sarah.connor@acmeroofing.com",
                            "first_name": "Sarah",
                            "last_name": "Connor",
                            "title": "Founder & CEO",
                            "mobile_phone": "+15125550188",
                        }
                    ]
                }
            },
        )

    provider = ProspeoProvider(api_key="test_prospeo_key")
    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        res = await provider.enrich("acmeroofing.com", client=client)

    assert res.emails == ["sarah.connor@acmeroofing.com"]
    assert res.mobile_phones == ["+15125550188"]
    assert res.decision_makers[0]["name"] == "Sarah Connor"
    assert res.provider_used == "prospeo"


@pytest.mark.asyncio
async def test_datagma_provider():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "gateway.datagma.com"
        assert request.url.params["apiKey"] == "test_datagma_key"
        return httpx.Response(
            200,
            json={
                "data": {
                    "email": "mike@acmehvac.com",
                    "mobilePhone": "+15125550177",
                    "firstName": "Mike",
                    "lastName": "Trout",
                    "jobTitle": "President",
                }
            },
        )

    provider = DatagmaProvider(api_key="test_datagma_key")
    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        res = await provider.enrich("acmehvac.com", client=client)

    assert res.emails == ["mike@acmehvac.com"]
    assert res.mobile_phones == ["+15125550177"]
    assert res.decision_makers[0]["name"] == "Mike Trout"
    assert res.provider_used == "datagma"


@pytest.mark.asyncio
async def test_findymail_provider():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "app.findymail.com"
        assert "Bearer test_findy_key" in request.headers["Authorization"]
        return httpx.Response(
            200,
            json={
                "contact": {
                    "email": "elena.rodriguez@acmelaw.com",
                    "mobile": "+15125550166",
                    "name": "Elena Rodriguez",
                    "title": "Managing Partner",
                }
            },
        )

    provider = FindymailProvider(api_key="test_findy_key")
    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        res = await provider.enrich("acmelaw.com", client=client)

    assert res.emails == ["elena.rodriguez@acmelaw.com"]
    assert res.mobile_phones == ["+15125550166"]
    assert res.decision_makers[0]["name"] == "Elena Rodriguez"
    assert res.provider_used == "findymail"


# --------------------------------------------------------------------------- #
# Cascade Fallback & Orchestration Tests
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_waterfall_cascade_falls_back_when_first_provider_returns_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.hunter.io":
            # Hunter returns nothing
            return httpx.Response(200, json={"data": {"emails": []}})
        if request.url.host == "api.prospeo.io":
            # Prospeo finds the direct email
            return httpx.Response(
                200,
                json={
                    "response": {
                        "emails": [
                            {
                                "email": "founder@samplebiz.com",
                                "first_name": "Alex",
                                "last_name": "Smith",
                                "title": "Founder",
                                "mobile_phone": "+15125550155",
                            }
                        ]
                    }
                },
            )
        return httpx.Response(404)

    keys = {
        "hunter": "key1",
        "prospeo": "key2",
    }
    providers = build_providers(keys, order=["hunter", "prospeo"])

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        res = await run_waterfall_cascade(
            domain="samplebiz.com",
            company_name="Sample Biz",
            existing_emails=["info@samplebiz.com"],
            providers=providers,
            client=client,
        )

    assert res.provider_used == "prospeo"
    assert "founder@samplebiz.com" in res.emails
    # Direct email ranks first, generic email follows
    assert res.emails[0] == "founder@samplebiz.com"
    assert "info@samplebiz.com" in res.emails
    assert "+15125550155" in res.mobile_phones


@pytest.mark.asyncio
async def test_waterfall_cascade_handles_all_empty_gracefully():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"emails": []}})

    providers = build_providers({"hunter": "key1"})
    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        res = await run_waterfall_cascade(
            domain="emptybiz.com",
            existing_emails=["info@emptybiz.com"],
            providers=providers,
            client=client,
        )

    assert res.provider_used is None
    assert res.emails == ["info@emptybiz.com"]
    assert res.mobile_phones == []
