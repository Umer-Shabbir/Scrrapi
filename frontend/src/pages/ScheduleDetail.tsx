// Schedule & Monitoring screen (Figma [SCREEN] schedule-detail), route
// `/schedules/:id`. Header (name/cadence/next-run/enable/run-now) + Run
// History table -- every job this schedule has fired.
//
// The Figma mock also shows a delta chart (new/changed/disappeared leads per
// run, as stacked bars) and a change feed with before/after diffs. Both are
// omitted: there is no place-identity tracking across separate scrape runs to
// diff against (each Job/Result is fully independent), and building that is a
// data-modeling project on its own, not a screen-wiring task. Run History
// reports what's actually knowable instead -- targets, places, duration,
// status -- via GET /api/schedules/{id}/runs.

import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import NeoButton from "../components/neo/NeoButton";
import NeoStatusBadge from "../components/neo/NeoStatusBadge";
import InlineWarning from "../components/neo/InlineWarning";
import { SkeletonTable, SkeletonCard } from "../components/neo/Skeleton";
import { color, font } from "../theme/neobrutalist";
import type { JobTemplate, Schedule, ScheduleRun } from "../types";

function formatDuration(seconds: number): string {
  if (seconds <= 0) return "—";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
}

export default function ScheduleDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const scheduleQuery = useQuery({
    queryKey: ["schedules", id],
    queryFn: () => api.get<Schedule>(`/api/schedules/${id}`),
    enabled: !!id,
  });
  const templatesQuery = useQuery({
    queryKey: ["templates"],
    queryFn: () => api.get<JobTemplate[]>("/api/templates/"),
  });
  const runsQuery = useQuery({
    queryKey: ["schedules", id, "runs"],
    queryFn: () => api.get<ScheduleRun[]>(`/api/schedules/${id}/runs`),
    enabled: !!id,
    refetchInterval: 10000,
  });

  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api.patch(`/api/schedules/${id}`, { enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["schedules", id] }),
  });

  const runNow = useMutation({
    mutationFn: () => api.post<{ id: string }>(`/api/schedules/${id}/run`),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["schedules", id, "runs"] });
      navigate(`/results/${job.id}`);
    },
  });

  // Cross-cutting #10: both branches below used to drop straight into their
  // content with no back-link -- render it above both, same as the loaded
  // state, so a failed/slow fetch doesn't stand the user with no way back to
  // the Schedules list.
  const backLink = (
    <button
      type="button"
      onClick={() => navigate("/schedules")}
      style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink60, marginBottom: 8 }}
    >
      ← Schedules
    </button>
  );

  if (scheduleQuery.isLoading) {
    return (
      <div style={{ maxWidth: 1126 }}>
        {backLink}
        <div style={{ marginBottom: 24 }}>
          <SkeletonCard height={80} />
        </div>
        <SkeletonTable rows={4} columns={7} />
      </div>
    );
  }

  if (scheduleQuery.isError || !scheduleQuery.data) {
    return (
      <div>
        {backLink}
        <div style={{ background: color.white, border: `3px solid ${color.ink}`, borderLeft: `6px solid ${color.pink}`, padding: 16, maxWidth: 500 }}>
          <InlineWarning tone="ink" fontSize={13} fontWeight={700}>Couldn&rsquo;t load schedule</InlineWarning>
          <p style={{ margin: "4px 0 12px", fontFamily: font.body, fontSize: 13, color: color.ink }}>
            {scheduleQuery.error instanceof ApiError ? scheduleQuery.error.message : "Couldn't reach the API server"}
          </p>
          <NeoButton variant="destructive" size="sm" onClick={() => scheduleQuery.refetch()}>Retry</NeoButton>
        </div>
      </div>
    );
  }

  const schedule = scheduleQuery.data;
  const templateName = templatesQuery.data?.find((t) => t.id === schedule.templateId)?.name ?? "—";

  return (
    <div>
      <button
        type="button"
        onClick={() => navigate("/schedules")}
        style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink60, marginBottom: 8 }}
      >
        ← Schedules
      </button>

      <div className="neo-responsive-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 20, color: color.ink }}>{schedule.name.toUpperCase()}</h1>
          <p style={{ margin: "6px 0 0", fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
            {schedule.cadence} ({schedule.timezone}) · Next run:{" "}
            {schedule.nextRunAt ? new Date(schedule.nextRunAt).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
            {" "}· Template: {templateName}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 11, color: color.ink60 }}>ENABLED</span>
          <button
            type="button"
            role="switch"
            aria-checked={schedule.enabled}
            disabled={toggle.isPending}
            onClick={() => toggle.mutate(!schedule.enabled)}
            style={{ width: 44, height: 24, border: `3px solid ${color.ink}`, background: schedule.enabled ? color.green : color.sand, position: "relative", cursor: "pointer" }}
          >
            <span style={{ position: "absolute", top: 1, left: schedule.enabled ? 22 : 1, width: 16, height: 16, background: color.ink }} />
          </button>
          <NeoButton variant="primary" loading={runNow.isPending} onClick={() => runNow.mutate()}>
            Run now
          </NeoButton>
        </div>
      </div>

      {runNow.isError && (
        <div style={{ margin: "0 0 16px" }}>
          <InlineWarning tone="pink" fontSize={12} fontWeight={700}>
            {runNow.error instanceof ApiError ? runNow.error.message : "Couldn't reach the API server"}
          </InlineWarning>
        </div>
      )}

      <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: "6px 6px 0px 0px #111", padding: 20 }}>
        <p style={{ margin: "0 0 16px", fontFamily: font.body, fontWeight: 500, fontSize: 14, color: color.ink }}>RUN HISTORY</p>

        {runsQuery.isLoading && <SkeletonTable rows={4} columns={7} />}

        {runsQuery.isError && (
          <InlineWarning tone="pink" fontSize={13} fontWeight={400}>
            {runsQuery.error instanceof ApiError ? runsQuery.error.message : "Couldn't reach the API server"}
          </InlineWarning>
        )}

        {runsQuery.data && runsQuery.data.length === 0 && (
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
            No runs yet — this schedule hasn&rsquo;t fired, and nobody has run it manually.
          </p>
        )}

        {runsQuery.data && runsQuery.data.length > 0 && (
          <>
            <div className="neo-responsive-table" style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 700 }}>
                <thead>
                  <tr style={{ background: color.sand }}>
                    {["STARTED", "DURATION", "TARGETS", "PLACES", "LEADS", "STATUS", ""].map((h) => (
                      <th key={h} style={{ textAlign: "left", padding: "10px 12px", fontFamily: font.body, fontWeight: 500, fontSize: 11, color: color.ink60 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {runsQuery.data.map((run, i) => (
                    <tr
                      key={run.jobId}
                      className="neo-row-enter"
                      style={{ borderTop: `1px solid ${color.rule}`, ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms` }}
                    >
                      <td style={{ padding: "12px", fontFamily: font.body, fontSize: 13, color: color.ink }}>
                        {new Date(run.startedAt).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </td>
                      <td style={{ padding: "12px", fontFamily: font.body, fontSize: 13, color: color.ink }}>{formatDuration(run.durationSeconds)}</td>
                      <td style={{ padding: "12px", fontFamily: font.mono, fontSize: 12, color: color.ink }}>{run.targetsTotal}</td>
                      <td style={{ padding: "12px", fontFamily: font.mono, fontSize: 12, color: color.ink }}>{run.placesFound}</td>
                      <td style={{ padding: "12px", fontFamily: font.mono, fontSize: 12, color: color.ink }}>{run.resultsCount}</td>
                      <td style={{ padding: "12px" }}><NeoStatusBadge status={run.status} /></td>
                      <td style={{ padding: "12px" }}>
                        <NeoButton variant="ghost" size="sm" onClick={() => navigate(`/results/${run.jobId}`)}>
                          Results
                        </NeoButton>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="neo-responsive-cards">
              {runsQuery.data.map((run, i) => (
                <div
                  key={run.jobId}
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
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                    <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink }}>
                      {new Date(run.startedAt).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </span>
                    <NeoStatusBadge status={run.status} />
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
                    <span>Duration: {formatDuration(run.durationSeconds)}</span>
                    <span style={{ fontFamily: font.mono, color: color.ink }}>{run.resultsCount} leads ({run.placesFound} places)</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontFamily: font.mono, fontSize: 11, color: color.ink60 }}>{run.targetsTotal} targets</span>
                    <NeoButton variant="ghost" size="sm" onClick={() => navigate(`/results/${run.jobId}`)}>
                      Results
                    </NeoButton>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
