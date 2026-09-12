// Shared types, mirrored from backend Pydantic schemas (app/api/routers/*).

// "paused" and "cancelled" are only ever reached through the queue controls
// (POST /api/jobs/{id}/pause | cancel). No worker produces them, and a JobTarget
// is never "paused" — pausing is a property of the job, so an area that is
// already scraping either finishes or is cancelled with the rest.
export type JobStatus = "queued" | "running" | "paused" | "done" | "error" | "cancelled";

// Which queue controls the job will accept right now. Sent by the API rather
// than derived here so the button state and the endpoint that would 409 can't
// disagree (backend: app/workers/control.py::job_actions).
export interface JobActions {
  pause: boolean;
  resume: boolean;
  cancel: boolean;
  delete: boolean;
}

export interface Job {
  id: string;
  status: JobStatus;
  source: JobSource;
  /** Set on the New Job Wizard's review step; null for jobs created without one. */
  name: string | null;
  createdAt: string;
  actions: JobActions;
  /** Present only on list rows (GET /api/jobs) -- places-done/places-found, 0-100. */
  progressPct?: number;
  /** Present only on list rows (GET /api/jobs). */
  leadsCount?: number;
}

// GET /api/jobs/stats -- dashboard stat row. Proxy health and quota are absent
// on purpose: neither has a backing data source yet (jobs.py::get_stats).
export interface JobStats {
  jobsRunning: number;
  placesScrapedToday: number;
  /** null when no results have landed today yet (nothing to take a % of). */
  leadsWithEmailPct: number | null;
}

// GET /api/jobs/activity -- derived from Job.updated_at, not a real event log.
export interface ActivityEntry {
  jobId: string;
  jobName: string | null;
  kind: "started" | "finished" | "failed" | "cancelled" | "paused" | string;
  status: JobStatus;
  at: string;
}

// What the control endpoints answer with: the job's fresh payload plus a summary
// of what the call actually did, so the UI can say "paused, 3 areas finishing"
// rather than a bare "paused" and then look wrong when results keep arriving.
export interface JobControlResponse extends Job {
  paused?: { released: number; stillRunning: number };
  resumed?: { dispatched: number; status: JobStatus };
  cancelled?: { targetsCancelled: number; terminated: number };
}

export interface JobDeleteResponse {
  deleted: {
    jobId: string;
    wasLive: boolean;
    targets: number;
    results: number;
    exports: number;
    filesRemoved: number;
  };
}

// GET /api/jobs/{id} returns the same shape plus its targets (jobs.py::_job_dict).
export interface JobDetail extends Job {
  targets: JobTarget[];
}

export interface JobTarget {
  id: string;
  keyword: string;
  locationLabel: string;
  // The ZIP this target searches, plus what it was picked under. Null on a
  // hand-typed location, which has a label and nothing else.
  zipCode: string | null;
  city: string | null;
  region: string | null;
  country: string | null;
  status: JobStatus;
  // Two-phase: the feed scrape sets placesFound, then each place scrape counts
  // itself off in placesDone. The target is only done when they meet.
  placesFound: number;
  placesDone: number;
  // "queued" now means one of two things, and this is the difference: false is
  // waiting behind the concurrency limit, true is handed to a worker.
  dispatched: boolean;
}

export type JobSource = "google" | "bing";

export interface Result {
  id: string;
  /** Present on every Result row (backend: app/api/routers/jobs.py::_result_dict). */
  jobId: string;
  category: string | null;
  name: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  zipCode: string | null;
  /**
   * Both may hold several values joined with ", ": the Maps listing's own,
   * followed by whatever the deep site crawl found on the business's website.
   * Duplicates across the two sources are merged, so a number Maps and the site
   * both list appears once.
   */
  phone: string | null;
  email: string | null;
  /** Direct mobile / personal phone lines. */
  mobilePhone: string | null;
  /** Discovered decision maker (Owner, Founder, CEO names). */
  decisionMaker: string | null;
  website: string | null;
  latitude: number | null;
  longitude: number | null;
  // Social profiles, one column per network, filled by the deep site crawler
  // only — null on every row scraped with it switched off. `otherSocials` is the
  // joined tail (Pinterest, Telegram, Yelp …) that has no column of its own.
  facebook: string | null;
  instagram: string | null;
  linkedin: string | null;
  twitter: string | null;
  youtube: string | null;
  tiktok: string | null;
  whatsapp: string | null;
  otherSocials: string | null;
  scrapedAt: string;

