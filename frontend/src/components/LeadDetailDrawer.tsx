// Feedback/Drawer instance for the Lead Detail screen (Figma nodes 125:4159 /
// 344:380, drawer-over-Results; also reachable standalone at
// /results/:jobId/lead/:leadId -- see pages/LeadDetail.tsx). Right-aligned,
// never stacked on the results grid underneath it -- the scrim is what keeps
// the page from reading as broken while the drawer is open.
//
// Blocks, top to bottom, per the Figma content slot: Identity (score dial +
// reason breakdown + claimed/open badge), Contact, Web, Location, Provenance,
// History, then the actions row (COPY VCARD / SUPPRESS / TAG / PUSH TO CRM).
// Empty/loading/error are the orphaned Foundations frames (255:442, 256:549,
// 257:654) -- treated as canonical per docs/FIGMA-MCP-PROTOCOL.md's note on
// cross-cutting issue #11, just mis-filed on the wrong page.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import NeoButton from "./neo/NeoButton";
import { api, ApiError } from "../api/client";
import { color, font, shadow, scrim, mq } from "../theme/neobrutalist";
import { useMediaQuery } from "../hooks/useMediaQuery";
import type { LeadDetail, LeadStatus } from "../types";

interface Props {
  jobId: string;
  leadId: string;
  onClose: () => void;
}

const DRAWER_WIDTH = 480;

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ width: "100%" }}>
      <p style={{ margin: "0 0 12px", fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink, textTransform: "uppercase" }}>
        {label}
      </p>
      {children}
    </div>
  );
}

function Rule() {
  return <div style={{ width: "100%", height: 3, background: color.ink }} />;
}

/** Score Dial: a ring rendered from the score fraction, ink border per spec
 * (bug fix: the Figma instance shipped with no border around the ring). */
function ScoreDial({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div
      style={{
        width: 72,
        height: 72,
        borderRadius: "50%",
        border: `3px solid ${color.ink}`,
        display: "grid",
        placeItems: "center",
        background: `conic-gradient(${color.green} ${pct * 3.6}deg, ${color.sand} 0deg)`,
        flexShrink: 0,
      }}
    >
      <div style={{ width: 56, height: 56, borderRadius: "50%", background: color.white, display: "grid", placeItems: "center" }}>
        <span style={{ fontFamily: font.head, fontSize: 22, color: color.ink }}>{Math.round(pct)}</span>
      </div>
    </div>
  );
}

/** Status/Badge, lead-specific fills (claimed=blue, open=sand, closed=ink-60
 * on sand). Glyph prefix per cross-cutting #7 (badges were missing theirs). */
function LeadStatusBadge({ status: leadStatus }: { status: LeadStatus }) {
  const FILL: Record<LeadStatus, string> = { claimed: color.blue, open: color.sand, closed: color.sand };
  const GLYPH: Record<LeadStatus, string> = { claimed: "✓", open: "●", closed: "✕" };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: 22,
        padding: "0 10px",
        border: `2px solid ${color.ink}`,
        background: FILL[leadStatus],
        fontFamily: font.body,
        fontWeight: 500,
        fontSize: 10,
        color: color.ink,
        textTransform: "uppercase",
      }}
    >
      {GLYPH[leadStatus]} {leadStatus}
    </span>
  );
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard?.writeText(value).catch(() => {});
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 500, fontSize: 11, color: color.blue }}
    >
      {copied ? "COPIED" : "COPY"}
    </button>
  );
}

function ContactRow({ value, meta, onCopy }: { value: string; meta: string; onCopy: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "7px 11px", border: `1px solid ${color.rule}`, background: color.white }}>
      <div>
        <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink }}>{value}</p>
        <p style={{ margin: "4px 0 0", fontFamily: font.body, fontSize: 11, color: color.ink60 }}>{meta}</p>
      </div>
      <CopyButton value={onCopy} />
    </div>
  );
}

function IdentityBlock({ lead }: { lead: LeadDetail }) {
  return (
    <div style={{ width: "100%" }}>
      <p style={{ margin: "0 0 24px", fontFamily: font.body, fontWeight: 500, fontSize: 11, color: color.ink60, textTransform: "uppercase" }}>
        {lead.category ?? "Uncategorized"}
      </p>
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <ScoreDial value={lead.score.value} />
        <p style={{ margin: "6px 0 0", fontFamily: "Inter, sans-serif", fontSize: 11, color: color.ink60, flex: 1 }}>
          {lead.score.reasons.length > 0
            ? `Score reasons: ${lead.score.reasons.join(", ")}`
            : "No score signals found yet — no phone, email, website, rating, or social profile on this lead."}
        </p>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
        <LeadStatusBadge status={lead.status} />
        {lead.decisionMaker && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              height: 22,
              padding: "0 10px",
              border: `2px solid ${color.ink}`,
              background: color.yellow,
              fontFamily: font.body,
              fontWeight: 700,
              fontSize: 10,
              color: color.ink,
              textTransform: "uppercase",
            }}
          >
            👤 {lead.decisionMaker}
          </span>
        )}
      </div>
    </div>
  );
}

