// Pause / resume / cancel / delete for one job, used by the results header.
// Neobrutalist rebuild -- replaces the legacy MUI (Dialog/Snackbar/Alert/
// IconButton) with NeoButton plus a flat-ink-scrim confirm dialog matching
// LeadDetailDrawer's own DrawerShell scrim convention, and a plain toast
// styled like the rest of this page's inline error banners.
//
// Which buttons are offered comes from the job's own `actions` block rather than
// from a status check written here — the API sends it, and the endpoints
// validate against the same predicates, so the UI can't offer a control that
// would come back 409 (backend: app/workers/control.py).
//
// The two destructive ones ask first. Cancel is destructive because the areas it
// retires are not resumable; delete because the results go with it. Pause and
// resume are cheap and reversible, so they fire straight away.

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import NeoButton from "./neo/NeoButton";
import { api } from "../api/client";
import { color, font, shadow, scrim } from "../theme/neobrutalist";
import type { Job, JobControlResponse, JobDeleteResponse } from "../types";

type Action = "pause" | "resume" | "cancel" | "delete";

// Shown in the confirmation dialog. Both of these are one-way: a cancelled area
// is not resumable, and a deleted job takes its results with it — so the copy
// says what is lost rather than asking "are you sure?".
const CONFIRM: Record<"cancel" | "delete", { title: string; body: string; verb: string }> = {
  cancel: {
    title: "Cancel this job?",
    body:
      "Areas that have not finished are dropped and cannot be resumed — a cancelled job has to be started again from scratch. The leads already collected are kept, and can still be viewed and exported.",
    verb: "Cancel job",
  },
  delete: {
    title: "Delete this job?",
    body:
      "The job, its search areas, every lead it collected and any exports generated from it are removed for good. If it is still running it will be stopped first. This cannot be undone.",
    verb: "Delete",
  },
};

interface Props {
  job: Job;
  /** Called once the job is gone — the row or page showing it no longer has one. */
  onDeleted?: () => void;
  /** Icon-only, for a table row. Labelled buttons otherwise. */
  dense?: boolean;
}

function ConfirmDialog({
  kind,
  busy,
  onConfirm,
  onCancel,
}: {
  kind: "cancel" | "delete";
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const spec = CONFIRM[kind];
  return (
    <>
      {/* Flat 70% ink per spec — same convention as LeadDetailDrawer's scrim. */}
      <div onClick={onCancel} style={{ position: "fixed", inset: 0, background: scrim, zIndex: 1000 }} />
      <div
        role="alertdialog"
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: 420,
          maxWidth: "calc(100vw - 32px)",
          background: color.white,
          border: `3px solid ${color.ink}`,
          boxShadow: shadow.md,
          zIndex: 1001,
          padding: 20,
        }}
      >
        <p style={{ margin: 0, fontFamily: font.head, fontSize: 16, color: color.ink }}>{spec.title.toUpperCase()}</p>
        <p style={{ margin: "12px 0 20px", fontFamily: font.body, fontSize: 13, color: color.ink60, lineHeight: 1.5 }}>{spec.body}</p>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <NeoButton variant="ghost" size="sm" disabled={busy} onClick={onCancel}>
            Keep it
          </NeoButton>
          <NeoButton variant="destructive" size="sm" loading={busy} onClick={onConfirm}>
            {spec.verb}
          </NeoButton>
        </div>
      </div>
    </>
  );
}

function Toast({ text, error, onClose }: { text: string; error?: boolean; onClose: () => void }) {
  useEffect(() => {
    const t = setTimeout(onClose, 6000);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div
      style={{
        position: "fixed",
        bottom: 24,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 1002,
        background: error ? color.pink : color.green,
        border: `3px solid ${color.ink}`,
        boxShadow: shadow.sm,
        padding: "12px 16px",
        display: "flex",
        alignItems: "center",
        gap: 12,
        maxWidth: "calc(100vw - 32px)",
      }}
    >
      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink }}>{text}</p>
      <button
        type="button"
        onClick={onClose}
        style={{ border: "none", background: "transparent", cursor: "pointer", fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink, padding: 0 }}
      >
        ✕
      </button>
    </div>
  );
}

