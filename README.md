# Lead Generation Scraper

Scrapes Google/Bing Maps for business leads (name, address, phone, website, email),
tracks each run as a job, streams progress live, and exports the results as
CSV/XLSX/KML.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design and [MODULES.md](MODULES.md)
for the build checklist.

## Layout

- `backend/` — FastAPI + Celery + Playwright scraping engine (Python 3.12)
- `frontend/` — React + Vite + TypeScript UI
- `scripts/` — the dev runner and its helpers (Node, no dependencies)

## Run it

```bash
npm run dev
```

That's the whole thing. From a cold checkout it will, skipping whatever's already
done:

1. write `backend/.env` from `.env.example`
2. `docker compose up -d app_db geo_db redis` and wait for all three healthy
3. create `backend/.venv`, `pip install -e ".[dev]"`, `playwright install chromium`
4. `npm install` in `frontend/`
5. run Alembic to `app@head` and `geo@head`
6. provision a dev user + license
7. start uvicorn, the Celery worker and Vite in one terminal, and open the browser

```
UI    http://localhost:5173
API   http://localhost:8000/docs
Login dev@local.test / devpassword
```

Ctrl-C stops all three. The first run takes a few minutes (pip + Chromium +
npm); later ones start in seconds.

| Command | What it does |
|---|---|
| `npm run dev` | The above. `--no-worker`, `--no-open`, `--no-docker`, `--skip-install` are accepted after `--`. |
| `npm run setup` | Steps 1–6 only, then exit. |
| `npm run user -- you@example.com pw` | Add or reset an account (also extends its license). |
| `npm run seed` | Import GeoNames worldwide (~250 countries / 1.1M cities / 1.8M ZIPs) so the location pickers fill up. `-- --countries US,CA,GB` for a fast subset. |
| `npm run check` | Same three gates as CI: ruff, pytest, `tsc --noEmit`. |
| `npm run smoke` | Playwright browser check (`scripts/playwright_smoke.py`). |
| `npm run dev:docker` | The whole stack in containers instead (`docker compose up --build`). |
| `npm run reset` | `docker compose down -v` — wipes both databases. |

Ports come from `API_PORT`/`UI_PORT` if you need to move them. Both are strict:
if something else holds one, the runner says so instead of quietly picking
another.

### Containers instead

```bash
npm run dev:docker
```

Both Postgres instances, Redis, an Alembic pass against each DB, the API, a Celery
worker, and the built frontend behind nginx. Ordering is healthcheck-driven, so a
cold start (empty volumes, `initdb` running) works without retries. The UI is on
http://localhost:5173 either way — nginx proxies `/api` (and the progress
WebSocket) to the backend, so the browser only ever talks to one origin and no API
hostname is baked into the bundle.

## Using the app

1. **Categories** — type keywords (comma/newline separated) or upload a CSV.
   Autocomplete is fed by `GET /api/categories`.
2. **Locations** — type to search Country → State → City, then tick some ZIP codes
   or take all of them; City also offers *All cities in this state*. All four
   levels are search boxes, not dropdowns: `npm run seed` loads the whole world,
   which is more options than a browser can render. Adding is **append** (keeps the
   queue, skips duplicates) or **replace** (discards it first). Typing `Austin, TX`
   by hand still works whether or not the seed has run, but it searches the whole
   area in one query — see below.
3. **Jobs** — the keyword list and the ZIP queue are both shown on the job form;
   pick Google or Bing and start. Every keyword × ZIP pair becomes one `JobTarget`
   and one search, and the count is shown before you commit.
4. **Results** — the grid fills live over the job's WebSocket. Above it, a **Live
   activity** feed shows what the workers are doing right now: the search being
   scrolled, how many places it turned up, each place page as it opens, the
   fields scraped off it, and any retry or rate-limit backoff. The per-target
   table underneath counts places (`placesDone/placesFound`). Quick filter,
   column picker and a client-side CSV dump are in the grid toolbar.
5. **Export** — CSV/XLSX/KML; generation is a Celery task, so the page polls
   until the download is ready.
6. **Settings** — scrape concurrency and the **deep website crawl** (below).
   Installation-wide, not per-account: there is one worker fleet.
7. **Account** — plan, seats, expiry, API version.

