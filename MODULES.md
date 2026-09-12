# Build Modules — tackle one at a time

Checklist, ordered. Each module = one sitting, one thing working end to end. Check off as done.
Files referenced already exist as stubs from the scaffold — fill in the `NotImplementedError`.

`npm run dev` at the repo root does every setup step below that can be automated
(infra, venv, Chromium, npm install, both migrations, dev user) and then runs the
API, worker and UI together. See the README.

---

## Phase 0 — Foundations

- [x] **0.1 Local infra up**
  Files: `docker-compose.yml`, `backend/.env`
  Run `docker-compose up -d app_db geo_db redis`. Confirm both Postgres instances and Redis are reachable (`psql`, `redis-cli ping`).
  `scripts/dev.mjs` starts these and blocks on their healthchecks. Compose publishes
  app_db on **5434** and geo_db on **5433** — they can't both have 5432 — and
  `.env.example` now matches.

- [x] **0.2 App DB migrations**
  Files: `backend/app/db/migrations/`, `backend/alembic.ini`
  `alembic revision --autogenerate -m "init app tables"` against `AppBase.metadata`, then `alembic upgrade head`. Confirm `users/licenses/jobs/job_targets/results/exports` tables exist.

- [x] **0.3 Geo DB migrations**
  Files: same migrations dir, `-x target=geo`
  Same as above but against `GeoBase.metadata` → `country/region/city/zip_code` tables.

- [x] **0.4 FastAPI boots + health check passes**
  Files: `backend/app/main.py`, `backend/tests/test_health.py`
  `uvicorn app.main:app --reload`, hit `/api/health`, run `pytest`. Already mostly wired — just verify.

- [X] **0.5 Frontend boots**
  Files: `frontend/`
  `npm install && npm run dev`, confirm blank routed pages load at `/`, `/categories`, `/locations`, `/account`.

---

## Phase 1 — Geo reference data (unblocks location UI early)

- [x] **1.1 GeoNames seed script**
  File: `backend/scripts/seed_geo.py` (`npm run seed`)
  Seeds **the whole world** by default — ~250 countries, ~4k regions, ~1.25M
  cities/areas, ~1.8M postal codes — from four GeoNames exports, because no single
  one has all four levels: `countryInfo.txt` (every country), `admin1CodesASCII.txt`
  (every state/province), the postal export (ZIPs and their towns, 121 countries),
  and `cities500.zip` (~235k places, down to villages and neighbourhoods) for the
  other 131. `--countries US,CA,GB` is the fast dev subset. Truncate-first.

  `cities500` rather than `cities15000`: those places are the *search areas* where
  postal codes don't exist, so a 15k-population floor is useless — it yields whole
  towns, which is the granularity the per-ZIP split exists to get away from.
  cities500 gives Lagos State 33 areas instead of a handful.

  **`CityResolver` — what a postal row's "city" actually is.** The postal export's
  `place_name` is whatever the national post office calls a delivery area, and
  that is only sometimes a city. In the US it is ("Austin"); in Pakistan it is the
  individual post office — "Lahore Gpo", "Lahore Alflah", "Lahore Model Town" —
  so taking it literally put thirty one-ZIP "cities" in the City dropdown instead
  of one Lahore with thirty ZIPs. A locality folds onto a real place name (from
  cities500) on a **word-prefix match**, longest match first. Longest-first is
  what leaves the US alone: a place_name that *is* a known city matches itself
  exactly, so no shorter prefix can steal it (Kansas City ↛ Kansas).

  Coordinates can veto the match, but only when the row's `accuracy` column is 4+
  (a real gazetteer position) rather than 1 (estimated). That distinction is the
  whole fix: every Lahore post office is accuracy 1 and plotted hundreds of km
  away — "Lahore Model Town" lands in the Cholistan desert, 516km out — so an
  unconditional distance check rejected precisely the rows it was meant to repair,
  while "Nawan Lahore" and "Wagha Lahore", which must stay separate, are accuracy
  4. Both seed passes call it through `city_for`; they compute `city_id` from the
  result, so a disagreement would orphan every postal code. Net effect worldwide
  is small — 1.5% of rows rewritten. Covered by `tests/test_city_resolver.py`.

  Three things make world scale work. Ids are `uuid5` of the natural key, not
  `uuid4`, so a child row recomputes its parent's id instead of the script
  holding a million-entry map — and ids stay stable across re-seeds, so a
  location queue saved in someone's browser survives a data refresh. Rows go in
  via Postgres `COPY` rather than executemany, which is the difference between
  seconds and minutes for 1.8M rows. And the wipe is `TRUNCATE`, not `DELETE` —
  `DELETE FROM city` re-checks the zip_code foreign key for every one of a
  million rows and takes minutes on its own. The run ends with `ANALYZE`; freshly
  COPY'd tables have no statistics, and without them the planner ignores the
  search indexes and type-ahead seq-scans every city.

