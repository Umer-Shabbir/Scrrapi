// Account & Billing screen (Figma [SCREEN] account, SCREENLIST.md §21).
// Backend: GET /api/auth/account (quota + usage history), reuses the same
// license/user data the TopBar already holds via useAuth() — see below for
// why, rather than the previous version's independent license fetch.
//
// SCREENLIST.md's "Critical" bug: the TopBar license chip and this page's
// License panel could show contradictory states because each ran its own
// separate `/api/auth/license` query. Fixed by having this page read
// `useAuth()`'s license (the same object instance the TopBar renders from)
// instead of a second independent query — the two can no longer disagree,
// because there is only ever one fetch now.
//
// QUOTA and USAGE HISTORY are new this cycle — no prior endpoint computed
// either (see backend/app/api/routers/auth.py's read_account docstring).
// The quota ceiling comes from a small plan→limit catalog
// (backend/app/core/plans.py) since `License.plan` is a free-text string
// with no numeric ceiling of its own. Usage history shows real per-month
// counts for whichever months actually have data — not padded to 12 bars,
// since this app's own DB has no organic history before its first job.

import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import NeoButton from "../components/neo/NeoButton";
import { color, font } from "../theme/neobrutalist";
import type { AccountResponse } from "../types";

function Panel({ title, badge, children, width }: { title: string; badge?: React.ReactNode; children: React.ReactNode; width?: number }) {
  return (
    <div style={{ background: color.white, border: `3px solid ${color.ink}`, padding: 16, display: "flex", flexDirection: "column", gap: 10, width, boxSizing: "border-box" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>{title}</span>
        <div style={{ flex: 1 }} />
        {badge}
      </div>
      {children}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink60 }}>{label}</span>
      <div style={{ flex: 1 }} />
      <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink }}>{children}</span>
    </div>
  );
}

function Badge({ label, tone }: { label: string; tone: "green" | "pink" }) {
  return (
    <span
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        height: 22, padding: "0 8px", border: `2px solid ${color.ink}`,
        background: tone === "green" ? color.green : color.pink,
        fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.42px",
        textTransform: "uppercase", color: color.ink, whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}

function Meter({ label, value, limit, warning }: { label: string; value: number; limit: number; warning?: boolean }) {
  const pct = limit > 0 ? Math.min(100, (value / limit) * 100) : 0;
  const fill = warning ? color.yellow : pct > 90 ? color.pink : pct > 75 ? color.yellow : color.green;
  return (
    <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", alignItems: "center" }}>
        <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 11, letterSpacing: "0.22px", color: color.ink }}>{label}</span>
        <div style={{ flex: 1 }} />
        <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink }}>
          {value.toLocaleString()} / {limit.toLocaleString()}
        </span>
      </div>
      <div style={{ height: 16, border: `3px solid ${color.ink}`, background: color.sand, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: fill }} />
      </div>
    </div>
  );
}