  // Lead Detail only (backend: app/api/routers/jobs.py::_result_dict). Present
  // on every Result row, including the ones the paginated grid returns.
  status: LeadStatus;
  tags: string[];
  suppressed: boolean;
  /** From the place scraper's own listing data. Never set by anything else. */
  rating: number | null;
  /** Total review count from Google Maps listing. */
  reviewsCount: number | null;
  /** Sentiment analysis score (0.0 to 1.0). */
  sentimentScore: number | null;
  /** Sentiment label (Positive, Neutral, Mixed, Negative). */
  sentimentLabel: string | null;
  /** Extracted pain points / complaints summary from customer reviews. */
  painPoints: string | null;
  /** Whether the Google/Bing Maps listing has a "Claim this business" prompt. */
  isUnclaimed: boolean | null;
  /** "maps listing" | "site crawl" | null -- which stage first supplied the value. */
  phoneSource: string | null;
  emailSource: string | null;
  /** From a one-off home-page fetch (backend: tech_fingerprint.py), not the deep crawler. */
  techStack: string[];
}

// Lead Detail's claimed/closed badge (Figma: Identity Block > Badge Row).
// "closed" has no UI action yet -- nothing sets it -- but the type allows for
// it rather than a bare open/claimed boolean, matching the backend column.
export type LeadStatus = "open" | "claimed" | "closed";

// Recomputed on every read from columns already on the row (phone/email/
// website/rating/tech stack/socials) -- never persisted, never fabricated.
export interface LeadScore {
  value: number;
  reasons: string[];
}

// One changed field on a re-scraped lead (backend/app/db/models/result.py::
// ResultHistory). Written only when a later job's result shares an earlier
// one's place_key and a tracked field (phone/email/rating) differs -- so this
// is empty for the common case of a lead scraped exactly once.
export interface ResultHistoryEntry {
  field: string;
  oldValue: string | null;
  newValue: string | null;
  changedAt: string;
}

// GET/PATCH /api/jobs/{jobId}/results/{resultId} -- same Result shape plus the
// two fields only the single-lead endpoint computes/queries.
export interface LeadDetail extends Result {
  history: ResultHistoryEntry[];
  score: LeadScore;
}

// Every list endpoint (jobs, results) answers with this envelope.
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export interface GeoOption {
  id: string;
  name: string;
  code?: string; // present on /api/geo/countries rows only
}

// GET /api/geo/zips answers with an envelope, not a bare list: a region-wide
// request can outrun the server's cap, and "select all" over a silently
// truncated list would queue fewer ZIPs than the user asked for.
export interface ZipOption extends GeoOption {
  cityName: string;
}

export interface ZipPage {
  items: ZipOption[];
  total: number;
  truncated: boolean;
}

// GET /api/geo/cities — same envelope, same reason: a large region holds tens
// of thousands of them, so the picker has to know it's seeing a capped slice.
export interface CityPage {
  items: GeoOption[];
  total: number;
  truncated: boolean;
  // False for the ~131 countries with no postal code system. There is no source
  // that can supply ZIPs for them, so the picker selects cities as the search
  // areas instead — see ZipCascadeSelect.
  regionHasZips: boolean;
}

// One queued search area — a ZIP, or a hand-typed label with nothing under it.
// Mirrors LocationSpec in backend/app/api/routers/jobs.py; sent as-is to
// POST /api/jobs and stored on the JobTarget it becomes.
export interface LocationTarget {
  /** Stable key for React lists and dedup: the geo zip id, or the label itself. */
  id: string;
  /** What gets appended to the keyword in the Maps query. */
  label: string;
  zipCode: string | null;
  city: string | null;
  region: string | null;
  country: string | null;
}

