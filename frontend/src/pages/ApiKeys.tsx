// API Keys screen (Figma [SCREEN] api-keys, SCREENLIST.md §17). Programmatic
// access to jobs/results/exports: key table + create-key modal (one-time
// plaintext reveal) + revoke.
//
// Fixes applied from SCREENLIST.md's bug list:
// - create-key form order is label/scopes/IP FIRST, key generated+revealed
//   only after submit (Figma's own frame reads backwards -- key shown before
//   the fields that define it).
// - "COPY KEY" uses NeoButton's bordered `secondary` variant, not a borderless
//   ghost button, so a safety-critical one-time-reveal action doesn't read as
//   plain text.
// - Scope checkboxes use the shared NeoCheckbox (white tick), not an unticked
//   solid square.
//
// Usage (30d) sparkline: no route in this app currently authenticates with an
// API key (every router still only checks the JWT session token), so real
// usage is genuinely all-zero right now -- rendered as a flat baseline rather
// than invented traffic. See backend/app/db/models/api_key.py.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import NeoButton from "../components/neo/NeoButton";
import NeoCheckbox from "../components/neo/NeoCheckbox";
import InlineWarning from "../components/neo/InlineWarning";
import { api, ApiError } from "../api/client";
import { color, font, shadow } from "../theme/neobrutalist";
import type { ApiKeyRecord, ApiKeyScope, ApiKeysResponse, CreateApiKeyResponse } from "../types";

const SCOPE_OPTIONS: { scope: ApiKeyScope; label: string }[] = [
  { scope: "read_results", label: "Read results" },
  { scope: "create_jobs", label: "Create jobs" },
  { scope: "export", label: "Export" },
  { scope: "admin", label: "Admin" },
];

const SCOPE_LABEL: Record<ApiKeyScope, string> = {
  read_results: "read results",
  create_jobs: "create jobs",
  export: "export",
  admin: "admin",
};

function formatDate(iso: string | null): string {
  if (!iso) return "never";
  return iso.slice(0, 10);
}

