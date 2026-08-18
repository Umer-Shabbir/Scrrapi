# MapScrape — Screen List (Dev Handoff)

Full context per screen for an implementing dev agent. Figma file: **ABC**
(`xekOTabc4uKIM7fdXDv6Eq`) — https://www.figma.com/design/xekOTabc4uKIM7fdXDv6Eq/ABC

All 23 screens are **design-complete** in Figma (`design/screens.json` status:
`completed`). This list adds what the registry doesn't carry: states built,
breakpoints covered, components used, and every open visual/functional bug
found during QA — a dev implementing from these frames should fix these rather
than pixel-matching the bug.

Sources merged into this doc:
- [design/screens.json](design/screens.json) — task registry (status/owner/frame)
- [SCREENS.md](SCREENS.md) — product spec per screen
- [neobrutalistdesignsystem.md](neobrutalistdesignsystem.md) — token/component rules
- [DESIGN-SYSTEM-FIGMA.md](DESIGN-SYSTEM-FIGMA.md) — Figma production rules, canvas namespace
- [design/UX-UI-AUDIT-2026-08-10.md](design/UX-UI-AUDIT-2026-08-10.md) — newest, most complete QA pass (103 frames) — **primary bug source**
- [design/DESIGN-CRITIC-REPORT.md](design/DESIGN-CRITIC-REPORT.md) / [DESIGN-CRITIC-FINDINGS.md](DESIGN-CRITIC-FINDINGS.md) — earlier QA pass (82 frames) — kept for findings not repeated in the newer audit

Frame naming in Figma: `[SCREEN] <id> — <state> — <breakpoint>`. Canvas
namespace: `SCREEN/<id>/<state>/<breakpoint>`.

**Figma pages (live, confirmed via `use_figma` — 6 total):**

| Page | Node ID | Contents |
|---|---|---|
| 00 — Foundations | `0:1` | tokens/swatches doc + a handful of orphaned state frames (see per-screen tables below, marked "orphan") |
| 01 — Components | `4:2` | shared component library (table below) |
| 02 — App Shell | `4:3` | `Shell/TopBar` (`35:2`), `Shell/Sidebar` (`37:47`), `Shell/AppLayout` (`46:12`) |
| 03 — Screens | `4:4` | canonical loaded frames + some already-migrated states |
| 04 — States | `4:5` | additional 1024 responsive frames + a few error/empty states |
| 99 — Archive | `4:6` | not inventoried — archive only |

Every node ID below was pulled live via `use_figma` (not from the static
audit docs, which are a point-in-time snapshot and in a few places disagree
with current canvas state — e.g. more 1024 breakpoint frames exist now than
either audit lists). To open any frame directly:
`https://www.figma.com/design/xekOTabc4uKIM7fdXDv6Eq/ABC?node-id=<id-with-colon-replaced-by-dash>`.

**Shared component library** (page `01 — Components`, node `4:2`):

| Component | Node ID |
|---|---|
| `Button/Primary` | `13:41` |
| `Button/Secondary` | `14:41` |
| `Button/Destructive` | `14:81` |
| `Button/Ghost` | `14:121` |
| `Button/Icon` | `16:53` |
| `Status/Badge` | `17:34` |
| `Form/Input` | `18:74` |
| `Form/Checkbox` | `20:6` |
| `Form/Radio` | `20:11` |
| `Form/Switch` | `21:8` |
| `Form/Select` | `22:30` |
| `Form/Slider` | `23:23` |
| `Data/TableHeader` | `27:22` |
| `Data/TableRow` | `28:58` |
| `Data/Table` | `29:80` |
| `Data/BulkActionBar` | `29:81` |
| `Data/Progress` | `29:106` |
| `Feedback/Toast` | `32:90` |
| `Feedback/Tooltip` | `32:91` |
| `Feedback/Modal` | `33:88` |
| `Feedback/Drawer` | `34:82` |
| `Feedback/Skeleton` | `34:86` |
| `Feedback/EmptyState` | `34:87` |
| `Feedback/ErrorState` | `34:93` |
| `Card/StatTile` | `50:1390` |
| `Card/TemplateCard` | `85:72` |

---

## Cross-cutting — fix once, applies to every screen below

These live in shared components. A dev should fix the source component once,
not per-screen.

1. **`Shell/Sidebar` nav icons render as blank placeholder squares** instead of
   17px outline icons, on every screen/state.
2. **`Shell/Sidebar` "Jobs" nav label renders garbled/overlapping** ("Jodbs"-
   style double glyph) on most screens built after Categories/Locations
   (templates, schedules, suppression, proxies, integrations, webhook-log,
   team, api-keys, audit, system, settings, account, onboarding, not-found).
3. **Nav badge fill inconsistent** — "Jobs" badge has accent fill, sibling
   badges ("Categories", "Locations") have none.
4. **768px breakpoint is broken wherever it exists** (categories, locations,
   dashboard): no sidebar, no hamburger/drawer trigger, an unexplained solid
   grey rectangle clips the top-bar's right quarter, and tables stay desktop
   multi-column instead of converting to stacked cards.
5. **Radio buttons render as circles system-wide** — design system mandates
   squares (3px ink border, inset 8px ink square), "this system has no
   circles." Found on: job-new, export, settings, team invite-drawer.
6. **Checkbox checked-state has no white tick mark** — solid ink-black square
   instead of blue fill + white 2.5px stroke tick. Found on: results,
   export, integrations, api-keys.
7. **Status/badge pills missing required glyph prefix** (`●`/`✓`/`✕`/`!`).
   Found on: proxies, integrations, webhook-log, team, lead-detail, account
   (account also uses the *wrong* glyph — `●` instead of `✕` — for "expired").
8. **Modal/drawer scrim opacity far below spec's flat 70% ink** — reads as a
   light-medium grey wash. Found on: templates delete-confirm, settings
   purge-confirm, all 6 onboarding frames.
9. **Loading skeletons are generic flat blocks**, not shaped to the real
   content (table rows, card grid, stat tiles) and don't use the bold
   border/hard-shadow language the rest of the system uses. Found on:
   categories, suppression, integrations, api-keys, team, audit, system,
   webhook-log.
10. **Error states inconsistently discard the page shell.** On locations,
    export, and schedule-detail, error replaces the *entire* page (header,
    panels, nav) with a centered message, while empty/loading on the same
    screens keep full layout. Standardize: error should scope to the affected
    panel, keep header + shell visible.
11. **7 orphaned duplicate state frames live on page "00 — Foundations"**
    instead of "03 — Screens" (schedule-detail, results, lead-detail
    loading/error/empty). For **lead-detail** these orphans are the *only*
    place its empty/loading/error states exist — dev should treat them as
    canonical content but note the frame is mis-filed.
12. **"!" warning glyph typed as a raw character**, not an icon component
    (confirmed on login, likely repeats elsewhere).

---

## 1. Login — `/login`

- **Route:** `/login` · **Nav:** none (outside AppLayout) · **Priority:** 1
- **Page:** 03 — Screens (`4:4`), except loading/error variants on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 | 768 |
  |---|---|---|---|
  | loaded | `50:2` | `50:1344` | `50:1354` |
  | loading | `50:528` | — | — |
  | error (bad credentials) | `50:538` | — | — |
  | error-locked (lockout) | `50:548` | — | — |
  | error-offline | `50:558` | — | — |
  | totp (2FA) | `50:568` | — | — |
- **States built:** idle/loaded, submitting/loading, error (bad credentials),
  error-locked (account lockout), error-offline (backend unreachable), totp
  (2FA step)
