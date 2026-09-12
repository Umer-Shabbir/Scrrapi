from app.scraping.common.decision_maker_miner import (
    extract_decision_makers,
    format_decision_makers,
    is_valid_name,
)


def test_is_valid_name() -> None:
    assert is_valid_name("John Doe") is True
    assert is_valid_name("Jane Smith-Jones") is True
    assert is_valid_name("Mary Jane Watson") is True
    assert is_valid_name("Privacy Policy") is False
    assert is_valid_name("Contact Us") is False
    assert is_valid_name("A") is False
    assert is_valid_name("john doe") is False


def test_extract_decision_makers_prefix() -> None:
    html = """
    <div>
        <p>Owner: Alice Walker</p>
        <p>Founder & CEO: Bob Robertson</p>
    </div>
    """
    results = extract_decision_makers(html)
    names = [r["name"] for r in results]
    assert "Alice Walker" in names
    assert "Bob Robertson" in names


def test_extract_decision_makers_suffix() -> None:
    html = """
    <div>
        <h2>Sarah Connor, Founder</h2>
        <h3>Michael Scott (President & General Manager)</h3>
    </div>
    """
    results = extract_decision_makers(html)
    names = [r["name"] for r in results]
    assert "Sarah Connor" in names
    assert "Michael Scott" in names


def test_extract_decision_makers_founded_by() -> None:
    html = "<p>The company was founded by David Hasselhoff in 1999.</p>"
    results = extract_decision_makers(html)
    assert len(results) == 1
    assert results[0]["name"] == "David Hasselhoff"
    assert results[0]["title"] == "Founder"


def test_format_decision_makers() -> None:
    dms = [
        {"name": "Alice Walker", "title": "Founder & CEO"},
        {"name": "Bob Robertson", "title": "Owner"},
    ]
    formatted = format_decision_makers(dms)
    assert formatted == "Alice Walker (Founder & CEO), Bob Robertson (Owner)"
    assert format_decision_makers([]) is None