function lastUsedLabel(iso: string | null): string {
  if (!iso) return "never";
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function Sparkline({ daily }: { daily: number[] }) {
  const max = Math.max(1, ...daily);
  return (
    <div style={{ display: "flex", gap: 2, height: 24, alignItems: "flex-end" }}>
      {daily.map((v, i) => (
        <div
          key={i}
          style={{
            width: 6,
            // A real-zero day still renders a visible 2px baseline tick
            // rather than disappearing -- distinguishes "no usage yet" from
            // a missing/broken bar.
            height: Math.max(2, (v / max) * 20),
            background: v > 0 ? color.blue : color.rule,
          }}
        />
      ))}
    </div>
  );
}

function KeysTable({
  keys,
  onRevoke,
  pendingId,
}: {
  keys: ApiKeyRecord[];
  onRevoke: (k: ApiKeyRecord) => void;
  pendingId: string | null;
}) {
  const columns: [string, number][] = [
    ["LABEL", 160],
    ["PREFIX", 120],
    ["SCOPES", 220],
    ["CREATED", 110],
    ["LAST USED", 110],
    ["EXPIRY", 110],
    ["USAGE (30D)", 140],
    ["ACTIONS", 156],
  ];

  return (
    <div style={{ background: color.white, border: `3px solid ${color.ink}`, maxWidth: 1126, overflowX: "auto" }}>
      <div style={{ display: "flex", background: color.sand, borderBottom: `3px solid ${color.ink}`, height: 36 }}>
        {columns.map(([h, w]) => (
          <div key={h} style={{ display: "flex", alignItems: "center", padding: "0 10px", width: w, flexShrink: 0 }}>
            <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10, letterSpacing: "0.2px", color: color.ink }}>
              {h}
            </span>
          </div>
        ))}
      </div>
      {keys.map((k, i) => (
        <div
          key={k.id}
          className="neo-row-enter"
          style={{ display: "flex", minHeight: 44, borderBottom: `3px solid ${color.rule}`, alignItems: "center", ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms` }}
        >
          <div style={{ padding: "10px", width: 160, flexShrink: 0 }}>
            <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink }}>{k.label}</span>
          </div>
          <div style={{ padding: "10px", width: 120, flexShrink: 0 }}>
            <span style={{ fontFamily: font.mono, fontSize: 11, color: color.ink }}>{k.prefix}</span>
          </div>
          <div style={{ padding: "10px", width: 220, flexShrink: 0 }}>
            <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink }}>
              {k.scopes.map((s) => SCOPE_LABEL[s]).join(" · ") || "—"}
            </span>
          </div>
          <div style={{ padding: "10px", width: 110, flexShrink: 0 }}>
            <span style={{ fontFamily: font.mono, fontSize: 11, color: color.ink }}>{formatDate(k.createdAt)}</span>
          </div>
          <div style={{ padding: "10px", width: 110, flexShrink: 0 }}>
            <span style={{ fontFamily: font.mono, fontSize: 11, color: color.ink }}>{lastUsedLabel(k.lastUsedAt)}</span>
          </div>
          <div style={{ padding: "10px", width: 110, flexShrink: 0 }}>
            <span style={{ fontFamily: font.mono, fontSize: 11, color: color.ink }}>{formatDate(k.expiresAt)}</span>
          </div>
          <div style={{ padding: "10px", width: 140, flexShrink: 0 }}>
            <Sparkline daily={k.usageDaily} />
          </div>
          <div style={{ padding: "10px", width: 156, flexShrink: 0 }}>
            <button
              type="button"
              onClick={() => onRevoke(k)}
              disabled={pendingId === k.id}
              style={{
                border: "none",
                background: "transparent",
                cursor: pendingId === k.id ? "default" : "pointer",
                padding: 0,
                fontFamily: font.body,
                fontWeight: 500,
                fontSize: 12,
                color: color.pink,
              }}
            >
              REVOKE
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function TableSkeleton() {
  return (
    <div style={{ maxWidth: 1126, display: "flex", flexDirection: "column", border: `3px solid ${color.ink}` }}>
      <div className="neo-skeleton" style={{ height: 36, borderBottom: `3px solid ${color.ink}` }} />
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} style={{ height: 44, borderBottom: i < 3 ? `3px solid ${color.rule}` : "none", display: "flex", alignItems: "center", gap: 16, padding: "0 10px" }}>
          {[160, 120, 220, 110, 110, 110, 140].map((w, j) => (
            <div key={j} className="neo-skeleton" style={{ width: w - 20, height: 12 }} />
          ))}
        </div>
      ))}
    </div>
  );
}

function CreateKeyModal({ onClose }: { onClose: () => void }) {
  const [label, setLabel] = useState("");
  const [scopes, setScopes] = useState<ApiKeyScope[]>([]);
  const [ipAllowlist, setIpAllowlist] = useState("");
  const [result, setResult] = useState<CreateApiKeyResponse | null>(null);
  const [copied, setCopied] = useState(false);

  const create = useMutation({
    mutationFn: () =>
      api.post<CreateApiKeyResponse>("/api/api-keys/", {
        label,
        scopes,
        ip_allowlist: ipAllowlist.trim() || null,
      }),
    onSuccess: (data) => setResult(data),
  });

  function toggleScope(s: ApiKeyScope) {
    setScopes((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  }

  async function handleCopy() {
    if (!result) return;
    await navigator.clipboard.writeText(result.key);
    setCopied(true);
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(17,17,17,0.7)", display: "grid", placeItems: "center", zIndex: 1000 }}>
      <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: shadow.lg, width: 640, display: "flex", flexDirection: "column" }}>
        <div style={{ background: color.ink, color: color.white, padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", textTransform: "uppercase" }}>
            {result ? "Key created" : "Create key"}
          </span>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", color: color.white, cursor: "pointer", fontSize: 16 }}>✕</button>
        </div>

        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Label + scopes + IP allowlist come first -- fixed order from the
              bug list (Figma's own frame shows the key before these fields). */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3675px", color: color.ink, textTransform: "uppercase" }}>
              Label
            </label>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              disabled={!!result}
              placeholder="CI Pipeline"
              style={{ height: 40, padding: "0 12px", border: `3px solid ${color.ink}`, fontFamily: font.body, fontSize: 13, color: color.ink, background: result ? color.sand : color.white }}
            />
            <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10, letterSpacing: "0.4px", color: color.ink60, textTransform: "uppercase" }}>
              A short name to identify this key later.
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <label style={{ fontFamily: font.body, fontWeight: 700, fontSize: 11, letterSpacing: "0.33px", color: color.ink }}>
              SCOPES
            </label>
            {SCOPE_OPTIONS.map((opt) => (
              <div key={opt.scope} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <NeoCheckbox checked={scopes.includes(opt.scope)} onChange={() => toggleScope(opt.scope)} disabled={!!result} />
                <span
                  onClick={() => !result && toggleScope(opt.scope)}
                  style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink, cursor: result ? "default" : "pointer" }}
                >
                  {opt.label}
                </span>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3675px", color: color.ink, textTransform: "uppercase" }}>
              IP allowlist (optional)
            </label>
            <input
              value={ipAllowlist}
              onChange={(e) => setIpAllowlist(e.target.value)}
              disabled={!!result}
              style={{ height: 40, padding: "0 12px", border: `3px solid ${color.ink}`, fontFamily: font.body, fontSize: 13, color: color.ink, background: result ? color.sand : color.white }}
            />
            <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10, letterSpacing: "0.4px", color: color.ink60, textTransform: "uppercase" }}>
              Comma-separated CIDR blocks. Leave blank to allow any IP.
            </span>
          </div>

          {create.isError && (
            <InlineWarning tone="pink" fontSize={12} fontWeight={700}>
              {create.error instanceof ApiError ? create.error.message : "Couldn't create that key"}
            </InlineWarning>
          )}

          {result && (
            <>
              <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 12.5, color: color.ink }}>
                Copy this key now — it will not be shown again.
              </p>
              <div style={{ background: color.yellow, border: `3px solid ${color.ink}`, padding: "12px 14px", wordBreak: "break-all" }}>
                <span style={{ fontFamily: font.mono, fontSize: 13, color: color.ink }}>{result.key}</span>
              </div>
              <div>
                <NeoButton variant="secondary" size="sm" onClick={handleCopy}>
                  {copied ? "Copied" : "Copy key"}
                </NeoButton>
              </div>
            </>
          )}
        </div>

        <div style={{ padding: "12px 20px 16px", display: "flex", justifyContent: "flex-end", gap: 12 }}>
          {result ? (
            <NeoButton variant="primary" onClick={onClose}>Done</NeoButton>
          ) : (
            <>
              <NeoButton variant="secondary" onClick={onClose} disabled={create.isPending}>Cancel</NeoButton>
              <NeoButton variant="primary" onClick={() => create.mutate()} loading={create.isPending} disabled={!label.trim()}>
                Generate key
              </NeoButton>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ApiKeys() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const keysQuery = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => api.get<ApiKeysResponse>("/api/api-keys/"),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["api-keys"] });

  const revoke = useMutation({
    mutationFn: (id: string) => api.del(`/api/api-keys/${id}`),
    onSettled: () => setPendingId(null),
    onSuccess: invalidate,
  });

  const keys = keysQuery.data?.keys ?? [];

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>API KEYS</h1>
        <p style={{ margin: "4px 0 0", fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink60 }}>
          Programmatic access to jobs, results and exports.
        </p>
      </div>

      <div style={{ marginBottom: 24 }}>
        <NeoButton variant="primary" onClick={() => setCreateOpen(true)} disabled={keysQuery.isError}>
          Create key
        </NeoButton>
      </div>

      {keysQuery.isLoading && <TableSkeleton />}

      {keysQuery.isError && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "48px 0" }}>
          <div style={{ width: 64, height: 64, background: color.pink, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>API KEYS FAILED TO LOAD</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 400 }}>
            Your keys could not be fetched from the server.
          </p>
          <p style={{ margin: 0, fontFamily: font.mono, fontSize: 12, color: color.ink60 }}>
            {keysQuery.error instanceof ApiError ? keysQuery.error.message : "ERR_APIKEYS_FETCH_FAILED"}
          </p>
          <NeoButton variant="destructive" onClick={() => keysQuery.refetch()}>
            Retry
          </NeoButton>
        </div>
      )}

      {keysQuery.isSuccess && keys.length === 0 && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "48px 0" }}>
          <div style={{ width: 64, height: 64, background: color.yellow, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>NO API KEYS YET</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 420 }}>
            Create a key to authenticate programmatic access to jobs, results and exports.
          </p>
          <NeoButton variant="primary" onClick={() => setCreateOpen(true)}>
            Create key
          </NeoButton>
        </div>
      )}

      {keysQuery.isSuccess && keys.length > 0 && (
        <KeysTable
          keys={keys}
          pendingId={pendingId}
          onRevoke={(k) => {
            if (!window.confirm(`Revoke "${k.label}"? Anything using this key will stop working immediately.`)) return;
            setPendingId(k.id);
            revoke.mutate(k.id);
          }}
        />
      )}

      {createOpen && (
        <CreateKeyModal
          onClose={() => {
            setCreateOpen(false);
            invalidate();
          }}
        />
      )}
    </div>
  );
}
