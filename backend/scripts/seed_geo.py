"""GeoNames seed script — populates the geo DB's country/region/city/zip_code
tables so the location pickers cover the whole world.

Four source files, because no single GeoNames export has all four levels:

- `dump/countryInfo.txt`      -> every country on earth (~250), ISO code + name
- `dump/admin1CodesASCII.txt` -> every first-level division (~3900): US states,
                                 German Bundesländer, Japanese prefectures ...
- `zip/allCountries.zip`      -> postal codes and the towns they belong to, for
                                 the 121 countries GeoNames has postal data for
- `dump/cities500.zip`        -> ~235k populated places down to villages and
                                 neighbourhoods, for everywhere else

About that last one. Roughly half the world's countries have no postal code
system at all — the UPU lists Hong Kong, Ghana, Qatar, Panama and many more —
so no source can supply ZIPs for them, and the ones that do have a system
(Nigeria, Tanzania) are not in any free bulk dataset. What the ZIP is actually
*for* here is partitioning a city into pieces small enough that Google Maps'
~120-results-per-query ceiling stops binding, and a place list does that just as
well: Lagos State comes out as 33 searchable areas (Agege, Ikeja, Ikoyi, Apapa,
Festac Town ...) instead of one query for "Lagos". So those countries get areas
rather than postal codes, and the picker switches mode accordingly.

`cities500` rather than `cities15000` (the previous choice) because a 15k-people
floor only yields whole towns — too coarse to partition a city at all. It also
supplies the real city names that `CityResolver` folds postal localities onto:
Pakistan's postal export names the post office, not the town, so without that
step Lahore appears as thirty one-ZIP "cities" rather than one city with thirty
postal codes.

Row identity is a deterministic uuid5 of the natural key, not uuid4. That is
what keeps this memory-bounded at world scale: a child row can compute its
parent's id from the same key rather than holding a 900k-entry map of them.
It also makes ids stable across re-seeds, so a saved location queue in someone's
browser still points at real rows after the data is refreshed.

Idempotent via truncate-first: every run replaces the four tables' contents
wholesale with whatever was just downloaded, so re-running never double-inserts
and never leaves stale rows from a previous subset.

Usage:
    python scripts/seed_geo.py                       # the whole world (default)
    python scripts/seed_geo.py --countries US,CA,GB  # just these (fast, for dev)
    python scripts/seed_geo.py --no-places           # skip the populated-places fill-in
    python scripts/seed_geo.py --cache-dir tmp/geonames

The whole world is ~35MB of downloads and a few minutes of load. Files are
cached in `--cache-dir`, so a second run with a different flag re-parses rather
than re-downloads. `npm run seed` calls this with no arguments.
"""

from __future__ import annotations

import argparse
import csv
import io
import math
import sys
import uuid
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path

import httpx
from sqlalchemy import text

from app.db.session import GeoSessionLocal

ZIP_EXPORT_URL = "https://download.geonames.org/export/zip/{code}.zip"
ALL_COUNTRIES_ZIP_URL = "https://download.geonames.org/export/zip/allCountries.zip"
COUNTRY_INFO_URL = "https://download.geonames.org/export/dump/countryInfo.txt"
ADMIN1_URL = "https://download.geonames.org/export/dump/admin1CodesASCII.txt"
PLACES_URL = "https://download.geonames.org/export/dump/cities500.zip"
PLACES_FILE = "cities500"

# uuid5 namespace for this dataset. Fixed forever -- changing it renumbers every
# row and orphans any id already saved in a browser's location queue.
GEO_NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

ZIP_COLUMNS = [
    "country_code",
    "postal_code",
    "place_name",
    "admin_name1",
    "admin_code1",
    "admin_name2",
    "admin_code2",
    "admin_name3",
    "admin_code3",
    "latitude",
    "longitude",
    "accuracy",
]

# cities500.txt is the geoname dump layout; only these three columns matter here.
CITY_DUMP_COUNTRY_CODE = 8
CITY_DUMP_NAME = 1
CITY_DUMP_ADMIN1 = 10
CITY_DUMP_LAT = 4
CITY_DUMP_LON = 5

UNKNOWN_REGION = "Unknown"
COPY_BATCH = 50_000


# --------------------------------------------------------------------------
# ids
# --------------------------------------------------------------------------
# Every level's key includes its parents', so "Springfield" in Illinois and
# "Springfield" in Missouri are different cities, and the same town reached from
# the postal file and from the places file collapses onto one row.


def country_id(code: str) -> uuid.UUID:
    return uuid.uuid5(GEO_NS, f"country:{code}")


