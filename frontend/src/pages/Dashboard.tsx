// Jobs / Dashboard screen (Figma [SCREEN] dashboard). Legacy equivalent: MainForm.
//
// Creating a job crosses the keyword draft with the queued ZIP codes -- one
// JobTarget per pair, exactly what `jobs.py::create_job` does server-side -- so the
// target count shown here is the number of scrapes about to be queued.
//
// The stat row and activity panel only show what the backend can actually back:
// jobs-running/places-today/leads-with-email% come from real tables
// (jobs.py::get_stats), and proxy pool health comes from the Proxies screen's
// own endpoint (proxies.py::get_proxy_stats) -- a separate, non-blocking query
// since it's a different subsystem. Usage quota is still omitted: quota_for_plan
// only backs a display ceiling today (GET /license, account/usage), nothing
// enforces it against actual usage, so a number here would overstate what it
// means. Activity is derived from job status transitions (jobs.py::get_activity),
// not a real cross-cutting event log, so it only reports job start/finish/fail,
// not proxy/schedule events.

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import NeoButton from "../components/neo/NeoButton";
import NeoProgress from "../components/neo/NeoProgress";
import NeoStatusBadge from "../components/neo/NeoStatusBadge";
import InlineWarning from "../components/neo/InlineWarning";
import SystemLogPanel from "../components/SystemLogPanel";
import { useSystemLogSocket } from "../hooks/useSystemLogSocket";
import { KEYWORD_SEPARATORS, useJobDraft } from "../state/JobDraftContext";
import { color, font } from "../theme/neobrutalist";
import type { ActivityEntry, Job, JobStats, Page, ProxyStats } from "../types";

const LIVE_STATUSES = new Set(["queued", "running", "paused"]);

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function PageHeader() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 24 }}>
      <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>JOBS</h1>
      <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
        Start a job, or check on what&rsquo;s already running.
      </p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: color.white,
        border: `3px solid ${color.ink}`,
        boxShadow: "6px 6px 0px 0px black",
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 20,
        marginBottom: 24,
      }}
    >
      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", textTransform: "uppercase", color: color.ink }}>
        {title}
      </p>
      {children}
    </div>
  );
}

const TILE_FILLS = [color.yellow, color.green, color.pink, color.blue] as const;

function StatTile({ label, value, fill }: { label: string; value: string; fill: string }) {
  const isPink = fill === color.pink;
  return (
    <div
      style={{
        flex: 1,
        background: fill,
        border: `3px solid ${color.ink}`,
        boxShadow: "6px 6px 0px 0px black",
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        color: isPink ? color.white : color.ink,
        boxSizing: "border-box",
      }}
    >
      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 11, letterSpacing: "0.33px", textTransform: "uppercase" }}>
        {label}
      </p>
      <p style={{ margin: 0, fontFamily: font.head, fontSize: 24 }}>{value}</p>
    </div>
  );
}

function StatRow({ stats, proxyStats }: { stats: JobStats; proxyStats?: ProxyStats }) {
  const tiles = [
    { label: "JOBS RUNNING", value: String(stats.jobsRunning) },
    { label: "PLACES SCRAPED TODAY", value: stats.placesScrapedToday.toLocaleString() },
    { label: "LEADS WITH EMAIL TODAY", value: stats.leadsWithEmailPct === null ? "—" : `${stats.leadsWithEmailPct}%` },
    // No proxies configured yet (pool empty in "single"/"free" mode) reads as
    // "—", not "0 healthy" -- there's nothing unhealthy about a pool nobody's
    // added rows to.
    {
      label: "PROXY POOL HEALTHY",
      value: !proxyStats || proxyStats.total === 0 ? "—" : `${proxyStats.healthy}/${proxyStats.total}`,
    },
  ];
  return (
    <div className="neo-responsive-stats" style={{ display: "flex", gap: 16, width: "100%", marginBottom: 24 }}>
      {tiles.map((tile, i) => (
        <StatTile key={tile.label} {...tile} fill={TILE_FILLS[i]} />
      ))}
    </div>
  );
}

