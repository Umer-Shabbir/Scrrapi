"""Geo cascade endpoints, backed by the geo reference DB (GeoNames-seeded).

GET /api/geo/countries?q=                   -- every country on earth
GET /api/geo/regions?country=<id>&q=
GET /api/geo/cities?region=<id>&q=
GET /api/geo/zips?city=<id>&q=              -- one city's postal codes
GET /api/geo/zips?region=<id>&q=            -- every postal code in the state

Seeded worldwide this is ~250 countries, ~4k regions, ~1.1M cities and ~1.8M
postal codes, so every level takes a `q=` search term and every level is
capped. The pickers query as you type rather than rendering an option list.

Matching is "starts with, then contains", ranked in that order: typing `aus`
puts Austin above Fort Augustus, while `york` still finds New York. Both sides
go through `geo_norm()` (lowercase + strip accents), so `sao` finds "São Paulo"
and `munchen` finds "München" — outside English, expecting people to type the
diacritics makes the picker unusable. Both halves are index-assisted
(`c93f5a08d1e7`); an unindexed contains-match here is a sequential scan of every
city on earth on every keystroke.
"""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, literal, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_geo_db
from app.core.config import get_settings
from app.db.models.geo import City, Country, Region, ZipCode

router = APIRouter()
settings = get_settings()

# Below this a search term matches too much to be worth narrowing on -- "a"
# would rank a hundred thousand cities. The picker just shows the head of the
# list until the second character arrives.
MIN_SEARCH_LEN = 2

# There are ~250 countries and that is not going to change much, so the country
# list is exempt from the shared page cap -- it ships whole and the picker
# filters it locally. Every other level is large enough to need the server.
COUNTRY_LIMIT = 500


def _parse_uuid(raw: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid {field_name} id",
        ) from exc


def _clean(q: str | None) -> str:
    """Trimmed search term, or "" when it's too short to narrow anything.

    LIKE wildcards in user input are escaped: a stray `%` would otherwise turn
    a two-character term into a full scan.
    """
    term = (q or "").strip()
    if len(term) < MIN_SEARCH_LEN:
        return ""
    return term.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def _name_search(stmt: Select, column, term: str) -> Select:
    """Filter to names starting with or containing `term`, prefix hits first.

    Both sides are normalized by `geo_norm` (the migration's lowercase +
    unaccent), never by Python: doing the folding in SQL is what guarantees the
    predicate matches the expression the indexes were built on. Fold it here
    instead and every query silently falls back to a sequential scan.
    """
    if not term:
        return stmt.order_by(column)
    name = func.geo_norm(column)
    needle = func.geo_norm(term)
    starts = name.like(needle.concat("%"), escape="\\")
    contains = name.like(literal("%").concat(needle).concat("%"), escape="\\")
    return stmt.where(or_(starts, contains)).order_by(starts.desc(), column)


def _cap(limit: int | None) -> int:
    return min(limit or settings.geo_page_limit, settings.geo_page_limit)


@router.get("/countries")
def list_countries(
    db: Session = Depends(get_geo_db),
    q: str | None = None,
    limit: int | None = Query(None, ge=1),
) -> list[dict]:
    """Every country, unpaginated by default — ~250 rows is one small response
    the picker can filter client-side without a round trip per keystroke."""
    stmt = _name_search(select(Country), Country.name, _clean(q))
    rows = db.execute(stmt.limit(min(limit or COUNTRY_LIMIT, COUNTRY_LIMIT))).scalars().all()
    return [{"id": str(c.id), "name": c.name, "code": c.code} for c in rows]


@router.get("/regions")
def list_regions(
    country: str,
    db: Session = Depends(get_geo_db),
    q: str | None = None,
    limit: int | None = Query(None, ge=1),
) -> list[dict]:
    stmt = select(Region).where(Region.country_id == _parse_uuid(country, "country"))
    stmt = _name_search(stmt, Region.name, _clean(q)).limit(_cap(limit))
    rows = db.execute(stmt).scalars().all()
    return [{"id": str(r.id), "name": r.name} for r in rows]


