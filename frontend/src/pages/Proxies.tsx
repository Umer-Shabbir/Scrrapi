// Proxies screen (Figma [SCREEN] proxies). Pool health strip (stat tiles),
// an add-proxies paste box (scheme://user:pass@host:port, one per line), and
// a table with real per-proxy stats (LEASES/SUCCESS/LATENCY/BLOCKS/LAST USED)
// and Test/Disable/Drain/Delete actions.
//
// DRAIN is real but behaviorally identical to DISABLE today -- both just
// exclude the proxy from rotation immediately. There is no in-flight-lease
// tracking to make DRAIN wait for anything (backend: app/db/models/proxy.py's
// docstring), so it isn't a fake "draining…" state that never resolves.
//
// Stat tiles and the degraded banner are computed from the same
// GET /api/proxies/stats response the table's own rows would sum to --
// SCREENLIST.md §13's "Major" bug (banner/tiles disagreeing) can't recur
// here because there's only one source.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import NeoButton from "../components/neo/NeoButton";
import InlineWarning from "../components/neo/InlineWarning";
import { api, ApiError } from "../api/client";
import { color, font } from "../theme/neobrutalist";
import type { ProxyBulkResponse, ProxyProtocol, ProxyRecord, ProxyStats, ProxyTestResult } from "../types";

const STATUS_FILL: Record<string, string> = {
  active: color.green,
  cooling: color.yellow,
  disabled: color.sand,
  retired: color.sand,
};
const STATUS_GLYPH: Record<string, string> = {
  active: "✓",
  cooling: "!",
  disabled: "✕",
  retired: "✕",
};
const STATUS_LABEL: Record<string, string> = {
  active: "healthy",
  cooling: "cooling",
  disabled: "retired",
  retired: "retired",
};

const PROXY_TABLE_COLUMNS = [
  { label: "HOST", width: 150 },
  { label: "PORT", width: 80 },
  { label: "PROTO", width: 90 },
  { label: "COUNTRY", width: 90 },
  { label: "STATE", width: 110 },
  { label: "LEASES", width: 80 },
  { label: "SUCCESS", width: 80 },
  { label: "LATENCY", width: 90 },
  { label: "BLOCKS", width: 80 },
  { label: "LAST USED", width: 100 },
  { label: "ACTIONS", width: 260, flex: true },
];

// One line: `[scheme://][user:pass@]host:port`
const PASTE_LINE_RE =
  /^(?:(http|https|socks5):\/\/)?(?:([^:@]+):([^:@]+)@)?([^:@\s]+):(\d{1,5})$/i;

interface ParsedLine {
  raw: string;
  ok: boolean;
  protocol: ProxyProtocol;
  host: string;
  port: number;
  username: string | null;
  password: string | null;
}

function parsePasteLine(line: string): ParsedLine | null {
  const trimmed = line.trim();
  if (!trimmed) return null;
  const match = trimmed.match(PASTE_LINE_RE);
  if (!match) return { raw: trimmed, ok: false, protocol: "http", host: "", port: 0, username: null, password: null };
  const [, scheme, user, pass, host, portStr] = match;
  const port = Number(portStr);
  if (port < 1 || port > 65535) {
    return { raw: trimmed, ok: false, protocol: "http", host: "", port: 0, username: null, password: null };
  }
  return {
    raw: trimmed,
    ok: true,
    protocol: (scheme?.toLowerCase() as ProxyProtocol) ?? "http",
    host,
    port,
    username: user ?? null,
    password: pass ?? null,
  };
}

