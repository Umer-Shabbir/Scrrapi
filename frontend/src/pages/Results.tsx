// Results screen (Figma [SCREEN] results) for one job: tabs (Leads/Targets/
// Activity), live progress header, results grid, activity feed. Figma's
// separate Errors tab is folded into Activity, which already surfaces
// place/target failures inline (ActivityFeed's error/warning tones) --
// splitting them into a second tab would just filter the same feed twice.
//
// The socket carries two things -- a counts snapshot and a running activity
// log. The counts drive the header/progress bar and invalidate the results
// query (the grid stays fed by the paginated endpoint, which is
// authoritative); the activity log is rendered as-is, so the page shows the
// leads arriving one by one instead of only a number going up.
//
// Reused as-is (real, working infrastructure): useJobSocket. ActivityFeed,
// JobControls and ResultsGrid were legacy MUI components restyled to the
// neobrutalist system in place (see each file's own header comment) rather
// than reused verbatim -- this page is the only screen that used them, so
// the rebuild is fully scoped here.
//
// Figma's fifth tab ("Changes", before/after diffs across scheduled runs) is
// omitted -- same reason as Schedule & Monitoring's delta chart: no
// place-identity tracking exists across separate jobs to diff against.
// "Push to CRM" has no backend (Integrations isn't built) and is disabled.
//
// Leads grid is server-paginated for real (GET .../results?page=&page_size=),
// not a fixed first-N-rows fetch -- every row a job collected is reachable by
// paging through, not just the first page's worth.

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import ActivityFeed from "../components/ActivityFeed";
import JobControls from "../components/JobControls";
import LeadDetailDrawer from "../components/LeadDetailDrawer";
import NeoButton from "../components/neo/NeoButton";
import NeoStatusBadge from "../components/neo/NeoStatusBadge";
import InlineWarning from "../components/neo/InlineWarning";
import ResultsGrid from "../components/ResultsGrid";
import { useJobSocket } from "../hooks/useJobSocket";
import { api, ApiError } from "../api/client";
import { color, font } from "../theme/neobrutalist";
import type { JobDetail, JobStatus, Page, Result } from "../types";

const DEFAULT_PAGE_SIZE = 50;
const LIVE_STATUSES = new Set(["queued", "running", "paused"]);
const UNFINISHED_TARGET_STATUSES = new Set(["queued", "running"]);
const TABS = ["Leads", "Targets", "Activity"] as const;
type Tab = (typeof TABS)[number];

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 10, color: color.ink60 }}>{label}</p>
      <p style={{ margin: "2px 0 0", fontFamily: font.body, fontSize: 15, color: color.ink }}>{value}</p>
    </div>
  );
}

