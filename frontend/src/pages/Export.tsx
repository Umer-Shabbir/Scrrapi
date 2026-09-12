// Export screen (Figma [SCREEN] export). Format picker (CSV/XLSX/KML real --
// see below; JSONL/Google Sheets "coming soon", no writer exists), column
// selection (group checkboxes), row scope (radio -- only "All rows" is wired;
// "Current filter"/"Current selection" need grid-side filter/selection state
// the backend can't reconstruct, same limitation as suppression -- shown
// disabled rather than invented), generate action, and export history table
// (download/delete, real row count/size/expiry).
//
// SCREENLIST.md §11 says "CSV is the only functional format currently" --
// stale against the live code (app/export/{csv,xlsx,kml}_writer.py + the
// _EXPORT_WRITERS registry all three are already wired into): XLSX and KML
// both write real files (verified directly), so both are enabled here rather
// than parroting a doc note the code itself has moved past -- same
// live-code-supersedes-stale-audit precedent the rest of the doc already
// applies to other screens. JSONL/Google Sheets have no writer at all and
// stay "coming soon".
//
// Legacy equivalent: ExportManager's format dropdown / "Export" button.

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import NeoButton from "../components/neo/NeoButton";
import NeoCheckbox from "../components/neo/NeoCheckbox";
import NeoRadio from "../components/neo/NeoRadio";
import InlineWarning from "../components/neo/InlineWarning";
import { SkeletonCard, SkeletonTable } from "../components/neo/Skeleton";
import { api, ApiError } from "../api/client";
import { color, font } from "../theme/neobrutalist";
import { EXPORT_COLUMN_GROUPS } from "../types";
import type { ExportColumnGroup, ExportFormat, ExportRecord, JobDetail } from "../types";

const LIVE_STATUSES = new Set(["queued", "running", "paused"]);
const TERMINAL_EXPORT_STATUSES = new Set(["done", "error"]);

const FORMATS: { value: ExportFormat; label: string; hint: string }[] = [
  { value: "csv", label: "CSV", hint: "Universal, opens in Sheets/Excel" },
  { value: "xlsx", label: "XLSX", hint: "Native Excel workbook" },
  { value: "kml", label: "KML", hint: "For Google Earth / Maps" },
];
// JSONL/Google Sheets genuinely have no writer (no app/export/*.py for
// either, nothing in _EXPORT_WRITERS) -- these two stay forward-compat only.
const COMING_SOON: { value: string; label: string; hint: string }[] = [
  { value: "jsonl", label: "JSONL", hint: "One JSON object per line" },
  { value: "sheets", label: "Google Sheets", hint: "Pushes directly to a new sheet" },
];

