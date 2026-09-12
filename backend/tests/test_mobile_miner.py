from app.scraping.common.mobile_miner import (
    extract_mobile_phones,
    is_international_mobile_pattern,
    is_mobile_number,
)


def test_is_international_mobile_pattern() -> None:
    # UK mobile 07123456789
    assert is_international_mobile_pattern("07123456789") is True
    assert is_international_mobile_pattern("447123456789") is True

    # Germany mobile 01511234567
    assert is_international_mobile_pattern("01511234567") is True
    assert is_international_mobile_pattern("491511234567") is True

    # France mobile 0612345678
    assert is_international_mobile_pattern("0612345678") is True
    assert is_international_mobile_pattern("33612345678") is True

    # Spain mobile 612345678
    assert is_international_mobile_pattern("612345678") is True
    assert is_international_mobile_pattern("34612345678") is True

    # Landline pattern (e.g. US landline / normal phone without context)
    assert is_international_mobile_pattern("5125550100") is False


def test_is_mobile_number_with_context() -> None:
    assert is_mobile_number("512-555-0199", context="Call our direct mobile: 512-555-0199") is True
    assert is_mobile_number("512-555-0199", context="Office main phone line: 512-555-0199") is False


def test_extract_mobile_phones_from_html() -> None:
    html = """
    <div>
        <a href="https://wa.me/15125550199">Chat on WhatsApp</a>
        <p>Direct Mobile: (512) 555-0188</p>
        <p>Main Switchboard: (512) 555-0100</p>
    </div>
    """
    mobiles = extract_mobile_phones(html)
    assert len(mobiles) >= 2
    assert any(
        "5125550199" in m.replace("-", "").replace(" ", "").replace("+", "") for m in mobiles
    )
    assert any(
        "5125550188" in m.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        for m in mobiles
    )
