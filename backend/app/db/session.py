"""Engine + session factories for the app DB and geo DB."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Default pool_size=5/max_overflow=10 (15 connections total) was sized for a
# handful of requests, not a worker running MAX_CONCURRENT_TARGETS (64)
# threads at once -- each `scrape_place`/`scrape_google_maps` task opens its
# own `AppSessionLocal()` (see app.workers.tasks), so 64 in-flight tasks want
# up to 64 connections from this one process. Sized to the worker's own pool
# ceiling plus headroom, not to whatever `concurrent_targets` happens to be
# set to today -- that setting changes at runtime with no restart, but a pool
# size can't, so it has to cover the max the worker will ever ask for.
# Postgres' own default max_connections is 100; this (72) leaves room for the
# API process and psql/admin connections alongside one worker at full tilt.
app_engine = create_engine(
    settings.app_db_url, pool_pre_ping=True, pool_size=32, max_overflow=40
)
geo_engine = create_engine(settings.geo_db_url, pool_pre_ping=True)

AppSessionLocal = sessionmaker(bind=app_engine, autoflush=False, autocommit=False)
GeoSessionLocal = sessionmaker(bind=geo_engine, autoflush=False, autocommit=False)