def region_id(code: str, region_key: str) -> uuid.UUID:
    return uuid.uuid5(GEO_NS, f"region:{code}:{region_key}")


def city_id(code: str, region_key: str, city: str) -> uuid.UUID:
    return uuid.uuid5(GEO_NS, f"city:{code}:{region_key}:{city}")


def zip_id(code: str, region_key: str, city: str, postal: str) -> uuid.UUID:
    return uuid.uuid5(GEO_NS, f"zip:{code}:{region_key}:{city}:{postal}")


def region_key_for(admin_code1: str, admin_name1: str) -> str:
    """Stable key for a first-level division.

    The admin1 code (`TX`, `13`) is preferred because the postal export and
    admin1CodesASCII agree on it while their display names sometimes differ
    ("Texas" vs "Texas State"); keying on the name would split one state into
    two rows. Falls back to the name where a country has no admin codes.
    """
    return (admin_code1 or "").strip() or (admin_name1 or "").strip() or UNKNOWN_REGION


# --------------------------------------------------------------------------
# downloads
# --------------------------------------------------------------------------


def _cache_path(cache_dir: Path, name: str) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / name


def _download(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    print(f"  downloading {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length") or 0)
        done = 0
        with tmp.open("wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
                done += len(chunk)
                if total:
                    pct = done * 100 // total
                    print(f"\r    {pct:3d}%  {done / 1e6:.1f} MB", end="", flush=True)
        if total:
            print()
    # Rename only once the body is complete, so an interrupted download is not
    # cached as if it were the real file.
    tmp.replace(dest)
    return dest


def _tsv_rows(path: Path) -> Iterator[list[str]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            yield line.rstrip("\n").split("\t")


def _zip_member_rows(zip_path: Path, inner_name: str) -> Iterator[list[str]]:
    with zipfile.ZipFile(zip_path) as zf, zf.open(inner_name) as raw:
        yield from csv.reader(io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t")


# --------------------------------------------------------------------------
# sources
# --------------------------------------------------------------------------


def fetch_countries(cache_dir: Path) -> dict[str, str]:
    """ISO code -> country name, for every country GeoNames knows.

    This is the whole country list, not just the ones with postal data, so the
    Country dropdown covers the world even where the ZIP level is empty.
    """
    dest = _cache_path(cache_dir, "countryInfo.txt")
    try:
        _download(COUNTRY_INFO_URL, dest)
    except httpx.HTTPError as exc:
        print(f"  warn: countryInfo.txt unavailable ({exc}); names fall back to ISO codes")
        return {}
    return {p[0]: p[4] for p in _tsv_rows(dest) if len(p) >= 5 and p[0] and p[4]}


def fetch_admin1(cache_dir: Path) -> dict[tuple[str, str], str]:
    """(country_code, admin1_code) -> region name, worldwide.

    Gives every country its states/provinces up front, including the ones whose
    postal data would otherwise never mention them.
    """
    dest = _cache_path(cache_dir, "admin1CodesASCII.txt")
    try:
        _download(ADMIN1_URL, dest)
    except httpx.HTTPError as exc:
        print(f"  warn: admin1CodesASCII.txt unavailable ({exc}); regions from postal data only")
        return {}

    out: dict[tuple[str, str], str] = {}
    for parts in _tsv_rows(dest):
        if len(parts) < 2 or "." not in parts[0]:
            continue
        code, admin1 = parts[0].split(".", 1)
        name = parts[1].strip()
        if code and admin1 and name:
            out[(code, admin1)] = name
    return out


def postal_rows(cache_dir: Path, countries: list[str] | None) -> Iterator[dict]:
    """Postal-code rows for the requested countries, or the whole world."""
    if countries is None:
        dest = _cache_path(cache_dir, "allCountries.zip")
        _download(ALL_COUNTRIES_ZIP_URL, dest)
        sources = [(dest, "allCountries.txt")]
    else:
        sources = []
        for code in countries:
            dest = _cache_path(cache_dir, f"{code}.zip")
            _download(ZIP_EXPORT_URL.format(code=code), dest)
            sources.append((dest, f"{code}.txt"))

    for zip_path, inner in sources:
        for row in _zip_member_rows(zip_path, inner):
            if len(row) >= 11:
                yield dict(zip(ZIP_COLUMNS, row, strict=False))


def populated_place_rows(cache_dir: Path) -> Iterator[tuple[str, str, str, float, float]]:
    """(country_code, admin1_code, place_name, lat, lon) for every place of 500+.

    Villages and city neighbourhoods, not just whole towns — this is the search
    partition wherever postal codes don't exist, so it has to be fine enough
    that one entry is a sensible Maps query on its own. It is also the list of
    real city names that `CityResolver` anchors postal localities to.
    """
    dest = _cache_path(cache_dir, f"{PLACES_FILE}.zip")
    try:
        _download(PLACES_URL, dest)
    except httpx.HTTPError as exc:
        print(f"  warn: {PLACES_FILE}.zip unavailable ({exc}); skipping the place fill-in")
        return
    for row in _zip_member_rows(dest, f"{PLACES_FILE}.txt"):
        if len(row) <= CITY_DUMP_ADMIN1:
            continue
        code = row[CITY_DUMP_COUNTRY_CODE].strip().upper()
        name = row[CITY_DUMP_NAME].strip()
        if not code or not name:
            continue
        try:
            lat, lon = float(row[CITY_DUMP_LAT]), float(row[CITY_DUMP_LON])
        except ValueError:
            continue
        yield code, row[CITY_DUMP_ADMIN1].strip(), name, lat, lon


# --------------------------------------------------------------------------
# city resolution
# --------------------------------------------------------------------------


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = math.radians
    dlat, dlon = r(lat2 - lat1), r(lon2 - lon1)
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(h))


class CityResolver:
    """Maps a postal row's `place_name` onto the city a person would name.

    The postal export's `place_name` is whatever the national post office calls
    a delivery area, and that is only sometimes a city. In the US it is: 78701
    is "Austin". In Pakistan it is the post office — 54000 "Lahore Gpo", 54020
    "Lahore Alflah", 54030 "Lahore Aitcheson College" — and taking it literally
    turned one city into dozens of one-ZIP "cities" in the picker, which is
    exactly backwards: those are Lahore's postal codes.

    A locality folds into a real city on a **word-prefix match**: `place_name`
    is the city name, or begins with it followed by a space. "Lahore Gpo" ->
    Lahore. "Nawan Lahore" and "Wagha Lahore" are left alone — they merely
    contain the word and are genuinely separate towns.

    The longest matching prefix wins, which is what keeps the US untouched: a
    place_name that is *itself* a known city matches itself exactly, and no
    shorter prefix can beat that. Verified against Kansas City, Salt Lake City,
    New York Mills and Springfield Gardens — all anchor to themselves.

    Coordinates can veto the match, but **only when GeoNames says they are real**.
    The postal export's `accuracy` column is 1 for an estimated position and 4+
    when it came from an actual gazetteer entry, and Pakistan is precisely the
    case where that matters: every Lahore post office is accuracy 1 and plotted
    hundreds of kilometres away — "Lahore Model Town" lands in the Cholistan
    desert, 516km out. An unconditional distance check therefore rejected exactly
    the rows this exists to fix. Meanwhile "Nawan Lahore" and "Wagha Lahore",
    the ones that must stay separate, are accuracy 4. So: trust the name when
    that is all there is, and let good coordinates overrule it when they exist —
    which is what stops a far-away namesake in the same state from swallowing a
    locality.

    Anchors come from the populated-places file, so a locality in a region with
    no known places keeps its own name and behaves exactly as it did before.
    """

    MAX_ANCHOR_KM = 50.0
    # GeoNames postal accuracy: 1 = estimated, 3 = ..., 4 = from a geonameid,
    # 6 = centroid of real addresses. Below 4 the position is a guess.
    RELIABLE_ACCURACY = 4

    def __init__(self) -> None:
        # (country, admin1) -> lowercased place name -> (canonical name, lat, lon)
        self._by_region: dict[tuple[str, str], dict[str, tuple[str, float, float]]] = {}

    def add_place(self, code: str, admin1: str, name: str, lat: float, lon: float) -> None:
        region = self._by_region.setdefault((code, region_key_for(admin1, "")), {})
        region.setdefault(name.lower(), (name, lat, lon))

    def _position(self, lat: str, lon: str, accuracy: str) -> tuple[float, float] | None:
        """The row's coordinates, or None when they aren't worth trusting."""
        try:
            if int(accuracy) < self.RELIABLE_ACCURACY:
                return None
        except (TypeError, ValueError):
            return None  # blank/unparseable accuracy is not a basis for a veto
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            return None

    def resolve(
        self, code: str, region_key: str, place_name: str, lat: str, lon: str, accuracy: str
    ) -> str:
        """The city `place_name` belongs to, or `place_name` itself."""
        region = self._by_region.get((code, region_key))
        if not region:
            return place_name

        words = place_name.split()
        position = self._position(lat, lon, accuracy)

        # Longest prefix first: the whole name before any shorter head of it.
        for end in range(len(words), 0, -1):
            anchor = region.get(" ".join(words[:end]).lower())
            if anchor is None:
                continue
            name, alat, alon = anchor
            if position is None:
                return name
            if _haversine_km(position[0], position[1], alat, alon) <= self.MAX_ANCHOR_KM:
                return name
            # A same-named place too far away is a different place; keep looking
            # at shorter prefixes rather than giving up on the row.
        return place_name


def city_for(resolver: CityResolver, code: str, rkey: str, row: dict) -> str:
    """The city a postal row belongs to. Used identically by both passes."""
    return resolver.resolve(
        code,
        rkey,
        (row["place_name"] or "").strip(),
        row["latitude"],
        row["longitude"],
        row["accuracy"],
    )


# --------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------


def copy_rows(session, table: str, columns: list[str], rows: Iterable[tuple]) -> int:
    """Bulk-load via Postgres COPY.

    1.8M postal codes through SQLAlchemy's executemany is minutes of round
    trips; the same rows through COPY is seconds, and psycopg 3 exposes it
    directly on the raw cursor.
    """
    written = 0
    raw = session.connection().connection
    with raw.cursor() as cur:
        cols = ", ".join(columns)
        with cur.copy(f"COPY {table} ({cols}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)
                written += 1
                if written % 250_000 == 0:
                    print(f"\r    {table}: {written:,}", end="", flush=True)
    if written >= 250_000:
        print(f"\r    {table}: {written:,}")
    return written


def truncate(session) -> None:
    """Wipe the four tables before reloading.

    TRUNCATE, not DELETE. A re-seed clears ~1.8M postal codes and ~1.25M cities,
    and `DELETE FROM city` spends minutes on WAL and on re-checking the foreign
    key from every zip row; TRUNCATE just drops the file. Naming all four in one
    statement satisfies Postgres' requirement that every FK-referencing table be
    included, so no CASCADE and no ordering is needed.

    The tradeoff: TRUNCATE takes an ACCESS EXCLUSIVE lock for the rest of the
    transaction, so the geo endpoints block until the whole load commits -- about
    ten minutes for a world seed, where a DELETE would have let readers keep
    seeing the old rows. Fine for what this is (an admin one-off against
    reference data), but don't run it against a live instance and expect the
    location pickers to keep answering.
    """
    session.execute(
        text("TRUNCATE TABLE zip_code, city, region, country RESTART IDENTITY")
    )


def seed(
    session,
    cache_dir: Path,
    countries_filter: list[str] | None,
    use_places: bool,
) -> dict[str, int]:
    """Two passes over the postal export, because zip rows need their city's id.

    Pass one collects the distinct country/region/city keys and writes those
    three tables; pass two re-reads the file and streams postal codes straight
    into COPY without ever holding them. Only the key *sets* live in memory
    (strings, not row dicts), which is what keeps a world-scale run bounded --
    the ids themselves are recomputed with uuid5 rather than remembered.

    Both passes route `place_name` through the same `CityResolver`, which is
    load-bearing: the city name feeds `city_id`, so if the two passes disagreed
    the postal codes would point at cities that were never inserted.
    """
    print("== Reading country and region reference data")
    country_names = fetch_countries(cache_dir)
    admin1_names = fetch_admin1(cache_dir)

    wanted = set(countries_filter) if countries_filter else None

    # Anchors first: the postal pass needs them to know that "Lahore Gpo" is
    # Lahore. Loaded even under --countries, where the place *rows* are skipped,
    # so a dev subset resolves cities the same way a full run does.
    resolver = CityResolver()
    places: list[tuple[str, str, str]] = []
    if use_places:
        print("== Reading populated places")
        for code, admin1, name, lat, lon in populated_place_rows(cache_dir):
            if wanted is not None and code not in wanted:
                continue
            resolver.add_place(code, admin1, name, lat, lon)
            places.append((code, admin1, name))

    # --- pass 1: distinct keys ------------------------------------------
    print("== Pass 1/2 — scanning postal areas")
    seen_countries: set[str] = set()
    region_names: dict[tuple[str, str], str] = {}
    city_keys: set[tuple[str, str, str]] = set()

    def note(code: str, rkey: str, rname: str, city: str | None) -> None:
        seen_countries.add(code)
        if (code, rkey) not in region_names:
            region_names[(code, rkey)] = (
                admin1_names.get((code, rkey)) or rname or UNKNOWN_REGION
            )
        if city:
            city_keys.add((code, rkey, city))

    for row in postal_rows(cache_dir, countries_filter):
        code = (row["country_code"] or "").strip().upper()
        postal = (row["postal_code"] or "").strip()
        if not code or not postal:
            continue
        rkey = region_key_for(row["admin_code1"], row["admin_name1"])
        note(code, rkey, (row["admin_name1"] or "").strip(), city_for(resolver, code, rkey, row))

    # Every country and division, including those the postal export never
    # mentions -- otherwise the dropdowns simply stop at the 121 countries
    # GeoNames has postal data for.
    if wanted is None:
        for code in country_names:
            seen_countries.add(code)
        for (code, admin1), name in admin1_names.items():
            region_names.setdefault((code, admin1), name)

    for code, admin1, name in places:
        note(code, region_key_for(admin1, ""), "", name)

    print(
        f"  {len(seen_countries):,} countries, {len(region_names):,} regions, "
        f"{len(city_keys):,} cities"
    )

    # --- write the three parent tables ----------------------------------
    print("== Loading")
    truncate(session)

    copy_rows(
        session,
        "country",
        ["id", "code", "name"],
        ((country_id(c), c, country_names.get(c, c)) for c in sorted(seen_countries)),
    )
    copy_rows(
        session,
        "region",
        ["id", "country_id", "name"],
        (
            (region_id(code, rkey), country_id(code), name)
            for (code, rkey), name in region_names.items()
        ),
    )
    copy_rows(
        session,
        "city",
        ["id", "region_id", "name"],
        (
            (city_id(code, rkey, city), region_id(code, rkey), city)
            for code, rkey, city in city_keys
        ),
    )

    # --- pass 2: postal codes, streamed ---------------------------------
    print("== Pass 2/2 — postal codes")
    # Deduped on the *id*, not the key tuple it came from. The id is a pure
    # function of that tuple, so it is exactly as discriminating -- and 1.8M
    # 16-byte digests cost a fraction of 1.8M four-string tuples. Skipping the
    # dedupe entirely is not an option: a repeated key produces a repeated uuid5
    # and COPY has no ON CONFLICT to absorb it.
    seen_zip_ids: set[bytes] = set()

    def zip_tuples() -> Iterator[tuple]:
        for row in postal_rows(cache_dir, countries_filter):
            code = (row["country_code"] or "").strip().upper()
            postal = (row["postal_code"] or "").strip()
            if not code or not postal:
                continue
            rkey = region_key_for(row["admin_code1"], row["admin_name1"])
            city = city_for(resolver, code, rkey, row)
            if not city:
                continue
            # Two things collapse here. One postal code appears on several rows
            # (different accuracy, different admin3), and -- now that localities
            # fold into their city -- Lahore's 30-odd post offices all resolve to
            # the same city, so "54000 under Lahore" can arrive many times over.
            zid = zip_id(code, rkey, city, postal)
            if zid.bytes in seen_zip_ids:
                continue
            seen_zip_ids.add(zid.bytes)
            yield zid, city_id(code, rkey, city), postal

    zips = copy_rows(session, "zip_code", ["id", "city_id", "code"], zip_tuples())

    session.commit()

    # Freshly COPY'd tables have no statistics, so the planner ignores the
    # search indexes until this runs -- type-ahead would seq-scan every city.
    print("== ANALYZE")
    session.execute(text("ANALYZE country, region, city, zip_code"))
    session.commit()

    return {
        "countries": len(seen_countries),
        "regions": len(region_names),
        "cities": len(city_keys),
        "zips": zips,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--countries",
        default="",
        help="comma-separated ISO codes to seed instead of the whole world (dev shortcut)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="seed the whole world (the default; accepted for compatibility)",
    )
    parser.add_argument(
        "--no-places",
        action="store_true",
        help="skip the populated-places fill-in for countries without postal data",
    )
    parser.add_argument(
        "--cache-dir",
        default="tmp/geonames",
        help="where downloaded GeoNames files are cached (default: tmp/geonames)",
    )
    args = parser.parse_args()

    countries = [c.strip().upper() for c in args.countries.split(",") if c.strip()] or None
    if countries and args.all:
        print("--all and --countries are mutually exclusive", file=sys.stderr)
        raise SystemExit(2)

    scope = "the whole world" if countries is None else ", ".join(countries)
    print(f"Seeding the geo database: {scope}\n")

    session = GeoSessionLocal()
    try:
        counts = seed(session, Path(args.cache_dir), countries, not args.no_places)
    finally:
        session.close()

    print(
        f"\ndone: {counts['countries']:,} countries, {counts['regions']:,} regions, "
        f"{counts['cities']:,} cities, {counts['zips']:,} postal codes"
    )


if __name__ == "__main__":
    main()
