// Audit Log screen (Figma [SCREEN] audit, SCREENLIST.md §18). Every action
// taken in this workspace, who did it, and from where -- filterable by
// actor/action-type/date range, with expandable before/after diffs and a CSV
// export.
//
// Fixes applied from SCREENLIST.md's bug list:
// - TARGET cell truncates with a visible ellipsis + title tooltip instead of
//   hard-clipping mid-word with no way to see the full value.
// - Expanded BEFORE/AFTER diff rows are collapsible (click the row to
//   toggle), not permanently stuck open.
//
// Real data only: rows come from app.core.audit.log_audit_event, called from
// the routers instrumented this cycle (auth login, team invite/role-change/
// disable/enable/remove, api-keys create/revoke, settings update,
// suppression create/bulk/delete). Actions outside that set aren't logged
// yet -- a real, documented gap, not fabricated completeness.

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import NeoButton from "../components/neo/NeoButton";
import { api, ApiError, BASE_URL, getToken } from "../api/client";
import { color, font } from "../theme/neobrutalist";
import type {
  AuditActionTypesResponse,
  AuditActorsResponse,
  AuditEvent,
  AuditEventsResponse,
} from "../types";

function ResultChip({ success }: { success: boolean }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "3px 8px",
        border: `2px solid ${color.ink}`,
        background: success ? color.green : color.pink,
        fontFamily: font.body,
        fontWeight: 700,
        fontSize: 10,
        color: color.ink,
        whiteSpace: "nowrap",
      }}
    >
      {success ? "✓ SUCCESS" : "✕ FAILED"}
    </span>
  );
}