function ContactBlock({ lead }: { lead: LeadDetail }) {
  const phones = lead.phone ? lead.phone.split(",").map((p) => p.trim()).filter(Boolean) : [];
  const mobiles = lead.mobilePhone ? lead.mobilePhone.split(",").map((p) => p.trim()).filter(Boolean) : [];
  const emails = lead.email ? lead.email.split(",").map((p) => p.trim()).filter(Boolean) : [];
  if (phones.length === 0 && mobiles.length === 0 && emails.length === 0) {
    return (
      <Section label="Contact">
        <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>No phone or email found.</p>
      </Section>
    );
  }
  return (
    <Section label="Contact">
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {mobiles.map((mobile) => (
          <ContactRow
            key={`mobile-${mobile}`}
            value={mobile}
            meta="Direct Mobile / Personal Line"
            onCopy={mobile}
          />
        ))}
        {phones.map((phone) => (
          <ContactRow
            key={`phone-${phone}`}
            value={phone}
            meta={lead.phoneSource ? `Found via ${lead.phoneSource}` : "Store / Main Line"}
            onCopy={phone}
          />
        ))}
        {emails.map((email) => (
          <ContactRow
            key={`email-${email}`}
            value={email}
            meta={lead.emailSource ? `Found via ${lead.emailSource}` : "Source unknown"}
            onCopy={email}
          />
        ))}
      </div>
    </Section>
  );
}

function WebBlock({ lead }: { lead: LeadDetail }) {
  if (!lead.website) {
    return (
      <Section label="Web">
        <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>No website found.</p>
      </Section>
    );
  }
  const host = (() => {
    try {
      return new URL(/^https?:\/\//i.test(lead.website!) ? lead.website! : `https://${lead.website}`).host.replace(/^www\./, "");
    } catch {
      return lead.website;
    }
  })();
  return (
    <Section label="Web">
      <a
        href={/^https?:\/\//i.test(lead.website) ? lead.website : `https://${lead.website}`}
        target="_blank"
        rel="noreferrer noopener"
        style={{ fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.blue, textDecoration: "none" }}
      >
        {host}
      </a>
      {lead.techStack.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 12 }}>
          {lead.techStack.map((tech) => (
            <span key={tech} style={{ border: `1px solid ${color.ink}`, background: color.sand, padding: "3px 8px", fontFamily: font.body, fontWeight: 500, fontSize: 9, color: color.ink, textTransform: "uppercase" }}>
              {tech}
            </span>
          ))}
        </div>
      )}
    </Section>
  );
}

function ReviewsAndSentimentBlock({ lead }: { lead: LeadDetail }) {
  if (lead.rating == null && lead.reviewsCount == null && !lead.sentimentLabel && !lead.painPoints) {
    return null;
  }

  const sentimentColor =
    lead.sentimentLabel === "Positive"
      ? color.green
      : lead.sentimentLabel === "Negative"
      ? color.pink
      : lead.sentimentLabel === "Mixed"
      ? color.yellow
      : color.sand;

  const painPointsList = lead.painPoints
    ? lead.painPoints.split(",").map((p) => p.trim()).filter(Boolean)
    : [];

  return (
    <Section label="Reviews & Customer Sentiment">
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        {lead.rating != null && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "4px 8px",
              border: `2px solid ${color.ink}`,
              background: color.sand,
              fontFamily: font.body,
              fontWeight: 700,
              fontSize: 12,
              color: color.ink,
            }}
          >
            ★ {lead.rating.toFixed(1)}
            {lead.reviewsCount != null && (
              <span style={{ fontWeight: 400, color: color.ink60, marginLeft: 2 }}>
                ({lead.reviewsCount} reviews)
              </span>
            )}
          </span>
        )}
        {lead.sentimentLabel && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              height: 24,
              padding: "0 10px",
              border: `2px solid ${color.ink}`,
              background: sentimentColor,
              fontFamily: font.body,
              fontWeight: 700,
              fontSize: 11,
              color: color.ink,
              textTransform: "uppercase",
            }}
          >
            {lead.sentimentLabel === "Positive" ? "✓" : lead.sentimentLabel === "Negative" ? "✕" : "●"}{" "}
            {lead.sentimentLabel} Sentiment
            {lead.sentimentScore != null && ` (${Math.round(lead.sentimentScore * 100)}%)`}
          </span>
        )}
      </div>

      {painPointsList.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <p style={{ margin: "0 0 6px", fontFamily: font.body, fontWeight: 700, fontSize: 11, color: color.pink, textTransform: "uppercase" }}>
            ⚠️ Extracted Customer Pain Points:
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {painPointsList.map((point) => (
              <div
                key={point}
                style={{
                  padding: "6px 10px",
                  border: `1px solid ${color.pink}`,
                  background: color.white,
                  fontFamily: font.body,
                  fontSize: 12,
                  color: color.ink,
                  borderLeft: `4px solid ${color.pink}`,
                }}
              >
                {point}
              </div>
            ))}
          </div>
        </div>
      )}
    </Section>
  );
}