- [x] **1.2 Geo API — countries**
  File: `backend/app/api/routers/locations.py::list_countries`
  Query `country` table, return `[{id, name, code}]`.

- [x] **1.3 Geo API — regions/cities/zips**
  Same file, remaining 3 endpoints. Each filters by parent id, indexed lookup.
  Every level takes `q=` and is capped (`geo_page_limit`, 200) — with the world
  seeded, `/cities` over one region can be tens of thousands of rows. Matching is
  starts-with then contains, prefix hits ranked first, wildcards in user input
  escaped. Countries are exempt from the cap: ~250 rows ship whole and the picker
  filters them locally.
  `/cities` and `/zips` answer `{items, total, truncated}` — a bare list can't say
  it was capped, and "select all" over a capped list queues the wrong areas.
  `/zips` takes `city=` **or** `region=` (every city in the state) and its rows carry
  `cityName`, because a region-wide list spans cities and each label needs its own.
  `/cities` also returns `regionHasZips` (an EXISTS, not a count — some regions hold
  six figures of postal codes and the caller only needs zero-or-not). That flag is
  what puts the picker into area mode for the 131 countries with no postal system.

  Needs `c93f5a08d1e7` (geo branch) — `text_pattern_ops` + pg_trgm indexes. The DB
  collates `en_US.utf8`, so without them even `name LIKE 'Aus%'` is a seq scan.

- [x] **1.4 ZipCascadeSelect component**
  File: `frontend/src/components/ZipCascadeSelect.tsx` (was `LocationCascadeSelect`)
  Country → State → City → ZIP, all four as type-to-search `Autocomplete`s: at world
  scale nothing but the country list can be rendered as a list of options. Region,
  city and ZIP query the server on a 250ms debounce (`hooks/useDebounced.ts`) with
  `keepPreviousData` so the list doesn't flicker empty between keystrokes, and
  `filterOptions={(x) => x}` so MUI doesn't re-filter what the server already ranked.
  Picking a parent resets its children. Emits ready-to-queue `LocationTarget`s,
  not geo ids.

  The last level is multi-select with select-all and runs in one of two modes.
  **ZIP mode**: City is a single select with an extra "All cities in this state"
  option, and the multi-select holds postal codes. **Area mode** (`regionHasZips`
  false): the City step is hidden and the multi-select holds the region's places
  instead — those countries have no postal system, so there is nothing to load and
  nothing to wait for. Both emit the same shape; an area target just has no
  `zipCode`. A city inside a ZIP-mode region that happens to have no codes of its
  own still gets the single "Use &lt;city&gt;" fallback.

- [x] **1.5 Locations page wired to real API**
  File: `frontend/src/pages/Locations.tsx`
  Builds the ZIP queue held in `state/JobDraftContext` (localStorage-backed) so the
  job form can read it. Adding is **append or replace** — a queue gets assembled over
  several passes and the destructive option has to be picked deliberately.
  Free-text entry sits alongside the cascade — `create_job` still takes bare label
  strings, so the page stays usable before 1.1 has ever been run; those search a
  whole area in one query and return far less than the same area covered ZIP by ZIP.

---

## Phase 2 — Auth & licensing (thin slice, enough to gate routes)

- [x] **2.1 User model + password hashing**
  Files: `backend/app/db/models/user.py`, `backend/app/core/security.py`
  `hash_password`/`verify_password` implemented, covered by a unit test.

- [x] **2.2 Login endpoint issues JWT**
  File: `backend/app/api/routers/auth.py::login`
  Verify credentials, return `create_access_token`.

- [x] **2.3 `get_current_user` dependency enforced**
  File: `backend/app/api/deps.py`
  Protect one real endpoint (start with `/api/jobs`) with `Depends(get_current_user)`.

