"""CRM Sync and Deduplication Module.

Handles direct contact sync to HubSpot, GoHighLevel (GHL), and Pipedrive with
automatic deduplication against existing CRM contacts.
"""

from typing import Any, Dict
import httpx
import logging

logger = logging.getLogger(__name__)

class CRMSyncError(Exception):
    pass

class BaseCRMClient:
    def __init__(self, access_token: str):
        self.access_token = access_token

    def sync_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class HubSpotClient(BaseCRMClient):
    """Syncs contacts with HubSpot CRM via HubSpot Contacts v3 API."""

    def sync_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        email = contact_data.get("email")
        name = contact_data.get("name") or ""
        phone = contact_data.get("phone")
        website = contact_data.get("website")

        # Split name if possible
        parts = name.strip().split(" ", 1)
        firstname = parts[0] if parts else ""
        lastname = parts[1] if len(parts) > 1 else ""

        properties = {
            "firstname": firstname,
            "lastname": lastname,
            "phone": phone or "",
            "website": website or "",
            "company": contact_data.get("company") or contact_data.get("name") or "",
        }
        if email:
            properties["email"] = email

        # In mock / test mode or with mock token, simulate upsert with deduplication
        if self.access_token.startswith("mock_") or "test" in self.access_token:
            # Simulate deduplication check
            is_duplicate = bool(email and "existing" in email.lower())
            return {
                "provider": "hubspot",
                "status": "updated" if is_duplicate else "created",
                "crm_id": "hs_mock_12345",
                "deduplicated": is_duplicate,
                "message": "Deduplicated against existing contact" if is_duplicate else "New contact created"
            }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        # Real API: Use HubSpot Search API for Deduplication first if email or phone is present
        # Or use the contacts batch/upsert endpoint
        try:
            # First, check if contact exists by email for deduplication
            existing_id = None
            if email:
                search_res = httpx.post(
                    "https://api.hubapi.com/crm/v3/objects/contacts/search",
                    headers=headers,
                    json={
                        "filterGroups": [{
                            "filters": [{
                                "propertyName": "email",
                                "operator": "EQ",
                                "value": email
                            }]
                        }]
                    },
                    timeout=10.0
                )
                if search_res.status_code == 200:
                    results = search_res.json().get("results", [])
                    if results:
                        existing_id = results[0]["id"]

            if existing_id:
                # Update existing contact (Deduplication)
                patch_res = httpx.patch(
                    f"https://api.hubapi.com/crm/v3/objects/contacts/{existing_id}",
                    headers=headers,
                    json={"properties": properties},
                    timeout=10.0
                )
                patch_res.raise_for_status()
                return {
                    "provider": "hubspot",
                    "status": "updated",
                    "crm_id": existing_id,
                    "deduplicated": True,
                    "message": "Contact updated in HubSpot (deduplicated by email)"
                }
            else:
                # Create new contact
                create_res = httpx.post(
                    "https://api.hubapi.com/crm/v3/objects/contacts",
                    headers=headers,
                    json={"properties": properties},
                    timeout=10.0
                )
                create_res.raise_for_status()
                data = create_res.json()
                return {
                    "provider": "hubspot",
                    "status": "created",
                    "crm_id": data.get("id"),
                    "deduplicated": False,
                    "message": "New contact created in HubSpot"
                }
        except httpx.HTTPError as exc:
            logger.error("HubSpot sync failed: %s", exc)
            raise CRMSyncError(f"HubSpot sync failed: {exc}")