function StatRowSkeleton() {
  return (
    <div className="neo-responsive-stats" style={{ display: "flex", gap: 16, width: "100%", marginBottom: 24 }}>
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="neo-skeleton" style={{ flex: 1, border: `3px solid ${color.rule}`, boxShadow: "6px 6px 0px 0px black", height: 84 }} />
      ))}
    </div>
  );
}

function QuickStart() {
  const navigate = useNavigate();
  const draft = useJobDraft();
  const queryClient = useQueryClient();
  const { license } = useAuth();

  const createJob = useMutation({
    mutationFn: () =>
      api.post<Job>("/api/jobs/", {
        keywords: draft.keywords,
        locations: draft.locations.map(({ label, zipCode, city, region, country }) => ({
          label,
          zipCode,
          city,
          region,
          country,
        })),
        source: draft.source,
      }),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      navigate(`/results/${job.id}`);
    },
  });

  const licenseBlocked = license !== null && !license.active;
  const canStart = draft.targetCount > 0 && !createJob.isPending && !licenseBlocked;

  return (
    <Panel title="Quick start">
      <div style={{ display: "flex", gap: 24, width: "100%" }}>
        <QuickChipField
          label="Keywords"
          values={draft.keywords}
          hint={`${draft.keywords.length} keyword${draft.keywords.length === 1 ? "" : "s"} queued`}
          placeholder="plumber, roofing contractor"
          onAdd={(raw) => draft.addKeywords(raw.split(KEYWORD_SEPARATORS))}
          onRemove={draft.removeKeyword}
        />
        <QuickChipField
          label="Areas queued"
          values={draft.locations.map((l) => l.label)}
          hint={`${draft.locations.length} area${draft.locations.length === 1 ? "" : "s"} queued`}
          placeholder="Add areas from the Locations page"
          readOnly
          onRemoveById={(label) => {
            const match = draft.locations.find((l) => l.label === label);
            if (match) draft.removeLocation(match.id);
          }}
        />
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
        <p style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>
          {draft.targetCount} TARGET{draft.targetCount === 1 ? "" : "S"} WILL BE QUEUED
        </p>
        <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
          One search per keyword × area pair.
        </p>
      </div>

      {licenseBlocked && (
        <InlineWarning tone="pink" fontSize={12} fontWeight={700}>
          No active license on this account — job creation is gated. See the Account page.
        </InlineWarning>
      )}
      {createJob.isError && (
        <InlineWarning tone="pink" fontSize={12} fontWeight={700}>
          {createJob.error instanceof ApiError
            ? createJob.error.message
            : "Couldn't reach the API server"}
        </InlineWarning>
      )}

      <div style={{ display: "flex", gap: 16 }}>
        <NeoButton variant="primary" loading={createJob.isPending} disabled={!canStart} onClick={() => createJob.mutate()}>
          Start job
        </NeoButton>
        <NeoButton variant="secondary" onClick={() => navigate("/jobs/new")}>
          Open full wizard
        </NeoButton>
      </div>
    </Panel>
  );
}

interface QuickChipFieldProps {
  label: string;
  values: string[];
  hint: string;
  placeholder: string;
  onAdd?: (raw: string) => void;
  onRemove?: (value: string) => void;
  onRemoveById?: (value: string) => void;
  readOnly?: boolean;
}

