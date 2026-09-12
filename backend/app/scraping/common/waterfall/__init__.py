"""Waterfall Email & Mobile Phone Enrichment providers and cascade engine."""

from app.scraping.common.waterfall.base import EnrichmentProvider, WaterfallResult
from app.scraping.common.waterfall.datagma import DatagmaProvider
from app.scraping.common.waterfall.engine import run_waterfall_cascade
from app.scraping.common.waterfall.findymail import FindymailProvider
from app.scraping.common.waterfall.hunter import HunterProvider
from app.scraping.common.waterfall.prospeo import ProspeoProvider

__all__ = [
    "EnrichmentProvider",
    "WaterfallResult",
    "HunterProvider",
    "ProspeoProvider",
    "DatagmaProvider",
    "FindymailProvider",
    "run_waterfall_cascade",
]
