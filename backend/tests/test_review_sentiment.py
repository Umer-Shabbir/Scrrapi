from app.scraping.common.review_sentiment import analyze_reviews


def test_analyze_reviews_positive() -> None:
    reviews = [
        "Great and friendly staff! They did an amazing job and were very fast and professional.",
        "Excellent service, highly recommended! Very honest pricing.",
    ]
    result = analyze_reviews(reviews, review_count=2)
    assert result["review_count"] == 2
    assert result["sentiment_label"] == "Positive"
    assert result["sentiment_score"] is not None and result["sentiment_score"] >= 0.7
    assert (
        "Fast response & punctual" in result["positive_highlights"]
        or "Friendly & courteous staff" in result["positive_highlights"]
    )
    assert result["pain_points"] == []


def test_analyze_reviews_negative_pain_points() -> None:
    reviews = [
        "Terrible experience. The technician was 3 hours late and very slow. Rude service.",
        "Overpriced and charged hidden fees. Awful quality, broke next day, refund refused.",
    ]
    result = analyze_reviews(reviews, review_count=2)
    assert result["sentiment_label"] == "Negative"
    assert result["sentiment_score"] is not None and result["sentiment_score"] <= 0.4
    assert len(result["pain_points"]) >= 2
    assert result["pain_points_summary"] is not None
    assert "Slow turnaround / long wait times" in result["pain_points"]
    assert "High pricing / unexpected fees" in result["pain_points"]


def test_analyze_empty_reviews() -> None:
    result = analyze_reviews([], review_count=0)
    assert result["review_count"] == 0
    assert result["sentiment_score"] is None
    assert result["sentiment_label"] is None
    assert result["pain_points"] == []
    assert result["pain_points_summary"] is None