export default function JobControls({ job, onDeleted, dense = false }: Props) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState<"cancel" | "delete" | null>(null);
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null);

  const run = useMutation({
    mutationFn: async (action: Action) => {
      if (action === "delete") {
        return { action, body: await api.del<JobDeleteResponse>(`/api/jobs/${job.id}`) } as const;
      }
      const body = await api.post<JobControlResponse>(`/api/jobs/${job.id}/${action}`);
      return { action, body } as const;
    },
    onSuccess: ({ action, body }) => {
      setConfirming(null);
      setNotice({ text: describe(action, body) });
      if (action === "delete") {
        // The detail query would 404 from here on; drop it rather than refetch.
        queryClient.removeQueries({ queryKey: ["job", job.id] });
        queryClient.invalidateQueries({ queryKey: ["jobs"] });
        onDeleted?.();
        return;
      }
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["job", job.id] });
      // The controls hand slots between jobs, so the queue counts on the
      // Settings page are stale the moment any of them lands.
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (error: Error) => setNotice({ text: error.message, error: true }),
  });

  const busy = run.isPending;
  const actions = job.actions;

  // Pause and resume are the same slot: a job is only ever offered one of them.
  const toggle = actions.resume
    ? { action: "resume" as const, label: "Resume", hint: "Put this job back in the queue" }
    : { action: "pause" as const, label: "Pause", hint: "Stop starting new areas — areas already scraping finish" };
  const showToggle = actions.pause || actions.resume;

  const size = dense ? "sm" : "md";

  return (
    <>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {showToggle && (
          <NeoButton variant="secondary" size={size} disabled={busy} onClick={() => run.mutate(toggle.action)}>
            {toggle.label}
          </NeoButton>
        )}
        {actions.cancel && (
          <NeoButton variant="secondary" size={size} disabled={busy} onClick={() => setConfirming("cancel")}>
            Cancel
          </NeoButton>
        )}
        {actions.delete && (
          <NeoButton variant="destructive" size={size} disabled={busy} onClick={() => setConfirming("delete")}>
            Delete
          </NeoButton>
        )}
      </div>

      {confirming && (
        <ConfirmDialog
          kind={confirming}
          busy={busy}
          onConfirm={() => run.mutate(confirming)}
          onCancel={() => setConfirming(null)}
        />
      )}

      {notice && <Toast text={notice.text} error={notice.error} onClose={() => setNotice(null)} />}
    </>
  );
}

/**
 * What actually happened, from the summary the endpoint returns.
 *
 * Pause is the one that needs saying out loud: it stops new areas but lets the
 * ones already open finish, so results keep arriving for a while afterwards.
 * Reported as a bare "Paused" that reads as a bug.
 */
function describe(action: Action, body: JobControlResponse | JobDeleteResponse): string {
  if (action === "delete") {
    const { results, targets } = (body as JobDeleteResponse).deleted;
    return `Job deleted — ${results} lead${results === 1 ? "" : "s"} and ${targets} area${targets === 1 ? "" : "s"} removed.`;
  }

  const control = body as JobControlResponse;
  if (action === "pause") {
    const running = control.paused?.stillRunning ?? 0;
    return running
      ? `Paused — no new areas will start; ${running} already scraping will finish.`
      : "Paused — nothing is running, no new areas will start.";
  }
  if (action === "resume") {
    const started = control.resumed?.dispatched ?? 0;
    return started ? `Resumed — ${started} area(s) started.` : "Resumed — waiting for a free slot.";
  }
  const dropped = control.cancelled?.targetsCancelled ?? 0;
  return `Cancelled — ${dropped} unfinished area${dropped === 1 ? "" : "s"} dropped. Leads already collected are kept.`;
}
