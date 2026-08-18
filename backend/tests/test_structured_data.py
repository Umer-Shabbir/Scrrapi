from app.scraping.common.structured_data import extract_structured_contacts

LOCAL_BUSINESS = """
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "Joe's Plumbing",
  "telephone": "+1 512-555-0100",
  "email": "mailto:office@joesplumbing.com",
  "sameAs": ["https://facebook.com/joesplumbing", "https://x.com/joesplumbing"],
  "contactPoint": {"@type": "ContactPoint", "telephone": "+1 512-555-0188"}
}
</script>
"""


def test_reads_phone_email_and_profiles() -> None:
    contacts = extract_structured_contacts(LOCAL_BUSINESS)

    assert contacts["phones"] == ["+1 512-555-0100", "+1 512-555-0188"]
    assert contacts["emails"] == ["office@joesplumbing.com"]
    assert contacts["socials"] == [
        "https://facebook.com/joesplumbing",
        "https://x.com/joesplumbing",
    ]


def test_graph_wrapper_is_walked() -> None:
    html = """
    <script type="application/ld+json">
    {"@graph": [{"@type": "WebSite"}, {"@type": "Organization", "telephone": "020 7946 0018"}]}
    </script>
    """

    assert extract_structured_contacts(html)["phones"] == ["020 7946 0018"]


def test_malformed_block_is_skipped_not_raised() -> None:
    html = '<script type="application/ld+json">{ this is not json </script>'

    assert extract_structured_contacts(html) == {"emails": [], "phones": [], "socials": []}


def test_page_without_structured_data_yields_nothing() -> None:
    assert extract_structured_contacts("<p>hello</p>") == {
        "emails": [],
        "phones": [],
        "socials": [],
    }