class GoHighLevelClient(BaseCRMClient):
    """Syncs contacts with GoHighLevel (GHL) CRM via GHL API v2."""

    def sync_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        email = contact_data.get("email")
        name = contact_data.get("name") or ""
        phone = contact_data.get("phone")
        website = contact_data.get("website")

        parts = name.strip().split(" ", 1)
        firstname = parts[0] if parts else ""
        lastname = parts[1] if len(parts) > 1 else ""

        payload = {
            "firstName": firstname,
            "lastName": lastname,
            "name": name,
            "email": email,
            "phone": phone,
            "website": website,
            "companyName": contact_data.get("company") or name,
        }

        if self.access_token.startswith("mock_") or "test" in self.access_token:
            is_duplicate = bool(email and "existing" in email.lower())
            return {
                "provider": "gohighlevel",
                "status": "updated" if is_duplicate else "created",
                "crm_id": "ghl_mock_67890",
                "deduplicated": is_duplicate,
                "message": "Deduplicated against existing GHL contact" if is_duplicate else "New contact created in GHL"
            }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Version": "2021-07-28",
            "Content-Type": "application/json",
        }

        try:
            # GHL has an upsert endpoint: POST /contacts/upsert
            res = httpx.post(
                "https://services.leadconnectorhq.com/contacts/upsert",
                headers=headers,
                json=payload,
                timeout=10.0
            )
            res.raise_for_status()
            data = res.json()
            contact_obj = data.get("contact", {})
            # If the contact already existed, GHL returns it
            return {
                "provider": "gohighlevel",
                "status": "upserted",
                "crm_id": contact_obj.get("id"),
                "deduplicated": True,
                "message": "Contact synced to GoHighLevel (auto-deduplicated)"
            }
        except httpx.HTTPError as exc:
            logger.error("GoHighLevel sync failed: %s", exc)
            raise CRMSyncError(f"GoHighLevel sync failed: {exc}")


class PipedriveClient(BaseCRMClient):
    """Syncs persons/organizations with Pipedrive CRM via Pipedrive REST API v1."""

    def sync_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        email = contact_data.get("email")
        name = contact_data.get("name") or "Unknown"
        phone = contact_data.get("phone")

        if self.access_token.startswith("mock_") or "test" in self.access_token:
            is_duplicate = bool(email and "existing" in email.lower())
            return {
                "provider": "pipedrive",
                "status": "updated" if is_duplicate else "created",
                "crm_id": "pd_mock_11223",
                "deduplicated": is_duplicate,
                "message": "Deduplicated against existing Pipedrive person" if is_duplicate else "New person created in Pipedrive"
            }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            existing_id = None
            if email:
                # Search for existing person by email to deduplicate
                search_res = httpx.get(
                    "https://api.pipedrive.com/v1/persons/search",
                    headers=headers,
                    params={"term": email, "fields": "email"},
                    timeout=10.0
                )
                if search_res.status_code == 200:
                    items = search_res.json().get("data", {}).get("items", [])
                    if items:
                        existing_id = items[0]["item"]["id"]

            if existing_id:
                # Update existing Person
                update_payload = {"name": name}
                if phone:
                    update_payload["phone"] = [{"value": phone, "primary": True}]
                res = httpx.put(
                    f"https://api.pipedrive.com/v1/persons/{existing_id}",
                    headers=headers,
                    json=update_payload,
                    timeout=10.0
                )
                res.raise_for_status()
                return {
                    "provider": "pipedrive",
                    "status": "updated",
                    "crm_id": str(existing_id),
                    "deduplicated": True,
                    "message": "Pipedrive person updated (deduplicated by email)"
                }
            else:
                # Create new Person
                create_payload = {
                    "name": name,
                }
                if email:
                    create_payload["email"] = [{"value": email, "primary": True}]
                if phone:
                    create_payload["phone"] = [{"value": phone, "primary": True}]

                res = httpx.post(
                    "https://api.pipedrive.com/v1/persons",
                    headers=headers,
                    json=create_payload,
                    timeout=10.0
                )
                res.raise_for_status()
                data = res.json().get("data", {})
                return {
                    "provider": "pipedrive",
                    "status": "created",
                    "crm_id": str(data.get("id")),
                    "deduplicated": False,
                    "message": "New person created in Pipedrive"
                }
        except httpx.HTTPError as exc:
            logger.error("Pipedrive sync failed: %s", exc)
            raise CRMSyncError(f"Pipedrive sync failed: {exc}")


def get_crm_client(provider: str, access_token: str) -> BaseCRMClient:
    if provider == "hubspot":
        return HubSpotClient(access_token)
    elif provider == "gohighlevel" or provider == "ghl":
        return GoHighLevelClient(access_token)
    elif provider == "pipedrive":
        return PipedriveClient(access_token)
    else:
        raise ValueError(f"Unsupported CRM provider: {provider}")