function StatTile({ label, value, delta, fill }: { label: string; value: string; delta?: string; fill?: string }) {
  return (
    <div style={{ background: fill ?? color.white, border: `3px solid ${color.ink}`, padding: 14, flex: 1, minWidth: 180 }}>
      <p style={{ margin: "0 0 8px", fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.315px", color: color.ink, textTransform: "uppercase" }}>
        {label}
      </p>
      <p style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>{value}</p>
      {delta && (
        <p style={{ margin: "4px 0 0", fontFamily: font.body, fontSize: 11, color: color.ink60 }}>{delta}</p>
      )}
    </div>
  );
}

function StatusChip({ status: proxyStatus }: { status: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: 20,
        padding: "0 8px",
        border: `2px solid ${color.ink}`,
        background: STATUS_FILL[proxyStatus] ?? color.sand,
        fontFamily: font.body,
        fontWeight: 700,
        fontSize: 10,
        color: color.ink,
        textTransform: "uppercase",
        opacity: proxyStatus === "disabled" || proxyStatus === "retired" ? 0.6 : 1,
      }}
    >
      {STATUS_GLYPH[proxyStatus] ?? "●"} {STATUS_LABEL[proxyStatus] ?? proxyStatus}
    </span>
  );
}

function AddProxiesPanel({ onAdded }: { onAdded: () => void }) {
  const [text, setText] = useState("");
  const [feedback, setFeedback] = useState<ProxyBulkResponse | null>(null);

  const parsedLines = text.split("\n").map(parsePasteLine).filter((l): l is ParsedLine => l !== null);
  const validLines = parsedLines.filter((l) => l.ok);
  const invalidCount = parsedLines.length - validLines.length;

  const bulkAdd = useMutation({
    mutationFn: () =>
      api.post<ProxyBulkResponse>("/api/proxies/bulk", {
        entries: validLines.map((l) => ({
          host: l.host, port: l.port, protocol: l.protocol, username: l.username, password: l.password,
        })),
      }),
    onSuccess: (result) => {
      setFeedback(result);
      setText("");
      onAdded();
    },
  });

  return (
    <div style={{ background: color.white, border: `3px solid ${color.ink}`, padding: 16, marginBottom: 24 }}>
      <p style={{ margin: "0 0 4px", fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>
        ADD PROXIES
      </p>
      <p style={{ margin: "0 0 10px", fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
        Paste one per line: scheme://user:pass@host:port
      </p>
      <textarea
        value={text}
        onChange={(e) => { setText(e.target.value); setFeedback(null); }}
        rows={5}
        placeholder={"http://user1:pass1@203.0.113.10:8080\nhttp://user2:pass2@203.0.113.11:8080\nsocks5://user3:pass3@203.0.113.12:1080"}
        style={{ width: "100%", boxSizing: "border-box", padding: 12, border: `3px solid ${color.ink}`, background: color.sand, fontFamily: font.mono, fontSize: 12, color: color.ink60, resize: "vertical", marginBottom: 10 }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", gap: 16, fontFamily: font.body, fontSize: 12 }}>
          <span style={{ color: color.ink }}>
            <span style={{ color: color.green }}>●</span> {feedback ? feedback.created : validLines.length} accepted
          </span>
          <span style={{ color: color.ink }}>
            <span style={{ color: color.pink }}>●</span> {invalidCount} rejected
          </span>
          <span style={{ color: color.ink60 }}>
            <span style={{ color: color.ink60 }}>●</span> {feedback ? feedback.skipped : 0} duplicate skipped
          </span>
        </div>
        <NeoButton
          variant="primary"
          onClick={() => bulkAdd.mutate()}
          disabled={validLines.length === 0}
          loading={bulkAdd.isPending}
        >
          Add {validLines.length || ""} {validLines.length === 1 ? "proxy" : "proxies"}
        </NeoButton>
      </div>
      {bulkAdd.isError && (
        <div style={{ margin: "8px 0 0" }}>
          <InlineWarning tone="pink" fontSize={12} fontWeight={700}>
            {bulkAdd.error instanceof ApiError ? bulkAdd.error.message : "Couldn't add those proxies"}
          </InlineWarning>
        </div>
      )}
    </div>
  );
}

function ProxyRow({ proxy, onChanged, rowIndex }: { proxy: ProxyRecord; onChanged: () => void; rowIndex: number }) {
  const [testResult, setTestResult] = useState<ProxyTestResult | null>(null);
  const isRetired = proxy.status === "disabled" || proxy.status === "retired";

  const test = useMutation({
    mutationFn: () => api.post<ProxyTestResult>(`/api/proxies/${proxy.id}/test`),
    onSuccess: (result) => { setTestResult(result); onChanged(); },
  });
  const disable = useMutation({
    mutationFn: () => api.post(`/api/proxies/${proxy.id}/disable`),
    onSuccess: onChanged,
  });
  const drain = useMutation({
    mutationFn: () => api.post(`/api/proxies/${proxy.id}/drain`),
    onSuccess: onChanged,
  });
  const remove = useMutation({
    mutationFn: () => api.del(`/api/proxies/${proxy.id}`),
    onSuccess: onChanged,
  });

  const cellStyle: React.CSSProperties = { padding: "0 12px", height: 40, display: "flex", alignItems: "center", opacity: isRetired ? 0.55 : 1 };

  return (
    <div
      className="neo-row-enter"
      style={{ display: "flex", borderBottom: `3px solid ${color.rule}`, ["--neo-delay" as string]: `${Math.min(rowIndex, 12) * 24}ms` }}
    >
      <div style={{ ...cellStyle, minWidth: 150 }}>
        <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink }}>{proxy.host}</span>
      </div>
      <div style={{ ...cellStyle, minWidth: 80 }}>
        <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink }}>{proxy.port}</span>
      </div>
      <div style={{ ...cellStyle, minWidth: 90 }}>
        <span style={{ fontFamily: font.mono, fontSize: 11, color: color.ink, textTransform: "uppercase" }}>{proxy.protocol}</span>
      </div>
      <div style={{ ...cellStyle, minWidth: 90 }}>
        <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink }}>{proxy.country ?? "—"}</span>
      </div>
      <div style={{ ...cellStyle, minWidth: 110, opacity: 1 }}>
        <StatusChip status={proxy.status} />
      </div>
      <div style={{ ...cellStyle, minWidth: 80 }}>
        <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink }}>{proxy.totalUses}</span>
      </div>
      <div style={{ ...cellStyle, minWidth: 80 }}>
        <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink }}>{proxy.successRate != null ? `${proxy.successRate}%` : "—"}</span>
      </div>
      <div style={{ ...cellStyle, minWidth: 90 }}>
        <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink }}>{proxy.avgLatencyMs != null ? `${proxy.avgLatencyMs}ms` : "—"}</span>
      </div>
      <div style={{ ...cellStyle, minWidth: 80 }}>
        <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink }}>{proxy.blockCount}</span>
      </div>
      <div style={{ ...cellStyle, minWidth: 100 }}>
        <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink }}>
          {proxy.lastUsedAt ? new Date(proxy.lastUsedAt).toLocaleString() : "never"}
        </span>
      </div>
      <div style={{ padding: "0 12px", height: 40, display: "flex", alignItems: "center", gap: 8, flex: 1, flexWrap: "wrap" }}>
        <button type="button" onClick={() => test.mutate()} disabled={isRetired || test.isPending} style={{ border: "none", background: "transparent", cursor: isRetired ? "default" : "pointer", padding: 0, fontFamily: font.body, fontWeight: 500, fontSize: 12, color: isRetired ? color.ink60 : color.blue }}>
          TEST
        </button>
        <span style={{ color: color.ink60 }}>·</span>
        <button type="button" onClick={() => disable.mutate()} disabled={isRetired || disable.isPending} style={{ border: "none", background: "transparent", cursor: isRetired ? "default" : "pointer", padding: 0, fontFamily: font.body, fontWeight: 500, fontSize: 12, color: isRetired ? color.ink60 : color.blue }}>
          DISABLE
        </button>
        <span style={{ color: color.ink60 }}>·</span>
        <button type="button" onClick={() => drain.mutate()} disabled={isRetired || drain.isPending} style={{ border: "none", background: "transparent", cursor: isRetired ? "default" : "pointer", padding: 0, fontFamily: font.body, fontWeight: 500, fontSize: 12, color: isRetired ? color.ink60 : color.blue }}>
          DRAIN
        </button>
        <span style={{ color: color.ink60 }}>·</span>
        <button type="button" onClick={() => remove.mutate()} disabled={remove.isPending} style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 700, fontSize: 12, color: color.pink }}>
          DELETE
        </button>
        {testResult && (
          <span style={{ fontFamily: font.mono, fontSize: 10.5, color: testResult.ok ? color.green : color.pink }}>
            {testResult.ok ? `✓ ${testResult.latencyMs}ms` : `✕ ${testResult.detail}`}
          </span>
        )}
      </div>
    </div>
  );
}