The keyword list and the ZIP queue live in the browser (`localStorage`), not the
database — the backend has no categories or locations table, and `create_job`
takes the areas inline.

### Deep website crawl

Off by default; the switch is on the **Settings** page. With it on, every result
that has a website gets that website *walked* rather than skimmed, and everything
found is added to the row:

- **Emails** — `mailto:` links, Cloudflare-obfuscated addresses, plain text, and
  the `info [at] example [dot] com` dodge.
- **Phone numbers** — `tel:` links, WhatsApp click-to-chat links, the schema.org
  JSON-LD block, and validated numbers printed in the page text.
- **Social profiles** — Facebook, Instagram, LinkedIn, X/Twitter, YouTube,
  TikTok, WhatsApp each get their own column, with Pinterest, Telegram, Yelp and
  friends joined into **Other socials**. Share buttons and empty theme
  placeholders (`href="https://facebook.com/"`) are not profiles and are dropped.

**It appends, it does not replace.** The Email and Phone columns hold a
comma-separated list with the Maps value first. A number or address that appears
in both places is kept once — the comparison is on the number itself, so Maps'
`+1 512-555-0100` and the site's `(512) 555-0100` do not both land in the column.

**Not just the home page.** The crawler reads `robots.txt` (which it obeys) and
the site's own sitemap, then works through internal links in priority order:
`/contact`, `/impressum`, `/kontakt`, `/contacto`, `/about`, `/team`,
`/locations` first, dated blog archives last. So a 25-page budget on a 400-page
site still lands on the pages that carry contact details, and a site whose menu
is rendered in JavaScript is still reachable through its sitemap.

**It costs time.** One crawl runs per result, so a 2000-place job means 2000
crawls; expect a run to take noticeably longer with it on. Pages per site is the
dial (Settings page, default 25); depth, wall-clock, response size and
concurrency are capped in `.env` (`DEEP_CRAWL_*`). Turning it off applies to
places still queued, not just to new jobs.

### Why one search per ZIP

Maps stops feeding its results list at roughly a couple of hundred places per
query. "Plumber in Austin" therefore returns a slice of Austin's plumbers no
matter how patiently the feed is scrolled. Splitting the city into its 74 postal
codes makes each query small enough that the ceiling stops binding, so the same
city yields several times the leads — at the cost of 74 browser sessions instead
of one. That is why the target count on the job form is worth reading before
starting: it is roughly the cost of the run. A job over `MAX_JOB_TARGETS` (2000)
is refused, so split a whole-state sweep across several jobs or fewer keywords.

It also fills in the grid's City/State/Country/ZIP columns. Google's place panel
gives one unsplit address string and nothing parses it, so those four come from
the target's own ZIP — which the search already knew. Hand-typed locations carry
no ZIP, so their rows leave those cells blank.

### Geo coverage

`npm run seed` loads the world from four GeoNames exports. Downloads are ~35MB
and cached in `backend/tmp/geonames`; the load itself takes about ten minutes,
most of it spent populating the trigram search indexes as the rows land. It
replaces the tables wholesale inside one transaction, which takes an exclusive
lock — **the location pickers stop answering until it finishes**, so don't reseed
a live instance mid-use. What you get:

| Level | Rows | Source |
|---|---|---|
| Countries | ~250 | `countryInfo.txt` — every country |
| States / regions | ~4,000 | `admin1CodesASCII.txt` — every first-level division |
| Cities / areas | ~1,250,000 | postal export, plus `cities500` (villages and neighbourhoods) |
| ZIP codes | ~1,826,000 | postal export — 121 countries; see below |

### Countries without postal codes

**121 of the 252 countries have postal codes. The other 131 mostly don't have a
postal system at all** — Hong Kong, Ghana, Qatar, Panama and many more have never
had one, so no dataset can supply ZIPs for them. A handful (Nigeria, Tanzania) do
have national schemes that simply aren't in any free bulk dataset; OpenStreetMap
carries scattered `addr:postcode` tags but as per-building address data, not a
postal-code gazetteer, and Overpass is far too slow to seed from.

So for those countries the picker switches to **area mode**: the state's places
become the search areas and you multi-select them exactly as you would ZIPs. That
loses nothing that matters, because the ZIP was only ever a way to cut a city into
pieces small enough that Maps' result ceiling stops binding — and a place list
does that too. Lagos State comes out as 33 areas (Agege, Ikeja, Ikoyi, Apapa,
Festac Town …) rather than one query for "Lagos".

