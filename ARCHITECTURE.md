# Lead Generation Scraper — Architecture (Python, Web Stack)

## 1. Decision

**Stack: Python backend + separate web frontend.** Not .NET, not a single-process desktop app.

Rationale:
- Scraping/automation ecosystem in Python (Playwright, httpx, BeautifulSoup, regex/lxml) is stronger and better maintained than the C#/EO.WebBrowser equivalent used in the legacy app.
- Job queue + background worker model (Celery/RQ) maps directly onto "long unattended scraping jobs" — replaces the AutoRestartManager/watchdog hack with a proper supervised worker process.
- A web frontend (React) handles the cascading Country → State → City → ZIP UI, results grid, and category/location upload forms with far less code than WinForms, and runs on any OS.
- Backend and frontend as separate deployables lets the scraping engine run headless on a server/VM for unattended jobs, while the frontend can be opened from any browser (including packaged as a local Electron/Tauri shell later if a "desktop app" feel is wanted — optional, not required for v1).

---

## 2. High-Level Architecture

```
┌─────────────────────┐        HTTPS/REST + WebSocket        ┌──────────────────────────┐
│   Frontend (React)  │ ─────────────────────────────────────▶│   Backend (FastAPI)      │
│   Vite + TypeScript │◀───────────────────────────────────── │   Python 3.12            │
└─────────────────────┘        job status, results stream     └──────────┬───────────────┘
                                                                          │
                                    ┌─────────────────────────────────────┼─────────────────────────┐
                                    │                                     │                         │
                            ┌───────▼────────┐                  ┌────────▼────────┐        ┌────────▼────────┐
                            │  Postgres (app) │                  │  Redis (broker)  │        │  Postgres (geo)  │
                            │  jobs, results,  │                  │  queue + cache  │        │  country/region/ │
                            │  users, licenses │                  └────────┬────────┘        │  city/zip (from  │
                            └─────────────────┘                            │                 │  GeoNames)       │
                                                                   ┌────────▼────────┐        └─────────────────┘
                                                                   │  Celery Workers  │
                                                                   │  (scraping jobs) │
                                                                   └────────┬────────┘
                                                                            │
                                                          ┌─────────────────┼──────────────────┐
                                                          │                 │                  │
                                                  ┌────────▼──────┐ ┌───────▼───────┐  ┌────────▼────────┐
                                                  │ Playwright     │ │ Proxy pool     │  │ Export writer   │
                                                  │ (headless      │ │ manager        │  │ (CSV/XLSX/KML)  │
                                                  │ Chromium)      │ │ (rotation)     │  └─────────────────┘
                                                  └────────────────┘ └────────────────┘
```

Two-database split kept from the original design, same reasoning: **geo reference DB** (country/region/city/zip from GeoNames) is separated from the **app DB** (jobs, results, users, licenses). This time both run on Postgres you control — no vendor-locked blob credential scheme needed, since this is your own product.

---

## 3. Backend (Python)

### 3.1 Stack
- **Framework:** FastAPI (async, OpenAPI docs free, WebSocket support for live job progress)
- **Task queue:** Celery + Redis (or RQ if you want something lighter) — one worker pool per data source (Google Maps / Bing Maps) so a stuck job on one source doesn't starve the other
- **Scraping engine:** Playwright (Python), headless Chromium — replaces EO.WebBrowser/Chromium embed and the dead PhantomJS path entirely
- **ORM:** SQLAlchemy 2.0 + Alembic migrations
- **Validation:** Pydantic v2 (shared request/response schemas, also generates the OpenAPI spec the frontend types off of)
- **Auth/licensing:** JWT session tokens + a `licenses` table (plan, seats, expiry) — replaces the ValidateRegistration title-bar hack with a real gate on API routes
- **Config:** `pydantic-settings`, `.env` per environment (dev/staging/prod), secrets via env vars or a secrets manager — no encrypted blob-in-DLL pattern needed

### 3.2 Module layout
```
backend/
  app/
    api/            # FastAPI routers: jobs, locations, categories, exports, auth
    core/           # config, security, celery app instance
    db/             # SQLAlchemy models + Alembic migrations (app DB + geo DB)
    scraping/
      google_maps/  # search request builder, feed scroller, place parser
      bing_maps/    # parallel implementation, same interface
      common/       # email/phone/social miners, website finder, site crawler,
                    # structured-data reader, data block parser
      proxy/         # proxy pool, rotation policy, rate-limit delay
    workers/        # celery tasks: run_scrape_job, scrape_place, export_job
                    # + dispatch.py (concurrency gate), control.py (pause/cancel/delete)
    export/         # csv/xlsx (openpyxl)/kml writers
  tests/
  pyproject.toml
```

