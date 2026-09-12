"""Utility for detecting generic role-based email addresses versus direct personal addresses.

Generic role-based emails (info@, contact@, support@, sales@, etc.) are commonly found
on business homepages and contact pages, but represent low-converting switchboard inboxes.
Direct personal emails (john.doe@, sarah@, etc.) are significantly higher value.

This module provides detection logic to trigger third-party waterfall enrichment cascades
when only generic emails (or no emails) are found by web scrapers.
"""

from app.scraping.common.email_miner import is_valid_email

# Common generic and department-level role-based email prefixes
GENERIC_EMAIL_PREFIXES = {
    "info",
    "contact",
    "contactus",
    "contact-us",
    "sales",
    "support",
    "hello",
    "admin",
    "administrator",
    "office",
    "help",
    "helpdesk",
    "billing",
    "inquiries",
    "inquiry",
    "service",
    "services",
    "team",
    "general",
    "mail",
    "mailbox",
    "press",
    "media",
    "jobs",
    "careers",
    "marketing",
    "customercare",
    "customer-care",
    "customerservice",
    "customer-service",
    "frontdesk",
    "front-desk",
    "reception",
    "enquiries",
    "enquiry",
    "feedback",
    "orders",
    "hq",
    "desk",
    "booking",
    "bookings",
    "reservations",
    "reservation",
    "privacy",
    "legal",
    "compliance",
    "hr",
    "accounting",
}


def is_generic_email(email: str | None) -> bool:
    """Determine whether an email address is a generic / role-based inbox."""
    if not email or "@" not in email:
        return True

    local_part = email.split("@", 1)[0].strip().lower()
    if not local_part:
        return True

    # Check exact match
    if local_part in GENERIC_EMAIL_PREFIXES:
        return True

    # Check prefix variations with separators (e.g. info.austin, contact-us, sales_team)
    cleaned_local = local_part.replace(".", "").replace("-", "").replace("_", "")
    if cleaned_local in GENERIC_EMAIL_PREFIXES:
        return True

    # Check tokenized subparts
    tokens = [
        t for t in local_part.replace(".", " ").replace("-", " ").replace("_", " ").split() if t
    ]
    for token in tokens:
        if token in GENERIC_EMAIL_PREFIXES:
            return True

    return False


def has_only_generic_emails(emails: list[str]) -> bool:
    """Check if the provided list of emails contains zero personal/direct email addresses.

    Returns True if:
    - The email list is empty, OR
    - Every valid email in the list is a generic role-based address.
    """
    valid_emails = [e for e in emails if is_valid_email(e)]
    if not valid_emails:
        return True

    return all(is_generic_email(e) for e in valid_emails)
