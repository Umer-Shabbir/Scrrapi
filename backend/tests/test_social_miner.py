from app.scraping.common.social_miner import (
    canonicalize_social_url,
    classify_social_url,
    extract_social_links,
)


def test_profiles_are_grouped_by_network() -> None:
    html = """
    <a href="https://www.facebook.com/joesplumbing">fb</a>
    <a href="https://instagram.com/joesplumbing/">ig</a>
    <a href="https://www.linkedin.com/company/joes-plumbing">li</a>
    """

    assert extract_social_links(html) == {
        "facebook": ["https://facebook.com/joesplumbing"],
        "instagram": ["https://instagram.com/joesplumbing"],
        "linkedin": ["https://linkedin.com/company/joes-plumbing"],
    }


def test_share_widgets_are_not_profiles() -> None:
    html = """
    <a href="https://www.facebook.com/sharer/sharer.php?u=https://joesplumbing.com">share</a>
    <a href="https://twitter.com/intent/tweet?url=https://joesplumbing.com">tweet</a>
    <a href="https://www.linkedin.com/sharing/share-offsite/?url=x">post</a>
    """

    assert extract_social_links(html) == {}


def test_bare_network_root_is_an_unfilled_placeholder() -> None:
    assert classify_social_url("https://facebook.com/") is None
    assert classify_social_url("https://www.instagram.com") is None


def test_content_links_are_not_accounts() -> None:
    assert classify_social_url("https://youtube.com/watch?v=abc123") is None
    assert classify_social_url("https://instagram.com/p/CxYz/") is None
    assert classify_social_url("https://youtube.com/@joesplumbing") == "youtube"


def test_same_profile_linked_twice_counts_once() -> None:
    html = """
    <a href="https://facebook.com/joesplumbing">header</a>
    <a href="https://www.facebook.com/joesplumbing/?utm_source=footer">footer</a>
    """

    assert extract_social_links(html)["facebook"] == ["https://facebook.com/joesplumbing"]


def test_facebook_numeric_profile_keeps_its_query() -> None:
    url = "https://www.facebook.com/profile.php?id=100064123456789&ref=page_internal"

    assert canonicalize_social_url(url) == ("https://facebook.com/profile.php?id=100064123456789")


def test_whatsapp_click_to_chat_is_a_profile() -> None:
    html = '<a href="https://api.whatsapp.com/send?phone=15125550100">WhatsApp</a>'

    assert extract_social_links(html)["whatsapp"] == [
        "https://api.whatsapp.com/send?phone=15125550100"
    ]


def test_secondary_networks_land_in_other() -> None:
    html = """
    <a href="https://www.pinterest.com/joesplumbing/">pin</a>
    <a href="https://t.me/joesplumbing">telegram</a>
    """

    assert extract_social_links(html)["other"] == [
        "https://pinterest.com/joesplumbing",
        "https://t.me/joesplumbing",
    ]


def test_profiles_in_json_ld_sameas_are_found_too() -> None:
    html = """
    <script type="application/ld+json">
    {"@type": "LocalBusiness", "sameAs": ["https://www.tiktok.com/@joesplumbing"]}
    </script>
    """

    assert extract_social_links(html)["tiktok"] == ["https://tiktok.com/@joesplumbing"]