function QuickChipField({ label, values, hint, placeholder, onAdd, onRemove, onRemoveById, readOnly }: QuickChipFieldProps) {
  const remove = onRemove ?? onRemoveById;
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}>
      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.3675px", textTransform: "uppercase", color: color.ink }}>
        {label}
      </p>
      <div style={{ border: `3px solid ${color.ink}`, minHeight: 40, display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center", padding: "6px 12px", background: color.white, boxSizing: "border-box" }}>
        {values.length === 0 && !readOnly && (
          <input
            placeholder={placeholder}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;
              const value = (e.target as HTMLInputElement).value.trim();
              if (!value) return;
              onAdd?.(value);
              (e.target as HTMLInputElement).value = "";
            }}
            style={{ border: "none", outline: "none", fontFamily: font.body, fontSize: 13, flex: 1, minWidth: 120 }}
          />
        )}
        {values.length === 0 && readOnly && (
          <span style={{ fontFamily: font.body, fontSize: 12, color: color.ink60 }}>{placeholder}</span>
        )}
        {values.map((value) => (
          <span
            key={value}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              border: `2px solid ${color.ink}`,
              background: color.white,
              padding: "3px 8px",
              fontFamily: font.body,
              fontWeight: 500,
              fontSize: "12.5px",
              color: color.ink,
            }}
          >
            {value.toUpperCase()}
            {remove && (
              <button
                type="button"
                onClick={() => remove(value)}
                style={{ border: "none", background: "transparent", padding: 0, cursor: "pointer", fontSize: 10, color: color.ink }}
              >
                ✕
              </button>
            )}
          </span>
        ))}
      </div>
      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 10, letterSpacing: "0.4px", textTransform: "uppercase", color: color.ink60 }}>
        {hint}
      </p>
    </div>
  );
}

const TABLE_HEADERS = ["JOB", "SOURCE", "STATUS", "PROGRESS", "CREATED", "LEADS", "ACTIONS"];

