// Settings screen (Figma [SCREEN] settings, SCREENLIST.md §20).
// Backend: GET/PATCH /api/settings, POST /api/settings/reset,
// POST /api/settings/purge-results (backend/app/api/routers/settings.py).
//
// Installation-wide, not per-user — one worker fleet, one set of knobs.
// Every control saves on its own (PATCH is a partial update) and the
// response is authoritative: the API clamps what it stores, so the value
// that comes back is what the workers will actually use.
//
// Figma's BROWSER section (headless mode, viewport, locale/timezone, dwell
// time) is dropped entirely — none of it is backend-configurable today
// (headless is a hardcoded literal at every Playwright launch call site,
// viewport/locale/dwell aren't set anywhere at all), and wiring them would
// mean inventing per-request browser config plumbing well beyond this
// screen. Same precedent as System Health dropping its BROWSER POOL/OBJECT
// STORE tiles — real gaps, not faked as configurable.
//
// SCRAPING's subdivision depth / saturation threshold fields are dropped for
// the same reason — no such algorithm exists anywhere in the scraper
// (grep for "subdivi"/"saturat" turns up nothing); cooldown base and retry
// ceiling are kept because both are real, wired settings.
//
// ENRICHMENT's email verification only offers Off / Syntax + MX — the third
// Figma option ("+ SMTP", a live handshake against the recipient's mail
// server) is not offered: that's a real per-lead connection to a third
// party's mail infrastructure with no rate-limit/blocklist story this cycle
// built. Syntax + MX is real (backend/app/scraping/common/email_verify.py,
// a genuine DNS MX lookup) but not yet wired into the scrape pipeline itself
// — see that module's docstring; the setting is stored correctly, it just
// doesn't change a running job's behavior yet. Documented in the field's
// help copy rather than hidden.

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import NeoButton from "../components/neo/NeoButton";
import NeoRadio from "../components/neo/NeoRadio";
import { color, font, shadow } from "../theme/neobrutalist";
import type { AppSettings, EmailVerificationMode, ScoreWeights } from "../types";

const REFETCH_MS = 5000;

function SectionShell({
  title,
  danger,
  headerRight,
  children,
}: {
  title: string;
  danger?: boolean;
  headerRight?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        background: color.white,
        border: `3px solid ${danger ? color.pink : color.ink}`,
        marginBottom: 24,
        maxWidth: 1126,
      }}
    >
      <div
        style={{
          background: danger ? color.pink : color.sand,
          color: danger ? color.white : color.ink,
          padding: "14px 16px",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12 }}>▾</span>
        <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 15, letterSpacing: "0.15px" }}>
          {title}
        </span>
        <div style={{ flex: 1 }} />
        {headerRight}
      </div>
      <div style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 16 }}>
        {children}
      </div>
    </div>
  );
}

function NumberField({
  label,
  help,
  value,
  onCommit,
  min,
  max,
  step = 1,
  suffix,
  disabled,
}: {
  label: string;
  help?: string;
  value: number;
  onCommit: (v: number) => void;
  min: number;
  max: number;
  step?: number;
  suffix?: string;
  disabled?: boolean;
}) {
  const [local, setLocal] = useState(String(value));
  useEffect(() => setLocal(String(value)), [value]);

  const commit = () => {
    const parsed = Number(local);
    if (Number.isFinite(parsed)) {
      onCommit(Math.min(max, Math.max(min, parsed)));
    } else {
      setLocal(String(value));
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1, minWidth: 0 }}>
      <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3675px", textTransform: "uppercase", color: color.ink }}>
        {label}
      </span>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <input
          type="number"
          value={local}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          onChange={(e) => setLocal(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          style={{
            height: 40,
            width: "100%",
            boxSizing: "border-box",
            border: `3px solid ${color.ink}`,
            background: disabled ? color.sand : color.white,
            padding: "0 12px",
            fontFamily: font.body,
            fontWeight: 500,
            fontSize: 13,
            color: disabled ? color.ink60 : color.ink,
          }}
        />
        {suffix && <span style={{ fontFamily: font.body, fontSize: 12, color: color.ink60 }}>{suffix}</span>}
      </div>
      {help && (
        <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10, letterSpacing: "0.4px", textTransform: "uppercase", color: color.ink60 }}>
          {help}
        </span>
      )}
    </div>
  );
}