- **Breakpoints:** 1440, 1024, 768 (loaded only — responsive reflow confirmed clean)
- **Components:** `Form/Input`, `Button/Primary`, footer link to `/docs`
- **Spec:** [SCREENS.md §1](SCREENS.md) — email+password, no signup (accounts via CLI), redirect to `/` if session exists, redirect back to originally-requested page after login, optional TOTP second factor, account lockout after 5 failed attempts (15-min cooldown, countdown shown)
- **Bugs to fix:**
  - Only the password field gets the red error outline in the `error` state — email field should too, since the message refers to both.
  - `error-locked`: no faster recovery path than waiting the timer out (no "contact admin" link).
  - `totp`: no back/cancel affordance to leave the 2FA step.
  - `loading`: button label is "..." with no spinner/motion — reads as broken, not busy.
  - `totp`: footer note ("accounts provisioned via CLI") is copy-pasted from the login card and irrelevant here.
  - Footer "/docs" link isn't styled as a link (no underline/color).
  - Error state shows two conflicting messages at once — inline "Required field" placeholder text in the password box *and* a separate "Incorrect email or password" message elsewhere. Should be one message in the field's help slot.
  - "!" warning icon is a typed character in 3 error banners — make it a real icon component (cross-cutting #12).

## 2. Jobs (Dashboard) — `/`

- **Route:** `/` · **Nav:** Jobs · **Priority:** 2
- **Page:** 03 — Screens (`4:4`), except empty/loading/error on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 | 768 |
  |---|---|---|---|
  | loaded | `50:1070` | `51:4669` | `175:7021` |
  | empty | `175:2258` | — | — |
  | loading | `175:2433` | — | — |
  | error | `175:2608` | — | — |
- **States built:** loaded, empty, loading, error
- **Breakpoints:** 1440 (all states), 1024 (loaded), 768 (loaded)
- **Components:** `Data/Progress` (stat tiles + job rows), stat tile cards, quick-start panel, recent jobs table, activity strip
- **Spec:** [SCREENS.md §2](SCREENS.md) — 4 stat tiles (jobs running, places scraped today, % leads w/ email, proxy health) each with delta; quick-start (keyword chips + queued areas + source picker + live target count/runtime + Start job/Open wizard); recent jobs table polling every 3s while any job queued/running; activity strip (last 10 events); license/quota warning banners
- **Bugs to fix:**
  - **Data-binding bug (Critical):** all 5 Recent Jobs progress labels show literal "62%" regardless of actual row progress — `Data/Progress` isn't bound to real values at any breakpoint.
  - 1024: progress-column percentage labels truncate to a single digit ("6" instead of "62%") — column too narrow.
  - 1024: 3 of 4 stat tiles render empty (no label/value/delta) — only Proxy Health populates.
  - 768: sidebar doesn't convert to overlay drawer — content is clipped off-frame into a grey void, no hamburger trigger.
  - 768: Recent Jobs stays a literal multi-column table instead of stacked cards.
  - StatTile white-on-saturated-color text (pink/purple tiles) has lower contrast than ink-on-yellow/green tiles.
  - `error`: Activity panel still shows fully-populated fake data despite the page claiming a load failure scoped to "job stats and recent activity."
  - `loading`: Quick Start panel's buttons/inputs stay fully rendered with real data while everything else skeletonizes — inconsistent skeleton rule.
  - `loading`: stat-tile skeletons keep their final accent-colored borders instead of the neutral sand-fill/rule-border skeleton treatment.
  - Activity panel status glyphs are raw characters, not icon components.
  - Activity panel unverified at 768 (rate-limited during audit) — check it explicitly.

## 3. New Job Wizard — `/jobs/new`

- **Route:** `/jobs/new` · **Nav:** none · **Priority:** 3
- **Page:** 03 — Screens (`4:4`) for step frames + loaded-1024; empty/loading/error/blocking states on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | step-1-keywords (loaded) | `50:851` | `51:5452` |
  | step-2-areas | `65:533` | — |
  | step-3-enrichment | `67:639` | — |
  | step-4-review-schedule | `68:751` | — |
  | empty | `51:2225` | — |
  | loading | `51:1946` | — |
  | error (step-4, all 3 blocking banners) | `51:3117` | — |
  | over-limit | `69:1079` | — |
  | no-license | `69:2606` | — |
  | quota-exceeded | `69:2739` | — |
- **States built:** 4 steps (keywords, areas, enrichment, review-schedule) × loaded, plus empty, loading, and blocking states (over-limit, no-license, quota-exceeded)
- **Breakpoints:** 1440 (all), 1024 (loaded)
- **Components:** persistent stepper, live cost panel (right rail), `Form/Radio`, `Form/Checkbox`, blocking banners
- **Spec:** [SCREENS.md §3](SCREENS.md) — 4-step wizard: Keywords (chips/CSV/Category Pack) → Areas (cascade/radius/GeoJSON) → Enrichment (deep crawl, email verify, tech fingerprint, adaptive depth) → Review & schedule (name, run now/schedule/save-as-template). Cost panel recomputes live on every change. Per-step validation; blocking states for >2000 targets, no license, quota exceeded.
- **Bugs to fix:**
  - **Cost panel is static (Major):** targets/places/runtime/bandwidth/quota numbers are byte-identical across all 4 steps even though step 3 toggles Deep Crawl + Email Verification, which should change bandwidth/runtime. Must actually recompute.
  - **Critical (1024):** Keyword List header says "(4)" but only 3 of 4 chips render — 4th dropped from the wrap container.
  - **Critical (step-3-enrichment):** Sidebar instance is 734px tall against an 836px body — visible gap at the bottom.
  - step-4-review-schedule: same sidebar-height truncation bug repeats.
  - step-4: Summary Box clips its 3rd line of text against the box's bottom edge (no padding).
  - `error` frame is actually step 4 with all 3 blocking banners stacked at once — clarify if intentional or rename/remove.
  - Blocking banners use a pale pink tint fill (spec bans tints — flat accent only), and the same 3 warnings on the Review step use a *different* treatment (white bg + pink left bar only) — unify to one treatment.
  - quota-exceeded: top-bar quota chip reads "118%" but stays green — must render `--pink` above 90%.
  - "Run now"/"Attach a schedule"/"Save as template" render as checkboxes but are mutually exclusive — should be radio.
  - step-4 "when to run" and the combined blocking frame render radio as filled circles — must be square per design system.
  - Stepper badge shape is square on step 1's own frame, circular when steps 2-4 render step 1 — pick one.
  - over-limit: quota-impact caption text is stale (doesn't match the projected places shown above it); quota bar stays green despite overage.
  - no-license: no self-service recovery link, unlike over-limit/quota-exceeded which both have one.
  - 1024: sidebar collapses to icon-only with no labels/badges/tooltips — real info loss.

## 4. Categories — `/categories`

- **Route:** `/categories` · **Nav:** Categories · **Priority:** 4
- **Page:** 03 — Screens (`4:4`), except empty/error/loading/1024/768 on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 | 768 |
  |---|---|---|---|
  | loaded | `50:742` | `51:2951` | `51:4562` |
  | empty | `51:1059` | — | — |
  | error | `51:1280` | — | — |
  | loading | `51:1830` | — | — |
- **States built:** loaded, empty, loading, error
- **Breakpoints:** 1440 (all states), 1024, 768 (loaded — reflow confirmed clean per newer audit)
- **Components:** autocomplete text field, chip list, CSV upload, Category Pack picker, synonym-expansion accept/reject chips
- **Spec:** [SCREENS.md §4](SCREENS.md) — free-text keyword entry w/ autocomplete from `GET /api/categories`; CSV/TSV/TXT upload (reports added/skipped/truncated); Category Packs; synonym expansion as accept/reject chips (not silent); chip list w/ clear-all + dedupe; not persisted server-side unless saved as a pack.
- **Bugs to fix:**
  - Loaded state has a Page Header (title+subtitle); empty/error/loading all omit it — biggest state-consistency gap on this screen.
  - Delete/accept/reject glyphs on chips are raw text characters, not icon components.
  - Loading skeletons use thin low-contrast outlines, breaking the bold-border/hard-shadow system.
  - "Jobs" badge has accent fill, "Categories"/"Locations" don't (cross-cutting #3).
  - 768: grey block clips right ~25% of frame (top-bar controls cut off) — cross-cutting #4.
- **Note:** this screen was previously audited and had prohibited Figma Section wrappers removed — confirmed clean of that issue now.

## 5. Locations — `/locations`

- **Route:** `/locations` · **Nav:** Locations · **Priority:** 5
- **Page:** 03 — Screens (`4:4`) for loaded-1440; empty/loading/error/1024/768 on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 | 768 |
  |---|---|---|---|
  | loaded | `50:1065` | `51:3769` | `80:3034` |
  | empty | `77:1415` | — | — |
  | loading | `77:1618` | — | — |
  | error | `77:1821` | — | — |
- **States built:** loaded, empty, loading, error
- **Breakpoints:** 1440 (all), 1024 (loaded), 768 (loaded)
- **Components:** cascade picker (Country→State→City→ZIP), radius-mode map control, polygon/GeoJSON upload, map preview (diamond markers), area chip queue w/ append/replace toggle
- **Spec:** [SCREENS.md §5](SCREENS.md) — 4 area-selection modes (cascade/ZIP or area/radius/polygon) + free-text search; map preview of queued areas; append/replace toggle; queue as removable grouped chips; empty-geo-DB hint.
- **Bugs to fix:**
  - **Critical (1024):** Map Preview panel entirely dropped at this breakpoint (~430px dead space) — doesn't stack like it does at 768.
  - **Critical (1024):** Area Chip rows hard-clipped at the frame's right edge instead of wrapping.
  - **Critical (error):** error state discards the entire page for a centered message — much bigger blast radius than a geo-lookup failure warrants; keep header/toggle/panels visible (cross-cutting #10).
  - 1024: Add Areas panel doesn't use freed width (~390px dead space).
  - empty: Queue panel shows header only, no empty-state message/illustration — large blank void.
  - 768: same chip-clipping bug as 1024.
  - The 4 states aren't structurally consistent (loaded/empty share a shell, loading skeletons it, error abandons it).
  - 1024: nav-active state on collapsed sidebar doesn't highlight "Locations" as current page.
  - loading: skeleton shapes don't mirror the real two-column field layout; Queue skeleton height mismatch will cause layout shift on load.
  - empty (1440): large grey rectangle overlapping the bottom of the frame — leftover/bleed-through content.
  - 768: table/queue region doesn't convert to stacked cards, stays dense desktop layout.

## 6. Job Templates — `/templates`

- **Route:** `/templates` · **Nav:** Templates · **Priority:** 6
- **Page:** 03 — Screens (`4:4`) for loaded-1440 and loaded-1024; empty/delete-confirm/loading/error on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `84:1028` | `331:8120` |
  | empty | `87:1134` | — |
  | delete-confirm | `88:1914` | — |
  | loading | `313:3762` | — |
  | error | `315:4298` | — |
- **States built:** loaded, empty, delete-confirm, loading, error (loading/error confirmed present live — earlier audits called this a coverage gap; verify current visual quality regardless)
- **Breakpoints:** 1440 only
- **Components:** card grid, per-card action row (Run now/Edit/Duplicate/Attach schedule/Delete), confirm modal
- **Spec:** [SCREENS.md §6](SCREENS.md) — card grid: name, keyword count, area count, target count, last run, owner.
- **Bugs to fix:**
  - ~~Coverage gap: no loading/error state~~ — stale, both exist live (`313:3762`, `315:4298`); verify visual quality directly instead of assuming the gap.
  - Card grid ends with an orphaned row (5 cards in a 3-col grid leaves an unfilled slot with no visual anchor).
  - Card action row spacing between "Attach Schedule" and "Delete" reads as misaligned.
  - delete-confirm: Confirm action is plain text, not a filled destructive button — same visual weight as Cancel.
  - delete-confirm: Cancel/Delete buttons lack the border/shadow convention every other button uses.
  - "Jobs"/"Categories" nav labels render garbled (cross-cutting #2).
  - delete-confirm modal scrim ~45-50% opacity, not the required flat 70% (cross-cutting #8).

## 7. Schedules — `/schedules`

- **Route:** `/schedules` · **Nav:** Schedules · **Priority:** 7
- **Page:** 03 — Screens (`4:4`) for loaded-1440; loaded-1024 on 04 — States (`4:5`); empty/loading/error on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `93:1134` | `332:73` |
  | empty | `96:2129` | — |
  | loading | `318:3972` | — |
  | error | `319:4288` | — |
- **States built:** loaded, empty, loading, error (loading/error exist live — earlier audit flagged as missing, stale)
- **Breakpoints:** 1440, 1024
- **Components:** table (name/template/cadence/next run/last run/last result/enabled toggle), new-schedule drawer (template picker, cadence builder w/ plain-English preview + next 5 fire times, timezone, notify-on, channels)
- **Spec:** [SCREENS.md §7](SCREENS.md)
- **Bugs to fix:**
  - ~~Coverage gap: no loading/error, no responsive~~ — stale; loading (`318:3972`), error (`319:4288`), and loaded-1024 (`332:73`) all exist live. 768 still genuinely missing.
  - **Critical:** TEMPLATE column for the "Misfire Warning" row shows the same text as the NAME cell — looks like a copy-paste data bug.
  - Misfire row is 64px tall vs 48px for every other row — breaks table rhythm.
  - "Never fired" (misfire row) vs "Never run" (different row) are two different states using near-identical, confusable copy — differentiate.
  - No reusable "row alert" pattern exists for the misfire subtext; it's bespoke to one row.
  - Status badges (DONE/FAILED/WAITING/MISFIRED) have rounded corners — spec forbids any radius >0px.
  - "WAITING" badge uses "…" glyph, not one of the defined `●`/`✓`/`✕`/`!`. "MISFIRED" has no glyph at all.
  - Enabled switch knob renders white/outlined, not the specified solid ink-filled square.

## 8. Schedule & Monitoring — `/schedules/:id`

- **Route:** `/schedules/:id` · **Nav:** none (drill-down from Schedules) · **Priority:** 8
- **Page:** loaded + empty on 03 — Screens (`4:4`); loaded-1024 on 04 — States (`4:5`); loading/error are genuine orphans on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `112:1176` | `337:140` |
  | empty | `247:5956` | — |
  | loading (orphan) | `248:2` | — |
  | error (orphan) | `249:115` | — |
- **States built:** loaded, empty (both canonical), loading/error (orphaned on Foundations — cross-cutting #11)
- **Breakpoints:** 1440, 1024
- **Components:** header (name/cadence/next run/enable-pause/Run now), delta chart (the only chart in the app), run history table, change feed
- **Spec:** [SCREENS.md §8](SCREENS.md) — delta chart is new/changed/disappeared per run as stacked bars; change feed shows individual diffs with before/after.
- **Bugs to fix:**
  - **Coverage gap:** loading/error only exist as orphans on Foundations (`248:2`, `249:115`) — move to Screens page, don't rebuild; 768 breakpoint still missing.
  - `Form/Switch` renders with a green ("on") track but the knob sits in the left/"off" position — contradicts itself; component-level bug, repeats on empty frame too.
  - Delta chart uses green/blue/pink bars instead of the mandated teal(new)/yellow(changed)/ink-60(gone); missing axes/gridlines/ink borders entirely.
  - Change-feed labels ("phone changed", "website went dark", "marked permanently closed") colored pink — pink is reserved for failure/destructive states, not neutral diffs.
  - "FAILED" status badge color not confirmed against the actual error token.
  - "VIEW RESULTS →" links use blue — not in the stated ink/sand/yellow token set; verify it's a registered link token.
  - Change Feed card shows only 3 entries with no overflow/view-all, despite runs having up to 60+ changes.
  - Delta chart legend's "DISAPPEARED" gray swatch has noticeably lower contrast than its neighbors.
  - 2 orphaned duplicate frames (loading `248:2`, error `249:115`) live on page `0:1` — move to page `4:4`.

## 9. Results — `/results/:jobId`

- **Route:** `/results/:jobId` · **Nav:** Results · **Priority:** 9
- **Page:** loaded + empty on 03 — Screens (`4:4`); loaded-1024 on 04 — States (`4:5`); loading/error are genuine orphans on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `118:1354` | `340:203` |
  | empty | `250:6276` | — |
  | loading (orphan) | `252:225` | — |
  | error (orphan) | `253:332` | — |
- **States built:** loaded, empty (both canonical), loading/error (orphaned on Foundations — cross-cutting #11)
- **Breakpoints:** 1440, 1024
- **Components:** header w/ status chip + `Data/Progress` (measured in places, not targets), tabs (Leads/Targets/Activity/Changes/Errors), live activity feed (pausable, filterable, auto-scroll-lock), virtualized `Data/Table` results grid w/ faceted filter rail + column picker + saved views + bulk action bar, targets table, errors tab w/ screenshot thumbnails
- **Spec:** [SCREENS.md §9](SCREENS.md) — fed by WebSocket w/ REST polling backstop; first 200 rows shown with export-for-rest note.
- **Bugs to fix:**
  - **Coverage gap:** loading/error only exist as orphans on Foundations (`252:225`, `253:332`) — move, don't rebuild; 768 breakpoint still missing.
  - Email addresses wrap to a second line and collide with the row border/next row — column too narrow.
  - Website links overflow/clip inconsistently across rows for the same reason.
  - Selected-row checkbox is solid ink-black with no white tick (cross-cutting #6).
  - Frozen Score/Name columns have no visible 3px ink right-edge boundary marking the freeze.
  - Progress caption leads with a targets ratio ("101 of 163 targets…") — spec requires places as the primary measurement, not targets.
  - Frozen-column boundary has no background tint — easy to miss the pinned-column affordance.
  - Row-count caption sits too close to the bulk action bar with no visual grouping.
  - "PLACES" metric shows current count (9,412) exceeding its own approximate target ceiling (~9,300) — data/logic inconsistency to verify against real binding.
  - Tab widths (LEADS/TARGETS/ACTIVITY/CHANGES/ERRORS) aren't proportional/consistent.
  - empty: Metrics row still shows an actively-running job (elapsed/remaining ticking) while the grid shows a static "no results" dead end — no in-progress affordance.
  - empty: icon is a generic rotated square, not a purposeful glyph.
  - 2 orphaned duplicate frames (loading `252:225`, error `253:332`) on page `0:1` — move to page `4:4`.

## 10. Lead Detail — `/results/:jobId/lead/:leadId`

- **Route:** `/results/:jobId/lead/:leadId` (drawer over Results; also standalone route) · **Nav:** none · **Priority:** 10
- **Page:** loaded on 03 — Screens (`4:4`); loaded-1024 on 04 — States (`4:5`); empty/loading/error are genuine orphans on 00 — Foundations (`0:1`) — the *only* place those states exist
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `124:1467` | `344:373` |
  | empty (orphan) | `255:442` | — |
  | loading (orphan) | `256:549` | — |
  | error (orphan) | `257:654` | — |
- **States built:** loaded (canonical); empty/loading/error exist only as orphaned frames on Foundations (cross-cutting #11)
- **Breakpoints:** 1440, 1024
- **Components:** identity block (score dial + reason breakdown, claimed/closed badges), contact block, web block, location block (mini-map), provenance block, history diff list, actions row (copy vCard/suppress/tag/push to CRM)
- **Spec:** [SCREENS.md §10](SCREENS.md)
- **Bugs to fix:**
  - Leftover placeholder/instructional text node ("Content slot — instance the relevant blocks here…") still in the layer tree, hidden behind the Identity block but not deleted — remove it.
  - **Production hygiene:** the only existing empty/loading/error states are the mis-filed orphan frames (`255:442`, `256:549`, `257:654`) — move to page `4:4` as canonical, don't rebuild.
  - Actions row order is COPY VCARD → SUPPRESS → TAG → PUSH TO CRM: destructive SUPPRESS sits adjacent to routine actions with no visual differentiation — separate or style distinctly.
  - Divider gap after the Identity block (20px) is ~2.5x the gap used at every other block transition (8px) — normalize to 8px.
  - Actions row leaves 70px of dangling unused space — right-align/balance it.
  - Score dial and dividers use a soft/flat style inconsistent with the neobrutalist hard-border/shadow language elsewhere.
  - Score dial has no 3px ink border around the ring (spec: every colored block gets one, no exceptions).
  - CLAIMED/OPEN badges are unfilled white outline pills — missing semantic accent fill and glyph prefix.
  - Drawer shows only a thin ink line on its left edge — missing the `hard-lg` offset shadow toward content.
  - Mini-map is an unlabeled grid of lines with one marker — reads unfinished next to fully-realized blocks.

## 11. Export — `/export/:jobId`

- **Route:** `/export/:jobId` · **Nav:** Exports · **Priority:** 11
- **Page:** loaded on 03 — Screens (`4:4`); loaded-1024 on 04 — States (`4:5`); empty/loading/error on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `129:4372` | `346:332` |
  | empty | `130:4545` | — |
  | loading | `130:4396` | — |
  | error | `130:4694` | — |
- **States built:** loaded, empty, loading, error
- **Breakpoints:** 1440, 1024
- **Components:** format picker (CSV/XLSX/KML/JSONL/Google Sheets), column selection w/ group toggles, row-scope picker (all/filtered/selected), progress bar (rows written), export history table
- **Spec:** [SCREENS.md §11](SCREENS.md) — **note: XLSX/KML/JSONL/Sheets writers not implemented in backend yet** (MODULES.md 8.3–8.6) — CSV is the only functional format currently; design shows all 5 for forward-compat.
- **Bugs to fix:**
  - **Critical (error):** entire page replaced by a centered message on error — loses all prior configuration context; keep header/format/columns/scope/history visible (cross-cutting #10).
  - Row-scope and format-picker controls render as circular radios — must be square (cross-cutting #5).
  - Column checkboxes have no white tick when checked (cross-cutting #6).
  - loading: "GENERATE EXPORT" collapses to a 58px icon-only stub instead of staying full-width with a busy indicator — layout shift.
  - loading: radio controls use hand-drawn ellipses instead of the real `Form/Radio` component (loaded uses the real component) — same screen, two implementations.
  - loading: "GENERATING…" shows literal text instead of the 3-square marching indicator spec requires for loading buttons.
  - loading: button fill looks reduced-opacity/washed-out — spec explicitly bans opacity reduction for disabled/loading states.
  - loading: progress row-count text left-aligned below the bar instead of right-aligned outside it; also the ~55% fill doesn't match its own label (1,526/3,180 ≈ 48%).
  - empty: no primary action button at all — spec requires exactly one on every empty state.
  - error: shown as a small inline banner instead of the prescribed layout (pink icon block, error class as h2, human cause, mono error id, Retry).
  - "Current selection" row-scope option is disabled with no explanation why.
  - 4 of 5 format cards are permanently "COMING SOON" at equal visual weight to the one usable option (CSV) — consider de-emphasizing given backend gap above.
  - **Coverage gap:** 768 breakpoint still missing (1024 exists — `346:332`).

## 12. Suppression List — `/suppression`

- **Route:** `/suppression` · **Nav:** Suppression · **Priority:** 12
- **Page:** loaded + confirm + empty on 03 — Screens (`4:4`)/00 — Foundations (`0:1`); loaded-1024 on 04 — States (`4:5`); error is an orphan on Foundations
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `132:2096` | `349:394` |
  | empty | `132:5138` | — |
  | confirm | `132:5073` | — |
  | error (orphan) | `324:7806` | — |
- **States built:** loaded, empty, confirm, error (error is an orphan — verify placement)
- **Breakpoints:** 1440, 1024
- **Components:** 3 tabs (Domains/Emails/Places), table, add-one/bulk-paste/upload, impact-preview panel, confirm modal
- **Spec:** [SCREENS.md §12](SCREENS.md) — impact preview must show row count before confirming a suppression rule (destructive).
- **Bugs to fix:**
  - **Needs direct in-app inspection:** confirm modal metadata and rendered screenshot disagree on copy — metadata shows generic bulk-delete text ("DELETE 1,284 ROWS"), render shows domain-specific text ("SUPPRESS THIS DOMAIN… competitor-crm.io"). Likely a stale/duplicate modal layer or desynced component override.
  - No impact-preview row count shown *before* the confirm modal opens — spec requires it visible earlier, not just inside the modal.
  - confirm: body copy says "Type SUPPRESS to confirm" but no visible text input exists — the typed-confirmation safety mechanic isn't actually implemented.
  - confirm: CANCEL/SUPPRESS render as bare colored text — no border, fill, or shadow on either; Destructive variant specifically needs pink fill + white 700 text + `hard-sm` shadow.
  - loaded: "N rows" count next to REMOVE in the Actions cell has no label/tooltip explaining what it counts.
  - loading: table area is a flat blank rectangle, indistinguishable from broken/unstyled.
  - confirm: destructive button uses pink/magenta — unconfirmed against the system's actual danger token.
  - ~~Coverage gap: no error state~~ — stale, error exists live (`324:7806`, orphan-filed). 768 still missing.

## 13. Proxies — `/proxies`

- **Route:** `/proxies` · **Nav:** Proxies · **Priority:** 13
- **Page:** loaded on 03 — Screens (`4:4`); loaded-1024 on 04 — States (`4:5`); empty/degraded/all-retired/loading/error on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `134:1995` | `351:462` |
  | empty | `135:5184` | — |
  | degraded | `135:5359` | — |
  | all-retired | `135:5534` | — |
  | loading | `321:3572` | — |
  | error | `322:3597` | — |
- **States built:** loaded, empty, degraded, all-retired, loading, error
- **Breakpoints:** 1440, 1024
- **Components:** pool health strip (stat tiles), proxy table (host/port/protocol/country/state/leases/success rate/latency/blocks/last used + Test/Disable/Drain/Delete), add-proxies paste box
- **Spec:** [SCREENS.md §13](SCREENS.md)
- **Bugs to fix:**
  - **Data-binding bug (Major):** degraded banner numbers ("38 proxies cooling", "8% block rate") don't match the stat tiles directly below (18, 2.1%) — stale copy or real binding bug, verify against actual data source.
  - Stat tiles (HEALTHY/COOLING/RETIRED/AVG LATENCY) are plain white cards with only colored text — spec requires one flat accent fill per tile; only BLOCK RATE is actually filled.
  - RETIRED tile uses the same neutral styling as active tiles — no visual distinction for a zero-capacity state.
  - RETIRED badge has a thin grey border instead of the standard 2px solid ink.
  - Retired row in `loaded` isn't visually dimmed, unlike the same row style in `all-retired` — make consistent.
  - Actions ("TEST · DISABLE · DRAIN · DELETE") have no differentiation for destructive DELETE in `loaded`; `all-retired` *does* color DELETE red — make consistent.
  - all-retired: one row's status chip renders with double-stacked dimming — nearly illegible.
  - empty: stat strip disappears entirely while all-retired keeps it visible at zero — pick one zero-state convention.
  - all-retired: blocking banner uses a full-color emoji icon instead of a flat ink-outline icon.
  - all-retired: BLOCK RATE tile keeps yellow (attention) fill even though the value is "—" (no rate to show).
  - all-retired: rows still show active-looking Test/Disable/Drain/Delete actions with no visual distinction, though none apply to an already-retired proxy.
  - Add Proxies panel keeps identical sample text/parse-status across all 4 states regardless of context.
  - ~~Coverage gap: no loading/error~~ — stale, both exist live (`321:3572`, `322:3597`). 768 still missing.

## 14. Integrations — `/integrations`

- **Route:** `/integrations` · **Nav:** Integrations · **Priority:** 14
- **Page:** loaded on 03 — Screens (`4:4`); loaded-1024 on 04 — States (`4:5`); empty/webhook-config/loading/error on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `137:2112` | `352:534` |
  | empty | `139:5625` | — |
  | webhook-config | `138:5551` | — |
  | loading | `268:3523` | — |
  | error | `325:3685` | — |
- **States built:** loaded, empty, webhook-config, loading, error
- **Breakpoints:** 1440, 1024
- **Components:** card grid (Webhooks/Slack/HubSpot/Pipedrive/Generic REST/Google Sheets), field-mapping table w/ dry-run preview
- **Spec:** [SCREENS.md §14](SCREENS.md)
- **Bugs to fix:**
  - webhook-config: checkbox column is structurally misaligned — checked vs unchecked event rows use two different layouts (checkbox-after-label vs checkbox-before-label), breaking the vertical column.
  - webhook-config: Endpoint URL field shows the generic placeholder example URL even for an already-connected, actively-delivering webhook — looks unconfigured when it isn't; bind to real value.
  - `empty` is not a true empty state — structurally identical to the loaded card grid with every card showing "NOT CONNECTED"; must use the real `Feedback/EmptyState` component (yellow rotated icon block, headline, one action).
  - loading: single flat placeholder block instead of 6 card-shaped skeletons matching the loaded grid.
  - CONNECTED/NOT CONNECTED badges missing glyph prefix.
  - webhook-config: checked event checkboxes solid black, no white tick.
  - webhook-config: signing secret uses body font instead of the `mono` type token specified for keys/ids.
  - webhook-config: no disconnect/remove action anywhere in the config drill-down.
  - "NOT CONNECTED" chip has no defined semantic color mapping in the design-system doc — spec gap, decide and document.
  - Card grid gap is 32px; spec calls for 16–20px card/panel gaps — confirm intentional exception or fix.
  - empty: unclear if the -6° rotation spec'd for the shared `EmptyState` icon actually renders — check the shared component directly.
  - ~~Coverage gap: no error state~~ — stale, error exists live (`325:3685`, orphan-filed). 768 still missing.

## 15. Webhook Delivery Log — `/integrations/webhooks/:id`

- **Route:** `/integrations/webhooks/:id` · **Nav:** none (drill-down from Integrations) · **Priority:** 15
- **Page:** loaded on 03 — Screens (`4:4`); loaded-1024 on 04 — States (`4:5`); back-off/disabled/loading on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded (all-delivering) | `140:2149` | `353:596` |
  | back-off | `141:5887` | — |
  | disabled | `141:5982` | — |
  | loading | `269:3547` | — |
- **States built:** loaded (all-delivering), back-off, disabled, loading
- **Breakpoints:** 1440, 1024
- **Components:** table (timestamp/event/status/attempt/duration), expandable row detail (request/response), Replay + Replay-all-failed
- **Spec:** [SCREENS.md §15](SCREENS.md)
- **Bugs to fix:**
  - The "job.completed" row's expanded detail is permanently open with no visible collapse affordance/chevron — every other row is collapsed; confirm expand/collapse is actually wired.
  - loading: single flat sand-colored rectangle, no skeleton rows shaped like the real table (header + 4 rows + actions column).
  - back-off: "REPLAY ALL FAILED" stays fully-enabled styling identical to all-delivering — correct behavior (backing off ≠ disabled) but no visual differentiation for the degraded condition beyond the banner text.
  - disabled: "2 failed in the last 24h" helper text greys out along with the disabled "REPLAY ALL FAILED" button — it's a status readout, not a control, shouldn't dim.
  - disabled: individual row REPLAY links stay blue/active while only the toolbar action is greyed — inconsistent disabled treatment for the same action in two places.
  - disabled: "RE-ENABLE" sits at the far right of the pink banner with no confirmation step — consider whether re-enabling a webhook that failed repeatedly needs the same friction as other state-changing actions (e.g. suppression's confirm modal).
  - disabled: blocking banner uses a full-color emoji icon instead of flat ink-outline.
  - 200/500/503 status chips show color+number only, no glyph prefix.
  - **Coverage gap:** genuinely still missing empty state (never-configured webhook), no responsive breakpoints below 1024.

## 16. Team & Roles — `/team`

- **Route:** `/team` · **Nav:** Team · **Priority:** 16
- **Page:** loaded on 03 — Screens (`4:4`); loaded-1024 on 04 — States (`4:5`); invite-drawer/seat-limit/loading/error on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `143:2321` | `355:653` |
  | invite-drawer | `143:6363` | — |
  | seat-limit | `143:6504` | — |
  | loading | `261:3295` | — |
  | error | `262:3322` | — |
- **States built:** loaded, invite-drawer, seat-limit, loading, error
- **Breakpoints:** 1440, 1024
- **Components:** member table (email/role/last seen/status/actions), invite drawer (email+role+CLI equivalent), role matrix panel, seat counter
- **Spec:** [SCREENS.md §16](SCREENS.md)
- **Bugs to fix:**
  - **Major:** seat-limit table shows only 4 members (Owner, 2× Operator, 1 disabled Viewer) but "SEATS 10/10 used" — 6 seats unaccounted for. Either show all 10 members or add pagination/scroll with a visible reconciling count.
  - Member table rows are 40px tall — matches neither compact (36px) nor comfortable (44px) spec.
  - ACTIVE/DISABLED status chips have no glyph prefix.
  - invite-drawer: Owner/Operator/Viewer role picker renders as circular radio dots — must be square.
  - invite-drawer: CLI snippet ("OR PROVISION FROM THE TERMINAL") is static, not templated from the actual email/role field values — if the role dropdown changes, the CLI command's `--role` doesn't update, risking a pasted mismatch. Fix: template the snippet live.
  - loading: 2 flat blank rectangles with no shape hinting at the Role Matrix (6×3) or Member table (5 cols) structure underneath.
  - seat-limit: confirm the "REMOVE" action in the ACTIONS column is sufficiently discoverable as the fix for the seat-limit banner (banner doesn't link/scroll to removable rows).
  - **Coverage gap:** error state confirmed to exist live (`262:3322`) — verify its quality against the `ERR_TEAM_FETCH_FAILED`/RETRY convention directly; empty state (single-owner workspace) and 768 breakpoint genuinely still missing.

## 17. API Keys — `/api-keys`

- **Route:** `/api-keys` · **Nav:** API Keys · **Priority:** 17
- **Page:** loaded on 03 — Screens (`4:4`); loaded-1024 on 04 — States (`4:5`); create-key/empty/loading/error on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `157:1893` | `357:712` |
  | create-key | `157:4965` | — |
  | empty | `326:3783` | — |
  | loading | `263:3354` | — |
  | error | `264:3379` | — |
- **States built:** loaded, create-key, empty, loading, error
- **Breakpoints:** 1440, 1024
- **Components:** key table (label/prefix/scopes/created/last used/expiry/revoke), create-key modal (copy-once panel), per-key scopes + IP allowlist, usage sparkline
- **Spec:** [SCREENS.md §17](SCREENS.md)
- **Bugs to fix:**
  - create-key: form reads backwards — the key is already generated/shown *before* its label and scopes are set, implying the key existed before the fields that define it. Fix flow order: label/scopes first, then generate+reveal.
  - create-key: full key display text node (320px) is narrower than its container (600px) with no wrap/overflow handling — risk with longer key formats.
  - create-key: "COPY KEY" ghost button has no visible border — reads as plain text, breaking the neobrutalist convention for a safety-critical one-time-reveal action.
  - loaded: "Admin Console" row's 2-line wrapped scopes text doesn't fit the fixed 44px row height used by every other 1-line row.
  - loaded: no density toggle in the toolbar despite the compact-default-with-comfortable-toggle convention; rows render at 44px with no toggle present.
  - error: "CREATE KEY" button is missing entirely (present on loaded/loading) — no way to attempt creation without first fixing the list load.
  - create-key: checked SCOPES checkboxes solid black, no white tick.
  - create-key: modal footer is only 106px wide inside a 640px modal — DONE button stranded far-left with dead space.
  - loading: skeleton is a single thin-bordered box, not shaped like real table rows.
  - ~~Coverage gap: no empty state~~ — stale, exists live (`326:3783`). 768 breakpoint still missing.
  - No security issue confirmed: full plaintext key shown only in the one-time-reveal modal; table view elsewhere correctly shows prefix only.

## 18. Audit Log — `/audit`

- **Route:** `/audit` · **Nav:** Audit · **Priority:** 18
- **Page:** loaded on 03 — Screens (`4:4`); loaded-1024 on 04 — States (`4:5`); empty/loading/error on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `160:1918` | `359:769` |
  | empty | `161:4746` | — |
  | loading | `265:3409` | — |
  | error | `266:3456` | — |
- **States built:** loaded, empty, loading, error
- **Breakpoints:** 1440, 1024
- **Components:** table (timestamp/actor/action/target/IP/result), filter row (actor/action type/date range), expandable before/after diff row
- **Spec:** [SCREENS.md §18](SCREENS.md)
- **Bugs to fix:**
  - TARGET cell text (e.g. `Suppression rule "competitor-crm.i...`) is cut off mid-word with no ellipsis character, no tooltip, no way to see the full value — reads as a rendering bug.
  - Filter row (Actor/Action Type/From/To) is vertically clipped by its containing row — only the top sliver of each control is visible, on both loaded and empty. Likely a container height bug.
  - loading: single flat sand rectangle, no skeleton rows shaped like the real table (6 cols, ~5 rows).
  - Expanded "BEFORE/AFTER" diff row for `settings.updated` is permanently shown open with no visible collapse control — same underlying "detail row" component issue as Webhook Delivery Log.
  - **Coverage gap:** error state confirmed live (`266:3456`) — verify it matches the `ERR_*_FETCH_FAILED`+RETRY convention directly; 768 breakpoint still missing.
  - No issues confirmed: filter row content itself is clear; SUCCESS/FAILED badges use correct semantic colors; empty state correctly explains "no audit history ever" vs filter-driven and offers a sensible next step.

## 19. System Health — `/system`

- **Route:** `/system` · **Nav:** System · **Priority:** 19
- **Page:** loaded on 03 — Screens (`4:4`); loaded-1024 on 04 — States (`4:5`); empty/loading/error on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `163:1965` | `360:848` |
  | empty | `258:6924` | — |
  | loading | `259:765` | — |
  | error | `260:789` | — |
- **States built:** loaded, empty, loading, error
- **Breakpoints:** 1440, 1024
- **Components:** component-status tiles (API/app DB/geo DB/Redis/Celery/browser pool/object store), queue-depth stat tiles, worker table, geo-seed status, version block
- **Spec:** [SCREENS.md §19](SCREENS.md)
- **Bugs to fix:**
  - **Major (empty):** "NO MONITORING DATA YET" only replaces the Queue Depth/Workers/Geo Seed/Version panels — the top service-status cards still render fully populated with live data (including an active DOWN/DEGRADED incident), directly contradicting the empty-state copy. Same scoping-mismatch pattern as Dashboard's error state (cross-cutting #10) — scope the empty state to actually-empty data only.
  - Object Store card's DOWN status dot is dark maroon/wine, not the semantic `--pink` required for failure states.
  - Object Store error string is cut off mid-sentence ("timed out after 3" — hides "retries") by the fixed-height tile — allow the tile to grow or truncate with visible ellipsis + tooltip.
  - Object Store's error message is multi-line while Celery Workers (also degraded) gets a one-line summary — inconsistent level of technical detail across cards of the same severity.
  - Status dot + text label duplicates the same info per card (dot alone would suffice) — flagged for consistency check, not necessarily wrong.
  - loading: 5 flat skeleton blocks that don't distinguish the top status-card row (~7 small cards) from Queue Depth (4 tiles) from Workers (a table).
  - **Coverage gap:** 768 breakpoint still missing (1024 exists — `360:848`). ~~"Only a loaded state exists"~~ is stale — empty/loading/error all exist live.

## 20. Settings — `/settings`

- **Route:** `/settings` · **Nav:** Settings · **Priority:** 20
- **Page:** loaded on 03 — Screens (`4:4`); loaded-1024 + error on 04 — States (`4:5`); purge-confirm/loading on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `164:2002` | `362:917` |
  | purge-confirm | `165:4970` | — |
  | loading | `327:7908` | — |
  | error | `328:2` | — |
- **States built:** loaded, purge-confirm, loading, error
- **Breakpoints:** 1440, 1024
- **Components:** collapsible sections (Scraping/Deep crawl/Enrichment/Lead scoring/Browser/Data retention/Danger zone), sliders, weight table w/ live preview, typed-confirm danger-zone modals
- **Spec:** [SCREENS.md §20](SCREENS.md) — each control saves independently; server's clamped response is authoritative; danger zone actions require typed confirmation.
- **Bugs to fix:**
  - purge-confirm: copy says "Type PURGE to confirm" but there is no text input in the modal — the irreversible action has no actual typed-confirmation gate. Must add the input.
  - Some section headers have a filled divider rule next to the title, others don't — inconsistent down the page.
  - "WEIGHT" table header's highlight background is clipped by the table border, misaligned with the adjacent plain header cell.
  - purge-confirm: modal's declared frame height (200px) is smaller than its stacked content (244px) — fragile, will visibly break if copy grows. Size to content.
  - Email Verification Mode radio renders inconsistently within the same file — square-right-of-label on one frame, circle-left-of-label (purge-confirm) on another. Must be one square component everywhere.
  - Filled input values render in the same light grey as placeholder text — ambiguous whether a value is real or empty.
  - Section-head chevrons are raw text characters at an unusual aspect ratio, not real icon components.
  - purge-confirm: three different strings for the same confirmation concept ("PURGE", "PURGE ALL", "PURGE ALL RESULTS") — pick one token.
  - ~~Coverage gap: no loading/error/empty~~ — stale: loading (`327:7908`) and error (`328:2`) both exist live. Empty state still genuinely missing (arguable whether Settings needs one at all — it's not a data-fetch-then-render screen in the usual sense); 768 breakpoint still missing.
  - No issues confirmed: destructive-action pattern in purge-confirm otherwise follows the system correctly (red header, explicit row count, type-to-confirm friction intent, calm-vs-destructive button placement, scrim) — just needs the actual input added.

## 21. Account & Billing — `/account`

- **Route:** `/account` · **Nav:** Account · **Priority:** 21
- **Page:** loaded on 03 — Screens (`4:4`); loaded-1024 + error on 04 — States (`4:5`); license-expired/loading on 00 — Foundations (`0:1`)
- **Node IDs:**

  | State | 1440 | 1024 |
  |---|---|---|
  | loaded | `166:2093` | `365:1041` |
  | license-expired | `167:5075` | — |
  | loading | `329:7965` | — |
  | error | `330:43` | — |
- **States built:** loaded, license-expired, loading, error
- **Breakpoints:** 1440, 1024
- **Components:** signed-in block, license panel, quota meters, usage-history bar chart
- **Spec:** [SCREENS.md §21](SCREENS.md)
- **Bugs to fix:**
  - **Critical:** the global TopBar license chip still reads "✓ LICENSED" (green) while the License panel on the same screen shows "✕ EXPIRED" — two indicators of the same fact contradicting each other. Bind the TopBar chip to the same license-status value as the panel.
  - Usage History is a *second* ad-hoc bar chart with its own blue/yellow palette — spec states there is exactly one chart in the whole app (Schedule Detail's delta series) specifically to prevent a second charting language. Either restyle to match the one chart system or justify the exception explicitly.
  - Within that chart, every bar is blue except August (yellow) with no legend/explanation — bar color must carry meaning; add a legend with text labels.
  - license-expired: EXPIRED badge uses `●` (defined for "running/in-progress"), should use `✕` for failed/expired.
  - license-expired: only the license panel changes state — QUOTA/Usage History/Signed In all render identically to active-license — confirm this is intended grace-period behavior, not an oversight.
  - license-expired: "EXTEND FROM THE TERMINAL" CLI snippet has no equivalent link/button to a billing portal for a non-technical Owner.
  - ~~Coverage gap: no empty/loading/error~~ — stale, loading (`329:7965`) and error (`330:43`) both exist live. No true empty state applies here (account always has data once logged in). 768 breakpoint still missing.

## 22. First-run / Compliance (Onboarding) — modal over `/`

- **Route:** modal over `/` · **Nav:** none · **Priority:** 22
- **Page:** compliance-1 + tour-1 on 03 — Screens (`4:4`); full 1024 set on 04 — States (`4:5`); compliance-2/3, tour-2/3 (1440) on 00 — Foundations (`0:1`)
- **Node IDs:**

  | Frame | 1440 | 1024 |
  |---|---|---|
  | compliance-1 | `168:1915` | `366:1205` |
  | compliance-2 | `168:5344` | `367:1217` |
  | compliance-3 | `168:5533` | `367:10140` |
  | tour-1-categories | `168:6041` | `367:10525` |
  | tour-2-locations | `168:6385` | `369:1719` |
  | tour-3-start-job | `168:6729` | `369:10484` |
- **States built:** compliance-1, compliance-2, compliance-3, tour-1, tour-2, tour-3 (6 frames, one flow) — each now also has a 1024 variant
- **Breakpoints:** 1440, 1024
- **Components:** compliance modal (centered, dark header, segment bar, full scrim), product-tour anchored callouts (no scrim, text-only step indicator)
- **Spec:** [SCREENS.md §22](SCREENS.md) — 3 compliance panes (data collection, robots.txt scope, GDPR/CCPA obligations) each requiring explicit "I understand" (writes an audit row), followed by an optional 3-step tour pointing at Categories/Locations/Start job.
- **Bugs to fix:**
  - **Critical:** compliance-3's step-indicator fill is wrong on the final step — segments 1 and 3 filled, segment 2 not, producing "done, skipped, current" instead of "done, done, current."
  - **Major:** compliance-1 overlays a fully-populated live dashboard (real jobs/leads/activity) rather than a true zero-state — misleading for what's meant to be a first-run screen.
  - **Major:** no back button on any compliance step and no visible close/dismiss — only "I UNDERSTAND." If not an intentional legal gate, add a way to revisit step 1/2.
  - **Major:** visual language flips abruptly between compliance (centered modal, segment bar, full scrim) and tour (anchored callouts, "STEP X OF 3" text, no scrim, no segment bar) — no interstitial or shared component bridges the two halves of one conceptual flow.
  - **Major:** two entirely different step-indicator systems for what's supposed to be one 6-step flow, and neither actually counts to 6 — each half only counts to 3. Unify into one "step N of 6" component.
  - compliance-1 and compliance-2 use a "NEXT" button instead of the explicit "I understand" acknowledgment the spec requires per pane (each pane's confirmation writes its own audit row — "NEXT" doesn't convey that).
  - tour-3 uses "GOT IT" to close out — not a verb, functionally the same as the explicitly-banned "OK"/acknowledgment-phrase pattern.
  - compliance-1: step indicator has no numeric label, inconsistent with tour's explicit "STEP X OF 3."
  - compliance-3: final step's button still says "I UNDERSTAND," identical to steps 1-2, no signal this is the last compliance step before the tour begins.
  - All 6 frames: modal/callout scrim opacity well below the required flat 70% ink (cross-cutting #8).
  - ~~Coverage gap: no responsive breakpoints~~ — stale, a full 1024 variant exists for all 6 panes. No error/loading/empty states apply to this screen type (a static compliance/tour flow, not a data-fetch screen) — not a real gap. 768 still missing.
  - No issues confirmed: tour-3 correctly relabels its button "FINISH TOUR" (aside from "GOT IT" above — check which frame that applies to) and correctly omits "Skip Tour" as the last step; all 6 frames otherwise clean of placeholder text, clipping, contrast problems.

## 23. Not Found / Error — `*`

- **Route:** `*` (catch-all) · **Nav:** none (outside AppLayout) · **Priority:** 23
- **Page:** 404-1440 on 03 — Screens (`4:4`); 404-1024 + 500-1024 on 04 — States (`4:5`); 500-1440 on 00 — Foundations (`0:1`)
- **Node IDs:**

  | Frame | 1440 | 1024 |
  |---|---|---|
  | 404 | `171:2441` | `370:1790` |
  | 500 | `171:6250` | `370:10337` |
- **States built:** 404, 500/boundary-crash — each now also has a 1024 variant
- **Breakpoints:** 1440, 1024
- **Components:** route-string display, error-code display, console-error disclosure (500 only)
- **Spec:** [SCREENS.md §23](SCREENS.md) — 404 shows the route that missed + nav back; 500 shows an error id to quote in a bug report, a Reload action, and the last 3 console-visible errors behind a disclosure.
- **Bugs to fix:**
  - **Critical:** 404 frame has no shell/TopBar/brand mark at all — floats as a disconnected white card. Per SCREENS.md, Login and Not Found are the *only* screens outside AppLayout, meaning both should share the same no-shell treatment — but 404 is missing even a brand mark that 500 has. Decide the correct minimal treatment and apply to both consistently (note: an earlier audit pass flagged the opposite — 404 wrongly *including* the full shell — the two passes disagree; verify directly in Figma which is actually true before fixing).
  - 404: "Back to Dashboard" button shows a stray duplicate stroke/offset shadow not present on the same component instance on the 500 frame.
  - 404: icon block filled `--sand` — spec's state-block pattern defines only yellow (empty) or pink (error) fills, no sand variant. Pick one.
  - 500: headline reads "SOMETHING WENT WRONG" — the exact phrase the content-voice section names as the bad example to avoid. Rewrite to name the actor/cause.
  - 500: only has a "RELOAD" action with no secondary path back to the dashboard, despite copy implying reload might not fix it ("if it keeps happening").
  - 404 vs 500 copy scoping is inconsistent — 404 is generic/app-wide, 500 is scoped to one specific view. Pick one convention.
  - 500: console-error disclosure shows only an always-expanded state — no collapsed variant for what's implied to be a toggle.
  - 500: pink monospace error text on white looked borderline on contrast — verify against WCAG AA.
  - Both route-string (404) and error-code (500) boxes are oversized relative to their single line of content.
  - ~~Coverage gap: no responsive breakpoints~~ — stale, both 404 and 500 have a 1024 variant (`370:1790`, `370:10337`). 768 still missing.

---

## Summary for dev handoff

- **23/23 screens** are Figma-complete per the task registry; none are blocking on missing frames.
- **Node IDs above were pulled live from the Figma canvas** (via `use_figma`, 2026-08-11) and supersede the two static audit docs wherever they disagree — the canvas has moved on since either audit was written. Concretely: templates, schedules, proxies, integrations, webhook-log, api-keys, settings, account, system, suppression, and onboarding all now have loading/error/empty/1024 frames that one or both audits listed as missing. Each screen section above marks corrected claims with ~~strikethrough~~; **768 (tablet) remains genuinely unbuilt everywhere** — that gap is real, not stale.
- **Only 3 screens still have a genuine state-coverage gap** after live verification: webhook-log (no empty state for a never-configured webhook), settings (no empty state — arguably not needed for a settings screen), and account (no true empty state — arguably not needed either, since an authenticated account always has data).
- **3 screens have states that exist only as mis-filed orphans on page "00 — Foundations" (`0:1`)** instead of "03 — Screens" (`4:4`) — content is real and usable, just needs moving: schedule-detail (loading `248:2`, error `249:115`), results (loading `252:225`, error `253:332`), lead-detail (empty `255:442`, loading `256:549`, error `257:654`).
- **1024 (laptop) now exists for nearly every screen** — 21 of 23 (all except job-templates' extra states and a couple of drill-downs are covered; check each screen's node ID table above for its 1024 ID). **768 (tablet) exists for only 5 screens** — login, dashboard, categories, locations, and job-new — and even there it's broken wherever it's been attempted (no drawer/hamburger, tables don't convert to cards, per cross-cutting #4). Building 768 for the remaining 18 screens is the single largest remaining design gap.
- Fix the **12 cross-cutting issues** at the shared-component level first (`Shell/Sidebar` icons/label, radio/checkbox components, badge glyphs, scrim token, skeleton components, error-state scoping) — this resolves the majority of individual per-screen findings in one pass each.
- **Known backend gaps that constrain the Export screen:** XLSX, KML, JSONL, and Google Sheets export writers are not implemented (see [MODULES.md](MODULES.md) §8.3–8.6) — only CSV is real today.
