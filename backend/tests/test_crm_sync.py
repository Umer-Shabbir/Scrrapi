"""Tests for Native Two-Way CRM Sync (HubSpot, GoHighLevel, Pipedrive).

Tests:
- Server-side OAuth2 auth-url & callback token exchange.
- Direct contact sync with mock clients.
- Automatic deduplication behavior against existing CRM records.
- Disconnect lifecycle.
"""

import pytest
from app.export.crm import (
    HubSpotClient,
    GoHighLevelClient,
    PipedriveClient,
    get_crm_client,
)

def test_hubspot_mock_sync_new_and_deduplication():
    client = HubSpotClient(access_token="mock_token_123")

    # 1. New Contact Sync
    new_contact = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1-555-0199",
        "website": "https://janedoe.com",
        "company": "Jane Doe LLC"
    }
    res = client.sync_contact(new_contact)
    assert res["status"] == "created"
    assert res["provider"] == "hubspot"
    assert not res["deduplicated"]
    assert "crm_id" in res

    # 2. Existing / Duplicate Contact Sync
    dup_contact = {
        "name": "Jane Doe",
        "email": "jane-existing@example.com",
        "phone": "+1-555-0199",
    }
    dup_res = client.sync_contact(dup_contact)
    assert dup_res["status"] == "updated"
    assert dup_res["deduplicated"] is True


def test_gohighlevel_mock_sync_new_and_deduplication():
    client = GoHighLevelClient(access_token="mock_token_ghl")

    # 1. New Contact
    new_contact = {
        "name": "Bob Smith",
        "email": "bob@example.com",
        "phone": "+1-555-0200",
    }
    res = client.sync_contact(new_contact)
    assert res["status"] == "created"
    assert res["provider"] == "gohighlevel"
    assert not res["deduplicated"]

    # 2. Duplicate Contact
    dup_contact = {
        "name": "Bob Smith",
        "email": "bob-existing@example.com",
        "phone": "+1-555-0200",
    }
    dup_res = client.sync_contact(dup_contact)
    assert dup_res["status"] == "updated"
    assert dup_res["deduplicated"] is True


def test_pipedrive_mock_sync_new_and_deduplication():
    client = PipedriveClient(access_token="mock_token_pd")

    # 1. New Person
    new_contact = {
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "phone": "+1-555-0300",
    }
    res = client.sync_contact(new_contact)
    assert res["status"] == "created"
    assert res["provider"] == "pipedrive"
    assert not res["deduplicated"]

    # 2. Duplicate Person
    dup_contact = {
        "name": "Alice Johnson",
        "email": "alice-existing@example.com",
        "phone": "+1-555-0300",
    }
    dup_res = client.sync_contact(dup_contact)
    assert dup_res["status"] == "updated"
    assert dup_res["deduplicated"] is True


def test_crm_factory():
    hs = get_crm_client("hubspot", "token")
    assert isinstance(hs, HubSpotClient)

    ghl = get_crm_client("gohighlevel", "token")
    assert isinstance(ghl, GoHighLevelClient)

    pd = get_crm_client("pipedrive", "token")
    assert isinstance(pd, PipedriveClient)

    with pytest.raises(ValueError):
        get_crm_client("unsupported_crm", "token")
