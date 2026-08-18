// Webhook Delivery Log (Figma [SCREEN] webhook-log, priority 15). Drill-down
// from Integrations' webhooks config panel -- every delivery attempt for the
// one configured webhook, expandable rows (request/response), replay one or
// all-failed, and the back-off/disabled banners.
//
// Backend: GET/POST /api/webhook-deliveries/* (backend/app/api/routers/
// webhook_deliveries.py) -- new this cycle. Integrations' own webhook config
// endpoints (GET/PUT /api/integrations/webhooks) are reused read-only for the
// endpoint URL shown in the header; nothing here writes to that screen's data.
//
// Bug fixes applied against the Figma handoff's per-screen bug list:
// - Every row starts collapsed; only one row expands at a time (the Figma
//   frame shows "job.completed" permanently open with no visible collapse
//   affordance -- confirmed here that expand/collapse is actually wired).
// - Loading uses skeleton rows shaped like the real table (header + rows +
//   a status-chip-shaped block), not a flat rectangle.
// - Disabled state disables BOTH "Replay all failed" and every individual
//   row's REPLAY link -- the Figma frame only greys the toolbar action,
//   leaving row-level replay inconsistently active.
// - The "2 failed in the last 24h" helper text next to REPLAY ALL FAILED
//   never dims -- it's a status readout, not a control, so disabling the
//   button next to it shouldn't grey the count out too.
// - Status chips get a real Status/Badge glyph prefix (✓/✕), not color+number
//   alone.