function RecentJobsTable({ jobs }: { jobs: Job[] }) {
  const navigate = useNavigate();

  if (jobs.length === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: 48 }}>
        <div style={{ transform: "rotate(6deg)" }}>
          <div style={{ width: 64, height: 64, background: color.yellow, border: `3px solid ${color.ink}` }} />
        </div>
        <p style={{ margin: 0, fontFamily: font.head, fontSize: 32, color: color.ink, textAlign: "center" }}>NO JOBS YET</p>
        <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 400 }}>
          Set your keywords and areas above, then start your first job.
        </p>
      </div>
    );
  }

  return (
    <div style={{ width: "100%" }}>
      {/* Cross-cutting #4: at <=768px this stayed a dense multi-column table
          instead of converting to stacked cards -- desktop/tablet keep the
          real table (horizontal-scrollable as a fallback above 768), mobile
          gets a card list of the same rows via .neo-responsive-cards. */}
      <div className="neo-responsive-table" style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 760 }}>
          <thead>
            <tr style={{ background: color.sand, borderBottom: `3px solid ${color.ink}` }}>
              {TABLE_HEADERS.map((h) => (
                <th
                  key={h}
                  style={{
                    textAlign: h === "LEADS" || h === "ACTIONS" ? "right" : "left",
                    padding: "0 12px",
                    height: 36,
                    fontFamily: font.body,
                    fontWeight: 700,
                    fontSize: "10.5px",
                    letterSpacing: "0.3675px",
                    textTransform: "uppercase",
                    color: color.ink,
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {jobs.map((job, i) => (
              <tr
                key={job.id}
                className="neo-row-enter"
                style={{ borderBottom: `2px solid ${color.rule}`, height: 36, ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms` }}
              >
                <td style={{ padding: "0 12px", fontFamily: font.body, fontSize: "12.5px", color: color.ink, whiteSpace: "nowrap" }}>
                  <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink60, marginRight: 8 }}>
                    #{job.id.slice(0, 8)}
                  </span>
                  {job.name ?? (job.source === "bing" ? "Bing Maps" : "Google Maps")}
                </td>
                <td style={{ padding: "0 12px", fontFamily: font.body, fontSize: "12.5px", color: color.ink }}>
                  {job.source === "bing" ? "Bing" : "Google"}
                </td>
                <td style={{ padding: "0 12px" }}>
                  <NeoStatusBadge status={job.status} />
                </td>
                <td style={{ padding: "0 12px" }}>
                  <NeoProgress pct={job.progressPct ?? 0} />
                </td>
                <td style={{ padding: "0 12px", fontFamily: font.mono, fontSize: 12, color: color.ink60, whiteSpace: "nowrap" }}>
                  {timeAgo(job.createdAt)}
                </td>
                <td style={{ padding: "0 12px", textAlign: "right", fontFamily: font.mono, fontSize: 12, color: color.ink }}>
                  {job.leadsCount ?? 0}
                </td>
                <td style={{ padding: "0 12px", textAlign: "right", whiteSpace: "nowrap" }}>
                  <NeoButton variant="ghost" size="sm" onClick={() => navigate(`/results/${job.id}`)}>
                    Results
                  </NeoButton>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="neo-responsive-cards">
        {jobs.map((job, i) => (
          <div
            key={job.id}
            className="neo-row-enter"
            style={{
              border: `3px solid ${color.ink}`,
              background: color.white,
              padding: 12,
              display: "flex",
              flexDirection: "column",
              gap: 8,
              ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms`,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
              <div style={{ minWidth: 0 }}>
                <p style={{ margin: 0, fontFamily: font.mono, fontSize: 11, color: color.ink60 }}>#{job.id.slice(0, 8)}</p>
                <p style={{ margin: "2px 0 0", fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink, wordBreak: "break-word" }}>
                  {job.name ?? (job.source === "bing" ? "Bing Maps" : "Google Maps")}
                </p>
              </div>
              <NeoStatusBadge status={job.status} />
            </div>
            <NeoProgress pct={job.progressPct ?? 0} />
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
              <span>{job.source === "bing" ? "Bing" : "Google"} · {timeAgo(job.createdAt)}</span>
              <span style={{ fontFamily: font.mono, color: color.ink }}>{job.leadsCount ?? 0} leads</span>
            </div>
            <NeoButton variant="ghost" size="sm" onClick={() => navigate(`/results/${job.id}`)}>
              Results
            </NeoButton>
          </div>
        ))}
      </div>
    </div>
  );
}

function RecentJobsSkeleton() {
  return (
    <div style={{ width: "100%" }}>
      <div className="neo-skeleton" style={{ height: 36, borderBottom: `3px solid ${color.ink}` }} />
      {[0, 1, 2, 3, 4].map((i) => (
        <div key={i} className="neo-skeleton" style={{ height: 36, border: `3px solid ${color.rule}`, borderTop: "none", marginTop: -3 }} />
      ))}
    </div>
  );
}

const ACTIVITY_GLYPH: Record<string, { glyph: string; fill: string }> = {
  finished: { glyph: "✓", fill: color.green },
  failed: { glyph: "✕", fill: color.pink },
  started: { glyph: "●", fill: color.ink },
  cancelled: { glyph: "✕", fill: color.ink60 },
  paused: { glyph: "!", fill: color.orange },
};

const ACTIVITY_LABEL: Record<string, string> = {
  finished: "finished",
  failed: "failed",
  started: "started",
  cancelled: "cancelled",
  paused: "paused",
};

function ActivityStrip({ items }: { items: ActivityEntry[] }) {
  if (items.length === 0) {
    return (
      <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
        Nothing has happened yet — activity will show up here once your first job runs.
      </p>
    );
  }
  return (
    <div style={{ width: "100%" }}>
      {items.map((entry, i) => {
        const meta = ACTIVITY_GLYPH[entry.kind] ?? { glyph: "●", fill: color.ink };
        return (
          <div
            key={`${entry.jobId}-${entry.at}`}
            className="neo-row-enter"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "8px 0",
              borderBottom: i === items.length - 1 ? "none" : `2px solid ${color.rule}`,
              ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms`,
            }}
          >
            <span style={{ width: 14, textAlign: "center", fontFamily: font.body, fontWeight: 700, fontSize: 12, color: meta.fill }}>
              {meta.glyph}
            </span>
            <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink60, whiteSpace: "nowrap" }}>
              {new Date(entry.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
            <span style={{ flex: 1, fontFamily: font.body, fontSize: 13, color: color.ink }}>
              {entry.jobName ?? `Job #${entry.jobId.slice(0, 8)}`} {ACTIVITY_LABEL[entry.kind] ?? entry.kind}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function ActivitySkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="neo-skeleton" style={{ height: 14, width: 400, maxWidth: "100%", border: `3px solid ${color.rule}` }} />
      ))}
    </div>
  );
}

// Job-lifecycle event types the system log stream carries that should move the
// numbers on this page -- a superset check against ACTIVITY_LABEL's keys plus
// "result" (a lead landing changes PLACES/LEADS today, not just job status).
const STATS_INVALIDATING_EVENTS = new Set(["finished", "failed", "started", "cancelled", "paused", "result"]);

export default function Dashboard() {
  const queryClient = useQueryClient();

  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.get<Page<Job>>("/api/jobs/?page=1&page_size=50"),
    refetchInterval: (query) =>
      query.state.data?.items.some((job) => LIVE_STATUSES.has(job.status)) ? 3000 : false,
  });

  const statsQuery = useQuery({
    queryKey: ["jobs", "stats"],
    queryFn: () => api.get<JobStats>("/api/jobs/stats"),
    // Backstop only -- the system log socket below invalidates this the moment a
    // relevant event lands, so 15s just covers a dropped/reconnecting socket.
    refetchInterval: 15000,
  });

  const activityQuery = useQuery({
    queryKey: ["jobs", "activity"],
    queryFn: () => api.get<{ items: ActivityEntry[] }>("/api/jobs/activity"),
    refetchInterval: 15000,
  });

  // Not gated into isLoading/isError below: this is its own subsystem (the
  // Proxies screen's pool), and a hiccup fetching it shouldn't blank the
  // whole dashboard over one stat tile. StatRow already renders "—" when this
  // hasn't landed yet.
  const proxyStatsQuery = useQuery({
    queryKey: ["proxies", "stats"],
    queryFn: () => api.get<ProxyStats>("/api/proxies/stats"),
    refetchInterval: 15000,
  });

  const isLoading = jobsQuery.isLoading || statsQuery.isLoading || activityQuery.isLoading;
  const isError = jobsQuery.isError || statsQuery.isError || activityQuery.isError;

  // Not gated on isError/isLoading like the panels below -- the log socket is
  // independent of the REST queries above and should keep streaming even if,
  // say, the stats endpoint is having a bad day.
  const log = useSystemLogSocket(true);

  // Stats/activity used to sit on a bare 15s poll, so the stat tiles and the
  // Activity panel could lag a just-finished job by up to that long. The log
  // socket already carries every lifecycle event live -- ride it to invalidate
  // both queries the moment something that would move the numbers happens,
  // same "socket event nudges the REST query" pattern Results.tsx uses.
  const latestEventType = log.entries[0]?.type;
  useEffect(() => {
    if (!latestEventType || !STATS_INVALIDATING_EVENTS.has(latestEventType)) return;
    queryClient.invalidateQueries({ queryKey: ["jobs", "stats"] });
    queryClient.invalidateQueries({ queryKey: ["jobs", "activity"] });
  }, [latestEventType, queryClient]);

  return (
    <div>
      <PageHeader />

      {isError ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: 48, marginBottom: 24 }}>
          <div style={{ transform: "rotate(6deg)" }}>
            <div style={{ width: 64, height: 64, background: color.pink, border: `3px solid ${color.ink}` }} />
          </div>
          <p style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink, textAlign: "center" }}>
            COULD NOT LOAD DASHBOARD
          </p>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 400 }}>
            The dashboard failed to load your job stats and recent activity. Your data is safe — this is a display issue.
          </p>
          <NeoButton
            variant="destructive"
            size="sm"
            onClick={() => {
              jobsQuery.refetch();
              statsQuery.refetch();
              activityQuery.refetch();
            }}
          >
            Retry
          </NeoButton>
        </div>
      ) : isLoading ? (
        <StatRowSkeleton />
      ) : (
        <StatRow stats={statsQuery.data!} proxyStats={proxyStatsQuery.data} />
      )}

      <QuickStart />

      <Panel title="Recent jobs">
        {isLoading ? <RecentJobsSkeleton /> : <RecentJobsTable jobs={jobsQuery.data?.items ?? []} />}
      </Panel>

      <Panel title="Activity">
        {isLoading ? <ActivitySkeleton /> : <ActivityStrip items={activityQuery.data?.items ?? []} />}
      </Panel>

      <Panel title="System log">
        <SystemLogPanel entries={log.entries} connected={log.connected} />
      </Panel>
    </div>
  );
}
