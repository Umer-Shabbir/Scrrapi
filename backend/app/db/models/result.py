import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AppBase

# Lead Detail's claimed/closed badge (Figma: Identity Block > Badge Row).
# "closed" has no dedicated UI action yet -- nothing sets it -- but the column
# allows for it rather than being a bare claimed/unclaimed boolean, since the
# design shows a 3-state badge (open/claimed/closed) even though only the
# open<->claimed transition is wired to an action today.
LEAD_STATUSES = ("open", "claimed", "closed")

# Social networks that get a column of their own, in the order they appear in the
# grid and every export. Everything else the crawler recognises lands joined in
# `other_socials` -- a column per network would be a schema change every time a
# new platform matters, and the tail is read, not filtered on.
SOCIAL_COLUMNS = (
    "facebook",
    "instagram",
    "linkedin",
    "twitter",
    "youtube",
    "tiktok",
    "whatsapp",
)

SOCIAL_COLUMN_CHARS = 500
OTHER_SOCIALS_CHARS = 1000

# `email`/`phone` hold every address and number found for the business, joined
# with ", " -- the Maps listing's first, then whatever the deep site crawl added.
# They are sized for that rather than for one value.
EMAIL_COLUMN_CHARS = 1000
PHONE_COLUMN_CHARS = 500


class Result(AppBase):
    __tablename__ = "results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"))

    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(PHONE_COLUMN_CHARS), nullable=True)
    email: Mapped[str | None] = mapped_column(String(EMAIL_COLUMN_CHARS), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Filled by the deep site crawler only (app.scraping.common.site_crawler);
    # NULL on every row scraped with it switched off.
    facebook: Mapped[str | None] = mapped_column(String(SOCIAL_COLUMN_CHARS), nullable=True)
    instagram: Mapped[str | None] = mapped_column(String(SOCIAL_COLUMN_CHARS), nullable=True)
    linkedin: Mapped[str | None] = mapped_column(String(SOCIAL_COLUMN_CHARS), nullable=True)
    twitter: Mapped[str | None] = mapped_column(String(SOCIAL_COLUMN_CHARS), nullable=True)
    youtube: Mapped[str | None] = mapped_column(String(SOCIAL_COLUMN_CHARS), nullable=True)
    tiktok: Mapped[str | None] = mapped_column(String(SOCIAL_COLUMN_CHARS), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(SOCIAL_COLUMN_CHARS), nullable=True)
    other_socials: Mapped[str | None] = mapped_column(String(OTHER_SOCIALS_CHARS), nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Lead Detail screen only (Lead Detail cycle, priority 10) -- see LEAD_STATUSES.
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open")
    # ", "-joined, same convention as `email`/`phone` -- read and filtered, not
    # queried relationally. NULL/empty means untagged.
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Job-scoped only: marks this row as "don't act on this lead again" within
    # this job's results. Not wired to the (separate, unbuilt) Suppression List
    # screen or the scrape queue -- there is no cross-job place identity to key
    # a global suppression list against yet.
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Both place scrapers (google_maps/place.py, bing_maps/place.py) already
    # extract this from the listing; it just wasn't persisted before Lead Detail.
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    # "maps listing" | "site crawl" -- whichever stage first supplied the value,
    # known at write time in workers/tasks.py. None for rows written before this
    # column existed.
    phone_source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email_source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Comma-joined signature names from app.scraping.common.tech_fingerprint, run
    # once against the business's own home page. NULL if there was no website to
    # check or the fetch failed -- absence of a signature is not "confirmed absent".
    tech_stack: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Deterministic identity for "this business" (see app.workers.tasks.compute_place_key)
    # so a re-scrape in a later job can be recognised as the same lead and diffed
    # into `result_history`. Not a real Google/Bing place id -- there is no reliable
    # one available without touching the live-scraper URL parsing.
    place_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


# Tracked fields a re-scrape can produce a history entry for. Whatever
# workers.tasks.record_history diffs against the prior same-place_key result.
HISTORY_FIELDS = ("phone", "email", "rating")


class ResultHistory(AppBase):
    """One changed field on a re-scraped lead (Lead Detail's HISTORY block).

    Written only when a new result's `place_key` matches an earlier result's
    (any job) and a tracked field differs -- see workers.tasks.record_history.
    Never backfilled for rows scraped before `place_key` existed.
    """

    __tablename__ = "result_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("results.id"), index=True)
    field: Mapped[str] = mapped_column(String(40))
    old_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
