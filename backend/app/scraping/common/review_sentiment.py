"""Sentiment analysis and pain-point extraction from Google Maps customer reviews.

Extracts customer sentiments, pain points (complaints, friction, service failures),
and positive highlights from review snippets and text blocks.
"""

import re
from typing import TypedDict

# Positive and negative word lists for sentiment scoring
POSITIVE_WORDS = {
    "great",
    "excellent",
    "amazing",
    "wonderful",
    "fantastic",
    "outstanding",
    "awesome",
    "best",
    "perfect",
    "good",
    "love",
    "loved",
    "friendly",
    "helpful",
    "professional",
    "fast",
    "quick",
    "prompt",
    "clean",
    "reliable",
    "honest",
    "fair",
    "affordable",
    "recommended",
    "recommend",
    "super",
    "impressed",
    "efficient",
    "knowledgeable",
    "courteous",
    "quality",
    "responsive",
    "seamless",
}

NEGATIVE_WORDS = {
    "terrible",
    "horrible",
    "awful",
    "worst",
    "bad",
    "poor",
    "rude",
    "unprofessional",
    "slow",
    "late",
    "delayed",
    "expensive",
    "overpriced",
    "scam",
    "ripoff",
    "rip-off",
    "waste",
    "dirty",
    "broken",
    "damaged",
    "unreliable",
    "useless",
    "disappointed",
    "disappointing",
    "avoid",
    "never",
    "refused",
    "ignored",
    "incompetent",
    "cheat",
    "liar",
    "disaster",
    "mess",
    "unresponsive",
    "overcharge",
    "overcharged",
    "hidden",
}

# Pain point patterns with categorized labels
PAIN_POINT_CATEGORIES = [
    (
        "Slow turnaround / long wait times",
        re.compile(
            r"\b(?:slow|waited\s+(?:too\s+long|hours|\d+\s+min)|long\s+wait|took\s+(?:forever|days|weeks)|delay|delayed|never\s+on\s+time|late)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "High pricing / unexpected fees",
        re.compile(
            r"\b(?:expensive|overpriced|overcharged?|hidden\s+(?:fees?|costs?)|rip\s*off|scam|too\s+much\s+money|not\s+worth\s+the\s+price|pricey)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Poor customer service / rude staff",
        re.compile(
            r"\b(?:rude|unfriendly|disrespectful|bad\s+attitude|unprofessional|ignored|dismissive|poor\s+service|terrible\s+customer\s+service)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Unresponsive / communication issues",
        re.compile(
            r"\b(?:never\s+called\s+back|no\s+(?:response|answer|reply)|unresponsive|impossible\s+to\s+reach|hard\s+to\s+contact|poor\s+communication)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Subpar quality / unfinished work",
        re.compile(
            r"\b(?:poor\s+quality|broke|broken|damaged|didn'?t\s+fix|unfinished|had\s+to\s+redo|faulty|defect|shoddy)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Billing / refund disputes",
        re.compile(
            r"\b(?:refused\s+(?:a\s+)?refund|billing\s+(?:issue|error|problem)|charged\s+extra|unauthorized\s+charge)\b",
            re.IGNORECASE,
        ),
    ),
]

# Positive highlight patterns
POSITIVE_HIGHLIGHT_CATEGORIES = [
    (
        "Fast response & punctual",
        re.compile(
            r"\b(?:fast|quick|prompt|speedy|on\s+time|same\s+day|rapid|efficient)\b", re.IGNORECASE
        ),
    ),
    (
        "Friendly & courteous staff",
        re.compile(
            r"\b(?:friendly|courteous|polite|welcoming|kind|caring|great\s+staff|wonderful\s+people)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "High quality & expert work",
        re.compile(
            r"\b(?:expert|high\s+quality|top\s+notch|flawless|professional|skilled|master|craftsmanship)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Fair & affordable pricing",
        re.compile(
            r"\b(?:fair\s+price|affordable|reasonable|great\s+value|honest\s+pricing|worth\s+every\s+penny)\b",
            re.IGNORECASE,
        ),
    ),
]


class ReviewAnalysisResult(TypedDict, total=False):
    review_count: int | None
    sentiment_score: float | None
    sentiment_label: str | None
    pain_points: list[str]
    positive_highlights: list[str]
    pain_points_summary: str | None


def analyze_reviews(reviews: list[str], review_count: int | None = None) -> ReviewAnalysisResult:
    """Analyze a collection of customer review texts.

    Calculates sentiment score, categorizes pain points and highlights.
    """
    if not reviews:
        return {
            "review_count": review_count,
            "sentiment_score": None,
            "sentiment_label": None,
            "pain_points": [],
            "positive_highlights": [],
            "pain_points_summary": None,
        }

    total_positive = 0
    total_negative = 0
    detected_pain_points: set[str] = set()
    detected_highlights: set[str] = set()

    for review in reviews:
        words = re.findall(r"\b[a-zA-Z\-']+\b", review.lower())
        pos_count = sum(1 for w in words if w in POSITIVE_WORDS)
        neg_count = sum(1 for w in words if w in NEGATIVE_WORDS)
        total_positive += pos_count
        total_negative += neg_count

        # Check pain points
        for label, pattern in PAIN_POINT_CATEGORIES:
            if pattern.search(review):
                detected_pain_points.add(label)

        # Check positive highlights
        for label, pattern in POSITIVE_HIGHLIGHT_CATEGORIES:
            if pattern.search(review):
                detected_highlights.add(label)

    # Compute normalized sentiment score from -1.0 to 1.0 (or 0.0 to 1.0)
    total_words = total_positive + total_negative
    if total_words > 0:
        raw_score = (total_positive - total_negative) / total_words
        # Normalize to 0.0 .. 1.0 range
        sentiment_score = round((raw_score + 1.0) / 2.0, 2)
    else:
        sentiment_score = 0.5

    if sentiment_score >= 0.7:
        sentiment_label = "Positive"
    elif sentiment_score <= 0.4:
        sentiment_label = "Negative"
    elif total_positive > 0 and total_negative > 0:
        sentiment_label = "Mixed"
    else:
        sentiment_label = "Neutral"

    pain_points_list = sorted(detected_pain_points)
    highlights_list = sorted(detected_highlights)
    summary = ", ".join(pain_points_list) if pain_points_list else None

    return {
        "review_count": review_count if review_count is not None else len(reviews),
        "sentiment_score": sentiment_score,
        "sentiment_label": sentiment_label,
        "pain_points": pain_points_list,
        "positive_highlights": highlights_list,
        "pain_points_summary": summary,
    }