- [x] **2.4 License check**
  Files: `backend/app/db/models/license.py`, `backend/app/api/deps.py::require_active_license`
  Query `licenses` table for user, 402 if expired/missing. Swap `get_current_user` → `require_active_license` on job-creation route.

- [x] **2.5 Account page**
  File: `frontend/src/pages/Account.tsx`
  Show plan/seats/expiry from `/api/auth/license`.
  Sign-in lives at `/login` (`auth/AuthContext` + `components/RequireAuth`); a 401
  from any call clears the session rather than leaving the UI retrying a dead token.

---

## Phase 3 — Google Maps scraping core (the meat)

- [ ] **3.1 Playwright smoke test**
  New file: `backend/scripts/playwright_smoke.py`
  Launch headless Chromium, load any URL, screenshot. Confirms `playwright install chromium` worked in the container/venv.

- [x] **3.2 Search URL builder**
  File: `backend/app/scraping/google_maps/query.py::build_search_url`
  `keyword + location → google.com/maps/search/...` string. Unit test with a couple of inputs.

- [x] **3.3 Feed scroller — collect place URLs**
  File: `backend/app/scraping/google_maps/feed.py::get_place_urls`
  Load search URL, scroll `div[role="feed"]`, count `a.hfpxzc` anchors until growth stalls, timeout guard. Return list of `/maps/place/` URLs. Test against one real query manually first (not in CI).

- [x] **3.4 Place detail scraper**
  File: `backend/app/scraping/google_maps/place.py::get_place_data`
  Open one place URL, extract name/address/phone/category/rating/lat/long, spoofed UA. Return `PlaceData` dict.
  `address` still comes back as one unsplit string, but `results.city/state/country/zip_code`
  are no longer NULL: the search runs per ZIP, so `scrape_place` copies the geo off the
  `JobTarget` that produced the place (`tasks.py::_target_area`). The columns are visible
  in the grid again. Rows from a hand-typed location have no ZIP behind them and stay blank.

- [ ] **3.5 Data block / packed response parser (only if not using network interception)**
  File: `backend/app/scraping/common/data_block.py::parse_packed_response`
  Decide first: scrape rendered DOM (3.3/3.4 above) vs intercept the XHR JSON via Playwright `page.on("response")`. Pick one path, implement it, drop the other.

---

## Phase 4 — Website + email mining

- [x] **4.1 Website validator**
  File: `backend/app/scraping/common/website_finder.py::get_website`
  Given a candidate URL from the listing, fetch with `httpx`, confirm it resolves/loads.

- [x] **4.2 Startpage fallback search**
  Same file, `search_website_on_startpage`
  When listing has no website: search business name + location, return best candidate URL.

- [x] **4.3 Email extraction**
  File: `backend/app/scraping/common/email_miner.py`
  `extract_first_valid_email` (regex over page HTML/mailto: links), `is_valid_email` (use `email-validator`), `get_domain_from_email`.

- [x] **4.4 Wire into place pipeline**
  File: `backend/app/scraping/common/place_enrichment.py::enrich_place_data`
  Connects 3.4 → 4.1/4.2 → 4.3 into one function: place data in, `email`/`website` fields filled in the result.

- [x] **4.5 Deep site crawler**
  Files: `backend/app/scraping/common/site_crawler.py`, `phone_miner.py`,
  `social_miner.py`, `structured_data.py`; settings in `app/core/runtime_settings.py`
  and `app/api/routers/settings.py`; UI in `frontend/src/pages/Settings.tsx`.

  Off by default, switched on from the Settings page. When a result has a
  website, the whole site is walked rather than just its home page: `robots.txt`
  for the rules and the `Sitemap:` lines, then a frontier of internal links and
  sitemap URLs **ordered by how contact-ish the path looks** (`/contact`,
  `/impressum`, `/kontakt`, `/about`, `/team` first, dated blog archives last).
  That ordering is what makes a 25-page budget useful on a 400-page site; the
  sitemap is what finds the contact page on a site whose menu is rendered
  client-side and therefore has no crawlable link to it.

  Four extractors run per page, because a business publishes its address in one
  of four ways and only one of them is a plain `mailto:`: Cloudflare's
  `data-cfemail` hex blobs are decoded, `info [at] example [dot] com` is
  reassembled, and the schema.org JSON-LD block is parsed separately — that last
  one is where the phone number lives on most site-builder sites, and the text
  scan can't reach it because script bodies are stripped before it runs (they
  are full of timestamps and ids that read as phone numbers).

  **Everything found is appended, not substituted.** `results.email`/`phone`
  become `", "`-joined lists with Maps' own value first, widened to 1000/500 by
  `f1c7d9a3b204`. Deduplication is on identity: `phone_key` compares the last
  nine digits, so Maps' "+1 512-555-0100" and the site's "(512) 555-0100" are one
  number. Social profiles get eight new columns (`facebook` … `whatsapp`,
  `other_socials`), hidden in the grid until a row actually has one.

  Bounded in every dimension (`DEEP_CRAWL_*` in `.env`): pages, depth,
  wall-clock, response size, concurrency. It runs once per place, so a 2000-place
  job pays for 2000 crawls — which is why the toggle is read per place rather
  than per worker, and turning it off mid-job applies to the places still queued.