function LocationBlock({ lead }: { lead: LeadDetail }) {
  const addressLine = [lead.address, [lead.city, lead.state].filter(Boolean).join(", "), lead.zipCode].filter(Boolean).join(", ");
  return (
    <Section label="Location">
      <p style={{ margin: "0 0 4px", fontFamily: font.body, fontSize: 13, color: color.ink }}>{addressLine || "No address on file."}</p>
      {lead.latitude != null && lead.longitude != null && (
        <p style={{ margin: 0, fontFamily: font.body, fontSize: 11, color: color.ink60 }}>
          {lead.latitude.toFixed(4)}° N, {Math.abs(lead.longitude).toFixed(4)}° {lead.longitude < 0 ? "W" : "E"}
        </p>
      )}
      {lead.latitude != null && lead.longitude != null && (
        <div style={{ marginTop: 12, height: 110, background: color.sand, border: `2px solid ${color.ink}`, display: "grid", placeItems: "center" }}>
          <div style={{ width: 14, height: 14, background: color.ink, transform: "rotate(45deg)" }} />
        </div>
      )}
    </Section>
  );
}

function ProvenanceBlock({ lead }: { lead: LeadDetail }) {
  return (
    <Section label="Provenance">
      <p style={{ margin: "0 0 4px", fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
        Job #{lead.jobId.slice(0, 8)}
      </p>
      <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
        Last scraped: {new Date(lead.scrapedAt).toLocaleString()}
      </p>
    </Section>
  );
}

function HistoryBlock({ lead }: { lead: LeadDetail }) {
  if (lead.history.length === 0) {
    return (
      <Section label="History">
        <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
          No changes recorded — this is the first time this business was scraped.
        </p>
      </Section>
    );
  }
  return (
    <Section label="History">
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {lead.history.map((entry, i) => (
          <div key={i} style={{ display: "flex", gap: 12 }}>
            <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink, width: 50, flexShrink: 0 }}>
              {new Date(entry.changedAt).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
            </span>
            <span style={{ fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
              {entry.field} changed — {entry.oldValue ?? "—"} → {entry.newValue ?? "—"}
            </span>
          </div>
        ))}
      </div>
    </Section>
  );
}

function DrawerShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  // Full-width below mobile instead of a fixed 480px panel -- at anything
  // under ~500px viewport the fixed width either overflowed the screen or
  // left a sliver of scrim showing on one edge, and every content block
  // inside already reflows to 100% (see Section/Rule/SkeletonBlock above).
  const isMobile = useMediaQuery(mq.mobile);
  return (
    <>
      {/* Flat 70% ink per spec (cross-cutting #8) -- the Figma frame ships a
          ~35% wash here, same bug as templates' delete-confirm/settings'
          purge-confirm/onboarding's 6 frames. */}
      <div
        onClick={onClose}
        style={{ position: "fixed", inset: 0, background: scrim, zIndex: 1000 }}
      />
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: isMobile ? "100%" : DRAWER_WIDTH,
          background: color.white,
          borderLeft: isMobile ? "none" : `3px solid ${color.ink}`,
          boxShadow: isMobile ? "none" : shadow.lg,
          zIndex: 1001,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{ borderBottom: `3px solid ${color.ink}`, background: color.ink, color: color.white, padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", textTransform: "uppercase" }}>{title}</span>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", color: color.white, cursor: "pointer", fontSize: 14, padding: 0 }}>✕</button>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 8 }}>
          {children}
        </div>
      </div>
    </>
  );
}

function SkeletonBlock({ height }: { height: number }) {
  return <div className="neo-skeleton" style={{ width: "100%", height }} />;
}

