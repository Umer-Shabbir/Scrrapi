"""Harvests decision-maker names and titles (Owner, Founder, CEO, President, etc.)
from a business website and structured data.

Extracts key leadership from three sources in confidence order:
1. Schema.org JSON-LD structured data (Person nodes with jobTitle or founder/employee relations).
2. Semantic HTML elements (team/about bio cards, executive lists).
3. Text patterns ("Owner: John Doe", "Founded by Jane Smith", "Jane Doe, CEO", etc.).
"""

import re

from bs4 import BeautifulSoup

# Standard executive / leadership titles to match
DECISION_MAKER_TITLES = [
    # Compound titles first
    "Founder & CEO",
    "Founder and CEO",
    "Co-Founder & CEO",
    "Co-Founder and CEO",
    "Owner & Founder",
    "Founder & Owner",
    "President & CEO",
    "President and CEO",
    "CEO & Founder",
    "CEO and Founder",
    "Owner & Operator",
    "Owner and Operator",
    "President & General Manager",
    "President and General Manager",
    # English
    "Owner",
    "Co-Owner",
    "Founder",
    "Co-Founder",
    "Chief Executive Officer",
    "CEO",
    "President",
    "Principal",
    "Managing Director",
    "General Manager",
    "Managing Partner",
    "Partner",
    "Executive Director",
    "Director",
    "Proprietor",
    "Operator",
    # German
    "Inhaber",
    "Inhaberin",
    "Gründer",
    "Gründerin",
    "Geschäftsführer",
    "Geschäftsführerin",
    "Vorstand",
    # Spanish
    "Fundador",
    "Fundadora",
    "Director General",
    "Propietario",
    "Propietaria",
    "Dueño",
    "Dueña",
    "Presidente",
    # French
    "Fondateur",
    "Fondatrice",
    "Dirigeant",
    "Dirigeante",
    "Président",
    "Présidente",
    "Gérant",
    "Gérante",
    # Italian
    "Fondatore",
    "Fondatrice",
    "Titolare",
    "Amministratore Delegato",
    "Presidente",
]

# Regex for title matching in case-insensitive contexts (longest title first)
_TITLES_PATTERN = "|".join(
    re.escape(t) for t in sorted(DECISION_MAKER_TITLES, key=len, reverse=True)
)

# Pattern 1: "Title: Name" or "Title - Name" (e.g. "Owner: John Doe", "Founder - Jane Smith")
_TITLE_PREFIX_RE = re.compile(
    rf"(?:^|[\n\r•|;\t])\s*(?i:(?:Meet the\s+)?(?:{_TITLES_PATTERN})\s*[:–—\-])\s*"
    rf"([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){{1,2}})(?=[\n\r•|;,.<]|$)"
)

# Pattern 2: "Name, Title" or "Name (Title)" (e.g. "John Doe, Owner", "Jane Smith (CEO & Founder)")
_TITLE_SUFFIX_RE = re.compile(
    rf"([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){{1,2}})\s*"
    rf"(?i:(?:,\s*|\s+[-–—]\s+|\s*\(\s*)(?:{_TITLES_PATTERN})"
    r"(?:\s*&|\s+and\s+[a-zA-Z\s]+)?(?:\s*\))?)"
)

# Pattern 3: "Founded by Name" / "Owned and operated by Name"
_FOUNDED_BY_RE = re.compile(
    r"(?i:(?:founded|co-founded|started|established|owned\s+and\s+operated|created)\s+by)\s+"
    r"([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,2})"
)

# Generic non-name terms to filter out false positives
STOP_WORDS = {
    "About Us",
    "Contact Us",
    "Our Team",
    "Our Story",
    "Home Page",
    "Read More",
    "Privacy Policy",
    "Terms Conditions",
    "Terms Service",
    "Learn More",
    "All Rights",
    "Rights Reserved",
    "United States",
    "New York",
    "San Francisco",
    "Customer Service",
    "Sales Department",
    "Support Team",
    "General Inquiries",
    "Header Menu",
    "Footer Menu",
    "Navigation Menu",
    "Site Map",
    "Google Maps",
    "WordPress Theme",
    "Wix Com",
    "Shopify Store",
    "Call Us",
    "Email Us",
    "Mon Fri",
    "Sat Sun",
    "Open Hours",
    "Mon Sat",
    "Opening Hours",
    "Street Suite",
    "Road Suite",
    "Avenue Suite",
    "Boulevard Suite",
}


