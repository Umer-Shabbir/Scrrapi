// Suppression List screen (Figma [SCREEN] suppression). Three tabs (Domains/
// Emails/Places), an add-entry bar (single value + bulk-paste/upload), a
// table with a live per-rule match count, and a destructive confirm modal
// with a typed "SUPPRESS" safety mechanic (SCREENLIST.md §12 bug: this was
// missing entirely -- body copy referenced it but no input existed).
//
// Adding a rule is real and irreversible: it deletes every currently-matching
// Result row immediately (backend: app/api/routers/suppression.py), which is
// why the impact-preview count is fetched and shown *before* the modal opens
// (§12 bug: the count previously only appeared inside the modal), not just as
// a number typed into the confirm copy.

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import NeoButton from "../components/neo/NeoButton";
import { SkeletonTable } from "../components/neo/Skeleton";
import InlineWarning from "../components/neo/InlineWarning";
import { api, ApiError } from "../api/client";
import { color, font } from "../theme/neobrutalist";
import type {
  SuppressionBulkResponse,
  SuppressionCreateResponse,
  SuppressionEntry,
  SuppressionKind,
} from "../types";

const TABS: { kind: SuppressionKind; label: string; fieldLabel: string; placeholder: string }[] = [
  { kind: "domain", label: "Domains", fieldLabel: "Domain", placeholder: "e.g. competitor-site.com" },
  { kind: "email", label: "Emails", fieldLabel: "Email", placeholder: "e.g. spam@example.com" },
  { kind: "place", label: "Places", fieldLabel: "Place ID", placeholder: "e.g. the place key shown on a lead" },
];

const CONFIRM_WORD = "SUPPRESS";