@router.get("/cities")
def list_cities(
    region: str,
    db: Session = Depends(get_geo_db),
    q: str | None = None,
    limit: int | None = Query(None, ge=1),
) -> dict:
    """Cities in one region. An envelope rather than a bare list: a large region
    holds tens of thousands, so the picker has to be able to say "keep typing"
    instead of implying the capped slice is everything.

    `regionHasZips` is what decides which mode the picker runs in. Roughly half
    the world's countries have no postal code system at all, and there is no
    source that invents one; where there are none, these cities *are* the search
    areas and the picker multi-selects them exactly as it would ZIPs.
    """
    region_id = _parse_uuid(region, "region")
    base = select(City).where(City.region_id == region_id)
    matched = _name_search(base, City.name, _clean(q))
    total = db.scalar(select(func.count()).select_from(matched.subquery())) or 0
    cap = _cap(limit)
    rows = db.execute(matched.limit(cap)).scalars().all()

    # EXISTS, not a count: some regions hold six figures of postal codes and the
    # picker only needs to know whether the number is zero.
    has_zips = db.scalar(
        select(
            select(ZipCode.id)
            .join(City, City.id == ZipCode.city_id)
            .where(City.region_id == region_id)
            .exists()
        )
    )

    return {
        "items": [{"id": str(c.id), "name": c.name} for c in rows],
        "total": total,
        "truncated": total > len(rows),
        "regionHasZips": bool(has_zips),
    }


@router.get("/zips")
def list_zips(
    db: Session = Depends(get_geo_db),
    city: str | None = None,
    region: str | None = None,
    q: str | None = Query(None, description="prefix filter on the postal code"),
    limit: int | None = Query(None, ge=1),
) -> dict:
    """Postal codes for one city, or for every city in a region.

    Envelope, like `/cities`, and for a sharper reason: the caller needs to know
    when it is looking at a capped slice, because "select all" over a silently
    truncated list would queue a subset of the ZIPs the user asked for.

    Each row carries its city name. A region-wide list spans many cities, and
    the label a target is built from ("78701, Austin, Texas") needs the city
    that particular code belongs to, not the one currently selected in the UI.
    """
    if (city is None) == (region is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="pass exactly one of city or region",
        )

    base = select(ZipCode, City.name).join(City, City.id == ZipCode.city_id)
    if city is not None:
        base = base.where(ZipCode.city_id == _parse_uuid(city, "city"))
    else:
        base = base.where(City.region_id == _parse_uuid(region, "region"))

    # Postal codes are short and structured, so a prefix match is the whole of
    # what "search" means here -- no contains half, no minimum length.
    term = (q or "").strip()
    if term:
        base = base.where(ZipCode.code.startswith(term))

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    cap = min(limit or settings.geo_zip_page_limit, settings.geo_zip_page_limit)
    rows = db.execute(base.order_by(City.name, ZipCode.code).limit(cap)).all()

    return {
        "items": [
            {"id": str(z.id), "name": z.code, "cityName": city_name} for z, city_name in rows
        ],
        "total": total,
        "truncated": total > len(rows),
    }


