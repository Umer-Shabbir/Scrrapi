// Job Templates screen (Figma [SCREEN] templates). Saved job definitions --
// keywords, areas, source -- ready to run again without re-filling the wizard.
//
// Backend: GET/POST /api/templates, PATCH/DELETE /api/templates/{id},
// POST /api/templates/{id}/{run,duplicate} (backend/app/api/routers/templates.py).
// "Attach schedule" stays disabled -- Schedules is a separate, unbuilt screen.

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import NeoButton from "../components/neo/NeoButton";
import InlineWarning from "../components/neo/InlineWarning";
import { color, font } from "../theme/neobrutalist";
import type { JobTemplate } from "../types";

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diffMs / 86_400_000);
  if (days < 1) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

function TemplateCard({
  template,
  onRun,
  onDuplicate,
  onDelete,
  running,
  className,
  style,
}: {
  template: JobTemplate;
  onRun: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  running: boolean;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={className}
      style={{
        background: color.white,
        border: `3px solid ${color.ink}`,
        boxShadow: "6px 6px 0px 0px #111",
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 12,
        width: 354,
        boxSizing: "border-box",
        ...style,
      }}
    >
      <div>
        <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 15, color: color.ink }}>{template.name}</p>
        <p style={{ margin: "4px 0 0", fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
          {template.source === "bing" ? "Bing Maps" : "Google Maps"}
        </p>
      </div>
      <div style={{ borderTop: `2px solid ${color.rule}` }} />
      <div style={{ display: "flex", gap: 24 }}>
        <Stat label="Keywords" value={template.keywordCount} />
        <Stat label="Areas" value={template.areaCount} />
        <Stat label="Targets" value={template.targetCount} />
      </div>
      <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
        {template.lastRunAt ? `Last run: ${timeAgo(template.lastRunAt)}` : "Never run"}
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        <NeoButton variant="primary" size="sm" onClick={onRun} loading={running}>
          Run now
        </NeoButton>
        <NeoButton variant="ghost" size="sm" onClick={onDuplicate}>
          Duplicate
        </NeoButton>
        <NeoButton variant="ghost" size="sm" disabled>
          Attach schedule
        </NeoButton>
        <div style={{ flex: 1 }} />
        <NeoButton variant="destructive" size="sm" onClick={onDelete}>
          Delete
        </NeoButton>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 10, color: color.ink60 }}>{label.toUpperCase()}</p>
      <p style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>{value}</p>
    </div>
  );
}

function DeleteConfirmModal({ template, onCancel, onConfirm, pending }: { template: JobTemplate; onCancel: () => void; onConfirm: () => void; pending: boolean }) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(17,17,17,0.7)", display: "grid", placeItems: "center", zIndex: 1000 }}>
      <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: "10px 10px 0px 0px #111", width: 440 }}>
        <div style={{ borderBottom: `3px solid ${color.ink}`, background: color.pink, color: color.white, padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", textTransform: "uppercase" }}>Delete template</span>
          <button type="button" onClick={onCancel} style={{ border: "none", background: "transparent", color: color.white, cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>
        <div style={{ padding: 20 }}>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink }}>
            This permanently deletes &ldquo;{template.name}&rdquo;. Jobs already run from it are unaffected. This cannot be undone.
          </p>
        </div>
        <div style={{ padding: "16px 20px", display: "flex", justifyContent: "flex-end", gap: 12 }}>
          <NeoButton variant="secondary" onClick={onCancel} disabled={pending}>
            Cancel
          </NeoButton>
          <NeoButton variant="destructive" onClick={onConfirm} loading={pending}>
            Delete template
          </NeoButton>
        </div>
      </div>
    </div>
  );
}

export default function Templates() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<JobTemplate | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);

  const templatesQuery = useQuery({
    queryKey: ["templates"],
    queryFn: () => api.get<JobTemplate[]>("/api/templates/"),
  });

  const runTemplate = useMutation({
    mutationFn: (id: string) => api.post<{ id: string }>(`/api/templates/${id}/run`),
    onMutate: (id) => setRunningId(id),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      navigate(`/results/${job.id}`);
    },
    onSettled: () => setRunningId(null),
  });

  const duplicateTemplate = useMutation({
    mutationFn: (id: string) => api.post(`/api/templates/${id}/duplicate`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["templates"] }),
  });

  const deleteTemplate = useMutation({
    mutationFn: (id: string) => api.del(`/api/templates/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      setDeleteTarget(null);
    },
  });

  return (
    <div>
      <div className="neo-responsive-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>TEMPLATES</h1>
          <p style={{ margin: "6px 0 0", fontFamily: font.body, fontSize: 13, color: color.ink60, maxWidth: 720 }}>
            Saved job definitions — keywords, areas, and source, ready to run again.
          </p>
        </div>
        <NeoButton variant="primary" onClick={() => navigate("/jobs/new")}>
          + New template
        </NeoButton>
      </div>

      {templatesQuery.isLoading && (
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
          {[0, 1, 2].map((i) => (
            <div key={i} className="neo-skeleton" style={{ width: 354, height: 264, border: `3px solid ${color.rule}` }} />
          ))}
        </div>
      )}

      {templatesQuery.isError && (
        <div style={{ background: color.white, border: `3px solid ${color.ink}`, borderLeft: `6px solid ${color.pink}`, padding: 16, display: "flex", flexDirection: "column", gap: 8, maxWidth: 500 }}>
          <InlineWarning tone="ink" fontSize={13} fontWeight={700}>Couldn&rsquo;t load templates</InlineWarning>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink }}>
            {templatesQuery.error instanceof ApiError ? templatesQuery.error.message : "Couldn't reach the API server"}
          </p>
          <div>
            <NeoButton variant="destructive" size="sm" onClick={() => templatesQuery.refetch()}>
              Retry
            </NeoButton>
          </div>
        </div>
      )}

      {templatesQuery.data && templatesQuery.data.length === 0 && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: 48 }}>
          <div style={{ transform: "rotate(6deg)" }}>
            <div style={{ width: 64, height: 64, background: color.yellow, border: `3px solid ${color.ink}` }} />
          </div>
          <p style={{ margin: 0, fontFamily: font.head, fontSize: 32, color: color.ink, textAlign: "center" }}>NO TEMPLATES YET</p>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 400 }}>
            Save a job as a template from the New Job Wizard&rsquo;s review step, or build one now.
          </p>
          <NeoButton variant="primary" onClick={() => navigate("/jobs/new")}>
            New template
          </NeoButton>
        </div>
      )}

      {templatesQuery.data && templatesQuery.data.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 20 }}>
          {templatesQuery.data.map((t, i) => (
            <TemplateCard
              key={t.id}
              template={t}
              running={runningId === t.id}
              onRun={() => runTemplate.mutate(t.id)}
              onDuplicate={() => duplicateTemplate.mutate(t.id)}
              onDelete={() => setDeleteTarget(t)}
              className="neo-row-enter"
              style={{ ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms` } as React.CSSProperties}
            />
          ))}
        </div>
      )}

      {deleteTarget && (
        <DeleteConfirmModal
          template={deleteTarget}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => deleteTemplate.mutate(deleteTarget.id)}
          pending={deleteTemplate.isPending}
        />
      )}
    </div>
  );
}