function NeoSwitch({ checked, onChange, disabled }: { checked: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={onChange}
      style={{
        width: 44,
        height: 24,
        padding: 2,
        boxSizing: "border-box",
        border: `3px solid ${color.ink}`,
        background: disabled ? color.sand : checked ? color.green : color.sand,
        cursor: disabled ? "default" : "pointer",
        position: "relative",
        flexShrink: 0,
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 1,
          left: checked ? 21 : 1,
          width: 16,
          height: 16,
          background: color.ink,
          border: `3px solid ${color.ink}`,
          boxSizing: "border-box",
          transition: "left 0.1s",
        }}
      />
    </button>
  );
}

function Slider({
  value,
  min,
  max,
  onCommit,
  disabled,
}: {
  value: number;
  min: number;
  max: number;
  onCommit: (v: number) => void;
  disabled?: boolean;
}) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  return (
    <input
      type="range"
      min={min}
      max={max}
      value={local}
      disabled={disabled}
      onChange={(e) => setLocal(Number(e.target.value))}
      onMouseUp={() => onCommit(local)}
      onTouchEnd={() => onCommit(local)}
      style={{ width: "100%", accentColor: color.blue }}
    />
  );
}

// Mirrors backend/app/core/runtime_settings.SCORE_WEIGHT_DEFAULTS exactly --
// the Lead Scoring section's "Reset to defaults" ghost button is scoped to
// just these six weights (unlike Danger Zone's "Reset Settings", which wipes
// every runtime setting on the page), so it PATCHes these values back rather
// than calling the whole-page reset endpoint.
const DEFAULT_SCORE_WEIGHTS: ScoreWeights = {
  email: 20,
  website: 15,
  phone: 20,
  social: 5,
  rating_high: 15,
  rating_good: 8,
  decision_maker: 10,
  mobile_phone: 10,
};

const SIGNAL_LABELS: [keyof ScoreWeights, string][] = [
  ["email", "Has email"],
  ["website", "Has website"],
  ["phone", "Has phone"],
  ["mobile_phone", "Has direct mobile line"],
  ["decision_maker", "Has decision maker (Owner/CEO)"],
  ["social", "Has ≥1 social profile (per profile, capped)"],
  ["rating_high", "Rating ≥ 4.5"],
  ["rating_good", "Rating ≥ 4.0 (and < 4.5)"],
];