- [x] **4.6 Data Enrichment Depth**
  Files: `backend/app/scraping/common/decision_maker_miner.py`,
  `mobile_miner.py`, `review_sentiment.py`, `structured_data.py`, `place_enrichment.py`;
  DB migration `e8f1a2c3b4d5_add_data_enrichment_depth_columns.py`; UI in
  `frontend/src/components/LeadDetailDrawer.tsx` and `ResultsGrid.tsx`.

  Enriches leads beyond store-level general contact details:
  1. **Decision-maker discovery**: Extracts Owner, Founder, CEO, and executive
     names & titles across structured schema.org JSON-LD (Person/jobTitle/founder
     nodes), semantic HTML team/leadership cards, and contextual patterns
     ("Owner: Jane Smith", "Founded by John Doe", "Jane Smith, CEO").
  2. **Direct personal mobile phone numbers**: Discovers direct cell/mobile lines
     using wa.me/sms links, labeled phone runs ("Mobile:", "Direct:", "Cell:"),
     and international mobile numbering plan heuristics (UK 07xxx, DE 015/016/017,
     FR 06/07, ES 6xx/7xx, IT 3xx, AU 04xx), distinguishing direct lines from general
     switchboards.
  3. **Customer review sentiment analysis & pain-point extraction**: Analyzes
     Google Maps customer reviews, computing sentiment scores/labels (Positive,
     Neutral, Mixed, Negative) and extracting customer pain points (long wait times,
     overpriced/hidden fees, rude customer service, communication friction, subpar quality).
  Wired into the result schema, lead scoring weights, exports (CSV/XLSX/JSONL/Sheets),
  and UI drawers/grids.

- [x] **4.7 Waterfall Email & Mobile Phone Enrichment**
  Files: `backend/app/scraping/common/generic_email.py`,
  `backend/app/scraping/common/waterfall/` (`base.py`, `hunter.py`, `prospeo.py`, `datagma.py`, `findymail.py`, `engine.py`);
  `backend/app/scraping/common/place_enrichment.py`, `backend/app/workers/tasks.py`;
  Settings: `backend/app/core/runtime_settings.py`, `backend/app/api/routers/settings.py`;
  UI: `frontend/src/pages/Settings.tsx`, `frontend/src/pages/JobWizard.tsx`.

  Provides automated waterfall cascade for hard-to-reach local businesses:
  1. **Trigger conditions**: Conditionally executes when internal website crawler yields
     no email, OR when all discovered emails are generic role-based inboxes
     (`info@`, `contact@`, `sales@`, `support@`, `admin@`, etc.).
  2. **Waterfall cascade engine**: Cascades through configured third-party B2B contact
     enrichment APIs (Hunter.io, Prospeo.io, Datagma, Findymail) in priority sequence.
  3. **Enrichment matching**: Discovers direct verified personal emails, direct mobile phone
     lines, and executive decision-maker names using business domain, business name,
     location, and leadership records.
  4. **Provenance & tracking**: Tracks origin with `email_source = "waterfall:<provider>"`
     and `phone_source = "waterfall:<provider>"`.
  5. **Runtime management & UI**: Fully configurable via runtime settings and the Settings
     page with secure API key inputs, live toggle, and Job Wizard Step 3 integration.