function TabStrip({ active, onSelect }: { active: SuppressionKind; onSelect: (kind: SuppressionKind) => void }) {
  return (
    <div style={{ display: "flex", gap: 4, marginBottom: 24 }}>
      {TABS.map((t) => (
        <button
          key={t.kind}
          type="button"
          onClick={() => onSelect(t.kind)}
          style={{
            padding: "10px 20px",
            fontFamily: font.body,
            fontWeight: 700,
            fontSize: 12.5,
            letterSpacing: "0.25px",
            textTransform: "uppercase",
            background: active === t.kind ? color.ink : color.white,
            color: active === t.kind ? color.white : color.ink,
            border: `3px solid ${color.ink}`,
            cursor: "pointer",
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

function ConfirmModal({
  kind,
  value,
  rowCount,
  onCancel,
  onConfirm,
  pending,
}: {
  kind: SuppressionKind;
  value: string;
  rowCount: number;
  onCancel: () => void;
  onConfirm: () => void;
  pending: boolean;
}) {
  const [typed, setTyped] = useState("");
  const canConfirm = typed.trim().toUpperCase() === CONFIRM_WORD;
  const noun = kind === "domain" ? "domain" : kind === "email" ? "email address" : "place";

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(17,17,17,0.7)", display: "grid", placeItems: "center", zIndex: 1000 }}>
      <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: "10px 10px 0px 0px #111", width: 440 }}>
        <div style={{ background: color.pink, color: color.white, padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", textTransform: "uppercase" }}>
            Suppress this {noun}
          </span>
          <button type="button" onClick={onCancel} style={{ border: "none", background: "transparent", color: color.white, cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>
        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink }}>
            This removes {rowCount.toLocaleString()} stored row{rowCount === 1 ? "" : "s"} matching{" "}
            <strong style={{ fontFamily: font.mono, fontWeight: 400 }}>{value}</strong> and strips them from every
            future export. This cannot be undone. Type {CONFIRM_WORD} to confirm.
          </p>
          <input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={`Type ${CONFIRM_WORD}`}
            style={{
              height: 40,
              padding: "0 12px",
              border: `3px solid ${color.ink}`,
              fontFamily: font.mono,
              fontSize: 13,
              color: color.ink,
            }}
          />
        </div>
        <div style={{ padding: "16px 20px", display: "flex", justifyContent: "flex-end", gap: 12 }}>
          <NeoButton variant="secondary" onClick={onCancel} disabled={pending}>
            Cancel
          </NeoButton>
          <NeoButton variant="destructive" onClick={onConfirm} disabled={!canConfirm} loading={pending}>
            Suppress
          </NeoButton>
        </div>
      </div>
    </div>
  );
}

function BulkModal({
  kind,
  onCancel,
  onSubmit,
  pending,
}: {
  kind: SuppressionKind;
  onCancel: () => void;
  onSubmit: (values: string[], reason: string) => void;
  pending: boolean;
}) {
  const [text, setText] = useState("");
  const [reason, setReason] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  function parseValues(): string[] {
    return text
      .split(/[\n,]/)
      .map((v) => v.trim())
      .filter(Boolean);
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    file.text().then((content) => setText((current) => (current ? `${current}\n${content}` : content)));
    e.target.value = "";
  }

  const values = parseValues();

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(17,17,17,0.7)", display: "grid", placeItems: "center", zIndex: 1000 }}>
      <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: "10px 10px 0px 0px #111", width: 520 }}>
        <div style={{ background: color.ink, color: color.white, padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", textTransform: "uppercase" }}>
            Bulk paste / upload
          </span>
          <button type="button" onClick={onCancel} style={{ border: "none", background: "transparent", color: color.white, cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>
        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
            One {kind} per line, or comma-separated.
          </p>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={8}
            style={{ padding: 12, border: `3px solid ${color.ink}`, fontFamily: font.mono, fontSize: 12, color: color.ink, resize: "vertical" }}
          />
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            style={{ alignSelf: "flex-start", border: "3px solid transparent", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 700, fontSize: 12, color: color.blue, textTransform: "uppercase" }}
          >
            Upload .txt/.csv instead
          </button>
          <input ref={fileInput} type="file" accept=".csv,.txt" hidden onChange={handleFile} />
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason (applies to all)"
            style={{ height: 40, padding: "0 12px", border: `3px solid ${color.ink}`, fontFamily: font.body, fontSize: 13, color: color.ink }}
          />
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 11, color: color.ink60 }}>
            {values.length} value{values.length === 1 ? "" : "s"} parsed.
          </p>
        </div>
        <div style={{ padding: "16px 20px", display: "flex", justifyContent: "flex-end", gap: 12 }}>
          <NeoButton variant="secondary" onClick={onCancel} disabled={pending}>
            Cancel
          </NeoButton>
          <NeoButton
            variant="primary"
            onClick={() => onSubmit(values, reason)}
            disabled={values.length === 0}
            loading={pending}
          >
            Add {values.length || ""}
          </NeoButton>
        </div>
      </div>
    </div>
  );
}

export default function Suppression() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<SuppressionKind>("domain");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [confirmTarget, setConfirmTarget] = useState<{ value: string; rowCount: number } | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);

  const tab = TABS.find((t) => t.kind === activeTab)!;

  const listQuery = useQuery({
    queryKey: ["suppression", activeTab],
    queryFn: () => api.get<SuppressionEntry[]>(`/api/suppression/?kind=${activeTab}`),
  });

  const previewQuery = useQuery({
    queryKey: ["suppression-preview", activeTab, value],
    queryFn: () => api.get<{ rowCount: number }>(`/api/suppression/preview?kind=${activeTab}&value=${encodeURIComponent(value)}`),
    enabled: value.trim().length > 1,
  });

  const createEntry = useMutation({
    mutationFn: () =>
      api.post<SuppressionCreateResponse>("/api/suppression/", { kind: activeTab, value, reason: reason || null }),
    onSuccess: () => {
      setValue("");
      setReason("");
      setConfirmTarget(null);
      queryClient.invalidateQueries({ queryKey: ["suppression", activeTab] });
    },
  });

  const bulkCreate = useMutation({
    mutationFn: (payload: { values: string[]; reason: string }) =>
      api.post<SuppressionBulkResponse>("/api/suppression/bulk", {
        kind: activeTab,
        values: payload.values,
        reason: payload.reason || null,
      }),
    onSuccess: () => {
      setBulkOpen(false);
      queryClient.invalidateQueries({ queryKey: ["suppression", activeTab] });
    },
  });

  const deleteEntry = useMutation({
    mutationFn: (id: string) => api.del(`/api/suppression/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["suppression", activeTab] }),
  });

  function handleAddClick() {
    if (!value.trim()) return;
    const rowCount = previewQuery.data?.rowCount ?? 0;
    setConfirmTarget({ value: value.trim(), rowCount });
  }

  const entries = listQuery.data ?? [];

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>SUPPRESSION LIST</h1>
        <p style={{ margin: "4px 0 0", fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink60, maxWidth: 700 }}>
          Domains, emails and place ids that are never scraped, never stored, and stripped from exports.
        </p>
      </div>

      <TabStrip active={activeTab} onSelect={(kind) => { setActiveTab(kind); setValue(""); setReason(""); }} />

      <div className="neo-responsive-row" style={{ background: color.sand, border: `3px solid ${color.ink}`, padding: 16, marginBottom: 24, display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, width: 360 }}>
          <label style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3675px", color: color.ink, textTransform: "uppercase" }}>
            {tab.fieldLabel}
          </label>
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            style={{ height: 40, padding: "0 12px", border: `3px solid ${color.ink}`, fontFamily: font.body, fontSize: 13, color: color.ink }}
          />
          <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 10, letterSpacing: "0.4px", color: color.ink60, textTransform: "uppercase" }}>
            {tab.placeholder}
          </p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, width: 360 }}>
          <label style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3675px", color: color.ink, textTransform: "uppercase" }}>
            Reason
          </label>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            style={{ height: 40, padding: "0 12px", border: `3px solid ${color.ink}`, fontFamily: font.body, fontSize: 13, color: color.ink }}
          />
          <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 10, letterSpacing: "0.4px", color: color.ink60, textTransform: "uppercase" }}>
            Why is this suppressed?
          </p>
        </div>
        <NeoButton variant="primary" onClick={handleAddClick} disabled={!value.trim()}>
          Add{previewQuery.data ? ` (${previewQuery.data.rowCount})` : ""}
        </NeoButton>
        <NeoButton variant="ghost" onClick={() => setBulkOpen(true)}>
          Bulk paste / upload
        </NeoButton>
      </div>

      {listQuery.isLoading && (
        <div style={{ maxWidth: 1126 }}>
          <SkeletonTable rows={4} columns={5} />
        </div>
      )}

      {listQuery.isError && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: "60px 0" }}>
          <div style={{ width: 32, height: 32, background: color.pink, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 16, color: color.ink }}>SUPPRESSION LIST FAILED TO LOAD</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center" }}>
            Your suppressed domains, emails and places could not be fetched.
          </p>
          <p style={{ margin: 0, fontFamily: font.mono, fontSize: 11, color: color.ink60 }}>
            {listQuery.error instanceof ApiError ? listQuery.error.message : "ERR_SUPPRESSION_FETCH_FAILED"}
          </p>
          <NeoButton variant="destructive" onClick={() => listQuery.refetch()}>
            Retry
          </NeoButton>
        </div>
      )}

      {listQuery.data && entries.length === 0 && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, padding: "80px 0" }}>
          <div style={{ width: 32, height: 32, background: color.yellow, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>NO {tab.label.toUpperCase()} SUPPRESSED</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center" }}>
            Add a {tab.kind} above, or bulk-paste a list, to keep it out of every scrape and export.
          </p>
        </div>
      )}

      {listQuery.data && entries.length > 0 && (
        <div style={{ border: `3px solid ${color.ink}`, background: color.white, width: "100%", maxWidth: 1126, overflowX: "auto" }}>
          <div style={{ display: "flex", background: color.sand, borderBottom: `3px solid ${color.ink}` }}>
            {[tab.fieldLabel.toUpperCase(), "REASON", "ADDED BY", "ADDED AT", "ACTIONS"].map((h, i) => (
              <div key={h} style={{ padding: "0 12px", height: 36, display: "flex", alignItems: "center", minWidth: i === 1 ? 300 : 150, flex: i === 4 ? 1 : undefined }}>
                <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.315px", color: color.ink }}>{h}</span>
              </div>
            ))}
          </div>
          {entries.map((entry, i) => (
            <div
              key={entry.id}
              className="neo-row-enter"
              style={{ display: "flex", borderBottom: `3px solid ${color.rule}`, ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms` }}
            >
              <div style={{ padding: "0 12px", height: 40, display: "flex", alignItems: "center", minWidth: 150 }}>
                <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink }}>{entry.value}</span>
              </div>
              <div style={{ padding: "0 12px", height: 40, display: "flex", alignItems: "center", minWidth: 300 }}>
                <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink }}>{entry.reason ?? "—"}</span>
              </div>
              <div style={{ padding: "0 12px", height: 40, display: "flex", alignItems: "center", minWidth: 150 }}>
                <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink }}>{entry.createdBy}</span>
              </div>
              <div style={{ padding: "0 12px", height: 40, display: "flex", alignItems: "center", minWidth: 150 }}>
                <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink }}>
                  {new Date(entry.createdAt).toLocaleDateString()}
                </span>
              </div>
              <div style={{ padding: "0 12px", height: 40, display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
                <span title="Results currently matching this rule -- should stay at 0 once enforcement has caught up" style={{ fontFamily: font.body, fontWeight: 500, fontSize: 10.5, color: color.ink60 }}>
                  {entry.rowCount} rows
                </span>
                <button
                  type="button"
                  onClick={() => deleteEntry.mutate(entry.id)}
                  disabled={deleteEntry.isPending}
                  style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.blue }}
                >
                  REMOVE
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {confirmTarget && (
        <ConfirmModal
          kind={activeTab}
          value={confirmTarget.value}
          rowCount={confirmTarget.rowCount}
          onCancel={() => setConfirmTarget(null)}
          onConfirm={() => createEntry.mutate()}
          pending={createEntry.isPending}
        />
      )}

      {bulkOpen && (
        <BulkModal
          kind={activeTab}
          onCancel={() => setBulkOpen(false)}
          onSubmit={(values, bulkReason) => bulkCreate.mutate({ values, reason: bulkReason })}
          pending={bulkCreate.isPending}
        />
      )}

      {createEntry.isError && (
        <div style={{ margin: "16px 0 0" }}>
          <InlineWarning tone="pink" fontSize={12} fontWeight={700}>
            {createEntry.error instanceof ApiError ? createEntry.error.message : "Couldn't add that rule"}
          </InlineWarning>
        </div>
      )}
    </div>
  );
}
