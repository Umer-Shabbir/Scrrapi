"""FastAPI application entrypoint.

Run with: uvicorn app.main:app --reload
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    api_keys,
    audit,
    auth,
    categories,
    exports,
    integrations,
    jobs,
    locations,
    proxies,
    schedules,
    suppression,
    system,
    team,
    templates,
    webhook_deliveries,
)
from app.api.routers import settings as settings_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()

# Install the structured handler before anything else logs (11.2). Workers do the
# same thing from Celery's `setup_logging` signal in app.core.celery_app.
configure_logging("api")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Lead Generation Scraper API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(locations.router, prefix="/api/geo", tags=["locations"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(exports.router, prefix="/api/exports", tags=["exports"])
app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["schedules"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(suppression.router, prefix="/api/suppression", tags=["suppression"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])
app.include_router(proxies.router, prefix="/api/proxies", tags=["proxies"])
app.include_router(team.router, prefix="/api/team", tags=["team"])
app.include_router(api_keys.router, prefix="/api/api-keys", tags=["api-keys"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(system.router, prefix="/api/system", tags=["system"])

app.include_router(
    webhook_deliveries.router, prefix="/api/webhook-deliveries", tags=["webhook-deliveries"]
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/version")
def version() -> dict:
    return {"version": app.version}