- [x] **4.8 GBP Unclaimed / Unverified Listing Detection & Filter**
  Files: `backend/app/scraping/google_maps/place.py`, `backend/app/scraping/bing_maps/place.py`,
  `backend/app/db/models/result.py`, `backend/app/db/migrations/versions/26520f75246a_add_result_is_unclaimed_column.py`,
  `backend/app/workers/tasks.py`, `backend/app/api/routers/jobs.py`,
  `backend/app/export/csv_writer.py`, `backend/app/db/models/export.py`,
  `frontend/src/types/index.ts`.

  Detects whether a Google Business Profile (or Bing Maps listing) has the "Claim this business" prompt:
  1. **Scraping extraction**: Checks for existence of merchant claim link (`a[data-item-id="merchant"]` in GBP and `a[href*="placeservicesservice.bing.com"]` in Bing).
  2. **Persistence**: Stored in `results.is_unclaimed` (Boolean, nullable=True) via Alembic migration `26520f75246a`.
  3. **API & Export integration**: Exposed in API endpoints (`isUnclaimed`), export writers (CSV/XLSX/JSONL/Sheets), and TypeScript frontend contracts.

---

## Phase 5 — Proxy pool & rate limiting

- [x] **5.1 Single-proxy mode**
  File: `backend/app/scraping/proxy/pool.py::get_proxy`
  Just returns the configured `PROXY_SINGLE_URL`. Wire into Playwright context launch args.

- [x] **5.2 Random delay between requests**
  Same file, `delay()`
  `asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)`, called between place scrapes.

- [x] **5.3 List mode**
  Load proxies from `PROXY_LIST_PATH`, round-robin or random pick per request.

- [x] **5.4 Free-list mode (optional, lowest priority)**
  Fetch from an aggregator source, cache with TTL, same interface as 5.1/5.3.

---

## Phase 6 — Job orchestration (Celery wiring)

- [x] **6.1 Job creation endpoint**
  File: `backend/app/api/routers/jobs.py::create_job`
  Accepts keyword list + location list, creates `Job` + `JobTarget` rows, then asks the
  dispatcher (6.7) to start as many as the concurrency limit allows — it no longer
  enqueues the whole job at once.
  Driven from the job form on `frontend/src/pages/Dashboard.tsx`.
  A location is a `LocationSpec` (`label` + `zipCode`/`city`/`region`/`country`) or a
  bare string, normalized and label-deduplicated by `normalize_locations`. One search
  per ZIP means the cross product grows fast — every ZIP in Texas is ~2600 targets per
  keyword — so anything over `max_job_targets` (2000) is refused up front instead of
  accepted and left to starve the queue for a day.

- [x] **6.2 `scrape_google_maps` task**
  File: `backend/app/workers/tasks.py`
  Pulls a `JobTarget`, runs 3.2→3.3, enqueues `scrape_place` per URL found, updates target status.

- [x] **6.3 `scrape_place` task**
  Same file. Runs Phase 3/4 pipeline for one place, writes a `Result` row.

- [x] **6.4 Job list/detail endpoints**
  File: `jobs.py::list_jobs`, `get_job`
  Real DB queries, paginated.

- [x] **6.5 Job results endpoint**
  `jobs.py::get_job_results` — paginated `Result` rows for a job.
  Note the query params are `page`/`page_size` (snake_case), not `pageSize`.

- [x] **6.7 Scrape concurrency limit**
  Files: `backend/app/workers/dispatch.py`, `backend/app/core/runtime_settings.py`,
  `backend/app/api/routers/settings.py`, `frontend/src/pages/Settings.tsx`
  How many targets may be in flight at once, set from the Settings page and stored in
  `app_settings` so workers see a change without a restart. Targets are created
  `queued` with `dispatched_at` NULL and handed to the broker a slot at a time;
  `dispatch_ready_targets` runs on job creation, on every target reaching a terminal
  state, and when the setting is raised. Claiming is serialised with a Postgres
  advisory lock — two workers finishing together would otherwise both fill the same
  slot. A target dispatched but never started for `TARGET_DISPATCH_STALE_S` is
  re-issued; the original copy notices its `dispatch_id` no longer matches and exits
  rather than scraping the area twice.
  Scope: areas, not browser tabs. The places inside one area are still bounded by the
  worker pool (`WORKER_CONCURRENCY`).