export default function Proxies() {
  const queryClient = useQueryClient();

  const statsQuery = useQuery({
    queryKey: ["proxy-stats"],
    queryFn: () => api.get<ProxyStats>("/api/proxies/stats"),
  });

  const listQuery = useQuery({
    queryKey: ["proxies"],
    queryFn: () => api.get<ProxyRecord[]>("/api/proxies/"),
  });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["proxies"] });
    queryClient.invalidateQueries({ queryKey: ["proxy-stats"] });
  }

  const stats = statsQuery.data;
  const proxies = listQuery.data ?? [];
  const degraded = stats && stats.total > 0 && (stats.cooling > 0 || (stats.blockRatePct ?? 0) > 1);
  const allRetired = stats && stats.total > 0 && stats.healthy === 0 && stats.cooling === 0;

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>PROXIES</h1>
        <p style={{ margin: "4px 0 0", fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink60 }}>
          Pool health and rotation for outbound scraping traffic.
        </p>
      </div>

      {allRetired && (
        <div style={{ background: color.pink, border: `3px solid ${color.ink}`, padding: "10px 14px", marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12, color: color.white }}>!</span>
          <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.white }}>
            All proxies are retired — scraping will fail until new proxies are added.
          </p>
        </div>
      )}
      {!allRetired && degraded && (
        <div style={{ background: color.yellow, border: `3px solid ${color.ink}`, padding: "10px 14px", marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12 }}>!</span>
          <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink }}>
            {stats!.cooling} of {stats!.total} proxies are cooling and block rate is {stats!.blockRatePct}% — jobs may slow down.
          </p>
        </div>
      )}

      {statsQuery.isLoading && (
        <div className="neo-responsive-stats" style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} style={{ background: color.white, border: `3px solid ${color.ink}`, padding: 14, flex: 1, minWidth: 180, display: "flex", flexDirection: "column", gap: 8 }}>
              <div className="neo-skeleton" style={{ height: 10, width: 60 }} />
              <div className="neo-skeleton" style={{ height: 20, width: 40 }} />
            </div>
          ))}
        </div>
      )}

      {stats && (
        <div className="neo-responsive-stats" style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
          <StatTile label="Healthy" value={String(stats.healthy)} fill={color.green} />
          <StatTile label="Cooling" value={String(stats.cooling)} fill={color.yellow} />
          <StatTile label="Retired" value={String(stats.retired)} fill={color.sand} />
          <StatTile label="Avg latency" value={stats.avgLatencyMs != null ? `${stats.avgLatencyMs}ms` : "—"} fill={color.purple} />
          <StatTile
            label="Block rate"
            value={stats.blockRatePct != null ? `${stats.blockRatePct}%` : "—"}
            fill={color.pink}
          />
        </div>
      )}

      <AddProxiesPanel onAdded={refresh} />

      {listQuery.isLoading && (
        <div style={{ border: `3px solid ${color.ink}`, background: color.white, maxWidth: 1200 }}>
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} style={{ height: 40, display: "flex", alignItems: "center", padding: "0 12px", borderBottom: `1px solid ${color.rule}` }}>
              <div className="neo-skeleton" style={{ height: 12, width: `${60 + i * 5}%` }} />
            </div>
          ))}
        </div>
      )}

      {listQuery.isError && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: "60px 0" }}>
          <div style={{ width: 32, height: 32, background: color.pink, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 16, color: color.ink }}>PROXY LIST FAILED TO LOAD</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
            The proxy pool could not be fetched from the database.
          </p>
          <p style={{ margin: 0, fontFamily: font.mono, fontSize: 11, color: color.ink60 }}>
            {listQuery.error instanceof ApiError ? listQuery.error.message : "ERR_PROXIES_FETCH_FAILED"}
          </p>
          <NeoButton variant="destructive" onClick={() => listQuery.refetch()}>
            Retry
          </NeoButton>
        </div>
      )}

      {listQuery.data && proxies.length === 0 && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, padding: "80px 0" }}>
          <div style={{ width: 32, height: 32, background: color.yellow, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>NO PROXIES YET</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 420 }}>
            The app runs direct without proxies — that risks getting blocked at scale on high-volume jobs.
          </p>
        </div>
      )}

      {listQuery.data && proxies.length > 0 && (
        <>
          <div className="neo-responsive-table" style={{ border: `3px solid ${color.ink}`, background: color.white, width: "100%", maxWidth: 1300, overflowX: "auto" }}>
            <div style={{ display: "flex", background: color.sand, borderBottom: `3px solid ${color.ink}` }}>
              {PROXY_TABLE_COLUMNS.map((col) => (
                <div key={col.label} style={{ padding: "0 12px", height: 36, display: "flex", alignItems: "center", minWidth: col.width, flex: col.flex ? 1 : undefined }}>
                  <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.315px", color: color.ink }}>{col.label}</span>
                </div>
              ))}
            </div>
            {proxies.map((proxy, i) => (
              <ProxyRow key={proxy.id} proxy={proxy} onChanged={refresh} rowIndex={i} />
            ))}
          </div>

          <div className="neo-responsive-cards">
            {proxies.map((proxy, i) => (
              <div
                key={proxy.id}
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
                    <span style={{ fontFamily: font.mono, fontWeight: 700, fontSize: 13, color: color.ink }}>
                      {proxy.host}:{proxy.port}
                    </span>
                    <p style={{ margin: "2px 0 0", fontFamily: font.body, fontSize: 11, color: color.ink60 }}>
                      {proxy.protocol.toUpperCase()}{proxy.country ? ` · ${proxy.country}` : ""}
                    </p>
                  </div>
                  <StatusChip status={proxy.status} />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontFamily: font.mono, fontSize: 12, color: color.ink }}>
                  <span>Latency: {proxy.avgLatencyMs != null ? `${proxy.avgLatencyMs}ms` : "—"}</span>
                  <span>Success: {proxy.successRate != null ? `${proxy.successRate}%` : "—"}</span>
                  <span>Blocks: {proxy.blockCount}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: `1px solid ${color.rule}`, paddingTop: 6 }}>
                  <span style={{ fontFamily: font.body, fontSize: 11, color: color.ink60 }}>
                    Last used: {proxy.lastUsedAt ? new Date(proxy.lastUsedAt).toLocaleDateString() : "never"}
                  </span>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => api.post(`/api/proxies/${proxy.id}/test`).then(refresh)}
                      style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 700, fontSize: 11.5, color: color.blue }}
                    >
                      TEST
                    </button>
                    <span style={{ color: color.ink60 }}>·</span>
                    <button
                      type="button"
                      onClick={() => api.del(`/api/proxies/${proxy.id}`).then(refresh)}
                      style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 700, fontSize: 11.5, color: color.pink }}
                    >
                      DELETE
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