The mode is decided per state from the data (`regionHasZips`), not from a
hardcoded country list, so anywhere that gains postal data in a later seed starts
using it automatically.

Re-running the seed is safe. Rows are keyed by a deterministic UUID of their
name, so ids don't change and a ZIP queue saved in your browser still resolves
afterwards.

**One city, one entry.** GeoNames' postal file names the *delivery area*, which
in some countries is the post office rather than the town — Pakistan lists 54000
as "Lahore Gpo", 54020 as "Lahore Alflah" and so on. Left alone that fills the
City dropdown with thirty one-ZIP "Lahores". The seed folds those onto the real
city, so you get one **Lahore** with its 31 postal codes underneath. Genuinely
separate towns that merely contain the name (Nawan Lahore, Wagha Lahore) stay
separate.

### Accounts

There's no self-serve signup — `licenses` is the paid gate. `npm run dev`
provisions `dev@local.test` / `devpassword` with a 365-day licence on first boot.
For anything else:

```bash
npm run user -- you@example.com yourpassword
# in containers:
docker compose exec backend python scripts/create_user.py you@example.com yourpassword
```

Job creation returns 402 without a non-expired row in `licenses` for that user;
the UI says so on the job form and the Account page rather than just failing.

### Waterfall Email & Mobile Phone Enrichment

When internal website mining discovers no email or only generic role-based inboxes (`info@`, `contact@`, `sales@`, `support@`, `admin@`, etc.), Scrrapi can automatically cascade through third-party data enrichment APIs (Hunter.io, Prospeo.io, Datagma, Findymail) to acquire direct, verified decision-maker emails and direct personal mobile numbers.

Configure provider API keys in `.env` or dynamically at runtime via the **Settings** page:

```env
WATERFALL_ENRICHMENT_ENABLED=true
WATERFALL_PROVIDERS=["hunter","prospeo","datagma","findymail"]
HUNTER_API_KEY=your_hunter_api_key
PROSPEO_API_KEY=your_prospeo_api_key
DATAGMA_API_KEY=your_datagma_api_key
FINDYMAIL_API_KEY=your_findymail_api_key
```

- **Trigger conditions:** Runs only when direct email is missing or generic.
- **Cascade order:** Stops cascading as soon as direct email and mobile numbers are found.
- **Provenance:** Tracked in `email_source` and `phone_source` (`waterfall:<provider>`).

### GBP Unclaimed / Unverified Listing Detection

Scrrapi detects whether a Google Business Profile (or Bing Maps listing) has the "Claim this business" prompt, exposing `is_unclaimed` on the lead record and across exports (CSV, XLSX, JSONL, Google Sheets). Unclaimed listings provide immediate, prime outreach opportunities for digital marketing agencies, SEO specialists, and reputation management consultants.

### Driving it from the API instead

Every endpoint except `/api/health` needs a bearer token from
`POST /api/auth/login`.

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -d 'username=dev@local.test&password=devpassword' | jq -r .access_token)

JOB=$(curl -s -X POST http://localhost:8000/api/jobs/ \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"keywords":["plumber"],"locations":["Austin, TX"],"source":"google"}' | jq -r .id)

curl -s http://localhost:8000/api/jobs/$JOB -H "Authorization: Bearer $TOKEN"
curl -s "http://localhost:8000/api/jobs/$JOB/results?page=1" -H "Authorization: Bearer $TOKEN"
```

A bare string like that is one broad search. To get the per-ZIP behaviour the UI
produces, send objects instead — `zipCode`/`city`/`region`/`country` are what end
up on the result rows:

```bash
curl -s "http://localhost:8000/api/geo/zips?city=$CITY_ID" -H "Authorization: Bearer $TOKEN"

curl -s -X POST http://localhost:8000/api/jobs/ \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"keywords":["plumber"],"source":"google","locations":[
        {"label":"78701, Austin, Texas","zipCode":"78701","city":"Austin","region":"Texas"},
        {"label":"78702, Austin, Texas","zipCode":"78702","city":"Austin","region":"Texas"}
      ]}'
