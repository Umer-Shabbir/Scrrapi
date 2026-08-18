// Schedules screen (Figma [SCREEN] schedules). Recurring runs of a saved
// template. Legacy equivalent: none -- this is a genuinely new capability.
//
// Backend: GET/POST /api/schedules, PATCH/DELETE /api/schedules/{id},
// GET /api/schedules/preview (backend/app/api/routers/schedules.py). Firing is
// a Celery Beat periodic task (app.workers.tasks.dispatch_due_schedules) that
// checks every minute -- this screen only ever reads/writes rows.
//
// Cadence builder offers Daily/Weekly/Custom; Daily and Weekly compile to a
// cron string client-side, Custom lets the raw cron expression through
// directly (validated server-side either way). Next-5-fire-times preview
// calls GET /api/schedules/preview live as the builder changes.

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import NeoButton from "../components/neo/NeoButton";
import InlineWarning from "../components/neo/InlineWarning";
import { color, font } from "../theme/neobrutalist";
import type { JobTemplate, Schedule } from "../types";

const WEEKDAYS = [
  { label: "Sun", value: "0" },
  { label: "Mon", value: "1" },
  { label: "Tue", value: "2" },
  { label: "Wed", value: "3" },
  { label: "Thu", value: "4" },
  { label: "Fri", value: "5" },
  { label: "Sat", value: "6" },
];

const COMMON_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Berlin",
  "Asia/Kolkata",
  "Asia/Tokyo",
  "Australia/Sydney",
];

type CadenceMode = "daily" | "weekly" | "custom";

function buildCadence(mode: CadenceMode, hour: number, minute: number, weekday: string, custom: string): string {
  if (mode === "custom") return custom;
  if (mode === "weekly") return `${minute} ${hour} * * ${weekday}`;
  return `${minute} ${hour} * * *`;
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diffMs / 86_400_000);
  if (days < 1) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

const RESULT_FILL: Record<string, string> = { done: color.green, error: color.pink, misfired: color.yellow };
const RESULT_GLYPH: Record<string, string> = { done: "✓", error: "✕", misfired: "!" };

function ResultBadge({ result }: { result: string | null }) {
  if (!result) {
    return (
      <span style={{ fontFamily: font.body, fontSize: 12, color: color.ink60 }}>—</span>
    );
  }
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: 18,
        padding: "0 8px",
        border: `2px solid ${color.ink}`,
        background: RESULT_FILL[result] ?? color.sand,
        fontFamily: font.body,
        fontWeight: 700,
        fontSize: "10.5px",
        letterSpacing: "0.42px",
        textTransform: "uppercase",
        color: color.ink,
      }}
    >
      {RESULT_GLYPH[result] ?? ""} {result}
    </span>
  );
}

function EnabledSwitch({ enabled, onToggle, pending }: { enabled: boolean; onToggle: () => void; pending: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      disabled={pending}
      onClick={onToggle}
      style={{
        width: 44,
        height: 24,
        border: `3px solid ${color.ink}`,
        background: enabled ? color.green : color.sand,
        position: "relative",
        cursor: pending ? "default" : "pointer",
        opacity: pending ? 0.6 : 1,
      }}
    >
      <span style={{ position: "absolute", top: 1, left: enabled ? 22 : 1, width: 16, height: 16, background: color.ink }} />
    </button>
  );
}