import { Fragment, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import NeoButton from "../components/neo/NeoButton";
import InlineWarning from "../components/neo/InlineWarning";
import { api, ApiError } from "../api/client";
import { color, font } from "../theme/neobrutalist";

interface WebhookDelivery {
  id: string;
  event: string;
  statusCode: number | null;
  succeeded: boolean;
  attempt: number;
  attemptMax: number;
  durationMs: number | null;
  requestHeaders: Record<string, string>;
  requestBody: unknown;
  responseBody: unknown;
  error: string | null;
  createdAt: string;
}

type EndpointStatus =
  | { kind: "all_delivering" }
  | { kind: "backing_off"; consecutiveFailures: number; nextRetrySeconds: number }
  | { kind: "disabled"; disabledAt: string; reason: string | null };

interface DeliveryLog {
  connectionId: string;
  url: string | null;
  endpointStatus: EndpointStatus;
  failedLast24h: number;
  deliveries: WebhookDelivery[];
}

function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`;
}

function formatRetryCountdown(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
}

function StatusChip({ delivery }: { delivery: WebhookDelivery }) {
  const fill = delivery.succeeded ? color.green : color.pink;
  const glyph = delivery.succeeded ? "✓" : "✕";
  const label = delivery.statusCode ?? delivery.error ?? "—";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: 20,
        padding: "0 8px",
        border: `2px solid ${color.ink}`,
        background: fill,
        fontFamily: font.mono,
        fontWeight: 700,
        fontSize: 11,
        color: color.ink,
        whiteSpace: "nowrap",
      }}
    >
      {glyph} {label}
    </span>
  );
}

function CodeBlock({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <p style={{ margin: "0 0 4px", fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3px", color: color.ink60, textTransform: "uppercase" }}>
        {label}
      </p>
      <pre
        style={{
          margin: 0,
          background: color.white,
          border: `2px solid ${color.ink}`,
          padding: 10,
          fontFamily: font.mono,
          fontSize: 12,
          color: color.ink,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          overflowX: "auto",
        }}
      >
        {value}
      </pre>
    </div>
  );
}

function DeliveryDetail({ delivery }: { delivery: WebhookDelivery }) {
  const headerLines = Object.entries(delivery.requestHeaders)
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n");
  return (
    <div style={{ background: color.sand, border: `3px solid ${color.rule}`, borderTop: "none", padding: 16 }}>
      <CodeBlock label="Request Headers" value={headerLines || "—"} />
      <CodeBlock label="Request Body" value={JSON.stringify(delivery.requestBody, null, 2)} />
      <CodeBlock
        label="Response Body"
        value={delivery.responseBody !== null && delivery.responseBody !== undefined ? JSON.stringify(delivery.responseBody, null, 2) : delivery.error ? `(no response — ${delivery.error})` : "(no response)"}
      />
    </div>
  );
}

function SkeletonRow() {
  return (
    <tr style={{ borderTop: `3px solid ${color.rule}` }}>
      {[130, 150, 0, 60, 70, 90].map((w, i) => (
        <td key={i} style={{ padding: "10px 12px" }}>
          {i === 2 ? (
            <div className="neo-skeleton" style={{ width: 60, height: 20, border: `2px solid ${color.rule}` }} />
          ) : (
            <div className="neo-skeleton" style={{ width: w || 80, height: 12 }} />
          )}
        </td>
      ))}
    </tr>
  );
}

export default function WebhookDeliveryLog() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [replayingId, setReplayingId] = useState<string | null>(null);

  const logQuery = useQuery({
    queryKey: ["webhook-delivery-log", id],
    queryFn: () => api.get<DeliveryLog>(`/api/webhook-deliveries/${id}`),
    enabled: !!id,
    refetchInterval: 10000,
  });

  const replay = useMutation({
    mutationFn: (deliveryId: string) =>
      api.post<WebhookDelivery>(`/api/webhook-deliveries/${id}/replay/${deliveryId}`),
    onMutate: (deliveryId) => setReplayingId(deliveryId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["webhook-delivery-log", id] }),
    onSettled: () => setReplayingId(null),
  });

  const replayAllFailed = useMutation({
    mutationFn: () => api.post<{ replayed: number; succeeded: number }>(`/api/webhook-deliveries/${id}/replay-failed`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["webhook-delivery-log", id] }),
  });

  const reEnable = useMutation({
    mutationFn: () => api.post<EndpointStatus>(`/api/webhook-deliveries/${id}/re-enable`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["webhook-delivery-log", id] }),
  });

  const log = logQuery.data;
  const disabled = log?.endpointStatus.kind === "disabled";
  const backingOff = log?.endpointStatus.kind === "backing_off";

  return (
    <div style={{ maxWidth: 1126 }}>
      <button
        type="button"
        onClick={() => navigate("/integrations")}
        style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink60, marginBottom: 8 }}
      >
        ← Back to Integrations
      </button>

      <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>WEBHOOK DELIVERY LOG</h1>
      <p style={{ margin: "4px 0 20px", fontFamily: font.mono, fontSize: 13, color: color.ink60 }}>
        {log?.url ?? "—"} · {log?.endpointStatus.kind === "all_delivering" ? "all-delivering" : log?.endpointStatus.kind === "backing_off" ? "backing off" : log?.endpointStatus.kind === "disabled" ? "disabled" : ""}
      </p>

      {logQuery.isError && (
        <p style={{ margin: "0 0 16px", fontFamily: font.body, fontWeight: 700, fontSize: 12, color: color.pink }}>
          ✕ {logQuery.error instanceof ApiError ? logQuery.error.message : "Couldn't reach the API server"}
        </p>
      )}

      {backingOff && log.endpointStatus.kind === "backing_off" && (
        <div style={{ background: color.orange, border: `3px solid ${color.ink}`, padding: "10px 14px", marginBottom: 16, display: "flex", gap: 8, alignItems: "center" }}>
          <InlineWarning tone="ink" fontSize={13} fontWeight={700}>
            Endpoint has failed {log.endpointStatus.consecutiveFailures} consecutive deliveries. Backing off — next retry in {formatRetryCountdown(log.endpointStatus.nextRetrySeconds)}.
          </InlineWarning>
        </div>
      )}

      {disabled && log.endpointStatus.kind === "disabled" && (
        <div style={{ background: color.pink, border: `3px solid ${color.ink}`, padding: "10px 14px", marginBottom: 16, display: "flex", gap: 12, alignItems: "center", justifyContent: "space-between" }}>
          <InlineWarning tone="ink" fontSize={13} fontWeight={700}>
            This webhook was auto-disabled after {log.endpointStatus.reason ?? "sustained failures"}. No further deliveries will be sent.
          </InlineWarning>
          <NeoButton variant="secondary" size="sm" loading={reEnable.isPending} onClick={() => reEnable.mutate()}>
            Re-enable
          </NeoButton>
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
        <NeoButton
          variant="primary"
          disabled={disabled || !log || log.failedLast24h === 0}
          loading={replayAllFailed.isPending}
          onClick={() => replayAllFailed.mutate()}
        >
          Replay all failed
        </NeoButton>
        {/* A status readout, not a control -- stays full-strength even while
            the button next to it is disabled (bug fix: Figma dims both). */}
        <span style={{ fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
          {log ? `${log.failedLast24h} failed in the last 24h` : ""}
        </span>
      </div>

      {/* Cross-cutting #4: desktop/tablet keep the real table (horizontal
          scroll as a fallback above 768 rather than clipping); mobile gets a
          stacked card per delivery instead of a squeezed 6-column table.
          Both share the same click-to-expand detail panel. */}
      <div className="neo-responsive-table" style={{ background: color.white, border: `3px solid ${color.ink}`, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 760 }}>
          <thead>
            <tr style={{ background: color.sand }}>
              {["TIMESTAMP", "EVENT", "STATUS", "ATTEMPT", "DURATION", "ACTIONS"].map((h) => (
                <th key={h} style={{ textAlign: "left", padding: "10px 12px", fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.315px", color: color.ink }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {logQuery.isLoading &&
              Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} />)}

            {log?.deliveries.length === 0 && !logQuery.isLoading && (
              <tr>
                <td colSpan={6} style={{ padding: 24, textAlign: "center", fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
                  No deliveries recorded yet for this webhook.
                </td>
              </tr>
            )}

            {log?.deliveries.map((d, i) => {
              const expanded = expandedId === d.id;
              return (
                <Fragment key={d.id}>
                  <tr
                    onClick={() => setExpandedId(expanded ? null : d.id)}
                    className="neo-row-enter"
                    style={{ borderTop: `3px solid ${color.rule}`, cursor: "pointer", ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms` }}
                  >
                    <td style={{ padding: "10px 12px", fontFamily: font.mono, fontSize: 12, color: color.ink }}>
                      {d.createdAt.replace("T", " ").slice(0, 19)}
                    </td>
                    <td style={{ padding: "10px 12px", fontFamily: font.body, fontSize: 13, color: color.ink }}>{d.event}</td>
                    <td style={{ padding: "10px 12px" }}>
                      <StatusChip delivery={d} />
                    </td>
                    <td style={{ padding: "10px 12px", fontFamily: font.mono, fontSize: 12, color: color.ink }}>
                      {d.attempt}/{d.attemptMax}
                    </td>
                    <td style={{ padding: "10px 12px", fontFamily: font.mono, fontSize: 12, color: color.ink }}>
                      {formatDuration(d.durationMs)}
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      <button
                        type="button"
                        disabled={disabled || replayingId === d.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          replay.mutate(d.id);
                        }}
                        style={{
                          border: "none",
                          background: "transparent",
                          cursor: disabled ? "default" : "pointer",
                          padding: 0,
                          fontFamily: font.body,
                          fontWeight: 500,
                          fontSize: 12.5,
                          color: disabled ? color.ink60 : color.blue,
                        }}
                      >
                        {replayingId === d.id ? "REPLAYING…" : "REPLAY"}
                      </button>
                    </td>
                  </tr>
                  {expanded && (
                    <tr>
                      <td colSpan={6} style={{ padding: 0 }}>
                        <DeliveryDetail delivery={d} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="neo-responsive-cards">
        {logQuery.isLoading &&
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="neo-skeleton" style={{ height: 84, border: `3px solid ${color.rule}` }} />
          ))}

        {log?.deliveries.length === 0 && !logQuery.isLoading && (
          <p style={{ margin: 0, padding: "24px 0", textAlign: "center", fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
            No deliveries recorded yet for this webhook.
          </p>
        )}

        {log?.deliveries.map((d, i) => {
          const expanded = expandedId === d.id;
          return (
            <div
              key={d.id}
              className="neo-row-enter"
              style={{ border: `3px solid ${color.ink}`, background: color.white, ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms` }}
            >
              <div
                onClick={() => setExpandedId(expanded ? null : d.id)}
                style={{ padding: 12, display: "flex", flexDirection: "column", gap: 6, cursor: "pointer" }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink }}>{d.event}</span>
                  <StatusChip delivery={d} />
                </div>
                <p style={{ margin: 0, fontFamily: font.mono, fontSize: 11.5, color: color.ink60 }}>
                  {d.createdAt.replace("T", " ").slice(0, 19)}
                </p>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink }}>
                    Attempt {d.attempt}/{d.attemptMax} · {formatDuration(d.durationMs)}
                  </span>
                  <button
                    type="button"
                    disabled={disabled || replayingId === d.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      replay.mutate(d.id);
                    }}
                    style={{
                      border: "none",
                      background: "transparent",
                      cursor: disabled ? "default" : "pointer",
                      padding: 0,
                      fontFamily: font.body,
                      fontWeight: 500,
                      fontSize: 12.5,
                      color: disabled ? color.ink60 : color.blue,
                    }}
                  >
                    {replayingId === d.id ? "REPLAYING…" : "REPLAY"}
                  </button>
                </div>
              </div>
              {expanded && <DeliveryDetail delivery={d} />}
            </div>
          );
        })}
      </div>

      {replay.isError && (
        <p style={{ margin: "12px 0 0", fontFamily: font.body, fontWeight: 700, fontSize: 12, color: color.pink }}>
          ✕ {replay.error instanceof ApiError ? replay.error.message : "Replay failed"}
        </p>
      )}
    </div>
  );
}
