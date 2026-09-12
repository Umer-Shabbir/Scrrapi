"""Live per-job activity events, carried on a Redis stream.

The job WebSocket used to send `{status, resultsCount}` and nothing else, so the
UI could tell you a number was going up but never what the scraper was actually
doing. This module is the other half: every interesting step a worker takes
(feed scrolled, place opened, fields extracted, row written, retry scheduled) is
appended to `job:<job_id>:events` as one JSON blob, and the WebSocket replays
that stream to the browser as it grows.

Redis streams rather than pub/sub on purpose -- a browser that connects a second
after the job starts, or reconnects after a refresh, still gets the backlog
instead of only whatever happens to be published while it's listening. The
stream is capped (`MAX_EVENTS`) and expires (`EVENT_TTL_S`), so this stays a
live activity feed, not a second copy of the results table.

Publishing is best-effort: a Redis hiccup must never fail a scrape that
otherwise worked, so every call swallows `RedisError` and logs at debug.

`publish_job_event` also mirrors every event onto one global stream
(`GLOBAL_STREAM_KEY`) -- the Dashboard's log panel reads that one instead of
having to fan out a subscription per job. Same event shape plus `jobId`, so one
line of code at the existing 18 call sites didn't need to change.
"""

import json
import logging
from functools import lru_cache
from typing import Any

import redis
import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Roughly a job's worth of activity at one line per place; older entries are
# trimmed as new ones arrive.
MAX_EVENTS = 2000
EVENT_TTL_S = 6 * 3600

# The Dashboard's log panel is a cross-job live view, not an audit trail --
# capped smaller and shorter-lived than a single job's own stream, since it's
# read continuously while the app is open rather than backfilled once per job.
GLOBAL_STREAM_KEY = "global:events"
MAX_GLOBAL_EVENTS = 500
GLOBAL_EVENT_TTL_S = 3600

# Entry id meaning "everything from the start of the stream" in XREAD terms.
STREAM_START = "0-0"


def stream_key(job_id: str) -> str:
    return f"job:{job_id}:events"


@lru_cache
def _sync_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


@lru_cache
def _async_client() -> aioredis.Redis:
    return aioredis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def publish_job_event(job_id: str, event_type: str, **fields: Any) -> None:
    """Append one activity event to a job's stream (worker side, synchronous).

    `event_type` is the discriminator the UI switches on; everything else rides
    along as free-form fields. Never raises.
    """
    payload = {"type": event_type, **{k: v for k, v in fields.items() if v is not None}}
    key = stream_key(job_id)
    try:
        client = _sync_client()
        client.xadd(
            key, {"payload": json.dumps(payload, default=str)}, maxlen=MAX_EVENTS, approximate=True
        )
        client.expire(key, EVENT_TTL_S)
        client.xadd(
            GLOBAL_STREAM_KEY,
            {"payload": json.dumps({"jobId": job_id, **payload}, default=str)},
            maxlen=MAX_GLOBAL_EVENTS,
            approximate=True,
        )
        client.expire(GLOBAL_STREAM_KEY, GLOBAL_EVENT_TTL_S)
    except redis.RedisError:
        logger.debug("could not publish job event", exc_info=True)


async def read_global_events(
    last_id: str = STREAM_START, *, count: int = 200
) -> tuple[list[dict], str]:
    """Read cross-job events after `last_id` (API side, async). Same contract
    as `read_job_events`: never raises, returns `last_id` unchanged when
    there's nothing new."""
    try:
        response = await _async_client().xread({GLOBAL_STREAM_KEY: last_id}, count=count)
    except redis.RedisError:
        logger.debug("could not read global events", exc_info=True)
        return [], last_id

    events: list[dict] = []
    cursor = last_id
    for _key, entries in response:
        for entry_id, data in entries:
            cursor = entry_id
            try:
                events.append(json.loads(data["payload"]))
            except (KeyError, ValueError):
                continue
    return events, cursor


async def read_job_events(
    job_id: str, last_id: str = STREAM_START, *, count: int = 200
) -> tuple[list[dict], str]:
    """Read events appended after `last_id` (API side, async).

    Returns the decoded events and the id to pass as `last_id` next time --
    unchanged when there was nothing new, so a caller can just keep handing it
    back. Never raises; a Redis error reads as "no new events".
    """
    try:
        response = await _async_client().xread({stream_key(job_id): last_id}, count=count)
    except redis.RedisError:
        logger.debug("could not read job events", exc_info=True)
        return [], last_id

    events: list[dict] = []
    cursor = last_id
    for _key, entries in response:
        for entry_id, data in entries:
            cursor = entry_id
            try:
                events.append(json.loads(data["payload"]))
            except (KeyError, ValueError):
                continue
    return events, cursor
