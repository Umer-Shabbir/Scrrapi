"""System Health endpoints (SCREENLIST.md §19). Read-only infrastructure
introspection -- no new table, nothing persisted, every number is a live
check made at request time.

GET /api/system         -> component status, queue depth, worker table, geo seed
                            counts, version block
WS  /api/system/events/stream -> live cross-job event feed for the Dashboard's
                            log panel (see app.core.events' module docstring)

Figma's mock also shows BROWSER POOL and OBJECT STORE tiles and a RUN SEED
button. This app has neither a persistent browser pool (Playwright launches
a fresh Chromium per scrape task -- see app.scraping.*.feed/place) nor an
object store (exports write to local disk, no S3/blob client anywhere), so
those two tiles are omitted rather than faked. RUN SEED is omitted too:
scripts/seed_geo.py is a multi-minute, ~35MB-download, truncate-and-replace
job with no API-triggerable wrapper -- wiring that as a one-click background
task is real scope beyond this screen (see that script's own docstring).
Geo seed counts are still real, read live from the geo DB.
"""

import asyncio
from contextlib import suppress
from datetime import datetime
from importlib.metadata import version as pkg_version

import redis
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import authenticate_ws_token, get_app_db, get_current_user, get_geo_db
from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.events import STREAM_START, read_global_events
from app.db.models.geo import City, Country, Region, ZipCode
from app.db.models.job import Job, JobTarget
from app.db.models.user import User
from app.workers.dispatch import count_waiting

router = APIRouter()
settings = get_settings()

# Mirrors FastAPI(version=...) in app.main -- duplicated as a literal rather
# than imported from there to avoid a circular import (main imports this
# router). Keep the two in sync if the API version changes.
_API_VERSION = "0.1.0"


def _ping_app_db(db: Session) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "up"}
    except Exception as exc:  # noqa: BLE001 -- health check must never 500 the page
        return {"status": "down", "error": str(exc)[:300]}


def _ping_geo_db(geo_db: Session) -> dict:
    try:
        geo_db.execute(text("SELECT 1"))
        return {"status": "up"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "down", "error": str(exc)[:300]}


def _ping_redis() -> dict:
    try:
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        client.ping()
        return {"status": "up"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "down", "error": str(exc)[:300]}


def _celery_worker_stats() -> tuple[dict, list[dict]]:
    """Returns (component status dict, per-worker rows) from Celery's real
    control-plane inspect API -- not simulated. A worker that doesn't answer
    the ping within Celery's own timeout is absent from the response, which
    is exactly the "unresponsive" case the Figma copy describes; there's no
    separate uptime/uptime-since field Celery exposes over this API, so rows
    report active task count and the last successful inspect as their
    heartbeat rather than a fabricated uptime clock."""
    try:
        # `stats()` and `active()` are each a separate broadcast round-trip,
        # so a stale/no-worker case pays this timeout twice -- kept short
        # (this is a page health-check, not a critical operation) so a
        # worst-case "nobody answered" still renders the page in ~1s, not
        # several seconds of visible loading.
        inspect = celery_app.control.inspect(timeout=0.5)
        stats = inspect.stats() or {}
        active = inspect.active() or {}
    except Exception as exc:  # noqa: BLE001
        return {"status": "down", "error": str(exc)[:300]}, []

    if not stats:
        return {"status": "down", "error": "no workers responded"}, []

    rows = []
    now = datetime.utcnow()
    for hostname in stats:
        rows.append(
            {
                "hostname": hostname,
                "activeTasks": len(active.get(hostname, [])),
                "lastHeartbeat": now.isoformat(),
                "online": True,
            }
        )
    return {"status": "up"}, rows


