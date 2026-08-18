"""Proxies screen endpoints: DB-backed pool CRUD + real actions.

GET    /api/proxies              -> list, with computed health stats
GET    /api/proxies/stats        -> pool health strip (stat tiles)
POST   /api/proxies              -> add one
POST   /api/proxies/bulk         -> add many (paste/upload)
POST   /api/proxies/{id}/test    -> one-off connectivity check (real HTTP request through it)
POST   /api/proxies/{id}/disable -> exclude from rotation
POST   /api/proxies/{id}/drain   -> exclude from rotation, status=retired (see Proxy model
                                     docstring on why this isn't behaviorally different from
                                     disable -- no in-flight-lease tracking exists to make
                                     drain wait for anything)
DELETE /api/proxies/{id}         -> remove
"""

import time
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app_db, get_current_user
from app.db.models.proxy import Proxy
from app.db.models.user import User
from app.scraping.proxy.store import record_proxy_outcome

router = APIRouter()

# A cheap, fast-answering endpoint to prove a proxy can actually reach the
# open internet -- not a Maps/Bing request, since the point is "does this
# proxy work at all", not "is this proxy currently unblocked on Google".
TEST_URL = "https://httpbin.org/ip"
TEST_TIMEOUT_S = 10.0


class CreateProxyRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    protocol: str = Field(default="http", pattern="^(http|https|socks5)$")
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=100)


class BulkProxyRequest(BaseModel):
    """One entry per line looks like `host:port` or `user:pass@host:port`,
    already split into that shape by the client -- see BulkEntry."""

    entries: list["BulkEntry"] = Field(min_length=1, max_length=2000)


class BulkEntry(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    protocol: str = Field(default="http", pattern="^(http|https|socks5)$")
    username: str | None = None
    password: str | None = None
    country: str | None = None


BulkProxyRequest.model_rebuild()


@router.get("/")
def list_proxies(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> list[dict]:
    proxies = db.execute(select(Proxy).order_by(Proxy.created_at)).scalars().all()
    return [_proxy_dict(p) for p in proxies]


@router.get("/stats")
def get_proxy_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """The pool health strip's stat tiles -- computed from the same rows
    `list_proxies` returns, not a separately-maintained summary, so the tiles
    and the table can never disagree (SCREENLIST.md §13's "Major" bug)."""
    proxies = db.execute(select(Proxy)).scalars().all()

    healthy = sum(1 for p in proxies if p.status == "active")
    cooling = sum(1 for p in proxies if p.status == "cooling")
    retired = sum(1 for p in proxies if p.status in ("disabled", "retired"))

    latencies = [p.avg_latency_ms for p in proxies if p.avg_latency_ms is not None]
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else None

    total_uses = sum(p.total_uses for p in proxies)
    total_blocks = sum(p.block_count for p in proxies)
    block_rate = round(100 * total_blocks / total_uses, 1) if total_uses else None

    return {
        "healthy": healthy,
        "cooling": cooling,
        "retired": retired,
        "avgLatencyMs": avg_latency,
        "blockRatePct": block_rate,
        "total": len(proxies),
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_proxy(
    payload: CreateProxyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    existing = db.execute(
        select(Proxy).where(Proxy.host == payload.host, Proxy.port == payload.port)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="proxy already in the pool")

    proxy = Proxy(
        host=payload.host, port=payload.port, protocol=payload.protocol,
        username=payload.username, password=payload.password, country=payload.country,
    )
    db.add(proxy)
    db.commit()
    return _proxy_dict(proxy)


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def bulk_create_proxies(
    payload: BulkProxyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    existing_pairs = {
        (host, port) for host, port in db.execute(select(Proxy.host, Proxy.port)).all()
    }

    created = 0
    skipped = 0
    for entry in payload.entries:
        if (entry.host, entry.port) in existing_pairs:
            skipped += 1
            continue
        existing_pairs.add((entry.host, entry.port))
        db.add(Proxy(
            host=entry.host, port=entry.port, protocol=entry.protocol,
            username=entry.username, password=entry.password, country=entry.country,
        ))
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped}


@router.post("/{proxy_id}/test")
def test_proxy(
    proxy_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Real one-off connectivity check -- an HTTP request through the proxy
    to a cheap, fast-answering URL, not a Maps/Bing page. Recorded as an
    outcome on the row like any other use, so a manual test contributes to
    (and can trigger) the same auto-cooldown as a real scrape would."""
    proxy = _get_proxy(db, proxy_id)

    started = time.monotonic()
    try:
        response = httpx.get(
            TEST_URL,
            proxy=proxy.url(),
            timeout=TEST_TIMEOUT_S,
        )
        response.raise_for_status()
        ok = True
        detail = f"{response.status_code}"
    except httpx.HTTPError as exc:
        ok = False
        detail = str(exc)[:300]
    latency_ms = int((time.monotonic() - started) * 1000)

    record_proxy_outcome(
        db, proxy.host, proxy.port, "success" if ok else "failure",
        latency_ms=latency_ms, consecutive_blocks={},
    )
    db.refresh(proxy)

    return {"ok": ok, "detail": detail, "latencyMs": latency_ms, "proxy": _proxy_dict(proxy)}


@router.post("/{proxy_id}/disable")
def disable_proxy(
    proxy_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    proxy = _get_proxy(db, proxy_id)
    proxy.status = "disabled"
    proxy.cooling_until = None
    db.commit()
    return _proxy_dict(proxy)


@router.post("/{proxy_id}/drain")
def drain_proxy(
    proxy_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Retires the proxy immediately -- see the module docstring on why this
    doesn't (and honestly can't yet) wait for in-flight leases first."""
    proxy = _get_proxy(db, proxy_id)
    proxy.status = "retired"
    proxy.cooling_until = None
    db.commit()
    return _proxy_dict(proxy)


@router.delete("/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_proxy(
    proxy_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> None:
    proxy = _get_proxy(db, proxy_id)
    db.delete(proxy)
    db.commit()


def _get_proxy(db: Session, proxy_id: str) -> Proxy:
    try:
        proxy_uuid = uuid.UUID(proxy_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid proxy id"
        ) from exc

    proxy = db.get(Proxy, proxy_uuid)
    if proxy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="proxy not found")
    return proxy


def _proxy_dict(proxy: Proxy) -> dict:
    return {
        "id": str(proxy.id),
        "host": proxy.host,
        "port": proxy.port,
        "protocol": proxy.protocol,
        "country": proxy.country,
        "status": proxy.status,
        "successCount": proxy.success_count,
        "failureCount": proxy.failure_count,
        "blockCount": proxy.block_count,
        "totalUses": proxy.total_uses,
        "successRate": proxy.success_rate,
        "blockRate": proxy.block_rate,
        "avgLatencyMs": proxy.avg_latency_ms,
        "coolingUntil": proxy.cooling_until.isoformat() if proxy.cooling_until else None,
        "lastUsedAt": proxy.last_used_at.isoformat() if proxy.last_used_at else None,
        "createdAt": proxy.created_at.isoformat(),
    }
