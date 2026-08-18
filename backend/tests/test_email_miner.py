import pytest

from app.scraping.common.email_miner import (
    decode_cfemail,
    extract_emails,
    extract_first_valid_email,
    get_domain_from_email,
    is_valid_email,
)


def test_extract_first_valid_email_prefers_mailto_over_text() -> None:
    html = """
    <p>Reach us at info@example.com or via the form.</p>
    <a href="mailto:contact@business.co">Email us</a>
    """

    assert extract_first_valid_email(html) == "contact@business.co"


def test_extract_first_valid_email_falls_back_to_text_scan() -> None:
    html = "<footer>Copyright 2026 - reach us at hello@business.co for quotes</footer>"

    assert extract_first_valid_email(html) == "hello@business.co"


def test_extract_first_valid_email_strips_mailto_query_string() -> None:
    html = '<a href="mailto:sales@business.co?subject=Quote">Email sales</a>'

    assert extract_first_valid_email(html) == "sales@business.co"


def test_extract_first_valid_email_skips_retina_image_filenames() -> None:
    html = '<img src="logo@2x.png"><img src="logo@3x.jpg">no real email here'

    assert extract_first_valid_email(html) is None


def test_extract_first_valid_email_returns_none_when_absent() -> None:
    html = "<p>No contact info on this page.</p>"

    assert extract_first_valid_email(html) is None


def test_is_valid_email_accepts_plausible_address() -> None:
    assert is_valid_email("owner@business.co") is True


def test_is_valid_email_rejects_missing_at_sign() -> None:
    assert is_valid_email("not-an-email") is False


def test_is_valid_email_rejects_malformed_address() -> None:
    assert is_valid_email("a@b") is False


def test_is_valid_email_rejects_image_filename_shaped_as_email() -> None:
    assert is_valid_email("banner@2x.png") is False


def test_get_domain_from_email_lowercases() -> None:
    assert get_domain_from_email("Owner@Business.CO") == "business.co"


def test_get_domain_from_email_rejects_non_email() -> None:
    with pytest.raises(ValueError):
        get_domain_from_email("not-an-email")


def test_sentry_dsn_is_not_an_email() -> None:
    """`https://<public key>@o1.ingest.sentry.io/42` in an inlined script tag is
    email-shaped, and it used to be the first match on any page with Sentry on it."""
    html = """
    <html><body><script>
      Sentry.init({dsn: "https://605a7baede844d278b89dc95af31b0c2@o447951.ingest.sentry.io/12"});
    </script>
    <p>Reach us at hello@roupdental.com</p></body></html>
    """
    assert extract_first_valid_email(html) == "hello@roupdental.com"


def test_placeholder_domains_are_skipped() -> None:
    html = '<html><body>you@example.com then <a href="mailto:info@realbiz.com">us</a></body></html>'
    assert extract_first_valid_email(html) == "info@realbiz.com"


def test_extract_emails_returns_every_address_best_first() -> None:
    html = """
    <p>Sales: sales@business.co · Support: support@business.co</p>
    <a href="mailto:office@business.co">Office</a>
    """

    assert extract_emails(html) == [
        "office@business.co",
        "sales@business.co",
        "support@business.co",
    ]


def test_extract_emails_deduplicates_case_insensitively() -> None:
    html = '<a href="mailto:Office@Business.co">Office</a><p>office@business.co</p>'

    assert extract_emails(html) == ["Office@Business.co"]


def test_cloudflare_obfuscated_address_is_decoded() -> None:
    # data-cfemail blob for "office@business.co" (key 0x7a).
    html = (
        '<span class="__cf_email__" data-cfemail="7a151c1c13191f3a180f0913141f0909541915">'
        "[email&#160;protected]</span>"
    )

    assert extract_first_valid_email(html) == "office@business.co"


def test_decode_cfemail_rejects_a_malformed_blob() -> None:
    assert decode_cfemail("zzzz") is None
    assert decode_cfemail("7a") is None


def test_hand_obfuscated_address_is_reassembled() -> None:
    html = "<p>Write to info [at] business [dot] co for a quote.</p>"

    assert extract_first_valid_email(html) == "info@business.co"


def test_hand_obfuscated_address_with_a_plain_domain() -> None:
    html = "<p>owner (at) business.co</p>"

    assert extract_first_valid_email(html) == "owner@business.co"


def test_prose_containing_at_and_dot_is_not_an_address() -> None:
    html = "<p>Meet us at reception. Dot the i's before signing.</p>"

    assert extract_first_valid_email(html) is None


def test_at_sign_html_entity_is_normalized() -> None:
    html = "<p>info&#64;business.co</p>"

    assert extract_first_valid_email(html) == "info@business.co"