export default function LeadDetailDrawer({ jobId, leadId, onClose }: Props) {
  const queryClient = useQueryClient();

  const leadQuery = useQuery({
    queryKey: ["lead", jobId, leadId],
    queryFn: () => api.get<LeadDetail>(`/api/jobs/${jobId}/results/${leadId}`),
  });

  const updateLead = useMutation({
    mutationFn: (body: { status?: LeadStatus; tags?: string[]; suppressed?: boolean }) =>
      api.patch<LeadDetail>(`/api/jobs/${jobId}/results/${leadId}`, body),
    onSuccess: (lead) => queryClient.setQueryData(["lead", jobId, leadId], lead),
  });

  const lead = leadQuery.data;
  const title = lead?.name ?? "Lead";

  if (leadQuery.isLoading) {
    return (
      <DrawerShell title={title} onClose={onClose}>
        <SkeletonBlock height={140} />
        <Rule />
        <SkeletonBlock height={146} />
        <Rule />
        <SkeletonBlock height={90} />
        <Rule />
        <SkeletonBlock height={190} />
        <Rule />
        <SkeletonBlock height={90} />
        <Rule />
        <SkeletonBlock height={72} />
      </DrawerShell>
    );
  }

  if (leadQuery.isError || !lead) {
    return (
      <DrawerShell title={title} onClose={onClose}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: "40px 0" }}>
          <div style={{ width: 32, height: 32, background: color.pink, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <p style={{ margin: 0, fontFamily: font.head, fontSize: 16, color: color.ink, textAlign: "center" }}>
            LEAD DETAILS FAILED TO LOAD
          </p>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60, textAlign: "center" }}>
            {leadQuery.error instanceof ApiError
              ? leadQuery.error.message
              : "This lead's full record could not be fetched."}
          </p>
          {/* Stable code to quote in a bug report -- the human cause above
              already carries the specific reason (404 vs offline vs 500). */}
          <p style={{ margin: 0, fontFamily: font.mono, fontSize: 11, color: color.ink60 }}>
            ERR_LEAD_FETCH_FAILED
          </p>
          <NeoButton variant="destructive" onClick={() => leadQuery.refetch()}>
            Retry
          </NeoButton>
        </div>
      </DrawerShell>
    );
  }

  return (
    <DrawerShell title={title} onClose={onClose}>
      <IdentityBlock lead={lead} />
      <Rule />
      <ContactBlock lead={lead} />
      <Rule />
      <WebBlock lead={lead} />
      <Rule />
      <LocationBlock lead={lead} />
      <Rule />
      <ReviewsAndSentimentBlock lead={lead} />
      <Rule />
      <ProvenanceBlock lead={lead} />
      <Rule />
      <HistoryBlock lead={lead} />

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: "auto", paddingTop: 8, justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <NeoButton
            variant="destructive"
            size="sm"
            loading={updateLead.isPending}
            onClick={() => updateLead.mutate({ suppressed: !lead.suppressed })}
          >
            {lead.suppressed ? "Unsuppress" : "Suppress"}
          </NeoButton>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <NeoButton variant="ghost" size="sm" onClick={() => {
            const vcard = [
              "BEGIN:VCARD",
              "VERSION:3.0",
              `FN:${lead.name ?? ""}`,
              lead.phone ? `TEL:${lead.phone.split(",")[0].trim()}` : "",
              lead.email ? `EMAIL:${lead.email.split(",")[0].trim()}` : "",
              lead.website ? `URL:${lead.website}` : "",
              "END:VCARD",
            ].filter(Boolean).join("\n");
            const blob = new Blob([vcard], { type: "text/vcard" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = `${lead.name ?? "lead"}.vcf`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
          }}>
            Copy vCard
          </NeoButton>
          <NeoButton
            variant="ghost"
            size="sm"
            onClick={() => {
              const next = window.prompt("Tags (comma-separated)", lead.tags.join(", "));
              if (next === null) return;
              updateLead.mutate({ tags: next.split(",").map((t) => t.trim()).filter(Boolean) });
            }}
          >
            Tag
          </NeoButton>
          <NeoButton
            variant="primary"
            size="sm"
            onClick={async () => {
              const crm = window.prompt("Push to which CRM? (hubspot, gohighlevel, pipedrive)", "hubspot");
              if (!crm) return;
              try {
                const res: any = await api.post(`/api/integrations/${crm}/sync`, { lead });
                window.alert(`Push successful:\n${JSON.stringify(res.syncResult || res)}`);
              } catch (err: any) {
                window.alert(`Push failed:\n${err.message || err.toString()}`);
              }
            }}
          >
            Push to CRM
          </NeoButton>
        </div>
      </div>
    </DrawerShell>
  );
}