- [x] **6.8 Queue controls: pause / resume / cancel / delete**
  Files: `backend/app/workers/control.py`, `jobs.py::pause|resume|cancel|delete`,
  `frontend/src/components/JobControls.tsx` (jobs table + results header)
  Statuses grow to `queued | running | paused | done | error | cancelled`; the sets and
  the roll-up rule live on `app/db/models/job.py` so the router, the dispatcher and the
  workers agree on what "finished" means.
  **Pause is a queue gate.** A paused job stops being a source of waiting targets
  (`dispatch._runnable_job`) and its dispatched-but-unstarted targets are revoked and
  put back in the waiting pool, freeing their slots for other jobs — but targets
  already scraping finish. Killing one mid-feed would discard the place URLs it had
  scrolled and re-scrape the area on resume, duplicating rows already written; letting
  it finish makes pause lossless.
  **Cancel** marks every unfinished target `cancelled` and revokes with `terminate`;
  results are kept and still exportable. **Delete** cancels first, then removes targets,
  results, exports and the files on disk. Illegal transitions are 409s, and each job
  payload carries an `actions` block so the UI offers only what the endpoint accepts.
  Revokes are best-effort broadcasts, so the guard that actually holds is in the tasks:
  `_abandon_reason` on scrape pickup, `_place_halt_reason` on place pickup *and* again
  before the insert (which is what stops a late row hitting a foreign key against a
  deleted job).

- [x] **6.6 Job status rolls up before its places finish**
  `_refresh_job_status` marks a job "done" once every `JobTarget` is terminal, but
  the `scrape_place` subtasks those targets enqueued are still running — observed
  results landing ~2 minutes after the job read "done". The status needs to account
  for outstanding place tasks (or the UI needs a separate "enriching" state).

---

## Phase 7 — Live progress (WebSocket)

- [x] **7.1 WS endpoint on backend**
  New route in `jobs.py` (add `@router.websocket("/{job_id}/stream")`)
  Push `{jobId, status, resultsCount}` on each `Result` insert / status change (simple: poll DB every N seconds server-side and push if changed; upgrade to pub/sub later).

- [x] **7.2 Frontend hook consumes it**
  File: `frontend/src/hooks/useJobSocket.ts`
  Already stubbed — confirm it receives real events, not just typed.
  Verified end to end: queued → running → done arrive live, both direct and through
  the dev-server proxy. Same-origin now (`ws: true` on Vite's `/api`, `Upgrade`
  headers in `nginx.conf`), so no separate WS host to configure.

- [x] **7.3 Results page live-updates**
  File: `frontend/src/pages/Results.tsx`, `frontend/src/components/ResultsGrid.tsx`
  Wire `ResultsGrid` to actual `/api/jobs/{id}/results` data + live count from the socket.
  A job already finished when the page opens closes the socket immediately, so the
  page falls back to the REST status/total rather than showing nothing.

---

## Phase 8 — Export

- [x] **8.1 CSV writer**
  File: `backend/app/export/csv_writer.py::write_csv`
  Column order fixed already (`COLUMNS`). Confirm output opens cleanly in Excel/Sheets.
  Writes a UTF-8 BOM, so accented names survive a double-click into Excel.

- [x] **8.2 Export job endpoint + Celery task**
  Files: `backend/app/api/routers/exports.py`, `backend/app/workers/tasks.py::export_job`
  POST enqueues, GET polls status + returns download URL once `file_path` set.

- [x] **8.3 XLSX writer**
  File: `backend/app/export/xlsx_writer.py::write_xlsx`
  `openpyxl`, same column order as CSV.

- [x] **8.4 KML writer**
  File: `backend/app/export/kml_writer.py::write_kml`
  Placemark per result with lat/long.

- [x] **8.5 Export page (frontend)**
  File: `frontend/src/pages/Export.tsx`
  Format picker, trigger, poll, show download link.
  The download goes through `fetch` + an object URL, not `<a download>` — the file
  route needs a bearer header an anchor can't send.

---

## Phase 9 — Bing Maps (mirror of Phase 3/4, once Google path is proven)

- [ ] **9.1 Bing search URL builder** — `backend/app/scraping/bing_maps/query.py`
- [ ] **9.2 Bing feed scroller** — `backend/app/scraping/bing_maps/feed.py`
- [ ] **9.3 Bing place scraper** — `backend/app/scraping/bing_maps/place.py`
- [ ] **9.4 Source toggle in job creation** — `create_job` accepts `source: "google" | "bing"`, `scrape_bing_maps` task in `tasks.py` wired same as 6.2.

---

## Phase 10 — Categories module