function formatBytes(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// The backend sends naive datetime.utcnow().isoformat() strings everywhere
// (no "Z"/offset suffix) -- same convention every other screen's timestamps
// already use. `new Date(iso)` treats a suffix-less string as local time, not
// UTC, so on a host whose local zone isn't UTC "just generated" reads back as
// hours off. Appending "Z" here (Export-local fix, not a backend/shared-type
// change) is what makes relative time on this screen actually correct.
function parseUtc(iso: string): Date {
  return new Date(/[Zz]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
}

function relativeTime(iso: string): string {
  const diffMs = Date.now() - parseUtc(iso).getTime();
  const hours = Math.floor(diffMs / 3_600_000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function expiryLabel(record: ExportRecord): string {
  if (!record.expiresAt) return "—";
  if (record.expired) return "expired";
  const days = Math.ceil((parseUtc(record.expiresAt).getTime() - Date.now()) / 86_400_000);
  return days <= 0 ? "expires today" : `in ${days}d`;
}

function ColumnGroupRow({
  group,
  checked,
  onToggle,
}: {
  group: (typeof EXPORT_COLUMN_GROUPS)[number];
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <div style={{ width: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 12.5, color: color.ink, textTransform: "uppercase" }}>
          {group.label}
        </p>
        <NeoCheckbox checked={checked} onChange={onToggle} />
      </div>
      <p style={{ margin: "4px 0 0", fontFamily: font.body, fontSize: 11.5, color: color.ink60 }}>{group.fields}</p>
    </div>
  );
}

function RowScopeOption({
  label,
  count,
  selected,
  disabled,
  onSelect,
}: {
  label: string;
  count: string;
  selected: boolean;
  disabled?: boolean;
  onSelect?: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "8px 10px",
        width: "100%",
        background: disabled ? "transparent" : selected ? color.sand : "transparent",
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 13, color: disabled ? color.ink60 : color.ink }}>
        {label}
      </p>
      <div style={{ flex: 1 }} />
      <p style={{ margin: 0, fontFamily: font.mono, fontSize: 12, color: color.ink60 }}>{count}</p>
      <NeoRadio checked={selected} disabled={disabled} onChange={onSelect} />
    </div>
  );
}

function ExportHistoryTable({
  jobId,
  exports,
  onDeleted,
  onGenerate,
  generating,
}: {
  jobId: string;
  exports: ExportRecord[];
  onDeleted: () => void;
  onGenerate: () => void;
  generating: boolean;
}) {
  const deleteExport = useMutation({
    mutationFn: (id: string) => api.del(`/api/exports/${id}`),
    onSuccess: onDeleted,
  });

  async function handleDownload(record: ExportRecord) {
    if (!record.downloadUrl) return;
    await api.download(record.downloadUrl, `leads-${jobId.slice(0, 8)}.${record.format}`);
  }

  if (exports.length === 0) {
    // Bug fix: the Figma frame ships with body text but no button (spec
    // requires exactly one primary action on every empty state) -- this
    // reuses the same createExport mutation the Generate button above uses,
    // so there is exactly one code path for "start an export", not two.
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: 48 }}>
        <div style={{ transform: "rotate(6deg)" }}>
          <div style={{ width: 64, height: 64, background: color.yellow, border: `3px solid ${color.ink}` }} />
        </div>
        <p style={{ margin: 0, fontFamily: font.head, fontSize: 32, color: color.ink }}>NO EXPORTS YET</p>
        <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 400 }}>
          Generate your first export above — it will show up here with a download link.
        </p>
        <NeoButton variant="primary" loading={generating} onClick={onGenerate}>
          Generate export
        </NeoButton>
      </div>
    );
  }

  const headers = ["FORMAT", "ROWS", "SIZE", "CREATED", "EXPIRES", "ACTIONS"];

  return (
    <>
      <div className="neo-responsive-table" style={{ border: `3px solid ${color.ink}`, background: color.white, width: "100%", maxWidth: 1126, overflowX: "auto" }}>
        <div style={{ display: "flex", background: color.sand, borderBottom: `3px solid ${color.ink}` }}>
          {headers.map((h) => (
            <div key={h} style={{ padding: "0 12px", height: 36, display: "flex", alignItems: "center", minWidth: h === "ACTIONS" ? 180 : 100, flex: h === "ACTIONS" ? 1 : undefined }}>
              <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.315px", color: color.ink }}>{h}</span>
            </div>
          ))}
        </div>
        {exports.map((record, i) => (
          <div
            key={record.id}
            className="neo-row-enter"
            style={{ display: "flex", borderBottom: `3px solid ${color.rule}`, ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms` }}
          >
            <div style={{ padding: "0 12px", height: 40, display: "flex", alignItems: "center", minWidth: 100 }}>
              <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink, textTransform: "uppercase" }}>{record.format}</span>
            </div>
            <div style={{ padding: "0 12px", height: 40, display: "flex", alignItems: "center", minWidth: 100 }}>
              <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink }}>{record.rowCount ?? "—"}</span>
            </div>
            <div style={{ padding: "0 12px", height: 40, display: "flex", alignItems: "center", minWidth: 100 }}>
              <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink }}>{formatBytes(record.sizeBytes)}</span>
            </div>
            <div style={{ padding: "0 12px", height: 40, display: "flex", alignItems: "center", minWidth: 100 }}>
              <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink }}>
                {record.generatedAt ? relativeTime(record.generatedAt) : record.status}
              </span>
            </div>
            <div style={{ padding: "0 12px", height: 40, display: "flex", alignItems: "center", minWidth: 100 }}>
              <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: record.expired ? color.ink60 : color.ink }}>
                {expiryLabel(record)}
              </span>
            </div>
            <div style={{ padding: "0 12px", height: 40, display: "flex", alignItems: "center", gap: 8, minWidth: 180, flex: 1 }}>
              {record.downloadUrl && !record.expired ? (
                <button type="button" onClick={() => handleDownload(record)} style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.blue }}>
                  DOWNLOAD
                </button>
              ) : (
                <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink60 }}>
                  {record.status === "error" ? "FAILED" : record.expired ? "EXPIRED" : record.status.toUpperCase()}
                </span>
              )}
              <span style={{ color: color.ink60 }}>·</span>
              <button
                type="button"
                onClick={() => deleteExport.mutate(record.id)}
                disabled={deleteExport.isPending}
                style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.blue }}
              >
                DELETE
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="neo-responsive-cards">
        {exports.map((record, i) => (
          <div
            key={record.id}
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
              <span style={{ fontFamily: font.mono, fontWeight: 700, fontSize: 14, color: color.ink, textTransform: "uppercase" }}>
                {record.format}
              </span>
              <span style={{ fontFamily: font.body, fontSize: 12, color: record.expired ? color.ink60 : color.ink }}>
                {expiryLabel(record)}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
              <span>{record.rowCount ?? "—"} rows · {formatBytes(record.sizeBytes)}</span>
              <span>{record.generatedAt ? relativeTime(record.generatedAt) : record.status}</span>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", borderTop: `1px solid ${color.rule}`, paddingTop: 8 }}>
              {record.downloadUrl && !record.expired ? (
                <NeoButton variant="primary" size="sm" onClick={() => handleDownload(record)}>
                  Download
                </NeoButton>
              ) : (
                <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink60 }}>
                  {record.status === "error" ? "FAILED" : record.expired ? "EXPIRED" : record.status.toUpperCase()}
                </span>
              )}
              <div style={{ flex: 1 }} />
              <NeoButton
                variant="ghost"
                size="sm"
                onClick={() => deleteExport.mutate(record.id)}
                disabled={deleteExport.isPending}
              >
                Delete
              </NeoButton>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

export default function ExportPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [format, setFormat] = useState<ExportFormat>("csv");
  const [selectedGroups, setSelectedGroups] = useState<Set<ExportColumnGroup>>(
    new Set(["identity", "contact", "location"]),
  );
  const [exportId, setExportId] = useState<string | null>(null);

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.get<JobDetail>(`/api/jobs/${jobId}`),
    enabled: !!jobId,
  });

  const historyQuery = useQuery({
    queryKey: ["exports", jobId],
    queryFn: () => api.get<ExportRecord[]>(`/api/exports/?job_id=${jobId}`),
    enabled: !!jobId,
  });

  const createExport = useMutation({
    mutationFn: () =>
      api.post<ExportRecord>("/api/exports/", {
        job_id: jobId,
        format,
        columns: Array.from(selectedGroups),
      }),
    onSuccess: (record) => {
      setExportId(record.id);
      queryClient.invalidateQueries({ queryKey: ["exports", jobId] });
    },
  });

  const activeExportQuery = useQuery({
    queryKey: ["export", exportId],
    queryFn: () => api.get<ExportRecord>(`/api/exports/${exportId}`),
    enabled: !!exportId,
    refetchInterval: (query) =>
      query.state.data && TERMINAL_EXPORT_STATUSES.has(query.state.data.status) ? false : 1500,
  });

  const activeStatus = activeExportQuery.data?.status;
  useEffect(() => {
    if (activeStatus && TERMINAL_EXPORT_STATUSES.has(activeStatus)) {
      // Terminal reached -- fold it into history; the one-off query above has
      // already stopped polling on its own (refetchInterval returns false).
      queryClient.invalidateQueries({ queryKey: ["exports", jobId] });
    }
  }, [activeStatus, jobId, queryClient]);

  function toggleGroup(group: ExportColumnGroup) {
    setSelectedGroups((current) => {
      const next = new Set(current);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  }

  const job = jobQuery.data;
  const running = job && LIVE_STATUSES.has(job.status);
  const generating = createExport.isPending || (activeExportQuery.data && !TERMINAL_EXPORT_STATUSES.has(activeExportQuery.data.status));

  const header = (
    <div>
      <button
        type="button"
        onClick={() => navigate(`/results/${jobId}`)}
        style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink60, marginBottom: 8 }}
      >
        ← Results
      </button>
      <div className="neo-responsive-header" style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>EXPORT</h1>
        <p style={{ margin: "4px 0 0", fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink60 }}>
          {jobQuery.data?.name ?? (jobId ? `Job #${jobId.slice(0, 8)}` : "—")}
        </p>
      </div>
    </div>
  );

  if (jobQuery.isLoading) {
    return (
      <div style={{ maxWidth: 1126 }}>
        {header}
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 24 }}>
          <div style={{ width: 198 }}><SkeletonCard height={118} /></div>
          <div style={{ width: 198 }}><SkeletonCard height={118} /></div>
          <div style={{ width: 198 }}><SkeletonCard height={118} /></div>
        </div>
        <div className="neo-responsive-row" style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 400 }}><SkeletonCard height={320} /></div>
          <div style={{ flex: 1, minWidth: 400 }}><SkeletonCard height={200} /></div>
        </div>
      </div>
    );
  }

  if (jobQuery.isError || !job) {
    // Cross-cutting #10: this used to discard the whole page shell for a
    // centered message -- keep the header (and the way back to Results)
    // visible, same as the loaded state does, and scope the failure to the
    // content area under it.
    return (
      <div>
        {header}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: "80px 0" }}>
          <div style={{ width: 32, height: 32, background: color.pink, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>EXPORT SETUP FAILED TO LOAD</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
            This job&rsquo;s details could not be fetched.
          </p>
          <p style={{ margin: 0, fontFamily: font.mono, fontSize: 11, color: color.ink60 }}>
            {jobQuery.error instanceof ApiError ? jobQuery.error.message : "ERR_JOB_FETCH_FAILED"}
          </p>
          <NeoButton variant="destructive" onClick={() => jobQuery.refetch()}>
            Retry
          </NeoButton>
        </div>
      </div>
    );
  }

  const totalPlaces = job.targets?.reduce((n, t) => n + t.placesFound, 0) ?? 0;

  return (
    <div>
      {header}

      {running && (
        <div style={{ marginBottom: 24 }}>
          <InlineWarning tone="pink" fontSize={13} fontWeight={500}>
            This job is still running — the export will only cover the {totalPlaces.toLocaleString()} places found so far.
          </InlineWarning>
        </div>
      )}

      <div style={{ marginBottom: 24 }}>
        <p style={{ margin: "0 0 10px", fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>
          FORMAT
        </p>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {FORMATS.map((f) => (
            // A <div role="button">, not a <button> -- NeoRadio inside is its
            // own real <button>, and a button can't nest a button (invalid
            // DOM, React warns and some browsers auto-close the outer one).
            <div
              key={f.value}
              role="button"
              tabIndex={0}
              onClick={() => setFormat(f.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setFormat(f.value);
                }
              }}
              style={{
                width: 198,
                boxSizing: "border-box",
                padding: 14,
                textAlign: "left",
                background: format === f.value ? color.yellow : color.white,
                border: `3px solid ${color.ink}`,
                cursor: "pointer",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink }}>{f.label}</span>
                <NeoRadio checked={format === f.value} onChange={() => setFormat(f.value)} />
              </div>
              <p style={{ margin: 0, fontFamily: font.body, fontSize: 11.5, color: color.ink60 }}>{f.hint}</p>
            </div>
          ))}
          {COMING_SOON.map((f) => (
            <div key={f.value} style={{ width: 198, padding: 14, background: color.white, border: `3px solid ${color.ink}`, opacity: 0.55 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink }}>{f.label}</span>
                <NeoRadio checked={false} disabled />
              </div>
              <p style={{ margin: "0 0 6px", fontFamily: font.body, fontSize: 11.5, color: color.ink60 }}>{f.hint}</p>
              <span style={{ display: "inline-block", background: color.sand, padding: "2px 6px", fontFamily: font.body, fontWeight: 700, fontSize: 9.5, letterSpacing: "0.285px", color: color.ink60 }}>
                COMING SOON
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="neo-responsive-row" style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
        <div style={{ background: color.white, border: `3px solid ${color.ink}`, padding: 16, display: "flex", flexDirection: "column", gap: 10, minWidth: 400, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>COLUMNS</p>
          </div>
          {EXPORT_COLUMN_GROUPS.map((group) => (
            <ColumnGroupRow key={group.key} group={group} checked={selectedGroups.has(group.key)} onToggle={() => toggleGroup(group.key)} />
          ))}
        </div>

        <div style={{ background: color.white, border: `3px solid ${color.ink}`, padding: 16, display: "flex", flexDirection: "column", gap: 10, minWidth: 400, flex: 1 }}>
          <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>ROW SCOPE</p>
          <RowScopeOption label="All rows" count={`${totalPlaces.toLocaleString()} places`} selected onSelect={() => {}} />
          {/* Disabled -- would need grid-side filter/selection state the
              backend has no way to reconstruct. Explained below rather than
              left as a bare disabled row with no reason (SCREENLIST bug:
              "disabled with no explanation why"). */}
          <RowScopeOption label="Current filter" count="not available" selected={false} disabled />
          <RowScopeOption label="Current selection" count="not available" selected={false} disabled />
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 11, color: color.ink60 }}>
            Exports cover every row in this job today. Scoping to a filtered view or a manual selection isn&rsquo;t wired up yet.
          </p>
        </div>
      </div>

      {/* Export accepted (201) but the background job later failed -- distinct
          from createExport.isError below, which only covers the POST itself
          rejecting. Scoped to this one row per cross-cutting #10 (the Figma
          frame keeps header/format/columns/scope/history all visible and
          fails only this one area, not the whole page). */}
      {activeExportQuery.data?.status === "error" && (
        <div style={{ background: color.pink, border: `3px solid ${color.ink}`, padding: "10px 14px", marginBottom: 16, maxWidth: 1126 }}>
          <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink }}>
            EXPORT GENERATION FAILED — your configuration above is unchanged.
          </p>
        </div>
      )}

      <div style={{ marginBottom: 32 }}>
        <NeoButton
          variant="primary"
          loading={!!generating}
          disabled={selectedGroups.size === 0}
          onClick={() => createExport.mutate()}
        >
          {activeExportQuery.data?.status === "error" ? "Retry Export" : "Generate Export"}
        </NeoButton>
        {createExport.isError && (
          <div style={{ margin: "8px 0 0" }}>
            <InlineWarning tone="pink" fontSize={12} fontWeight={700}>
              {createExport.error instanceof ApiError ? createExport.error.message : "Couldn't start the export"}
            </InlineWarning>
          </div>
        )}
      </div>

      <div>
        <p style={{ margin: "0 0 10px", fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>
          EXPORT HISTORY
        </p>
        {historyQuery.isLoading && (
          <div style={{ maxWidth: 1126 }}>
            <SkeletonTable rows={2} columns={6} />
          </div>
        )}
        {historyQuery.isError && (
          <InlineWarning tone="pink" fontSize={12} fontWeight={700}>
            {historyQuery.error instanceof ApiError ? historyQuery.error.message : "Couldn't load export history"}
          </InlineWarning>
        )}
        {historyQuery.data && jobId && (
          <ExportHistoryTable
            jobId={jobId}
            exports={historyQuery.data}
            onDeleted={() => queryClient.invalidateQueries({ queryKey: ["exports", jobId] })}
            onGenerate={() => createExport.mutate()}
            generating={!!generating}
          />
        )}
      </div>

      <button
        type="button"
        onClick={() => navigate(`/results/${jobId}`)}
        style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, marginTop: 24, fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink60 }}
      >
        ← Results
      </button>
    </div>
  );
}