def is_valid_name(name: str) -> bool:
    """Check if a string looks like a legitimate human person's name."""
    cleaned = name.strip()
    if not cleaned or len(cleaned) < 3 or len(cleaned) > 50:
        return False
    if cleaned in STOP_WORDS:
        return False
    # Must have 2-4 parts
    parts = cleaned.split()
    if len(parts) < 2 or len(parts) > 4:
        return False
    # Each part should start with uppercase and be alphabetic
    for part in parts:
        part_clean = re.sub(r"[.'-]", "", part)
        if not part_clean.isalpha() or not part[0].isupper():
            return False
        if part_clean.lower() in {
            "the",
            "and",
            "or",
            "inc",
            "llc",
            "ltd",
            "corp",
            "co",
            "suite",
            "street",
            "ave",
            "st",
            "in",
            "by",
            "for",
            "at",
            "to",
            "of",
        }:
            return False
    return True


def extract_decision_makers(
    html: str, text: str | None = None, limit: int = 5
) -> list[dict[str, str]]:
    """Extract decision-maker candidates from page HTML and text.

    Returns a list of dicts: `[{"name": "John Doe", "title": "Owner"}, ...]`
    deduplicated and sorted by confidence.
    """
    results: list[dict[str, str]] = []
    seen_names: set[str] = set()

    def add_candidate(name: str, title: str) -> None:
        clean_name = re.sub(r"\s+", " ", name).strip(" ,.;:-–—")
        clean_title = re.sub(r"\s+", " ", title).strip(" ,.;:-–—")
        if not is_valid_name(clean_name):
            return
        name_key = clean_name.lower()
        if name_key in seen_names:
            return
        seen_names.add(name_key)
        results.append(
            {
                "name": clean_name,
                "title": clean_title or "Decision Maker",
            }
        )

    # 1. Check DOM team / leadership card structures
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    # Search for bio/team elements
    card_selectors = [
        '[class*="team"]',
        '[class*="leadership"]',
        '[class*="founder"]',
        '[class*="bio"]',
        '[class*="member"]',
        '[class*="person"]',
        '[class*="executive"]',
        '[class*="about-us"]',
        '[class*="owner"]',
    ]
    for card in soup.select(", ".join(card_selectors)):
        card_text = card.get_text("\n", strip=True)
        # Check if card text contains a title
        for match in _TITLE_PREFIX_RE.finditer(card_text):
            title = _extract_matched_title(match.group(0))
            add_candidate(match.group(1), title)
        for match in _TITLE_SUFFIX_RE.finditer(card_text):
            title = _extract_matched_title(match.group(0))
            add_candidate(match.group(1), title)

    # 2. Text-level regex searches
    full_text = text if text is not None else soup.get_text("\n", strip=True)

    # Prefix matches ("Owner: Jane Smith")
    for match in _TITLE_PREFIX_RE.finditer(full_text):
        title = _extract_matched_title(match.group(0))
        add_candidate(match.group(1), title)

    # Suffix matches ("Jane Smith, Founder & CEO")
    for match in _TITLE_SUFFIX_RE.finditer(full_text):
        title = _extract_matched_title(match.group(0))
        add_candidate(match.group(1), title)

    # "Founded by..." matches
    for match in _FOUNDED_BY_RE.finditer(full_text):
        add_candidate(match.group(1), "Founder")

    return results[:limit]


def _extract_matched_title(matched_text: str) -> str:
    for title in sorted(DECISION_MAKER_TITLES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(title)}\b", matched_text, re.IGNORECASE):
            return title
    return "Decision Maker"


def format_decision_makers(decision_makers: list[dict[str, str]]) -> str | None:
    """Format a list of decision-maker dicts into a readable string representation.

    e.g. "Jane Doe (Founder & CEO), John Smith (President)"
    """
    if not decision_makers:
        return None
    formatted = []
    for dm in decision_makers:
        name = dm.get("name")
        title = dm.get("title")
        if name:
            if title and title.lower() != "decision maker":
                formatted.append(f"{name} ({title})")
            else:
                formatted.append(name)
    return ", ".join(formatted) if formatted else None