function UsageChart({ history }: { history: AccountResponse["usageHistory"] }) {
  if (history.length === 0) {
    return (
      <div style={{ padding: "24px 0", textAlign: "center" }}>
        <span style={{ fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
          No usage yet — bars appear once a job has scraped at least one place.
        </span>
      </div>
    );
  }
  const max = Math.max(...history.map((h) => h.places), 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 8, height: 140, alignItems: "flex-end" }}>
        {history.map((h) => (
          <div key={h.month} style={{ flex: 1, minWidth: 0, height: "100%", display: "flex", flexDirection: "column", gap: 4, alignItems: "center", justifyContent: "flex-end" }}>
            <span style={{ fontFamily: font.mono, fontSize: 9.5, color: color.ink60 }}>
              {h.places >= 1000 ? `${(h.places / 1000).toFixed(0)}k` : h.places}
            </span>
            <div style={{ width: "100%", maxWidth: 48, height: `${Math.max(4, (h.places / max) * 100)}%`, background: color.blue, border: `2px solid ${color.ink}` }} />
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        {history.map((h) => (
          <span key={h.month} style={{ flex: 1, minWidth: 0, textAlign: "center", fontFamily: font.body, fontWeight: 500, fontSize: 10, color: color.ink60 }}>
            {h.month.slice(5)}/{h.month.slice(2, 4)}
          </span>
        ))}
      </div>
      <div style={{ height: 3, background: color.ink }} />
    </div>
  );
}

export default function Account() {
  const { user, license } = useAuth();

  const accountQuery = useQuery({
    queryKey: ["account"],
    queryFn: () => api.get<AccountResponse>("/api/auth/account"),
  });

  const data = accountQuery.data;

  return (
    <div>
      <div className="neo-responsive-header" style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>ACCOUNT & BILLING</h1>
        <p style={{ margin: "4px 0 0", fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink60 }}>
          Your session, your license, and how much of it you have used.
        </p>
      </div>

      {accountQuery.isLoading && (
        <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 1126 }}>
          <div style={{ display: "flex", gap: 24 }}>
            <div className="neo-skeleton" style={{ height: 160, flex: 1, border: `3px solid ${color.ink}` }} />
            <div className="neo-skeleton" style={{ height: 160, flex: 1, border: `3px solid ${color.ink}` }} />
          </div>
          <div className="neo-skeleton" style={{ height: 80, border: `3px solid ${color.ink}` }} />
          <div className="neo-skeleton" style={{ height: 200, border: `3px solid ${color.ink}` }} />
        </div>
      )}

      {accountQuery.isError && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "64px 0" }}>
          <div style={{ width: 64, height: 64, background: color.pink, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>ACCOUNT DATA FAILED TO LOAD</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 400 }}>
            Your license, session and quota details could not be fetched.
          </p>
          <p style={{ margin: 0, fontFamily: font.mono, fontSize: 12, color: color.ink60 }}>
            {accountQuery.error instanceof ApiError ? accountQuery.error.message : "ERR_ACCOUNT_FETCH_FAILED"}
          </p>
          <NeoButton variant="destructive" onClick={() => accountQuery.refetch()}>Retry</NeoButton>
        </div>
      )}

      {data && (
        <>
          <div className="neo-responsive-row" style={{ display: "flex", gap: 24, marginBottom: 24, flexWrap: "wrap" }}>
            <Panel title="SIGNED IN" width={546}>
              <Row label="Email">{user?.email ?? data.user.email}</Row>
              <Row label="User ID"><span style={{ fontFamily: font.mono }}>{user?.id ?? data.user.id}</span></Row>
              <Row label="Role">{data.user.role}</Row>
              <Row label="API version"><span style={{ fontFamily: font.mono }}>{data.apiVersion} (/api/version)</span></Row>
              <Row label="2FA">
                <Badge label={data.user.twoFactorEnrolled ? "● Enrolled" : "✕ Not enrolled"} tone={data.user.twoFactorEnrolled ? "green" : "pink"} />
              </Row>
            </Panel>

            <Panel
              title="LICENSE"
              width={568}
              badge={<Badge label={license?.active ? "● Active" : "✕ Expired"} tone={license?.active ? "green" : "pink"} />}
            >
              <Row label="Plan">{license?.plan ?? "—"}</Row>
              <Row label="Seats">{license ? `${license.seats} seat${license.seats === 1 ? "" : "s"}` : "—"}</Row>
              <Row label="Expiry">
                {license?.expiresAt ? new Date(license.expiresAt).toLocaleDateString() : "—"}
              </Row>
              {license && !license.active && (
                <>
                  <div style={{ borderTop: `2px solid ${color.rule}`, margin: "4px 0" }} />
                  <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 11, letterSpacing: "0.22px", color: color.ink }}>EXTEND FROM THE TERMINAL</span>
                  <div style={{ background: color.sand, border: `2px solid ${color.rule}`, padding: 10, fontFamily: font.mono, fontSize: 11.5, color: color.ink }}>
                    mapscrape license extend --key &lt;NEW_LICENSE_KEY&gt;
                  </div>
                </>
              )}
            </Panel>
          </div>

          <p style={{ margin: "0 0 12px", fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>QUOTA</p>
          <div className="neo-responsive-row" style={{ background: color.white, border: `3px solid ${color.ink}`, padding: 16, display: "flex", gap: 24, marginBottom: 8, maxWidth: 1126 }}>
            <Meter label="PLACES THIS MONTH" value={data.quota.placesThisMonth} limit={data.quota.placesLimit} />
            <Meter
              label="EXPORTS THIS MONTH"
              value={data.quota.exportsThisMonth}
              limit={data.quota.exportsLimit}
              warning={data.quota.exportsLimit > 0 && data.quota.exportsThisMonth / data.quota.exportsLimit > 0.75}
            />
          </div>
          <p style={{ margin: "0 0 24px", fontFamily: font.body, fontSize: 11.5, color: color.ink60 }}>
            Resets {new Date(data.quota.resetsAt).toLocaleDateString()}
          </p>

          <p style={{ margin: "0 0 12px", fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>USAGE HISTORY</p>
          <div style={{ background: color.white, border: `3px solid ${color.ink}`, padding: "20px 20px 16px", maxWidth: 1126, boxSizing: "border-box" }}>
            <UsageChart history={data.usageHistory} />
          </div>
        </>
      )}
    </div>
  );
}
