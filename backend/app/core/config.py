"""App settings, loaded from environment / .env via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"

    app_db_url: str
    geo_db_url: str
    redis_url: str

    # Logging (11.2). `json` emits one JSON object per line for log shippers;
    # `text` is the human-readable form for local `uvicorn --reload` work.
    log_level: str = "INFO"
    log_format: str = "json"  # json | text
    # File the full log stream is also written to (always JSON, regardless of
    # log_format, so it stays grep/jq-able) -- None disables file logging.
    # `npm run dev` sets this per service so terminal stays thin while the
    # complete record still lands somewhere durable.
    log_file: str | None = None
    # Console handler's own level, independent of log_level (which still
    # governs what reaches the file/dashboard stream). Defaults to log_level
    # for anyone running uvicorn/celery directly; `npm run dev` raises this to
    # WARNING so routine INFO-level lifecycle lines don't flood the terminal --
    # see the note below on why console volume alone was once enough to crash
    # a terminal at worker concurrency 64.
    console_log_level: str | None = None

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Account lockout (login screen error-locked state). A failed attempt past
    # the threshold locks the account for the cooldown instead of allowing
    # unlimited guesses.
    login_max_failed_attempts: int = 5
    login_lockout_minutes: int = 15
    # Pre-auth token issued after password check when a user has TOTP enabled;
    # short-lived since it only proves "password was correct", not a session.
    totp_pending_token_minutes: int = 5

    default_user_agent: str = ""
    scrape_min_delay_ms: int = 500
    scrape_max_delay_ms: int = 2000

    # Adaptive 429 handling (11.3). On top of the fixed random delay above, a host
    # that answers 429/503 (or serves a "sorry"/challenge interstitial) goes into a
    # cooldown that doubles per consecutive hit: base, 2x base, 4x base ... capped
    # at max. A clean response resets it back to zero.
    rate_limit_base_cooldown_s: float = 30.0
    rate_limit_max_cooldown_s: float = 900.0

    # Celery retry/backoff (11.1). Retry n sleeps `base * 2**n` seconds, capped at
    # max, times a random jitter factor in [1 - jitter, 1 + jitter] so a batch of
    # tasks that all fail on the same block don't retry in lockstep.
    task_retry_backoff_base_s: float = 10.0
    task_retry_backoff_max_s: float = 900.0
    task_retry_jitter: float = 0.25
    task_max_retries_feed: int = 3
    task_max_retries_place: int = 2
    task_max_retries_export: int = 2
    task_soft_time_limit_s: int = 900
    task_time_limit_s: int = 1200

    proxy_mode: str = "single"  # single | list | free
    proxy_single_url: str | None = None
    proxy_list_path: str | None = None
    proxy_free_list_url: str = (
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http"
        "&timeout=10000&country=all&ssl=all&anonymity=all"
    )
    proxy_free_list_ttl_s: int = 600

    cors_origins: list[str] = ["http://localhost:5173"]

    job_stream_poll_interval_s: float = 2.0

    # One search runs per ZIP, so "every ZIP in Texas" x three keywords is tens of
    # thousands of browser sessions. Both caps exist so that number is refused up
    # front rather than discovered when the queue is already full.
    max_job_targets: int = 2000
    geo_zip_page_limit: int = 2000

    # Scrape concurrency. `default_concurrent_targets` is only the starting
    # value: the live number is a runtime setting stored in the app DB and
    # edited from the Settings page (app.core.runtime_settings), because a
    # worker fleet has to see the change without a redeploy. It caps how many
    # targets the dispatcher lets onto the broker at once -- everything else
    # sits in the DB as "queued, not dispatched" instead of flooding the queue.
    #
    # `max_concurrent_targets` is the ceiling the UI slider and the API accept;
    # past it the browsers cost more than the parallelism buys.
    default_concurrent_targets: int = 2
    max_concurrent_targets: int = 64
    # A dispatched target normally waits behind other tasks for a while, so this
    # has to be long: it is how patient the dispatcher is before deciding a
    # dispatched-but-never-started target's task is gone for good and handing it
    # out again. The re-issue is safe (the superseded task exits on its stale
    # `dispatch_id`), but too short a window still means pointless churn.
    target_dispatch_stale_s: int = 3600
    # How long a "running" target may go without a heartbeat before the
    # dispatcher assumes its worker/broker task is gone and hands the slot
    # back (see `dispatch._reclaim_stuck_running`). Longer than the dispatch
    # window above because a real scrape can legitimately run for a while
    # between places -- this only needs to fire for a worker that is actually
    # dead, not one that is merely slow.
    target_running_stale_s: int = 7200

    # Deep site crawl (app.scraping.common.site_crawler). Off unless the Settings
    # page turns it on -- it multiplies the network cost of every place scraped,
    # so it has to be a decision rather than a default. `deep_crawl_enabled` and
    # `deep_crawl_max_pages` are only the values used before anything has been
    # saved to the app DB; the live ones are runtime settings, for the same
    # reason the concurrency limit is (workers must see a change without a
    # redeploy). Everything below them is deployment config: it bounds what one
    # crawl may cost, which is not something a user should be able to raise from
    # the UI.
    deep_crawl_enabled: bool = False
    deep_crawl_max_pages: int = 25
    max_deep_crawl_pages: int = 200
    deep_crawl_max_depth: int = 3
    # Wall-clock ceiling per site. A place scrape already holds a Celery slot for
    # the Maps page load, so an unbounded crawl of a 40k-page site would park
    # that slot for the rest of the afternoon.
    deep_crawl_timeout_s: float = 45.0
    deep_crawl_request_timeout_s: float = 10.0
    deep_crawl_concurrency: int = 4
    deep_crawl_max_page_bytes: int = 2_000_000
    # The sitemap is what makes "every page" real on a site whose nav is rendered
    # client-side and whose contact page is therefore unreachable by link.
    deep_crawl_use_sitemap: bool = True
    deep_crawl_respect_robots: bool = True
    # Seeded worldwide the geo DB holds ~1.1M cities, so the country/region/city
    # pickers search server-side and never hand back more than this per request.
    geo_page_limit: int = 200

    export_dir: str = "./exports"
    # How long a generated export file stays downloadable before the retention
    # sweep deletes it. Figma's Export History shows a 5-day-from-creation
    # ceiling; nothing product-specific about the number, just a bound so
    # `export_dir` doesn't grow forever. The live value is a runtime setting
    # (app.core.runtime_settings) editable from Settings > Data Retention;
    # this is only the value used before anything has been saved.
    export_retention_days: int = 5
    max_export_retention_days: int = 365

    # Google Sheets export format. Service-account creds only (no OAuth
    # callback route exists) -- path to the downloaded JSON key file. Unset
    # means "sheets" exports fail loudly with a clear error rather than
    # fabricating a fake success (see app.export.sheets_writer).
    google_sheets_credentials_path: str | None = None
    # The service account itself owns any sheet it creates but has no human
    # inbox -- this address gets `writer` access added on every generated
    # sheet so it actually shows up in someone's Drive. Required alongside
    # the creds path; a export with creds but no share target is still
    # unusable (nobody can find the file).
    google_sheets_share_with: str | None = None

    # Results retention (Settings > Data Retention). No age-based cleanup of
    # the `results` table existed before this cycle -- see
    # app.core.runtime_settings.RESULTS_RETENTION_DAYS_KEY.
    results_retention_days: int = 180
    max_results_retention_days: int = 3650

    # Per-host cooldown base and Celery retry ceiling (Settings > Scraping).
    # Live values are runtime settings; these remain the pre-save defaults and
    # the UI/API-accepted bounds, same pattern as concurrency above.
    max_cooldown_base_s: float = 300.0
    max_retry_ceiling: int = 10

    # Waterfall Email & Mobile Phone Enrichment
    # Cascades through third-party APIs (Hunter, Prospeo, Datagma, Findymail)
    # when internal crawling finds no email or only generic role-based emails.
    waterfall_enrichment_enabled: bool = False
    waterfall_providers: list[str] = ["hunter", "prospeo", "datagma", "findymail"]
    hunter_api_key: str | None = None
    prospeo_api_key: str | None = None
    datagma_api_key: str | None = None
    findymail_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