// Where the ZIP list is being drawn from in the cascade: one city, or every
// city in the selected state.
export type ZipScope = "city" | "region";

// Mirrors GET /api/auth/me.
export type TeamRole = "owner" | "operator" | "viewer";

export interface CurrentUser {
  id: string;
  email: string;
  role: TeamRole;
  /** NULL until the 3-pane compliance flow (Onboarding) is completed --
   * gates whether that modal shows on this load. */
  complianceAckAt: string | null;
}

// Mirrors GET /api/auth/license. Replaces the legacy title-bar
// "...7.8.2 [UNREGISTERED]..." check (MainForm.ValidateRegistration).
export interface License {
  plan: string | null;
  seats: number;
  expiresAt: string | null;
  active: boolean;
}

// Mirrors GET /api/auth/account (backend/app/api/routers/auth.py) — backs the
// Account & Billing screen. One fetch for signed-in info, license, quota, and
// usage history. Installation-wide (this app has no multi-tenancy), not
// scoped per-user, same as every other cross-cutting count elsewhere.
export interface AccountResponse {
  user: {
    id: string;
    email: string;
    role: string;
    /** Derived from `totp_secret IS NOT NULL` — no dedicated enrollment flow
     * exists yet, so this reports status, not a toggle. */
    twoFactorEnrolled: boolean;
  };
  apiVersion: string;
  license: License;
  quota: {
    placesThisMonth: number;
    /** Ceiling from a small plan→limit catalog (backend/app/core/plans.py) —
     * `License.plan` has no numeric ceiling of its own, unknown plans (incl.
     * "dev") fall back to a documented default rather than showing unlimited. */
    placesLimit: number;
    exportsThisMonth: number;
    exportsLimit: number;
    /** Start of next calendar month (UTC), ISO 8601. */
    resetsAt: string;
  };
  /**
   * Real per-month counts for whichever of the last 12 calendar months
   * actually have at least one scraped result — oldest first. Not padded to
   * a fixed 12 bars: a fresh install has no organic history before its own
   * first job, so months with zero results are simply absent rather than
   * shown as fabricated zero-bars.
   */
  usageHistory: { month: string; places: number }[];
}

// Mirrors POST /api/categories/upload (backend/app/api/routers/categories.py).
export interface CategoryUpload {
  keywords: string[];
  count: number;
  skipped: number;
  truncated: boolean;
}

// Email verification modes (Settings > Enrichment). "syntax_mx" adds a real
// DNS MX lookup (backend/app/scraping/common/email_verify.py) but isn't wired
// into the scrape pipeline yet -- see that module's docstring. Figma's third
// option ("+ SMTP") is deliberately not offered at all (real abuse-surface
// with no rate-limit story this cycle) rather than faked.
export type EmailVerificationMode = "off" | "syntax_mx";

// The six signals backend/app/scraping/common/lead_score.py computes.
// Figma's handoff lists more (review count, opening hours, claimed listing,
// contact form, permanently closed, chain/franchise match) that have no
// backing column on Result and nothing scrapes -- not offered as
// configurable weights for signals that don't exist.
// Keys match backend/app/core/runtime_settings.SCORE_WEIGHT_KEYS verbatim --
// this is a plain dict on the wire (not a pydantic model), so it is not
// camelCased like the rest of the response.
export interface ScoreWeights {
  email: number;
  website: number;
  phone: number;
  social: number;
  rating_high: number;
  rating_good: number;
  decision_maker: number;
  mobile_phone: number;
}