function TargetsTable({ targets }: { targets: JobDetail["targets"] }) {
  return (
    <>
      <div className="neo-responsive-table" style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 700 }}>
          <thead>
            <tr style={{ background: color.sand }}>
              {["KEYWORD", "ZIP", "LOCATION", "PLACES", "STATUS"].map((h) => (
                <th key={h} style={{ textAlign: "left", padding: "10px 12px", fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.35px", color: color.ink }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {targets.map((target, i) => (
              <tr
                key={target.id}
                className="neo-row-enter"
                style={{ borderTop: `1px solid ${color.rule}`, ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms` }}
              >
                <td style={{ padding: "10px 12px", fontFamily: font.body, fontSize: 13, color: color.ink }}>{target.keyword}</td>
                <td style={{ padding: "10px 12px", fontFamily: font.mono, fontSize: 12, color: color.ink }}>{target.zipCode ?? "—"}</td>
                <td style={{ padding: "10px 12px", fontFamily: font.body, fontSize: 13, color: color.ink }}>
                  {[target.city, target.region].filter(Boolean).join(", ") || target.locationLabel}
                </td>
                <td style={{ padding: "10px 12px", fontFamily: font.mono, fontSize: 12, color: color.ink }}>
                  {target.placesFound > 0 ? `${target.placesDone}/${target.placesFound}` : "—"}
                </td>
                <td style={{ padding: "10px 12px" }}>
                  <NeoStatusBadge
                    status={target.status === "queued" && !target.dispatched ? "queued" : target.status}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="neo-responsive-cards">
        {targets.map((target, i) => (
          <div
            key={target.id}
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
              <div>
                <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink }}>
                  {target.keyword}
                </p>
                <p style={{ margin: "2px 0 0", fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
                  {[target.city, target.region].filter(Boolean).join(", ") || target.locationLabel}
                  {target.zipCode ? ` (${target.zipCode})` : ""}
                </p>
              </div>
              <NeoStatusBadge
                status={target.status === "queued" && !target.dispatched ? "queued" : target.status}
              />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: font.mono, fontSize: 12, color: color.ink }}>
              <span style={{ color: color.ink60, fontFamily: font.body }}>Places:</span>
              <span>{target.placesFound > 0 ? `${target.placesDone}/${target.placesFound}` : "—"}</span>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

export default function Results() {
  const { jobId, leadId } = useParams();
  const navigate = useNavigate();
  const { progress, activity, connected } = useJobSocket(jobId);
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("Leads");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.get<JobDetail>(`/api/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (query) =>
      query.state.data && LIVE_STATUSES.has(query.state.data.status) ? 5000 : false,
  });

  const resultsQuery = useQuery({
    queryKey: ["job-results", jobId, page, pageSize],
    queryFn: () => api.get<Page<Result>>(`/api/jobs/${jobId}/results?page=${page}&page_size=${pageSize}`),
    enabled: !!jobId,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!jobId || progress?.resultsCount === undefined) return;
    queryClient.invalidateQueries({ queryKey: ["job-results", jobId] });
    queryClient.invalidateQueries({ queryKey: ["job", jobId] });
  }, [jobId, progress?.resultsCount, progress?.status, queryClient]);

  const job = jobQuery.data;
  const status = (progress?.status ?? job?.status ?? "queued") as JobStatus;
  const total = resultsQuery.data?.total ?? 0;
  const resultsCount = progress?.resultsCount ?? total;
  const targets = progress?.targets ?? job?.targets ?? [];
  const finishedTargets = targets.filter((t) => !UNFINISHED_TARGET_STATUSES.has(t.status)).length;
  const waitingTargets =
    progress?.targetsWaiting ?? targets.filter((t) => t.status === "queued" && !t.dispatched).length;

  const placesFound = progress?.placesFound ?? targets.reduce((n, t) => n + t.placesFound, 0);
  const placesDone = progress?.placesDone ?? targets.reduce((n, t) => n + t.placesDone, 0);
  const live = LIVE_STATUSES.has(status);

  // Places, not targets, are the primary progress measurement (fixes the
  // "PLACES exceeds its own projected ceiling" confusion from a targets-first
  // reading) -- one target routinely holds dozens of places, so a
  // target-based percentage sits near zero for most of a run.
  const percent = placesFound
    ? (placesDone / placesFound) * 100
    : targets.length
      ? (finishedTargets / targets.length) * 100
      : 0;

  const rows = resultsQuery.data?.items ?? [];

  return (
    <div>
      <button
        type="button"
        onClick={() => navigate("/")}
        style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink60, marginBottom: 8 }}
      >
        ← Jobs
      </button>

      <div className="neo-responsive-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 20, color: color.ink }}>
              {job?.name ?? `Job #${jobId?.slice(0, 8)}`}
            </h1>
            <NeoStatusBadge status={status} />
          </div>
          <p style={{ margin: "6px 0 0", fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
            Job #{jobId?.slice(0, 8)}{job?.createdAt && ` · started ${new Date(job.createdAt).toLocaleString()}`}
          </p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          {job && <JobControls job={job} onDeleted={() => navigate("/")} />}
          <NeoButton variant="secondary" onClick={() => navigate(`/export/${jobId}`)} disabled={resultsCount === 0}>
            Export
          </NeoButton>
          <NeoButton variant="ghost" disabled>
            Push to CRM
          </NeoButton>
        </div>
      </div>

      <div style={{ display: "flex", gap: 40, marginBottom: 16, flexWrap: "wrap" }}>
        <Metric label="LEADS" value={String(resultsCount)} />
        <Metric label="PLACES" value={placesFound ? `${placesDone} / ~${placesFound}` : "—"} />
        <Metric label="TARGETS" value={targets.length ? `${finishedTargets} done · ${waitingTargets} waiting` : "—"} />
      </div>

      {status === "paused" && (
        <div style={{ background: color.sand, border: `2px solid ${color.ink}`, padding: 12, marginBottom: 16, fontFamily: font.body, fontSize: 13, color: color.ink }}>
          Paused — no new areas will be started. Areas already being scraped run to completion, so leads may keep arriving for a few minutes.
        </div>
      )}
      {status === "cancelled" && (
        <div style={{ background: color.sand, border: `2px solid ${color.ink}`, padding: 12, marginBottom: 16, fontFamily: font.body, fontSize: 13, color: color.ink }}>
          Cancelled — areas that hadn&rsquo;t finished were dropped. Everything collected before that is below and can still be exported.
        </div>
      )}

      {live && (
        <div style={{ background: color.sand, border: `2px solid ${color.ink}`, height: 16, marginBottom: 8, position: "relative" }}>
          <div style={{ background: color.green, height: 12, width: `${Math.min(100, percent)}%`, position: "absolute", top: 2, left: 2 }} />
        </div>
      )}
      {live && (
        <p style={{ margin: "0 0 20px", fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
          {placesFound.toLocaleString()} places found so far · {finishedTargets} of {targets.length} targets done
        </p>
      )}

      {jobQuery.isError && (
        <div style={{ margin: "0 0 16px" }}>
          <InlineWarning tone="pink" fontSize={12} fontWeight={700}>
            {jobQuery.error instanceof ApiError ? jobQuery.error.message : "Couldn't reach the API server"}
          </InlineWarning>
        </div>
      )}
      {resultsQuery.isError && (
        <div style={{ margin: "0 0 16px" }}>
          <InlineWarning tone="pink" fontSize={12} fontWeight={700}>
            {resultsQuery.error instanceof ApiError ? resultsQuery.error.message : "Couldn't reach the API server"}
          </InlineWarning>
        </div>
      )}
      <div style={{ display: "flex", gap: 4, marginBottom: 20 }}>
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            style={{
              padding: "10px 20px",
              fontFamily: font.body,
              fontWeight: 500,
              fontSize: 13,
              textTransform: "uppercase",
              background: tab === t ? color.ink : color.white,
              color: tab === t ? color.white : color.ink,
              border: `2px solid ${color.ink}`,
              cursor: "pointer",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Leads" && (
        <ResultsGrid
          results={rows}
          loading={resultsQuery.isLoading}
          onRowClick={(result) => navigate(`/results/${jobId}/lead/${result.id}`)}
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={setPage}
          onPageSizeChange={(size) => {
            setPageSize(size);
            setPage(1);
          }}
        />
      )}
      {tab === "Targets" && (
        <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: "6px 6px 0px 0px #111" }}>
          <TargetsTable targets={targets} />
        </div>
      )}
      {tab === "Activity" && <ActivityFeed entries={activity} connected={connected} live={live} />}

      {jobId && leadId && (
        <LeadDetailDrawer jobId={jobId} leadId={leadId} onClose={() => navigate(`/results/${jobId}`)} />
      )}
    </div>
  );
}