```

### Controlling a job that's already running

```bash
curl -s -X POST http://localhost:8000/api/jobs/$JOB/pause  -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/api/jobs/$JOB/resume -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/api/jobs/$JOB/cancel -H "Authorization: Bearer $TOKEN"
curl -s -X DELETE http://localhost:8000/api/jobs/$JOB     -H "Authorization: Bearer $TOKEN"
```

Same four controls sit on each row of the jobs table and in the results header.
What they mean:

- **Pause** is a queue gate, not a freeze. No new areas are dispatched and any
  area sitting on the broker unstarted is pulled back, so its slot goes to
  another job immediately — but areas *already being scraped* run to completion.
  A feed scrape holds the only copy of the place URLs it scrolled, so killing one
  mid-flight doesn't save the work, it throws it away and re-scrapes the area
  (duplicating the rows already written) on resume. Expect leads to keep arriving
  for a minute or two after pausing; the UI says so.
- **Resume** puts it back in the pool and dispatches straight away rather than
  waiting for another job's target to finish.
- **Cancel** is terminal: unfinished areas are dropped and running tasks are
  revoked (with `terminate`, so a wedged browser doesn't hold a slot). Leads
  already collected are kept, and a cancelled job still exports.
- **Delete** removes the job, its targets, its results and its exports — files on
  disk included. A job that's still live is cancelled first, so `DELETE` works
  from any status.

Anything a control can't do from the job's current status is a 409, and each job
payload carries an `actions` block (`{pause, resume, cancel, delete}`) saying
which are legal right now, so the UI never offers one that would fail.

Revoking is a best-effort broadcast to whatever workers are listening, so it is
not what makes any of this correct: every task re-reads the job's status when it
starts, and place tasks re-read it again before writing a row. A worker that was
down during a cancel picks the task up later, sees the job, and exits without
opening a browser.

## Checks

```bash
npm run check
```

CI runs the same three on every push (`.github/workflows/ci.yml`). Live scraping is
deliberately not in CI — run `npm run smoke` locally to verify the browser install
instead.

## Known limitations

- **CRM Integrations (HubSpot, GoHighLevel, Pipedrive)** are fully wired server-side with an OAuth2 handshake/mock token exchange and direct contact sync supporting automatic deduplication against existing CRM contacts (`backend/app/export/crm.py` and `backend/app/api/routers/integrations.py`). Users can trigger "Push to CRM" from the Lead Detail drawer.
- **Slack, Generic REST, and Google Sheets** remain UI-only or awaiting specialized writer implementations.
- **`npm run lint` (frontend)** now has a working ESLint config
  (`frontend/.eslintrc.cjs`) — it previously had no config at all and the
  script errored before checking anything. Running it today surfaces some
  pre-existing findings (a couple of real `react-hooks/rules-of-hooks`
  false-positives from locally-defined functions named `usePack`/`useAreaSet`
  that aren't actually hooks, some `react/no-unescaped-entities` nits, and
  `react-refresh` warnings on files that export both a component and
  constants) — none introduced by this pass, left for a follow-up cleanup
  rather than folded silently into an unrelated change.

## Operations

- **Logs** are one JSON object per line in containers; `npm run dev` sets
  `LOG_FORMAT=text` for readable local output. Scraping lines carry `job_id`,
  `target_id`, `place_url` and `source`, so one job's whole path is
  `docker compose logs worker | grep <job_id>`.
- **`npm run dev`'s terminal stays thin on purpose** — one status line per
  step/service, nothing per-request or per-scrape. The full stream for each
  service is under `logs/` at the repo root (`api.log`, `worker.log`,
  `ui.log`, plus one-shot install/migration logs); the API and worker also
  write their own structured JSON record to `logs/api.log`/`logs/worker-app.log`
  via `LOG_FILE` (`app.core.logging`), independent of console verbosity. The
  Dashboard's **Live log** panel (`SystemLogPanel`, `/api/system/events/stream`)
  is the other place logs surface, for anything you'd otherwise `grep` for
  live rather than after the fact.
- **Job progress** is two-phase per target: scroll the feed for place URLs
  (`places_found`), then scrape each one (`places_done`). A target — and so the
  job — only reports `done` once those meet, which is what stops a job going
  green while its places are still queued.
- **Scrape concurrency** — how many areas (keyword × location targets) are scraped
  at once — is a runtime setting on the **Settings** page, stored in the app DB and
  read by every worker, so changing it needs no restart. Creating a job no longer
  puts the whole cross product on the broker: targets wait as `queued` until a slot
  frees up (`app/workers/dispatch.py`). `DEFAULT_CONCURRENT_TARGETS` seeds it,
  `MAX_CONCURRENT_TARGETS` caps what the UI will accept -- and is also the fixed
  size the worker's own pool starts at (see below), so this slider is the *only*
  concurrency control anyone needs to touch.
- **Worker pool size** is a different, lower-level thing: `--concurrency` (Docker)
  / `--pool=threads --concurrency` (Windows dev, since Celery's prefork pool
  doesn't run there and `solo` scrapes one place at a time) sizes the pool that
  runs individual place scrapes inside an active area. It's started fixed at
  `MAX_CONCURRENT_TARGETS` rather than read from an env var, because Celery has
  no way to resize a running pool on every backend (the Windows `threads` pool
  in particular has no resize primitive at all) -- so instead of a second knob to
  keep in sync, the pool is simply always big enough for whatever the Settings
  slider above sends it. Idle threads/processes cost nothing: a browser only
  opens once a task is actually picked up.
- **Retries** back off exponentially with jitter; a 429 or block interstitial sets a
  per-host cooldown that doubles per consecutive hit and floors the retry countdown.
  Tune with `TASK_RETRY_*` and `RATE_LIMIT_*` in `.env`.
- **Getting blocked a lot?** Raise `SCRAPE_MIN_DELAY_MS`/`SCRAPE_MAX_DELAY_MS`, or
  set `PROXY_MODE=list` with a `PROXY_LIST_PATH`.
- **Job crawling slowly with the deep crawl on?** Lower *Pages per website* on the
  Settings page, or turn the crawl off — both apply to the places still queued,
  not only to the next job. `DEEP_CRAWL_TIMEOUT_S` (45s) is the hard ceiling one
  site can cost; a job that spends all of it is hitting sites that are slow, not
  a bug.
- **Database ports.** The two Postgres instances can't both take 5432 on the host,
  so compose publishes app on **5434** and geo on **5433**; `backend/.env` points
  at those. Inside compose the service hostnames override them.
# Claude Code — Figma Screen-by-Screen Implementation Workflow

This package is a reusable Claude Code workflow for taking an existing application,
replacing its existing frontend UI with the Figma design, filling genuine backend
feature gaps when the design requires them, and implementing **exactly one screen
per execution cycle**.

## Core behavior

1. Inspect the existing repository before changing anything.
2. Treat Figma as the visual source of truth and the existing backend as the
   functional source of truth unless a Figma-required feature is genuinely absent.
3. Remove the existing UI cleanly instead of layering the new UI over old UI.
4. Reuse existing backend APIs whenever they satisfy the screen.
5. If the Figma/spec requires a capability that the backend does not provide,
   implement the smallest production-ready backend addition required.
6. Implement one screen only.
7. Run verification/QA for that screen.
8. STOP. Do not start the next screen.
9. Only continue when the user explicitly says `continue`.

## Included

- `CLAUDE.md` — master agent instructions.
- `docs/WORKFLOW.md` — detailed operating procedure.
- `docs/SCREEN-STATE-MATRIX.md` — how to turn a screen list into implementation units.
- `docs/BACKEND-GAP-POLICY.md` — rules for deciding when backend work is justified.
- `docs/FRONTEND-RESET-POLICY.md` — rules for removing old UI safely.
- `docs/FIGMA-MCP-PROTOCOL.md` — Figma inspection and placement rules.
- `docs/QA-GATE.md` — definition of done for every screen.
- `.claude/skills/*` — task-specific skills.
- `.claude/commands/next-screen.md` — explicit continuation command.
- `scripts/workflow-state.js` — local state helper for the one-screen gate.
- `INITIATOR-PROMPT.md` — paste this into Claude Code to start the workflow.
- `SCREENLIST.md` — the supplied screen handoff.

## Expected usage

Run Claude Code from the root of the existing project after copying this package
into the project.

Start with the initiator prompt.

After Claude finishes one screen, it must stop. Say:

    continue

to authorize the next screen.

The agent must never interpret a successful screen implementation as permission to
continue automatically.