function NewScheduleDrawer({ templates, onClose, onCreated }: { templates: JobTemplate[]; onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [templateId, setTemplateId] = useState(templates[0]?.id ?? "");
  const [mode, setMode] = useState<CadenceMode>("daily");
  const [hour, setHour] = useState(9);
  const [minute, setMinute] = useState(0);
  const [weekday, setWeekday] = useState("1");
  const [customCadence, setCustomCadence] = useState("0 9 * * *");
  const [timezone, setTimezone] = useState("UTC");
  const [preview, setPreview] = useState<string[]>([]);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const cadence = buildCadence(mode, hour, minute, weekday, customCadence);

  useEffect(() => {
    let cancelled = false;
    api
      .get<{ nextRuns: string[] }>(`/api/schedules/preview?cadence=${encodeURIComponent(cadence)}&timezone=${encodeURIComponent(timezone)}`)
      .then((res) => {
        if (cancelled) return;
        setPreview(res.nextRuns);
        setPreviewError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setPreview([]);
        setPreviewError(err instanceof ApiError ? err.message : "Couldn't reach the API server");
      });
    return () => {
      cancelled = true;
    };
  }, [cadence, timezone]);

  const create = useMutation({
    mutationFn: () =>
      api.post("/api/schedules/", {
        name: name.trim(),
        templateId,
        cadence,
        timezone,
        enabled: true,
      }),
    onSuccess: onCreated,
  });

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(17,17,17,0.7)", display: "flex", justifyContent: "flex-end", zIndex: 1000 }}>
      <div className="neo-responsive-fill" style={{ width: 480, background: color.white, borderLeft: `3px solid ${color.ink}`, boxShadow: "-10px 0px 0px 0px #111", height: "100%", overflowY: "auto", padding: 24, boxSizing: "border-box", display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>NEW SCHEDULE</h2>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", cursor: "pointer", fontSize: 16 }}>✕</button>
        </div>

        <div>
          <p style={{ margin: "0 0 6px", fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.3675px", textTransform: "uppercase", color: color.ink }}>Name</p>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Weekly Plumbers Refresh"
            style={{ width: "100%", height: 40, boxSizing: "border-box", border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, fontSize: 13 }}
          />
        </div>

        <div>
          <p style={{ margin: "0 0 6px", fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.3675px", textTransform: "uppercase", color: color.ink }}>Template</p>
          {templates.length === 0 ? (
            <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
              No templates yet — save one from the New Job Wizard first.
            </p>
          ) : (
            <select
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              style={{ width: "100%", height: 40, boxSizing: "border-box", border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, fontSize: 13, background: color.white }}
            >
              {templates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          )}
        </div>

        <div>
          <p style={{ margin: "0 0 6px", fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.3675px", textTransform: "uppercase", color: color.ink }}>Cadence</p>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            {(["daily", "weekly", "custom"] as CadenceMode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                style={{
                  padding: "6px 12px",
                  fontFamily: font.body,
                  fontWeight: 700,
                  fontSize: 12,
                  textTransform: "uppercase",
                  background: mode === m ? color.ink : color.white,
                  color: mode === m ? color.white : color.ink,
                  border: mode === m ? "none" : `2px solid ${color.ink}`,
                  cursor: "pointer",
                }}
              >
                {m}
              </button>
            ))}
          </div>

          {mode !== "custom" && (
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
              {mode === "weekly" && (
                <select value={weekday} onChange={(e) => setWeekday(e.target.value)} style={{ height: 36, border: `2px solid ${color.ink}`, fontFamily: font.body, fontSize: 12 }}>
                  {WEEKDAYS.map((d) => (
                    <option key={d.value} value={d.value}>{d.label}</option>
                  ))}
                </select>
              )}
              <input
                type="number"
                min={0}
                max={23}
                value={hour}
                onChange={(e) => setHour(Math.max(0, Math.min(23, Number(e.target.value))))}
                style={{ width: 60, height: 36, border: `2px solid ${color.ink}`, fontFamily: font.mono, fontSize: 13, textAlign: "center" }}
              />
              <span style={{ fontFamily: font.body, fontSize: 13 }}>:</span>
              <input
                type="number"
                min={0}
                max={59}
                value={minute}
                onChange={(e) => setMinute(Math.max(0, Math.min(59, Number(e.target.value))))}
                style={{ width: 60, height: 36, border: `2px solid ${color.ink}`, fontFamily: font.mono, fontSize: 13, textAlign: "center" }}
              />
            </div>
          )}

          {mode === "custom" && (
            <input
              value={customCadence}
              onChange={(e) => setCustomCadence(e.target.value)}
              placeholder="0 9 * * *"
              style={{ width: "100%", height: 40, boxSizing: "border-box", border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.mono, fontSize: 13, marginBottom: 12 }}
            />
          )}

          <select
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            style={{ width: "100%", height: 40, boxSizing: "border-box", border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, fontSize: 13, background: color.white }}
          >
            {COMMON_TIMEZONES.map((tz) => (
              <option key={tz} value={tz}>{tz}</option>
            ))}
          </select>
        </div>

        <div style={{ background: color.sand, border: `2px solid ${color.ink}`, padding: 12 }}>
          <p style={{ margin: "0 0 8px", fontFamily: font.body, fontWeight: 700, fontSize: 10, letterSpacing: "0.4px", textTransform: "uppercase", color: color.ink60 }}>
            Next 5 runs
          </p>
          {previewError ? (
            <InlineWarning tone="pink" fontSize={12} fontWeight={400}>{previewError}</InlineWarning>
          ) : preview.length === 0 ? (
            <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>—</p>
          ) : (
            preview.map((iso) => (
              <p key={iso} style={{ margin: 0, fontFamily: font.mono, fontSize: 12, color: color.ink }}>
                {new Date(iso).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })} UTC
              </p>
            ))
          )}
        </div>

        {create.isError && (
          <InlineWarning tone="pink" fontSize={12} fontWeight={700}>
            {create.error instanceof ApiError ? create.error.message : "Couldn't reach the API server"}
          </InlineWarning>
        )}

        <div style={{ display: "flex", gap: 12, marginTop: "auto" }}>
          <NeoButton variant="secondary" onClick={onClose}>Cancel</NeoButton>
          <NeoButton
            variant="primary"
            loading={create.isPending}
            disabled={!name.trim() || !templateId || (mode === "custom" && !customCadence.trim())}
            onClick={() => create.mutate()}
          >
            Create schedule
          </NeoButton>
        </div>
      </div>
    </div>
  );
}

export default function Schedules() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const schedulesQuery = useQuery({
    queryKey: ["schedules"],
    queryFn: () => api.get<Schedule[]>("/api/schedules/"),
    refetchInterval: 30000,
  });
  const templatesQuery = useQuery({
    queryKey: ["templates"],
    queryFn: () => api.get<JobTemplate[]>("/api/templates/"),
  });

  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.patch(`/api/schedules/${id}`, { enabled }),
    onMutate: ({ id }) => setTogglingId(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["schedules"] }),
    onSettled: () => setTogglingId(null),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.del(`/api/schedules/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["schedules"] }),
  });

  const templateName = (id: string) => templatesQuery.data?.find((t) => t.id === id)?.name ?? "—";

  return (
    <div>
      <div className="neo-responsive-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>SCHEDULES</h1>
          <p style={{ margin: "6px 0 0", fontFamily: font.body, fontSize: 13, color: color.ink60, maxWidth: 720 }}>
            Recurring jobs. Attach a template to a cadence and MapScrape runs it automatically.
          </p>
        </div>
        <NeoButton variant="primary" onClick={() => setDrawerOpen(true)}>
          + New schedule
        </NeoButton>
      </div>

      {schedulesQuery.isLoading && (
        <div className="neo-skeleton" style={{ height: 200, border: `3px solid ${color.rule}` }} />
      )}

      {schedulesQuery.isError && (
        <div style={{ background: color.white, border: `3px solid ${color.ink}`, borderLeft: `6px solid ${color.pink}`, padding: 16, maxWidth: 500 }}>
          <InlineWarning tone="ink" fontSize={13} fontWeight={700}>Couldn&rsquo;t load schedules</InlineWarning>
          <p style={{ margin: "4px 0 12px", fontFamily: font.body, fontSize: 13, color: color.ink }}>
            {schedulesQuery.error instanceof ApiError ? schedulesQuery.error.message : "Couldn't reach the API server"}
          </p>
          <NeoButton variant="destructive" size="sm" onClick={() => schedulesQuery.refetch()}>Retry</NeoButton>
        </div>
      )}

      {schedulesQuery.data && schedulesQuery.data.length === 0 && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: 48 }}>
          <div style={{ transform: "rotate(6deg)" }}>
            <div style={{ width: 64, height: 64, background: color.yellow, border: `3px solid ${color.ink}` }} />
          </div>
          <p style={{ margin: 0, fontFamily: font.head, fontSize: 32, color: color.ink }}>NO SCHEDULES YET</p>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 400 }}>
            Attach a saved template to a cadence and it&rsquo;ll run on its own from here on.
          </p>
          <NeoButton variant="primary" onClick={() => setDrawerOpen(true)}>New schedule</NeoButton>
        </div>
      )}

      {schedulesQuery.data && schedulesQuery.data.length > 0 && (
        <>
          {/* Cross-cutting #4: desktop/tablet keep the real table (scrolls
              horizontally as a fallback above 768 rather than clipping),
              mobile gets a stacked card per schedule instead of a squeezed
              8-column table. */}
          <div className="neo-responsive-table" style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: "6px 6px 0px 0px #111", overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 900 }}>
              <thead>
                <tr style={{ background: color.sand }}>
                  {["NAME", "TEMPLATE", "CADENCE", "NEXT RUN", "LAST RUN", "RESULT", "ENABLED", ""].map((h) => (
                    <th key={h} style={{ textAlign: "left", padding: "10px 12px", fontFamily: font.body, fontWeight: 500, fontSize: 11, color: color.ink60 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {schedulesQuery.data.map((s, i) => (
                  <tr
                    key={s.id}
                    className="neo-row-enter"
                    style={{ borderTop: `1px solid ${color.rule}`, ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms` }}
                  >
                    <td style={{ padding: "12px" }}>
                      <button
                        type="button"
                        onClick={() => navigate(`/schedules/${s.id}`)}
                        style={{ border: "none", background: "transparent", padding: 0, cursor: "pointer", fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink, textDecoration: "underline" }}
                      >
                        {s.name}
                      </button>
                    </td>
                    <td style={{ padding: "12px", fontFamily: font.body, fontSize: 12, color: color.ink60 }}>{templateName(s.templateId)}</td>
                    <td style={{ padding: "12px", fontFamily: font.mono, fontSize: 12, color: color.ink }}>{s.cadence} ({s.timezone})</td>
                    <td style={{ padding: "12px", fontFamily: font.body, fontSize: 13, color: color.ink }}>
                      {s.nextRunAt ? new Date(s.nextRunAt).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                    </td>
                    <td style={{ padding: "12px", fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
                      {s.lastRunAt ? timeAgo(s.lastRunAt) : "Never run"}
                    </td>
                    <td style={{ padding: "12px" }}>
                      <ResultBadge result={s.lastResult} />
                    </td>
                    <td style={{ padding: "12px" }}>
                      <EnabledSwitch
                        enabled={s.enabled}
                        pending={togglingId === s.id}
                        onToggle={() => toggle.mutate({ id: s.id, enabled: !s.enabled })}
                      />
                    </td>
                    <td style={{ padding: "12px" }}>
                      <NeoButton variant="ghost" size="sm" onClick={() => remove.mutate(s.id)}>
                        Delete
                      </NeoButton>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="neo-responsive-cards">
            {schedulesQuery.data.map((s, i) => (
              <div
                key={s.id}
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
                  <button
                    type="button"
                    onClick={() => navigate(`/schedules/${s.id}`)}
                    style={{ border: "none", background: "transparent", padding: 0, cursor: "pointer", fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink, textAlign: "left" }}
                  >
                    {s.name}
                  </button>
                  <ResultBadge result={s.lastResult} />
                </div>
                <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
                  {templateName(s.templateId)} · <span style={{ fontFamily: font.mono }}>{s.cadence} ({s.timezone})</span>
                </p>
                <div style={{ display: "flex", justifyContent: "space-between", fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
                  <span>Next: {s.nextRunAt ? new Date(s.nextRunAt).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}</span>
                  <span>Last: {s.lastRunAt ? timeAgo(s.lastRunAt) : "Never run"}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <EnabledSwitch
                    enabled={s.enabled}
                    pending={togglingId === s.id}
                    onToggle={() => toggle.mutate({ id: s.id, enabled: !s.enabled })}
                  />
                  <NeoButton variant="ghost" size="sm" onClick={() => remove.mutate(s.id)}>
                    Delete
                  </NeoButton>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {drawerOpen && (
        <NewScheduleDrawer
          templates={templatesQuery.data ?? []}
          onClose={() => setDrawerOpen(false)}
          onCreated={() => {
            setDrawerOpen(false);
            queryClient.invalidateQueries({ queryKey: ["schedules"] });
          }}
        />
      )}
    </div>
  );
}