### 3.3 Scraping engine — mapped from legacy flow
| Legacy piece | Python equivalent |
|---|---|
| `GoogleMapsScraper.BuildSearchRequest` | `scraping/google_maps/query.py::build_search_url(keyword, location)` |
| `GetLinksData` (JS injection, scroll `div[role="feed"]`, count `a.hfpxzc`) | Playwright `page.evaluate()` scroll loop, same selectors, `asyncio` timeout guard instead of `[TIMEOUT]`/`[HARD_TIMEOUT]` |
| `ParseMapsPlaceUrlsFast` | regex/URL parse on collected `/maps/place/` hrefs |
| `GMCompanyPageScraper.GetData` (regex on `data-item-id="address"`, `tel:`, rating, lat/long) | Playwright locator queries + regex fallback, Chrome UA spoofed via Playwright's `user_agent` context option |
| `WebMiner.GetWeb` / `FindCorrectWeb` | `httpx` fetch + heuristic scoring of candidate site |
| `EmailMiner` (`ExtractFirstValidEmail`, `IsValidEmail`, `GetDomainFromEmail`) | `scraping/common/email_miner.py`, regex + `email-validator` package |
| *(no legacy equivalent)* | `scraping/common/site_crawler.py` — deep crawl of the business's own site for the contact details the Maps listing doesn't carry, with `phone_miner.py`, `social_miner.py` and `structured_data.py` doing the per-page extraction. See 3.5. |
| `WebMiner.SearchWebOnStartpage` | same target (Startpage), `httpx` + BeautifulSoup |
| `BingMapsScraper` | `scraping/bing_maps/` mirrors the Google module's interface (`get_links`, `get_place_data`) so job runner is source-agnostic |
| `DataBlock.Parse` (`],[` token parsing of Google's packed JSON) | `json.loads` with a small pre-processor for the packed array format, or Playwright network interception of the underlying XHR response (cleaner than scraping the packed blob at all) |
| `ProxyServer` (single/list/free-list, random delay) | `scraping/proxy/pool.py` — same three modes, `asyncio.sleep(random.uniform(...))` between requests |
| `AutoRestartManager` + `GLeadsLauncher.exe` watchdog | Not needed in this form — Celery's own worker supervision (`celery worker --autoscale`, or run under `supervisord`/systemd/Docker `restart: on-failure`) handles crash recovery. A Playwright browser crash is caught per-task and the task retried (`bind=True, max_retries=3`) instead of restarting a whole process. |

### 3.4 Job lifecycle
1. Frontend POSTs a job: list of keywords/categories × list of **ZIP codes**.
2. API creates `Job` row (status=`queued`) plus a `JobTarget` per keyword/ZIP pair, then dispatches only as many as the `concurrent_targets` setting allows (`app/workers/dispatch.py`); the rest wait in the DB until a slot frees.

**Why ZIP and not city.** Maps stops feeding its results list at roughly a couple of hundred places per query, so "plumber in Austin" returns a fraction of Austin's plumbers no matter how long the feed is scrolled. Running the same keyword once per postal code inside the city partitions the area into pieces small enough that each query's ceiling stops binding — 74 searches for Austin instead of one. The cross product is therefore large by design, and `max_job_targets` caps it per job.

A ZIP-scoped target also carries the `city`/`region`/`country` it was picked under, which is the only source for those columns on a `Result`: the place panel yields one unsplit address string.
3. Worker runs scrape → for each place found, enqueues a `scrape_place` subtask (get details, then get website + mine contact details).
4. Results streamed back via WebSocket (`job:{id}:progress`) so the frontend grid updates live, no polling needed.
5. On completion, `export_job` task builds CSV/XLSX/KML and stores a download URL.

A job can also be **paused, resumed, cancelled or deleted** at any point (`app/workers/control.py`, exposed as `POST /api/jobs/{id}/pause|resume|cancel` and `DELETE /api/jobs/{id}`). Statuses grow accordingly: `queued | running | paused | done | error | cancelled`.

**Pause is a queue gate, not a freeze.** A paused job stops being a source of waiting targets for the dispatcher, and any target handed to the broker but not yet picked up is revoked and returned to the waiting pool so its slot frees immediately — but targets *already scraping* run to completion. That asymmetry is deliberate: a feed scrape holds the only copy of the place URLs it scrolled, so killing it mid-flight doesn't bank the work, it discards it and guarantees the area is re-scraped on resume, duplicating the rows already written. Finishing the open areas makes pause lossless and resume free.

**Cancel is terminal**, marks every unfinished target `cancelled`, and revokes running tasks with `terminate`. **Delete** cancels first, then removes targets, results, exports and the generated files.

Revocation is best-effort — `celery_app.control.revoke` is a broadcast, and a worker that is down during it will still receive the task later. Correctness comes from the database instead: every scrape task re-reads its job's status on pickup (`tasks._abandon_reason`) and every place task re-reads it both on pickup and again before writing its row (`tasks._place_halt_reason`), which is also what stops a late insert from hitting a foreign key against a deleted job.

### 3.5 Deep site crawl

The Maps listing gives a name, an address, one phone number and (sometimes) a
website. Everything else a lead is worth having — the email, the mobile, the
branch lines, the social profiles — is on that website, and mostly not on its
home page: the address is on `/contact` (or `/impressum`, or `/kontakt`), the
second location's number is on `/locations`, and the profiles are in a footer
that half of themes only render on inner pages.

`scraping/common/site_crawler.py` walks the site instead of fetching one page. It
reads `robots.txt` for the rules and for `Sitemap:` lines, seeds a frontier from
the home page, the sitemap and every internal link it meets, and orders that
frontier by how likely a URL is to carry contact details — `/contact`,
`/impressum`, `/about`, `/team` ahead of `/blog/2019/...`. That ordering is what
makes a page budget work: with 25 pages of a 400-page site, the 25 read are the
25 worth reading. The sitemap matters for the same reason from the other end —
on a site whose menu is rendered client-side there is no crawlable link to the
contact page at all, and the sitemap lists it anyway.

Per page, four extractors run: `email_miner` (mailto, Cloudflare `data-cfemail`
blobs, plain text, and `info [at] example [dot] com` obfuscation), `phone_miner`
(`tel:` links, WhatsApp click-to-chat, and validated text runs), `social_miner`
(profile URLs by network, with share widgets and unfilled theme placeholders
rejected) and `structured_data` (the schema.org JSON-LD block, which is where the
phone number is on most site-builder sites and which the text scan can't reach
because script bodies are stripped before it).

**Merged, not replaced.** Everything found is appended to what Maps already had:
`results.email` and `results.phone` hold a `", "`-joined list with the listing's
own value first. Deduplication is on identity rather than text — `phone_key`
compares the last nine digits, so "+1 512-555-0100" from Maps and "(512) 555-0100"
from the site are one number, not two. Social profiles go to columns of their
own (`facebook` … `whatsapp`, plus `other_socials` for the tail).

**Off by default, and bounded when on.** It is a runtime setting
(`app.core.runtime_settings`, edited from the Settings page and read per place, so
turning it off applies to the places already queued) because it multiplies the
network cost of every result: a 2000-place job pays for 2000 crawls. Pages,
depth, wall-clock, response size and concurrency are all capped from config, and
the crawl degrades to "whatever it had found when the budget ran out" rather than
failing the enrichment.

### 3.6 Data Enrichment Depth

Extends beyond general store contact info with three high-value capabilities:
- **Decision-Maker Discovery** (`scraping/common/decision_maker_miner.py`): Finds Owner, Founder, CEO, and executive names from schema.org JSON-LD structured data, DOM bio/leadership cards, and contextual leadership patterns.
- **Direct Personal Mobile Phone Numbers** (`scraping/common/mobile_miner.py`): Identifies personal cell lines and WhatsApp direct numbers via context cues and international mobile numbering plan heuristics.
- **Review Sentiment & Pain-Point Extraction** (`scraping/common/review_sentiment.py`): Scores customer review sentiment and extracts recurring customer pain points (delays, unexpected fees, service quality, communication friction).
- **GBP Unclaimed / Unverified Listing Detection** (`scraping/google_maps/place.py`, `scraping/bing_maps/place.py`): Detects whether a Google Business Profile or Bing listing has the "Claim this business" prompt (`is_unclaimed`), identifying high-value outreach opportunities for agencies and SEO consultants.

### 3.7 Waterfall Email & Mobile Phone Enrichment

Provides automated fallback when internal web scraping yields no email or only generic role-based inboxes (`info@`, `contact@`, `sales@`, `support@`, `admin@`, etc.):
- **Generic Email Classifier** (`scraping/common/generic_email.py`): Distinguishes generic switchboard inboxes from personal direct business emails.
- **Third-Party Provider Adapters** (`scraping/common/waterfall/`): Modular adapters for Hunter.io, Prospeo.io, Datagma, and Findymail.
- **Cascade Engine** (`scraping/common/waterfall/engine.py`): Executes sequential provider queries until direct personal email and mobile phone numbers are found, or the cascade is exhausted.
- **Provenance Tracking**: Records exact source (`email_source` and `phone_source` set to `waterfall:<provider>`).
- **Live Configuration**: Managed dynamically via DB runtime settings (`app_settings`) and exposed on the Settings screen and Job Wizard.

---

## 4. Frontend

### 4.1 Stack
- **React 18 + TypeScript + Vite**
- **UI kit:** MUI or Mantine — gives you the DataGrid component for results (sortable/filterable table replacing the WinForms grid) and combobox components for the cascading dropdowns
- **State/data fetching:** TanStack Query (handles job polling/refetch, caching) + a WebSocket hook for live progress
- **Forms:** `react-hook-form` + zod schema (mirrors backend Pydantic schema)

### 4.2 Screens (mapped from legacy forms)
| Legacy WinForm | Web page |
|---|---|
| `MainForm` | Dashboard — job list, start/stop, export button |
| `UploadCategoriesForm` | Categories page — free text + CSV upload, tag-style multi-select |
| `UploadLocationsForm` / `LocationEditForm` | Locations page — cascading Country → State → City → ZIP selects, backed by `/api/geo/*` endpoints hitting the geo Postgres DB |
| Results grid | Results page — virtualized DataGrid, column set: Category, Name, Address, City/State/Country/ZIP, Phone, Email, Website, Latitude, Longitude, and the social columns the deep crawl fills. Phone/Email are multi-valued and render one link per value; the social columns stay hidden until a row actually has one, so a run with the crawler off looks exactly as it did before. |
| Export button | Export page/modal — pick CSV/XLSX/KML, triggers `export_job`, shows download link when ready |
| *(no legacy equivalent)* | Settings page — scrape concurrency and the deep website crawl (on/off + pages per site), both installation-wide |
| Title bar version/registration string | Account/license page — plan status, seat count, renewal date |

### 4.3 Cascading location dropdowns
`GET /api/geo/countries` → `GET /api/geo/regions?country=` → `GET /api/geo/cities?region=` → `GET /api/geo/zips?city=`, each backed by indexed queries against the geo DB tables seeded from GeoNames (same source data as the legacy app, just loaded via a Python seed script instead of a proprietary DB rebuild path).

**Seeded worldwide, so every level is a search, not a dropdown.** The default seed covers the whole world: ~250 countries, ~4k first-level divisions, ~1.1M cities, ~1.8M postal codes. Only the country list is small enough to ship whole and filter in the browser; region, city and ZIP take a `q=` term, are capped server-side, and are queried on a debounce as the user types.

Matching is *starts-with, then contains*, ranked in that order — `aus` puts Austin above Fort Augustus, `york` still finds New York. Both halves have to be index-assisted or each keystroke is a sequential scan of every city on earth, which is what `c93f5a08d1e7` exists for: this database collates as `en_US.utf8`, so a plain btree on `name` cannot serve `LIKE 'Aus%'` at all. It adds `text_pattern_ops` indexes on `lower(name)` for the prefix half and pg_trgm GIN indexes for the contains half.

The first three levels pick one value. The fourth is a multi-select with a select-all, because ZIP is the unit a job is built from — and the City picker carries an "All cities in this state" option that widens the ZIP list to `GET /api/geo/zips?region=`. `/cities` and `/zips` answer with `{items, total, truncated}` rather than a bare list: both run past the server's cap, and a select-all over a silently truncated list would queue fewer areas than the user asked for.

**"City" is not what the postal file says it is.** The postal export's `place_name` is whatever the national post office calls a delivery area. In the US that is the city; in Pakistan it is the individual post office, so 54000/54020/54030 arrive as "Lahore Gpo"/"Lahore Alflah"/"Lahore Aitcheson College" and a literal reading turns one city into thirty one-ZIP "cities". The seed folds such localities onto a real place name by word-prefix match, using the row's `accuracy` flag to decide whether its coordinates are trustworthy enough to veto the match — see `CityResolver` in `seed_geo.py`. The City level is therefore one entry per city, with the postal codes underneath it where they belong.

**Coverage is uneven, and the picker has two modes because of it.** 121 of the 252 countries have postal codes; the other 131 mostly have no postal system at all (Hong Kong, Ghana, Qatar, Panama …), so no source can supply ZIPs for them — this is a fact about the world, not a gap in the dataset. A few (Nigeria, Tanzania) do have schemes that aren't in any free bulk dataset; OSM holds scattered `addr:postcode` tags but as per-building address data, and Overpass is far too slow to seed from.

Rather than dead-ending there, the last level switches to **area mode**: the region's populated places (seeded from `cities500`, down to villages and neighbourhoods) become the search areas and are multi-selected exactly as ZIPs are. Nothing downstream changes — an area target is just a `LocationTarget` with a `city` and no `zipCode`. This costs nothing in fidelity because the ZIP was only ever a partitioning device: what matters is that each query covers a small enough area that the ~120-result ceiling stops binding, and 33 Lagos-State places do that as well as 33 postcodes would.

The mode is decided **per region from the data** (`regionHasZips` on `/api/geo/cities`), not from a hardcoded country list, so a country that gains postal data in a later seed starts using it with no code change.

Queueing is explicitly **append or replace** — a queue is usually assembled over several passes through the cascade, and the destructive one has to be chosen, not inferred.

---

## 5. Data Model (summary)

**App DB (Postgres):**
- `users`, `licenses` (plan, seats, expires_at)
- `jobs` (id, status, source [google/bing], created_by, created_at)
- `job_targets` (job_id, keyword, location_label, zip_code, city, region, country, status, places_found, places_done) — the geo four are nullable, since a hand-typed location has a label and nothing under it
- `results` (job_id, category, name, address, city, state, country, zip, phone, email, mobile_phone, decision_maker, reviews_count, sentiment_score, sentiment_label, pain_points, website, lat, lon, facebook, instagram, linkedin, twitter, youtube, tiktok, whatsapp, other_socials, scraped_at) — `phone`/`email`/`mobile_phone` each hold a `", "`-joined list; social columns, mobile, decision maker, and review sentiment are populated via the deep crawl and place enrichment pipeline
- `exports` (job_id, format, file_path, generated_at)
- `integration_connections` (id, provider, status, config, last_event_at, last_event_summary, updated_at) — manages webhook configurations and OAuth2-connected CRMs (HubSpot, GoHighLevel, Pipedrive) for two-way native sync and contact deduplication
- `app_settings` (key, value, updated_at) — runtime preferences the Settings page writes and every worker reads: `concurrent_targets`, `deep_crawl_enabled`, `deep_crawl_max_pages`

**Geo DB (Postgres, separate schema or separate instance):**
- `country`, `region`, `city`, `zip_code` — same shape as legacy, indexed on parent FK + name for fast cascading lookups.

---

## 6. Proxy & Rate-Limit Handling
- `proxy/pool.py`: pluggable sources — single proxy, static list, or fetched free-list (gatherproxy/proxyspy-style aggregators) — same three modes as legacy `ProxyServer`.
- Each Celery scrape task pulls a proxy from the pool per request, with a configurable random delay (`asyncio.sleep`) between requests to avoid rate-limiting — same behavior as legacy, implemented as an explicit, documented rate-limit-avoidance setting (not silent evasion) since this is your own product with your own ToS posture to decide on.

---

## 7. Deployment
- **Backend:** Docker Compose for dev (FastAPI + Celery worker + Redis + 2x Postgres); production on a VM or container host (Fly.io/Render/self-hosted). Playwright needs its browser binaries installed in the worker image (`playwright install chromium`).
- **Frontend:** static build (`vite build`) served via Nginx or a static host (Vercel/Netlify/S3+CDN); talks to backend over REST+WSS.
- **Licensing/updates:** replace the `updateGB.txt` version-check-on-a-text-file pattern with a simple `/api/version` endpoint the frontend checks on load, and license gating enforced server-side on the job-creation endpoint (not a client-side title bar swap that's trivial to patch).

---

## 8. What's Deliberately Dropped From the Legacy App
- EO.WebBrowser/Chromium embed → Playwright (actively maintained, no embedded-control licensing).
- Dead PhantomJS fallback path → removed entirely.
- `db32.dll` encrypted-blob credential scheme → normal secrets management (env vars/secrets manager), since there's no "vendor asset to protect from the client" concern when you own both ends.
- Process-level watchdog (`GLeadsLauncher.exe` + flag file) → Celery worker retry/autoscale + container restart policy.
- WinForms → React web UI (cross-platform, no .NET Framework 4.x dependency).

---

## 9. Build Order (suggested)
1. Geo DB seed script (GeoNames import) + `/api/geo/*` endpoints + location cascade UI — unblocks job creation forms early.
2. Google Maps scraping module (search → place list → place detail) as a standalone script first, prove it against real pages, then wrap in Celery task.
3. Job API + Celery wiring + WebSocket progress + results grid — the vertical slice.
4. Email/website mining module.
5. Export (CSV first, then XLSX/KML).
6. Bing Maps module (mirrors step 2's interface).
7. Proxy pool + rate limiting.
8. Auth/licensing.
