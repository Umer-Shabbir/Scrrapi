"""Celery application instance, shared by API (task dispatch) and worker processes."""

import logging
import subprocess
import sys

from celery import Celery
from celery.signals import setup_logging as setup_logging_signal
from celery.signals import worker_process_init as worker_process_init_signal

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()

celery_app = Celery(
    "leadgen",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # A scrape task that dies with its worker (OOM-killed Chromium, container
    # restart) goes back on the queue instead of vanishing -- this is the piece
    # that replaces the legacy AutoRestartManager watchdog.
    task_reject_on_worker_lost=True,
    # Hard ceilings so one wedged browser can't hold a worker slot forever. The
    # soft limit raises SoftTimeLimitExceeded inside the task (retryable); the
    # hard limit kills the child process.
    task_soft_time_limit=settings.task_soft_time_limit_s,
    task_time_limit=settings.task_time_limit_s,
    # Backoff defaults for tasks that call `self.retry()` without a countdown.
    task_default_retry_delay=int(settings.task_retry_backoff_base_s),
    # Redis has no native "invisible while processing" semantics; this is how long
    # a task may run before the broker re-delivers it. Must stay above the hard
    # time limit or a slow scrape gets picked up twice.
    broker_transport_options={"visibility_timeout": settings.task_time_limit_s + 60},
    broker_connection_retry_on_startup=True,
    task_routes={
        "app.workers.tasks.scrape_google_maps": {"queue": "google_maps"},
        "app.workers.tasks.scrape_bing_maps": {"queue": "bing_maps"},
        "app.workers.tasks.scrape_place": {"queue": "places"},
        "app.workers.tasks.export_job": {"queue": "exports"},
    },
    # Schedules screen: fires due schedules once a minute. Requires a beat
    # process alongside the worker(s): `celery -A app.core.celery_app beat`.
    beat_schedule={
        "dispatch-due-schedules": {
            "task": "app.workers.tasks.dispatch_due_schedules",
            "schedule": 60.0,
        },
        # Export screen's retention sweep -- daily is plenty for a multi-day
        # expiry window; see Export.expires_at / settings.export_retention_days.
        "purge-expired-exports": {
            "task": "app.workers.tasks.purge_expired_exports",
            "schedule": 86400.0,
        },
        # Settings screen's Data Retention section -- see
        # app.workers.tasks.purge_expired_results for why this didn't exist
        # before (only whole-job deletion touched `results` previously).
        "purge-expired-results": {
            "task": "app.workers.tasks.purge_expired_results",
            "schedule": 86400.0,
        },
    },
)

# Queues a worker must consume to cover every task above (`celery -Q ...`).
TASK_QUEUES = ("google_maps", "bing_maps", "places", "exports")


@setup_logging_signal.connect
def _configure_worker_logging(**_kwargs: object) -> None:
    """Take over Celery's logging setup so worker lines use the same structured
    format as the API (11.2). Connecting to this signal at all is what stops
    Celery from installing its own handlers over the top of ours."""
    configure_logging("worker", force=True)


@worker_process_init_signal.connect
def _reap_orphaned_playwright_drivers(**_kwargs: object) -> None:
    """Sweep leftover Playwright driver processes on worker startup.

    `task_time_limit` (see conf.update above) SIGKILLs a task's OS process when a
    browser wedges past the hard ceiling -- that's the intended backstop, but a
    SIGKILL skips every `finally: await browser.close()` in the scraper code, so
    the Chromium the dead task launched (and its Node "run-driver" host process)
    is orphaned instead of reaped. Nothing inside that dead process can clean up
    after itself; the next thing that can is this worker starting back up. Best
    effort only -- if this fails or no matches exist, that's fine, it just means
    there was nothing to sweep.
    """
    logger = logging.getLogger("app.worker")
    try:
        if sys.platform == "win32":
            # Playwright's Node driver process is invoked as
            # ".../playwright/driver/node.exe .../cli.js run-driver"; match on the
            # driver path so this only ever touches Playwright's own processes,
            # never an unrelated node.exe (e.g. the frontend dev server).
            result = subprocess.run(
                [
                    "wmic",
                    "process",
                    "where",
                    "CommandLine like '%playwright%driver%run-driver%'",
                    "get",
                    "ProcessId",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            pids = [line.strip() for line in result.stdout.splitlines() if line.strip().isdigit()]
            for pid in pids:
                subprocess.run(
                    ["taskkill", "/PID", pid, "/T", "/F"],
                    capture_output=True,
                    timeout=10,
                )
            if pids:
                logger.info("reaped orphaned playwright drivers", extra={"count": len(pids)})
        else:
            result = subprocess.run(
                ["pgrep", "-f", "playwright.*driver.*run-driver"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            pids = [line.strip() for line in result.stdout.splitlines() if line.strip().isdigit()]
            for pid in pids:
                subprocess.run(["kill", "-9", pid], capture_output=True, timeout=10)
            if pids:
                logger.info("reaped orphaned playwright drivers", extra={"count": len(pids)})
    except Exception:
        # Best effort -- a failed sweep must never block the worker from starting.
        logger.warning("orphaned playwright driver sweep failed", exc_info=True)