- [x] **10.1 Category list endpoint** — `backend/app/api/routers/categories.py::list_categories`
- [x] **10.2 CSV upload endpoint** — same file, `upload_categories`, parses uploaded file into keyword list
- [x] **10.3 Categories page (frontend)** — free-text entry + file upload UI, `frontend/src/pages/Categories.tsx`

---

## Phase 11 — Polish / hardening (do last, only once 1–10 work end to end)

- [x] **11.1 Celery retry/backoff tuning** on `scrape_place`/`scrape_google_maps` (replaces legacy watchdog)
  `app/workers/tasks.py::retry_countdown` — exponential + jitter, floored by a rate-limit cooldown when
  the failure was a block. Time limits, `task_reject_on_worker_lost`, and per-task queues in
  `app/core/celery_app.py`.
- [x] **11.2 Structured logging** across scraping tasks (job id, target id, place url in every log line)
  `app/core/logging.py` — JSON envelope + `log_context()` ContextVar binding, installed by `app.main`
  (API) and Celery's `setup_logging` signal (workers).
- [x] **11.3 Rate-limit/backoff on 429s** from Maps pages, not just fixed delay
  `app/scraping/common/rate_limit.py` — `guarded_goto()` replaces bare `page.goto` in both feed and
  place scrapers; per-host cooldown doubles per consecutive 429/503/interstitial, honours `Retry-After`.
- [x] **11.4 Dockerize end to end**, confirm `docker-compose up` runs the whole stack cold
  Healthcheck-gated ordering, one-shot `migrate` service, shared exports volume, nginx SPA config,
  `.dockerignore` for both images.
- [x] **11.5 CI**: `pytest` + `ruff` + `tsc --noEmit` on push
  `.github/workflows/ci.yml`. Ruff's rule set is pinned in `pyproject.toml` rather than left to the
  installed version's defaults.

---

## Phase 12 — App shell & one-command dev

- [x] **12.1 One command runs everything** — `npm run dev` (`scripts/dev.mjs`)
  Infra via compose (waited on healthchecks), venv + `pip install -e .[dev]` +
  Chromium, `npm install`, both Alembic branches, a dev user, then uvicorn + worker
  + Vite with prefixed output and one Ctrl-C. Every step is skipped when already
  done, so a warm start is seconds. `npm run setup/user/seed/check/smoke` cover the
  one-off tasks. Node builtins only — the root has nothing to install first.

- [x] **12.2 Single origin, no baked API host**
  Vite proxies `/api` (`ws: true`) and `/docs`; nginx does the same to `backend:8000`.
  `api/client.ts` uses relative URLs, so CORS never applies and the Docker image is
  no longer built per-hostname.

- [x] **12.3 Auth shell** — `/login`, `auth/AuthContext`, `components/RequireAuth`,
  and a persistent `AppLayout` (nav, license chip, light/dark, sign out).

- [x] **12.4 Job form** — `pages/Dashboard.tsx`
  Keyword draft and ZIP queue (`state/JobDraftContext`, localStorage-backed and
  shared with the Categories/Locations pages), source toggle, live target count,
  and the jobs table with links into results/export. Closes the "dashboard is still
  a stub" gap in the README. The location half is `components/LocationQueue.tsx`
  (read-only here, built on the Locations page); a draft saved by the pre-ZIP
  version reads back as label-only targets rather than being dropped.

- [x] **12.6 Native Two-Way CRM Sync (HubSpot, GoHighLevel, Pipedrive)**
  Files: `backend/app/export/crm.py`, `backend/app/api/routers/integrations.py`, `frontend/src/pages/Integrations.tsx`, `frontend/src/components/LeadDetailDrawer.tsx`
  Direct contact sync with automatic deduplication (matching on email and phone) and server-side OAuth2 handshake/mock token exchange. Integrated with "Push to CRM" actions on Lead Detail.

- [ ] **12.5 Not yet exercised end to end**
  5.1–5.4 (proxy pool), 8.3/8.4 (XLSX/KML writers), 9.x (Bing), and 1.1
  (`seed_geo.py`) are wired into the UI but have not been run against real data —
  the location cascade stays empty until the seed script is run.

---

## Suggested order for a solo build

Phase 0 → 1 → 2 (thin) → 3 → 4 → 5 (single mode only) → 6 → 7 → 8 (CSV only) → then loop back for 5 (list mode), 8 (xlsx/kml), 9, 10, 11.
Don't build Bing (9) or polish (11) until Google end-to-end (3→8) actually produces a CSV of real leads.