@router.get("/radius")
def search_radius(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(..., gt=0, le=1000),
    type: str = Query("zip", description="zip or city"),
    db: Session = Depends(get_geo_db),
    limit: int | None = Query(None, ge=1),
) -> dict:
    """Find cities or ZIPs within a Haversine radius."""
    if type not in ("zip", "city"):
        raise HTTPException(status_code=422, detail="type must be zip or city")

    model = ZipCode if type == "zip" else City

    # Approximation for bounding box
    lat_deg = radius_km / 111.0
    # Add a small buffer for longitude approximation issues
    cos_lat = math.cos(math.radians(lat))
    lon_deg = (radius_km / (111.0 * cos_lat)) if cos_lat > 0.01 else 180.0

    min_lat, max_lat = lat - lat_deg, lat + lat_deg
    min_lon, max_lon = lon - lon_deg, lon + lon_deg

    distance_expr = 6371.0 * func.acos(
        # Use case to prevent domain errors in acos if math precision issues cause >1 values
        func.least(
            1.0,
            func.greatest(
                -1.0,
                func.cos(func.radians(lat))
                * func.cos(func.radians(model.latitude))
                * func.cos(func.radians(model.longitude) - func.radians(lon))
                + func.sin(func.radians(lat)) * func.sin(func.radians(model.latitude)),
            ),
        )
    )

    base = select(model)
    if type == "zip":
        base = base.join(City, City.id == ZipCode.city_id).add_columns(
            City.name, distance_expr.label("dist")
        )
    else:
        base = base.add_columns(model.name, distance_expr.label("dist"))

    base = base.where(model.latitude.is_not(None), model.longitude.is_not(None))
    base = base.where(model.latitude.between(min_lat, max_lat))

    if min_lon < -180:
        base = base.where(or_(model.longitude >= (min_lon + 360), model.longitude <= max_lon))
    elif max_lon > 180:
        base = base.where(or_(model.longitude >= min_lon, model.longitude <= (max_lon - 360)))
    else:
        base = base.where(model.longitude.between(min_lon, max_lon))

    base = base.where(distance_expr <= radius_km)

    cap = _cap(limit)
    rows = db.execute(base.order_by(distance_expr).limit(cap)).all()

    # We want truncation checks? With complex spatial queries it's hard to count cheaply.
    # Radius bounds usually expect the exact items, no complex pagination yet.
    # We'll just return items.

    items = []
    if type == "zip":
        for z, city_name, dist in rows:
            items.append(
                {
                    "id": str(z.id),
                    "name": z.code,
                    "cityName": city_name,
                    "distanceKm": dist,
                    "latitude": z.latitude,
                    "longitude": z.longitude,
                }
            )
    else:
        for c, _name_ign, dist in rows:
            items.append(
                {
                    "id": str(c.id),
                    "name": c.name,
                    "distanceKm": dist,
                    "latitude": c.latitude,
                    "longitude": c.longitude,
                }
            )

    return {
        "items": items,
        "total": len(items),
        "truncated": len(items) == cap,
    }


@router.get("/bounds")
def search_bounds(
    min_lat: float = Query(..., ge=-90, le=90),
    max_lat: float = Query(..., ge=-90, le=90),
    min_lon: float = Query(..., ge=-180, le=180),
    max_lon: float = Query(..., ge=-180, le=180),
    type: str = Query("zip", description="zip or city"),
    db: Session = Depends(get_geo_db),
    limit: int | None = Query(None, ge=1),
) -> dict:
    """Find cities or ZIPs within a geographic bounding box."""
    if type not in ("zip", "city"):
        raise HTTPException(status_code=422, detail="type must be zip or city")

    model = ZipCode if type == "zip" else City

    base = select(model)
    if type == "zip":
        base = base.join(City, City.id == ZipCode.city_id).add_columns(City.name)
    else:
        base = base.add_columns(model.name)

    base = base.where(model.latitude.is_not(None), model.longitude.is_not(None))
    base = base.where(model.latitude.between(min_lat, max_lat))

    # Handle antimeridian crossing
    if min_lon > max_lon:
        base = base.where(or_(model.longitude >= min_lon, model.longitude <= max_lon))
    else:
        base = base.where(model.longitude.between(min_lon, max_lon))

    cap = _cap(limit)
    rows = db.execute(base.limit(cap)).all()

    items = []
    if type == "zip":
        for z, city_name in rows:
            items.append(
                {
                    "id": str(z.id),
                    "name": z.code,
                    "cityName": city_name,
                    "latitude": z.latitude,
                    "longitude": z.longitude,
                }
            )
    else:
        for c, _name_ign in rows:
            items.append(
                {
                    "id": str(c.id),
                    "name": c.name,
                    "latitude": c.latitude,
                    "longitude": c.longitude,
                }
            )

    return {
        "items": items,
        "total": len(items),
        "truncated": len(items) == cap,
    }