// Mirrors GET/PATCH /api/settings (backend/app/api/routers/settings.py).
// Installation-wide, not per-user — one worker fleet, one limit.
export interface AppSettings {
  /** How many areas may be scraped at the same time. */
  concurrentTargets: number;
  /** Ceiling the API will accept for the above. */
  maxConcurrentTargets: number;
  /** Areas in flight right now, across every job. */
  runningTargets: number;
  /** Areas queued but still behind the limit. */
  waitingTargets: number;
  /** Whether a result's website gets crawled for extra contact details. */
  deepCrawlEnabled: boolean;
  /** How many pages of one website a crawl may read. */
  deepCrawlMaxPages: number;
  /** Ceiling the API will accept for the above. */
  maxDeepCrawlPages: number;
  /** Per-host cooldown base (seconds). Takes effect on next worker restart —
   * see backend rate_limit.get_tracker's docstring. */
  cooldownBaseS: number;
  maxCooldownBaseS: number;
  /** Celery retry ceiling, applied uniformly across feed/place/export tasks. */
  retryCeiling: number;
  maxRetryCeiling: number;
  /** Whether a result's website gets an extra fetch to detect its platform/tooling. */
  techFingerprintEnabled: boolean;
  emailVerificationMode: EmailVerificationMode;
  emailVerificationModes: EmailVerificationMode[];
  scoreWeights: ScoreWeights;
  /** Days a result row is kept before the daily purge sweep removes it. */
  resultsRetentionDays: number;
  maxResultsRetentionDays: number;
  /** Days a generated export file is kept before the daily purge sweep removes it. */
  exportRetentionDays: number;
  maxExportRetentionDays: number;
  /** Whether waterfall third-party enrichment runs on missing/generic emails. */
  waterfallEnrichmentEnabled: boolean;
  waterfallProviders: string[];
  allWaterfallProviders: string[];
  hunterApiKey: string | null;
  prospeoApiKey: string | null;
  datagmaApiKey: string | null;
  findymailApiKey: string | null;
}

// Mirrors GET/POST /api/templates (backend/app/api/routers/templates.py).
export interface JobTemplate {
  id: string;
  name: string;
  source: JobSource;
  keywordCount: number;
  areaCount: number;
  targetCount: number;
  keywords: string[];
  locations: LocationTarget[];
  createdAt: string;
  lastRunAt: string | null;
}

// Mirrors GET/POST /api/schedules (backend/app/api/routers/schedules.py).
export type ScheduleResult = "done" | "error" | "misfired";

export interface Schedule {
  id: string;
  name: string;
  templateId: string;
  cadence: string;
  timezone: string;
  enabled: boolean;
  nextRunAt: string | null;
  lastRunAt: string | null;
  lastResult: ScheduleResult | null;
  lastJobId: string | null;
}

// GET /api/schedules/{id}/runs -- no new/changed/disappeared counts: there is
// no place-identity tracking across separate jobs to diff against yet.
export interface ScheduleRun {
  jobId: string;
  startedAt: string;
  durationSeconds: number;
  targetsTotal: number;
  placesFound: number;
  resultsCount: number;
  status: JobStatus;
}

// XLSX/KML are real; JSONL/Sheets are Figma-forward-compat only -- the
// backend has no writer for either (docs/SCREENLIST.md's own note on the
// Export screen). Kept out of this union so the format picker can't offer them.
export type ExportFormat = "csv" | "xlsx" | "kml";

// Mirrors app/db/models/export.py::COLUMN_GROUPS. "reviews" from the Figma
// IDENTITY group is deliberately absent -- no review-count field exists.
export type ExportColumnGroup = "identity" | "contact" | "location" | "sentiment" | "scoring";

export const EXPORT_COLUMN_GROUPS: { key: ExportColumnGroup; label: string; fields: string }[] = [
  { key: "identity", label: "Identity", fields: "Name · Category · Rating · Reviews · Decision Maker" },
  { key: "contact", label: "Contact", fields: "Phone · Mobile · Website · Email · Socials" },
  { key: "location", label: "Location", fields: "Address · City · State · Zip · Lat/Lng" },
  { key: "sentiment", label: "Sentiment", fields: "Sentiment Score · Label · Customer Pain Points" },
  { key: "scoring", label: "Scoring", fields: "Score · Signals" },
];