function WeightTable({
  weights,
  onCommit,
  disabled,
}: {
  weights: ScoreWeights;
  onCommit: (signal: keyof ScoreWeights, value: number) => void;
  disabled?: boolean;
}) {
  return (
    <div style={{ border: `3px solid ${color.ink}`, width: "100%", boxSizing: "border-box" }}>
      <div style={{ display: "flex", background: color.sand, borderBottom: `3px solid ${color.ink}`, height: 32 }}>
        <div style={{ display: "flex", alignItems: "center", padding: "0 12px", flex: "1 1 0", minWidth: 0 }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.21px", color: color.ink }}>SIGNAL</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", padding: "0 12px", width: 140, flexShrink: 0 }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.21px", color: color.ink }}>WEIGHT</span>
        </div>
      </div>
      {SIGNAL_LABELS.map(([signal, label]) => (
        <div key={signal} style={{ display: "flex", height: 36, alignItems: "center", borderBottom: `3px solid ${color.rule}` }}>
          <div style={{ padding: "0 12px", flex: "1 1 0", minWidth: 0 }}>
            <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink }}>{label}</span>
          </div>
          <div style={{ padding: "0 12px", width: 140, flexShrink: 0 }}>
            <input
              type="number"
              defaultValue={weights[signal]}
              disabled={disabled}
              key={weights[signal]}
              onBlur={(e) => {
                const v = Number(e.target.value);
                if (Number.isFinite(v) && v !== weights[signal]) onCommit(signal, v);
              }}
              style={{
                width: 70,
                height: 28,
                border: `2px solid ${color.ink}`,
                fontFamily: font.mono,
                fontSize: 12,
                color: weights[signal] < 0 ? color.pink : color.green,
                padding: "0 6px",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function computePreviewScore(w: ScoreWeights, signals: Partial<Record<keyof ScoreWeights | "social_count", number | boolean>>): number {
  let total = 0;
  if (signals.email) total += w.email;
  if (signals.website) total += w.website;
  if (signals.phone) total += w.phone;
  if (signals.mobile_phone) total += w.mobile_phone;
  if (signals.decision_maker) total += w.decision_maker;
  const socialCount = Number(signals.social_count || 0);
  if (socialCount) total += Math.min(Math.abs(w.social) * 2, socialCount * w.social);
  if (signals.rating_high) total += w.rating_high;
  else if (signals.rating_good) total += w.rating_good;
  return Math.max(0, Math.min(100, total));
}

const PREVIEW_SAMPLES: { name: string; signals: Partial<Record<keyof ScoreWeights | "social_count", number | boolean>>; reasons: string }[] = [
  {
    name: "Denver Roofing Co.",
    signals: { email: true, website: true, phone: true, social_count: 2, rating_good: true },
    reasons: "email, website, phone, 2 socials, rating",
  },
  {
    name: "QuickFix Plumbing LLC",
    signals: { email: true, phone: true },
    reasons: "email, phone",
  },
  {
    name: "Ace Hardware #4471",
    signals: { website: true, phone: true },
    reasons: "website, phone",
  },
];

function PurgeResultsModal({ onCancel, onConfirm, pending }: { onCancel: () => void; onConfirm: () => void; pending: boolean }) {
  const [typed, setTyped] = useState("");
  const confirmed = typed.trim().toUpperCase() === "PURGE";
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(17,17,17,0.7)", display: "grid", placeItems: "center", zIndex: 1000 }}>
      <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: shadow.md, width: 440 }}>
        <div style={{ borderBottom: `3px solid ${color.ink}`, background: color.pink, color: color.white, padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", textTransform: "uppercase" }}>Purge all results</span>
          <button type="button" onClick={onCancel} style={{ border: "none", background: "transparent", color: color.white, cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>
        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink }}>
            This permanently deletes every stored result and export artifact across every job.
            Job history and settings are kept. Type PURGE to confirm.
          </p>
          <input
            autoFocus
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="Type PURGE"
            style={{ height: 40, border: `3px solid ${color.ink}`, padding: "0 9px", fontFamily: font.body, fontSize: 13, boxSizing: "border-box" }}
          />
        </div>
        <div style={{ padding: "16px 20px", display: "flex", justifyContent: "flex-end", gap: 12 }}>
          <NeoButton variant="secondary" onClick={onCancel} disabled={pending}>Cancel</NeoButton>
          <NeoButton variant="destructive" onClick={onConfirm} disabled={!confirmed} loading={pending}>
            Purge all
          </NeoButton>
        </div>
      </div>
    </div>
  );
}

function ResetSettingsModal({ onCancel, onConfirm, pending }: { onCancel: () => void; onConfirm: () => void; pending: boolean }) {
  const [typed, setTyped] = useState("");
  const confirmed = typed.trim().toUpperCase() === "RESET";
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(17,17,17,0.7)", display: "grid", placeItems: "center", zIndex: 1000 }}>
      <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: shadow.md, width: 440 }}>
        <div style={{ borderBottom: `3px solid ${color.ink}`, background: color.pink, color: color.white, padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", textTransform: "uppercase" }}>Reset settings</span>
          <button type="button" onClick={onCancel} style={{ border: "none", background: "transparent", color: color.white, cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>
        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink }}>
            This restores every setting on this page to its factory default. Does not affect
            stored data. Type RESET to confirm.
          </p>
          <input
            autoFocus
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="Type RESET"
            style={{ height: 40, border: `3px solid ${color.ink}`, padding: "0 9px", fontFamily: font.body, fontSize: 13, boxSizing: "border-box" }}
          />
        </div>
        <div style={{ padding: "16px 20px", display: "flex", justifyContent: "flex-end", gap: 12 }}>
          <NeoButton variant="secondary" onClick={onCancel} disabled={pending}>Cancel</NeoButton>
          <NeoButton variant="destructive" onClick={onConfirm} disabled={!confirmed} loading={pending}>
            Reset settings
          </NeoButton>
        </div>
      </div>
    </div>
  );
}

function SectionsSkeleton() {
  return (
    <div style={{ maxWidth: 1126 }}>
      {[110, 130, 90, 260, 90].map((h, i) => (
        <div key={i} className="neo-skeleton" style={{ height: h, border: `3px solid ${color.ink}`, marginBottom: 24 }} />
      ))}
    </div>
  );
}

export default function Settings() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [purgeOpen, setPurgeOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<AppSettings>("/api/settings/"),
    refetchInterval: REFETCH_MS,
  });

  const save = useMutation({
    mutationFn: (patch: Omit<Partial<AppSettings>, "scoreWeights"> & { scoreWeights?: Partial<ScoreWeights> }) =>
      api.patch<AppSettings>("/api/settings/", patch),
    onSuccess: (updated) => {
      setError(null);
      queryClient.setQueryData(["settings"], updated);
    },
    onError: (err: Error) => setError(err.message),
  });

  const resetMutation = useMutation({
    mutationFn: () => api.post<AppSettings>("/api/settings/reset"),
    onSuccess: (updated) => {
      setError(null);
      queryClient.setQueryData(["settings"], updated);
      setResetOpen(false);
    },
    onError: (err: Error) => setError(err.message),
  });

  const purgeMutation = useMutation({
    mutationFn: () => api.post<{ resultsDeleted: number; exportsDeleted: number }>("/api/settings/purge-results"),
    onSuccess: () => {
      setError(null);
      setPurgeOpen(false);
    },
    onError: (err: Error) => setError(err.message),
  });

  const settings = settingsQuery.data;

  // Local mirrors for sliders/number fields while dragging/typing, re-synced
  // whenever the server answers -- same pattern as the concurrency slider.
  const [concurrency, setConcurrency] = useState(1);
  const [crawlPages, setCrawlPages] = useState(25);

  useEffect(() => {
    if (!settings) return;
    setConcurrency(settings.concurrentTargets);
    setCrawlPages(settings.deepCrawlMaxPages);
  }, [settings, settings?.concurrentTargets, settings?.deepCrawlMaxPages]);

  if (settingsQuery.isLoading) {
    return (
      <div>
        <Header />
        <SectionsSkeleton />
      </div>
    );
  }

  if (settingsQuery.isError || !settings) {
    return (
      <div>
        <Header />
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "64px 0" }}>
          <div style={{ width: 64, height: 64, background: color.pink, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>SETTINGS FAILED TO LOAD</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 400 }}>
            Installation-wide settings could not be fetched from the database.
          </p>
          <p style={{ margin: 0, fontFamily: font.mono, fontSize: 12, color: color.ink60 }}>
            {settingsQuery.error instanceof ApiError ? settingsQuery.error.message : "ERR_SETTINGS_FETCH_FAILED"}
          </p>
          <NeoButton variant="destructive" onClick={() => settingsQuery.refetch()}>Retry</NeoButton>
        </div>
      </div>
    );
  }

  const weights = settings.scoreWeights;

  return (
    <div>
      <Header />

      {error && (
        <div style={{ marginBottom: 16, padding: 12, border: `3px solid ${color.pink}`, background: color.white, maxWidth: 1126 }}>
          <span style={{ fontFamily: font.body, fontSize: 13, color: color.ink }}>{error}</span>
        </div>
      )}

      <SectionShell title="SCRAPING">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12, letterSpacing: "0.24px", color: color.ink }}>SCRAPE CONCURRENCY</span>
            <Chip label={`${settings.runningTargets} RUNNING`} bg={color.green} />
            <Chip label={`${settings.waitingTargets} WAITING`} bg={color.sand} />
          </div>
          <Slider
            value={concurrency}
            min={1}
            max={settings.maxConcurrentTargets}
            onCommit={(v) => { setConcurrency(v); save.mutate({ concurrentTargets: v }); }}
            disabled={save.isPending}
          />
          <span style={{ fontFamily: font.body, fontSize: 11, color: color.ink60 }}>Refreshes every 5s. {concurrency} of {settings.maxConcurrentTargets} max.</span>
        </div>
        <div className="neo-responsive-row" style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
          <NumberField
            label="Per-host cooldown base"
            help="Base delay before re-hitting the same host."
            value={settings.cooldownBaseS}
            min={1}
            max={settings.maxCooldownBaseS}
            step={0.5}
            suffix="s"
            onCommit={(v) => save.mutate({ cooldownBaseS: v })}
            disabled={save.isPending}
          />
          <NumberField
            label="Retry ceiling"
            help="Max retries before a target is marked failed."
            value={settings.retryCeiling}
            min={0}
            max={settings.maxRetryCeiling}
            onCommit={(v) => save.mutate({ retryCeiling: v })}
            disabled={save.isPending}
          />
        </div>
        <span style={{ fontFamily: font.body, fontSize: 11, color: color.ink60 }}>
          Cooldown base takes effect for scrapes started by a worker process that (re)starts
          after the change, not mid-run.
        </span>
      </SectionShell>

      <SectionShell
        title="DEEP WEBSITE CRAWL"
        headerRight={
          <NeoSwitch
            checked={settings.deepCrawlEnabled}
            onChange={() => save.mutate({ deepCrawlEnabled: !settings.deepCrawlEnabled })}
            disabled={save.isPending}
          />
        }
      >
        <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
          Findings from crawled pages are appended, not substituted. Turning this off only
          applies to places queued after the change — places already in progress finish with
          deep crawl on.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, opacity: settings.deepCrawlEnabled ? 1 : 0.5 }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12, letterSpacing: "0.24px", color: color.ink }}>
            PAGES PER WEBSITE — {crawlPages}
          </span>
          <Slider
            value={crawlPages}
            min={1}
            max={settings.maxDeepCrawlPages}
            onCommit={(v) => { setCrawlPages(v); save.mutate({ deepCrawlMaxPages: v }); }}
            disabled={!settings.deepCrawlEnabled || save.isPending}
          />
        </div>
      </SectionShell>

      <SectionShell title="ENRICHMENT">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12, letterSpacing: "0.24px", color: color.ink }}>EMAIL VERIFICATION MODE</span>
          <div style={{ display: "flex", gap: 10 }}>
            {(["off", "syntax_mx"] as EmailVerificationMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => save.mutate({ emailVerificationMode: mode })}
                disabled={save.isPending}
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  border: `${settings.emailVerificationMode === mode ? 3 : 2}px solid ${color.ink}`,
                  background: settings.emailVerificationMode === mode ? color.sand : color.white,
                  padding: "8px 12px", cursor: "pointer",
                }}
              >
                <NeoRadio checked={settings.emailVerificationMode === mode} />
                <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink }}>
                  {mode === "off" ? "Off" : "Syntax + MX"}
                </span>
              </button>
            ))}
          </div>
          <span style={{ fontFamily: font.body, fontSize: 11, color: color.ink60 }}>
            Syntax validation always runs during extraction. &quot;Syntax + MX&quot; adds a DNS MX-record
            check but is not yet wired into the live scrape path — the setting is saved for when
            it is.
          </span>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12, letterSpacing: "0.24px", color: color.ink }}>TECH FINGERPRINT</span>
          <div style={{ flex: 1 }} />
          <NeoSwitch
            checked={settings.techFingerprintEnabled}
            onChange={() => save.mutate({ techFingerprintEnabled: !settings.techFingerprintEnabled })}
            disabled={save.isPending}
          />
        </div>
      </SectionShell>

      <SectionShell
        title="WATERFALL EMAIL & MOBILE ENRICHMENT"
        headerRight={
          <NeoSwitch
            checked={settings.waterfallEnrichmentEnabled}
            onChange={() => save.mutate({ waterfallEnrichmentEnabled: !settings.waterfallEnrichmentEnabled })}
            disabled={save.isPending}
          />
        }
      >
        <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
          Automatically triggers a priority cascade across third-party enrichment providers when the internal
          website crawler discovers no email or only generic role-based inboxes (info@, contact@, support@, sales@).
          Direct personal emails and direct mobile numbers are merged into the lead record with full source tracking.
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 14, opacity: settings.waterfallEnrichmentEnabled ? 1 : 0.6 }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12, letterSpacing: "0.24px", color: color.ink }}>
            CASCADE PROVIDERS & API KEYS
          </span>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
            {/* Hunter.io */}
            <div style={{ border: `2px solid ${color.ink}`, padding: 12, background: color.sand }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12, color: color.ink }}>1. HUNTER.IO</span>
                <Chip label={settings.hunterApiKey ? "CONFIGURED" : "NO KEY"} bg={settings.hunterApiKey ? color.green : color.sand} />
              </div>
              <input
                type="password"
                placeholder="Hunter API Key (hidden)"
                defaultValue={settings.hunterApiKey || ""}
                disabled={!settings.waterfallEnrichmentEnabled || save.isPending}
                onBlur={(e) => {
                  const v = e.target.value.trim();
                  if (v !== (settings.hunterApiKey || "")) save.mutate({ hunterApiKey: v || null });
                }}
                style={{
                  width: "100%", height: 32, boxSizing: "border-box", border: `2px solid ${color.ink}`,
                  padding: "0 8px", fontFamily: font.mono, fontSize: 11, background: color.white,
                }}
              />
            </div>

            {/* Prospeo.io */}
            <div style={{ border: `2px solid ${color.ink}`, padding: 12, background: color.sand }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12, color: color.ink }}>2. PROSPEO.IO</span>
                <Chip label={settings.prospeoApiKey ? "CONFIGURED" : "NO KEY"} bg={settings.prospeoApiKey ? color.green : color.sand} />
              </div>
              <input
                type="password"
                placeholder="Prospeo X-KEY (hidden)"
                defaultValue={settings.prospeoApiKey || ""}
                disabled={!settings.waterfallEnrichmentEnabled || save.isPending}
                onBlur={(e) => {
                  const v = e.target.value.trim();
                  if (v !== (settings.prospeoApiKey || "")) save.mutate({ prospeoApiKey: v || null });
                }}
                style={{
                  width: "100%", height: 32, boxSizing: "border-box", border: `2px solid ${color.ink}`,
                  padding: "0 8px", fontFamily: font.mono, fontSize: 11, background: color.white,
                }}
              />
            </div>

            {/* Datagma */}
            <div style={{ border: `2px solid ${color.ink}`, padding: 12, background: color.sand }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12, color: color.ink }}>3. DATAGMA</span>
                <Chip label={settings.datagmaApiKey ? "CONFIGURED" : "NO KEY"} bg={settings.datagmaApiKey ? color.green : color.sand} />
              </div>
              <input
                type="password"
                placeholder="Datagma API Key (hidden)"
                defaultValue={settings.datagmaApiKey || ""}
                disabled={!settings.waterfallEnrichmentEnabled || save.isPending}
                onBlur={(e) => {
                  const v = e.target.value.trim();
                  if (v !== (settings.datagmaApiKey || "")) save.mutate({ datagmaApiKey: v || null });
                }}
                style={{
                  width: "100%", height: 32, boxSizing: "border-box", border: `2px solid ${color.ink}`,
                  padding: "0 8px", fontFamily: font.mono, fontSize: 11, background: color.white,
                }}
              />
            </div>

            {/* Findymail */}
            <div style={{ border: `2px solid ${color.ink}`, padding: 12, background: color.sand }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12, color: color.ink }}>4. FINDYMAIL</span>
                <Chip label={settings.findymailApiKey ? "CONFIGURED" : "NO KEY"} bg={settings.findymailApiKey ? color.green : color.sand} />
              </div>
              <input
                type="password"
                placeholder="Findymail Bearer Token (hidden)"
                defaultValue={settings.findymailApiKey || ""}
                disabled={!settings.waterfallEnrichmentEnabled || save.isPending}
                onBlur={(e) => {
                  const v = e.target.value.trim();
                  if (v !== (settings.findymailApiKey || "")) save.mutate({ findymailApiKey: v || null });
                }}
                style={{
                  width: "100%", height: 32, boxSizing: "border-box", border: `2px solid ${color.ink}`,
                  padding: "0 8px", fontFamily: font.mono, fontSize: 11, background: color.white,
                }}
              />
            </div>
          </div>
        </div>
      </SectionShell>

      <SectionShell
        title="LEAD SCORING"
        headerRight={
          <NeoButton variant="ghost" size="sm" onClick={() => save.mutate({ scoreWeights: DEFAULT_SCORE_WEIGHTS })}>
            Reset to defaults
          </NeoButton>
        }
      >
        <WeightTable
          weights={weights}
          disabled={save.isPending}
          onCommit={(signal, value) => save.mutate({ scoreWeights: { [signal]: value } })}
        />
        <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12, letterSpacing: "0.24px", color: color.ink }}>LIVE PREVIEW</span>
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
          {PREVIEW_SAMPLES.map((sample) => (
            <div key={sample.name} style={{ flex: "1 1 220px", background: color.sand, border: `2px solid ${color.ink}`, padding: 12, minWidth: 200 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink }}>{sample.name}</span>
                <div style={{ flex: 1 }} />
                <span style={{ fontFamily: font.mono, fontSize: 14, color: color.ink }}>{computePreviewScore(weights, sample.signals)}</span>
              </div>
              <span style={{ fontFamily: font.mono, fontSize: 10, color: color.ink60 }}>{sample.reasons}</span>
            </div>
          ))}
        </div>
      </SectionShell>

      <SectionShell title="DATA RETENTION">
        <div className="neo-responsive-row" style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
          <NumberField
            label="Results retention"
            value={settings.resultsRetentionDays}
            min={1}
            max={settings.maxResultsRetentionDays}
            suffix="days"
            onCommit={(v) => save.mutate({ resultsRetentionDays: v })}
            disabled={save.isPending}
          />
          <NumberField
            label="Export artifact retention"
            value={settings.exportRetentionDays}
            min={1}
            max={settings.maxExportRetentionDays}
            suffix="days"
            onCommit={(v) => save.mutate({ exportRetentionDays: v })}
            disabled={save.isPending}
          />
        </div>
        <span style={{ fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
          Purge sweeps run once a day.
        </span>
      </SectionShell>

      <SectionShell title="DANGER ZONE" danger>
        <div className="neo-responsive-row" style={{ display: "flex", gap: 16, alignItems: "center" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink }}>PURGE ALL RESULTS</p>
            <p style={{ margin: "2px 0 0", fontFamily: font.body, fontSize: 11.5, color: color.ink60 }}>
              Permanently deletes every stored result and export artifact. Job history and settings are kept.
            </p>
          </div>
          <NeoButton variant="destructive" onClick={() => setPurgeOpen(true)}>Purge all results</NeoButton>
        </div>
        <div className="neo-responsive-row" style={{ display: "flex", gap: 16, alignItems: "center" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink }}>RESET SETTINGS</p>
            <p style={{ margin: "2px 0 0", fontFamily: font.body, fontSize: 11.5, color: color.ink60 }}>
              Restores every setting on this page to its factory default. Does not affect stored data.
            </p>
          </div>
          <NeoButton variant="destructive" onClick={() => setResetOpen(true)}>Reset settings</NeoButton>
        </div>
      </SectionShell>

      {purgeOpen && (
        <PurgeResultsModal
          pending={purgeMutation.isPending}
          onCancel={() => setPurgeOpen(false)}
          onConfirm={() => purgeMutation.mutate()}
        />
      )}
      {resetOpen && (
        <ResetSettingsModal
          pending={resetMutation.isPending}
          onCancel={() => setResetOpen(false)}
          onConfirm={() => resetMutation.mutate()}
        />
      )}
    </div>
  );
}

function Header() {
  return (
    <div className="neo-responsive-header" style={{ marginBottom: 24 }}>
      <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>SETTINGS</h1>
      <p style={{ margin: "4px 0 0", fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink60 }}>
        Installation-wide runtime settings. Each control saves on its own — no restart needed.
      </p>
    </div>
  );
}

function Chip({ label, bg }: { label: string; bg: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", padding: "3px 8px", border: `2px solid ${color.ink}`, background: bg, fontFamily: font.body, fontWeight: 700, fontSize: 10.5, color: color.ink }}>
      {label}
    </span>
  );
}