@router.get("/")
def system_health(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
    geo_db: Session = Depends(get_geo_db),
) -> dict:
    celery_status, workers = _celery_worker_stats()

    components = {
        "api": {"status": "up"},  # answering this request is the check
        "appDb": _ping_app_db(db),
        "geoDb": _ping_geo_db(geo_db),
        "redis": _ping_redis(),
        "celeryWorkers": celery_status,
    }

    # QUEUED: every target sitting in "queued" status, whether or not it has
    # been handed to the broker yet -- the umbrella count. DISPATCHED narrows
    # that to the ones already on the broker (dispatched_at set); WAITING
    # narrows it to the ones that aren't (count_waiting, also excludes
    # paused/cancelled jobs -- see app.workers.dispatch's docstring for why).
    queued = (
        db.scalar(select(func.count()).select_from(JobTarget).where(JobTarget.status == "queued"))
        or 0
    )
    dispatched = (
        db.scalar(
            select(func.count())
            .select_from(JobTarget)
            .where(JobTarget.status == "queued", JobTarget.dispatched_at.is_not(None))
        )
        or 0
    )
    running = (
        db.scalar(select(func.count()).select_from(JobTarget).where(JobTarget.status == "running"))
        or 0
    )
    waiting = count_waiting(db)

    geo_seed = {
        "countries": geo_db.scalar(select(func.count()).select_from(Country)) or 0,
        "states": geo_db.scalar(select(func.count()).select_from(Region)) or 0,
        "cities": geo_db.scalar(select(func.count()).select_from(City)) or 0,
        "postalCodes": geo_db.scalar(select(func.count()).select_from(ZipCode)) or 0,
    }

    return {
        "components": components,
        "queueDepth": {
            "queued": queued,
            "dispatched": dispatched,
            "running": running,
            "waiting": waiting,
        },
        "workers": workers,
        "geoSeed": geo_seed,
        "version": {
            "api": _API_VERSION,
            "playwright": pkg_version("playwright"),
        },
    }


@router.websocket("/events/stream")
async def system_events_stream(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_app_db),
) -> None:
    """Live event feed for the Dashboard's log panel -- every job *this user*
    can see, merged into one stream.

    Same token-in-query-param auth as `WS /api/jobs/{id}/stream` (see that
    endpoint's docstring for why). "Cross-job" does not mean "cross-user":
    `GET /api/jobs` scopes the job list to `Job.created_by == user.id` (Team &
    Roles is one shared workspace with per-user job ownership, not separate
    tenants -- see User.role's column comment), so a viewer/operator who
    can't see another user's job in their own list must not see it here
    either. The underlying Redis stream has no such filter (`publish_job_event`
    mirrors every job unconditionally, cheaply, from deep inside scraping code
    that has no user in scope) -- so it's applied here instead, against a set
    of owned job ids re-read periodically rather than once at connect, so a job
    created after the socket opens still shows up without a reconnect.
    """
    try:
        user = authenticate_ws_token(db, token)
    except HTTPException as exc:
        await websocket.close(code=1008, reason=str(exc.detail))
        return

    await websocket.accept()

    last_event_id = STREAM_START
    owned_job_ids: set[str] = set()
    polls_since_refresh = 0
    # Re-querying every poll would be one extra indexed query per tick per open
    # socket -- cheap, but pointless when a user's job set changes at "creates
    # a job" cadence, not "every 2 seconds". Refreshed every 5th poll instead.
    REFRESH_EVERY_N_POLLS = 5
    try:
        while True:
            if polls_since_refresh == 0:
                db.expire_all()
                owned_job_ids = {
                    str(job_id)
                    for job_id in db.execute(
                        select(Job.id).where(Job.created_by == user.id)
                    ).scalars()
                }
            polls_since_refresh = (polls_since_refresh + 1) % REFRESH_EVERY_N_POLLS

            events, last_event_id = await read_global_events(last_event_id)
            for event in events:
                if event.get("jobId") in owned_job_ids:
                    await websocket.send_json(event)
            await asyncio.sleep(settings.job_stream_poll_interval_s)
    except WebSocketDisconnect:
        return

    with suppress(RuntimeError):
        await websocket.close()