// Only "all" does anything server-side today -- see Export.row_scope's
// column comment on why filter/selection scopes aren't wired yet.
export type ExportRowScope = "all";

// Mirrors GET/POST /api/exports (backend/app/api/routers/exports.py).
export interface ExportRecord {
  id: string;
  jobId: string;
  format: ExportFormat;
  status: "pending" | "running" | "done" | "error";
  columns: ExportColumnGroup[] | null;
  rowScope: ExportRowScope | null;
  rowCount: number | null;
  sizeBytes: number | null;
  downloadUrl?: string;
  generatedAt?: string;
  expiresAt?: string;
  expired?: boolean;
}

// Mirrors GET/POST /api/suppression (backend/app/api/routers/suppression.py).
// Global (install-wide, like AppSettings) -- not scoped per job or per user.
export type SuppressionKind = "domain" | "email" | "place";

export interface SuppressionEntry {
  id: string;
  kind: SuppressionKind;
  value: string;
  reason: string | null;
  createdBy: string;
  createdAt: string;
  /** Live count of results still matching this rule right now -- should be
   * 0 in steady state, since a match is deleted the moment the rule exists. */
  rowCount: number;
}

// Only present on the POST response (create), not on list rows.
export interface SuppressionCreateResponse extends SuppressionEntry {
  rowsRemoved: number;
}

export interface SuppressionBulkResponse {
  created: number;
  skipped: number;
  rowsRemoved: number;
}

export type IntegrationProvider = "webhooks" | "slack" | "hubspot" | "pipedrive" | "gohighlevel" | "rest" | "sheets";
export type IntegrationStatus = "connected" | "not_connected";

export interface IntegrationCard {
  provider: IntegrationProvider;
  status: IntegrationStatus;
  /** Only "webhooks" has a real CONFIGURE flow today -- see backend
   * app/db/models/integration.py for why the rest don't yet. */
  configurable: boolean;
  lastEventAt: string | null;
  lastEventSummary: string | null;
}

export interface WebhookConfig {
  provider: "webhooks";
  status: IntegrationStatus;
  url: string | null;
  events: string[];
  availableEvents: string[];
  signingSecretMasked: string | null;
  lastEventAt: string | null;
  lastEventSummary: string | null;
}

export interface WebhookSecretResponse extends WebhookConfig {
  /** Full secret, present only on the rotate response -- shown once. */
  signingSecret: string;
}

// Mirrors GET/POST /api/team (backend/app/api/routers/team.py). No
// multi-tenancy in this app -- every row is the one workspace's member list.
export type TeamMemberStatus = "active" | "disabled";

export interface RoleMatrixRow {
  capability: string;
  owner: boolean;
  operator: boolean;
  viewer: boolean;
}

export interface TeamMember {
  id: string;
  email: string;
  role: TeamRole;
  status: TeamMemberStatus;
  lastSeenAt: string | null;
  /** True within the server's "Online now" freshness window (2 min);
   * otherwise render a relative time from `lastSeenAt` on the frontend. */
  onlineNow: boolean;
}

export interface TeamResponse {
  roleMatrix: RoleMatrixRow[];
  seats: { used: number; total: number };
  members: TeamMember[];
}

export interface InviteMemberResponse extends TeamMember {
  /** One-time provisioning password -- there's no email/self-signup in this
   * app, so this is the only place it's ever shown (backend/app/api/routers
   * /team.py::invite_member). */
  tempPassword: string;
}

// Mirrors GET/POST /api/proxies (backend/app/api/routers/proxies.py). DB-backed
// as of the Proxies screen cycle -- app/scraping/proxy/pool.py's "list" mode
// reads this table; "single"/"free" modes are separate and have no UI here.
export type ProxyStatus = "active" | "disabled" | "retired" | "cooling";
export type ProxyProtocol = "http" | "https" | "socks5";