function DiffColumn({ label, data }: { label: string; data: Record<string, unknown> }) {
  return (
    <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.21px", color: color.ink60 }}>
        {label}
      </span>
      <pre style={{ margin: 0, background: color.white, border: `2px solid ${color.ink}`, padding: "8px 10px", fontFamily: font.mono, fontSize: 11, color: color.ink, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

function EventRow({ event, index }: { event: AuditEvent; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const hasDiff = !!event.beforeAfter;

  return (
    <>
      <div
        onClick={() => hasDiff && setExpanded((v) => !v)}
        className="neo-row-enter"
        style={{
          display: "flex",
          height: 40,
          borderBottom: `3px solid ${color.rule}`,
          alignItems: "center",
          cursor: hasDiff ? "pointer" : "default",
          ["--neo-delay" as string]: `${Math.min(index, 12) * 24}ms`,
        }}
      >
        <div style={{ padding: "0 12px", width: 160, flexShrink: 0 }}>
          <span style={{ fontFamily: font.mono, fontSize: 11, color: color.ink }}>
            {event.timestamp.slice(0, 19).replace("T", " ")}
          </span>
        </div>
        <div style={{ padding: "0 12px", width: 190, flexShrink: 0, overflow: "hidden" }}>
          <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", display: "block" }} title={event.actor ?? undefined}>
            {event.actor ?? "—"}
          </span>
        </div>
        <div style={{ padding: "0 12px", width: 220, flexShrink: 0, display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink }}>{event.action}</span>
          {hasDiff && (
            <span style={{ fontFamily: font.body, fontSize: 10, color: color.ink60, transform: expanded ? "rotate(180deg)" : "none" }}>▾</span>
          )}
        </div>
        <div style={{ padding: "0 12px", width: 220, flexShrink: 0, overflow: "hidden" }}>
          <span
            style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", display: "block" }}
            title={event.target ?? undefined}
          >
            {event.target ?? "—"}
          </span>
        </div>
        <div style={{ padding: "0 12px", width: 130, flexShrink: 0 }}>
          <span style={{ fontFamily: font.mono, fontSize: 11, color: color.ink }}>{event.ip ?? "—"}</span>
        </div>
        <div style={{ padding: "0 12px", width: 100, flexShrink: 0 }}>
          <ResultChip success={event.success} />
        </div>
      </div>
      {expanded && event.beforeAfter && (
        <div style={{ background: color.sand, border: `3px solid ${color.rule}`, borderTop: "none", padding: 16 }}>
          <div className="neo-responsive-row" style={{ background: color.white, display: "flex", gap: 16 }}>
            <DiffColumn label="BEFORE" data={event.beforeAfter.before} />
            <DiffColumn label="AFTER" data={event.beforeAfter.after} />
          </div>
        </div>
      )}
    </>
  );
}

function TableSkeleton() {
  return (
    <div style={{ maxWidth: 1020, border: `3px solid ${color.ink}` }}>
      <div className="neo-skeleton" style={{ height: 36, borderBottom: `3px solid ${color.ink}` }} />
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} style={{ height: 40, borderBottom: i < 4 ? `3px solid ${color.rule}` : "none", display: "flex", alignItems: "center", gap: 16, padding: "0 12px" }}>
          {[160, 190, 220, 220, 130, 80].map((w, j) => (
            <div key={j} className="neo-skeleton" style={{ width: w - 20, height: 12 }} />
          ))}
        </div>
      ))}
    </div>
  );
}

export default function AuditLog() {
  const [actor, setActor] = useState("");
  const [actionType, setActionType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const actorsQuery = useQuery({
    queryKey: ["audit-actors"],
    queryFn: () => api.get<AuditActorsResponse>("/api/audit/actors"),
  });
  const actionTypesQuery = useQuery({
    queryKey: ["audit-action-types"],
    queryFn: () => api.get<AuditActionTypesResponse>("/api/audit/action-types"),
  });

  const filterParams = new URLSearchParams();
  if (actor) filterParams.set("actor", actor);
  if (actionType) filterParams.set("action", actionType);
  if (dateFrom) filterParams.set("from", dateFrom);
  if (dateTo) filterParams.set("to", dateTo);
  const query = filterParams.toString();

  const eventsQuery = useQuery({
    queryKey: ["audit-events", actor, actionType, dateFrom, dateTo],
    queryFn: () => api.get<AuditEventsResponse>(`/api/audit/${query ? `?${query}` : ""}`),
  });

  const hasFilters = !!(actor || actionType || dateFrom || dateTo);
  const events = eventsQuery.data?.events ?? [];

  async function handleExport() {
    const token = getToken();
    const res = await fetch(`${BASE_URL}/api/audit/export.csv${query ? `?${query}` : ""}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return;
    const url = URL.createObjectURL(await res.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = "audit-log.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <div className="neo-responsive-header" style={{ display: "flex", alignItems: "flex-end", marginBottom: 24, gap: 16, maxWidth: 1126 }}>
        <div>
          <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>AUDIT LOG</h1>
          <p style={{ margin: "4px 0 0", fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink60 }}>
            Every action taken in this workspace, who did it, and from where.
          </p>
        </div>
        <div style={{ flex: 1 }} />
        <NeoButton variant="ghost" onClick={handleExport}>Export to CSV</NeoButton>
      </div>

      <div className="neo-responsive-row" style={{ display: "flex", gap: 12, alignItems: "flex-end", marginBottom: 20, maxWidth: 1126 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, width: 200 }}>
          <label style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3675px", color: color.ink, textTransform: "uppercase" }}>
            Actor
          </label>
          <select
            value={actor}
            onChange={(e) => setActor(e.target.value)}
            style={{ width: "100%", height: 40, boxSizing: "border-box", border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, fontSize: 13, background: color.white, color: color.ink }}
          >
            <option value="">All members</option>
            {(actorsQuery.data?.actors ?? []).map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6, width: 200 }}>
          <label style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3675px", color: color.ink, textTransform: "uppercase" }}>
            Action type
          </label>
          <select
            value={actionType}
            onChange={(e) => setActionType(e.target.value)}
            style={{ width: "100%", height: 40, boxSizing: "border-box", border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, fontSize: 13, background: color.white, color: color.ink }}
          >
            <option value="">All actions</option>
            {(actionTypesQuery.data?.actionTypes ?? []).map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6, width: 160 }}>
          <label style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3675px", color: color.ink, textTransform: "uppercase" }}>
            From
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            style={{ height: 40, boxSizing: "border-box", border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, fontSize: 13, color: color.ink }}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6, width: 160 }}>
          <label style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3675px", color: color.ink, textTransform: "uppercase" }}>
            To
          </label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            style={{ height: 40, boxSizing: "border-box", border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, fontSize: 13, color: color.ink }}
          />
        </div>
      </div>

      {eventsQuery.isLoading && <TableSkeleton />}

      {eventsQuery.isError && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "48px 0" }}>
          <div style={{ width: 64, height: 64, background: color.pink, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>AUDIT LOG FAILED TO LOAD</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 400 }}>
            The activity history for this workspace could not be fetched.
          </p>
          <p style={{ margin: 0, fontFamily: font.mono, fontSize: 12, color: color.ink60 }}>
            {eventsQuery.error instanceof ApiError ? eventsQuery.error.message : "ERR_AUDIT_FETCH_FAILED"}
          </p>
          <NeoButton variant="destructive" onClick={() => eventsQuery.refetch()}>
            Retry
          </NeoButton>
        </div>
      )}

      {eventsQuery.isSuccess && events.length === 0 && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "48px 0" }}>
          <div style={{ width: 64, height: 64, background: color.yellow, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>
            {hasFilters ? "NO MATCHING EVENTS" : "NO ACTIVITY YET"}
          </h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 420 }}>
            {hasFilters
              ? "Nothing in the audit log matches these filters. Try widening the date range or actor."
              : "Nothing has happened in this workspace yet. Actions like signing in, inviting a member, or changing a setting will show up here."}
          </p>
        </div>
      )}

      {eventsQuery.isSuccess && events.length > 0 && (
        <div style={{ background: color.white, border: `3px solid ${color.ink}`, maxWidth: 1020, overflowX: "auto" }}>
          <div style={{ display: "flex", background: color.sand, borderBottom: `3px solid ${color.ink}`, height: 36 }}>
            {[["TIMESTAMP", 160], ["ACTOR", 190], ["ACTION", 220], ["TARGET", 220], ["IP", 130], ["RESULT", 100]].map(([h, w]) => (
              <div key={h as string} style={{ display: "flex", alignItems: "center", padding: "0 12px", width: w as number, flexShrink: 0 }}>
                <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.21px", color: color.ink }}>{h}</span>
              </div>
            ))}
          </div>
          {events.map((event, i) => (
            <EventRow key={event.id} event={event} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
