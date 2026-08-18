from app.scraping.common.phone_miner import extract_phones, looks_like_phone, phone_key


def test_tel_links_come_first() -> None:
    html = """
    <p>Call 512-555-0199 for sales.</p>
    <a href="tel:+15125550100">Main line</a>
    """

    assert extract_phones(html, "Call 512-555-0199 for sales.")[0] == "+15125550100"


def test_tel_link_extension_is_dropped() -> None:
    html = '<a href="tel:+15125550100;ext=204">Reception</a>'

    assert extract_phones(html, "") == ["+15125550100"]


def test_whatsapp_link_is_a_phone_number() -> None:
    html = '<a href="https://wa.me/15125550100">Chat</a>'

    assert extract_phones(html, "") == ["+15125550100"]


def test_same_number_written_two_ways_appears_once() -> None:
    html = '<a href="tel:+15125550100">Call</a>'
    text = "Or dial (512) 555-0100 during business hours."

    assert extract_phones(html, text) == ["+15125550100"]


def test_text_numbers_are_found_when_there_is_no_tel_link() -> None:
    text = "Austin: (512) 555-0100 · Round Rock: (512) 555-0188"

    assert extract_phones("", text) == ["(512) 555-0100", "(512) 555-0188"]


def test_dates_are_not_phone_numbers() -> None:
    text = "Serving Texas since 1998. Updated 2026-01-15. Open 9.00 - 17.00."

    assert extract_phones("", text) == []


def test_bare_digit_runs_at_odd_lengths_are_rejected() -> None:
    # An 8-digit order id and a 13-digit EAN are not numbers to call.
    assert looks_like_phone("48210033") is False
    assert looks_like_phone("4006381333931") is False
    # A bare 10-digit run is a plausible national number.
    assert looks_like_phone("5125550100") is True


def test_international_numbers_are_kept_at_any_plan_length() -> None:
    assert looks_like_phone("+44 20 7946 0018") is True


def test_phone_key_ignores_formatting_and_country_code() -> None:
    assert phone_key("+1 512-555-0100") == phone_key("(512) 555-0100")
    assert phone_key("+44 20 7946 0018") == phone_key("020 7946 0018")


def test_phone_key_of_a_non_number_is_empty() -> None:
    assert phone_key("call us") == ""