export interface ProxyRecord {
  id: string;
  host: string;
  port: number;
  protocol: ProxyProtocol;
  country: string | null;
  status: ProxyStatus;
  successCount: number;
  failureCount: number;
  blockCount: number;
  /** Lifetime use count -- Figma's "LEASES" column. Not a concurrency gauge;
   * see app/db/models/proxy.py's Proxy.total_uses docstring. */
  totalUses: number;
  /** 0-100, or null if this proxy has never been used. */
  successRate: number | null;
  blockRate: number | null;
  avgLatencyMs: number | null;
  coolingUntil: string | null;
  lastUsedAt: string | null;
  createdAt: string;
}

export interface ProxyStats {
  healthy: number;
  cooling: number;
  /** disabled + retired combined -- see backend get_proxy_stats's comment. */
  retired: number;
  avgLatencyMs: number | null;
  /** Lifetime, not a rolling 1h window -- there's no timestamped event
   * history to compute a real window from, only running counters. */
  blockRatePct: number | null;
  total: number;
}

export interface ProxyTestResult {
  ok: boolean;
  detail: string;
  latencyMs: number;
  proxy: ProxyRecord;
}

export interface ProxyBulkResponse {
  created: number;
  skipped: number;
}

// Mirrors GET/POST/DELETE /api/api-keys (backend/app/api/routers/api_keys.py).
export type ApiKeyScope = "read_results" | "create_jobs" | "export" | "admin";

export interface ApiKeyRecord {
  id: string;
  label: string;
  /** e.g. "msk_live_7f2a" -- the only fragment of the key ever shown again. */
  prefix: string;
  scopes: ApiKeyScope[];
  createdAt: string;
  lastUsedAt: string | null;
  expiresAt: string | null;
  /** 30 daily request counts, oldest first. Real counts once API-key auth is
   * wired to any route (not yet) -- starts at 30 zeros, not fabricated. */
  usageDaily: number[];
}

export interface ApiKeysResponse {
  keys: ApiKeyRecord[];
}

export interface CreateApiKeyResponse extends ApiKeyRecord {
  /** Full plaintext key -- shown once, on this response only. */
  key: string;
}

// Mirrors GET /api/audit* (backend/app/api/routers/audit.py).
export interface AuditEvent {
  id: string;
  timestamp: string;
  actor: string | null;
  action: string;
  target: string | null;
  ip: string | null;
  success: boolean;
  /** Present only for actions that changed fields (e.g. settings.updated);
   * null means the row has no expandable before/after diff. */
  beforeAfter: { before: Record<string, unknown>; after: Record<string, unknown> } | null;
}

export interface AuditEventsResponse {
  events: AuditEvent[];
}

export interface AuditActorsResponse {
  actors: string[];
}

export interface AuditActionTypesResponse {
  actionTypes: string[];
}

// Mirrors GET /api/system (backend/app/api/routers/system.py). Figma's mock
// also shows BROWSER POOL/OBJECT STORE tiles and a RUN SEED action -- this
// app has neither subsystem (Playwright launches per-scrape, exports write
// to local disk) and the seed script isn't API-triggerable, so both are
// omitted rather than faked; see that router's docstring.
export interface ComponentStatus {
  status: "up" | "down";
  error?: string;
}

export interface SystemWorker {
  hostname: string;
  activeTasks: number;
  lastHeartbeat: string;
  online: boolean;
}

export interface SystemHealthResponse {
  components: {
    api: ComponentStatus;
    appDb: ComponentStatus;
    geoDb: ComponentStatus;
    redis: ComponentStatus;
    celeryWorkers: ComponentStatus;
  };
  queueDepth: {
    queued: number;
    dispatched: number;
    running: number;
    waiting: number;
  };
  workers: SystemWorker[];
  geoSeed: {
    countries: number;
    states: number;
    cities: number;
    postalCodes: number;
  };
  version: {
    api: string;
    playwright: string;
  };
}
