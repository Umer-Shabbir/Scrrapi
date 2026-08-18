// Shared bits for the New Job Wizard (Figma [SCREEN] job-new): stepper,
// panel/field primitives, blocking-condition banner, and the cost estimate.
//
// Cost estimate: TARGETS/PROJECTED PLACES are exact (keywords x areas, the
// same cross-product `create_job` builds server-side). PROJECTED RUNTIME and
// PROXY BANDWIDTH have no backend model anywhere -- Figma bakes in two
// hardcoded snapshots with no visible formula -- so these are a transparent,
// documented client-side estimate, not a precise simulation.

import { color, font } from "../../theme/neobrutalist";
import NeoButton from "../../components/neo/NeoButton";
import InlineWarning from "../../components/neo/InlineWarning";

export const STEPS = ["Keywords", "Areas", "Enrichment", "Review & Schedule"] as const;
export type StepIndex = 0 | 1 | 2 | 3;

// Estimate constants. Deliberately simple and named so the assumption is
// visible in code, not hidden in a magic number -- there is no real cost
// model to calibrate against yet.
const AVG_PLACES_PER_TARGET = 50;
const BASE_SECONDS_PER_TARGET = 90;
const BASE_MB_PER_TARGET = 1.6;
const DEEP_CRAWL_SECONDS_PER_TARGET = 55;
const DEEP_CRAWL_MB_PER_TARGET = 2.9;

export interface CostEstimate {
  targets: number;
  projectedPlaces: number;
  runtimeSeconds: number;
  bandwidthMb: number;
}

export function estimateCost(
  keywordCount: number,
  areaCount: number,
  deepCrawlEnabled: boolean,
): CostEstimate {
  const targets = keywordCount * areaCount;
  const perTargetSeconds = BASE_SECONDS_PER_TARGET + (deepCrawlEnabled ? DEEP_CRAWL_SECONDS_PER_TARGET : 0);
  const perTargetMb = BASE_MB_PER_TARGET + (deepCrawlEnabled ? DEEP_CRAWL_MB_PER_TARGET : 0);
  return {
    targets,
    projectedPlaces: targets * AVG_PLACES_PER_TARGET,
    runtimeSeconds: targets * perTargetSeconds,
    bandwidthMb: targets * perTargetMb,
  };
}

export function formatDuration(totalSeconds: number): string {
  if (totalSeconds <= 0) return "—";
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.round((totalSeconds % 3600) / 60);
  if (hours === 0) return `${minutes}m`;
  return `${hours}h ${minutes}m`;
}

export function formatBandwidth(mb: number): string {
  if (mb <= 0) return "—";
  if (mb < 1024) return `${Math.round(mb)} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}

export function Stepper({ current }: { current: StepIndex }) {
  return (
    <div style={{ display: "flex", alignItems: "center", width: "100%", marginBottom: 24 }}>
      {STEPS.map((label, i) => {
        const state = i < current ? "done" : i === current ? "current" : "upcoming";
        return (
          <div key={label} style={{ display: "flex", alignItems: "center", flex: i === STEPS.length - 1 ? "0 0 auto" : 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div
                style={{
                  width: 24,
                  height: 24,
                  display: "grid",
                  placeItems: "center",
                  border: `3px solid ${color.ink}`,
                  background: state === "done" ? color.green : state === "current" ? color.yellow : color.sand,
                  boxShadow: state === "current" ? "3px 3px 0px 0px #111" : "none",
                  fontFamily: font.body,
                  fontWeight: 700,
                  fontSize: 12,
                  color: color.ink,
                  flexShrink: 0,
                }}
              >
                {state === "done" ? "✓" : i + 1}
              </div>
              <span
                style={{
                  fontFamily: font.body,
                  fontWeight: 700,
                  fontSize: 11,
                  letterSpacing: "0.33px",
                  textTransform: "uppercase",
                  color: state === "upcoming" ? color.ink60 : color.ink,
                  whiteSpace: "nowrap",
                }}
              >
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && <div style={{ flex: 1, height: 2, background: color.rule, margin: "0 12px" }} />}
          </div>
        );
      })}
    </div>
  );
}

export function StepPanel({ title, copy, children }: { title: string; copy: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, flex: 1, minWidth: 0 }}>
      <div>
        <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>{title.toUpperCase()}</h2>
        <p style={{ margin: "4px 0 0", fontFamily: font.body, fontSize: 13, color: color.ink60 }}>{copy}</p>
      </div>
      {children}
    </div>
  );
}

export function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.3675px", textTransform: "uppercase", color: color.ink }}>
      {children}
    </p>
  );
}

export function HelpText({ children, error }: { children: React.ReactNode; error?: boolean }) {
  return (
    <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 10, letterSpacing: "0.4px", textTransform: "uppercase", color: error ? color.pink : color.ink60 }}>
      {children}
    </p>
  );
}

/** Blocking-condition banner. Only one is ever shown at a time -- see JobWizard's
 * priority order (license, then over-limit). White-bg/left-bar treatment, the
 * more refined of the two Figma uses (the flat-pink-fill variant is dropped). */
export function BlockingBanner({
  title,
  body,
  code,
  action,
}: {
  title: string;
  body: string;
  code?: string;
  action?: React.ReactNode;
}) {
  return (
    <div
      style={{
        background: color.white,
        border: `3px solid ${color.ink}`,
        boxShadow: "4px 4px 0px 0px #111",
        display: "flex",
        width: "100%",
        boxSizing: "border-box",
      }}
    >
      <div style={{ width: 6, background: color.pink, flexShrink: 0 }} />
      <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
        <InlineWarning tone="ink" fontSize={13} fontWeight={700}>{title}</InlineWarning>
        <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink }}>{body}</p>
        {code && (
          <code style={{ fontFamily: font.mono, fontSize: 12, background: color.sand, padding: "2px 6px", width: "fit-content" }}>
            {code}
          </code>
        )}
        {action}
      </div>
    </div>
  );
}

export function CostPanel({
  estimate,
  overLimit,
  maxTargets,
}: {
  estimate: CostEstimate;
  overLimit: boolean;
  maxTargets: number;
}) {
  return (
    <div
      style={{
        width: 360,
        flexShrink: 0,
        background: color.white,
        border: `3px solid ${color.ink}`,
        boxShadow: "6px 6px 0px 0px black",
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 16,
        height: "fit-content",
      }}
    >
      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", textTransform: "uppercase", color: color.ink, borderBottom: `3px solid ${color.ink}`, paddingBottom: 12 }}>
        Cost panel
      </p>
      <CostRow label="Targets" value={estimate.targets.toLocaleString()} danger={overLimit} />
      <CostRow label="Projected places" value={`~${estimate.projectedPlaces.toLocaleString()}`} />
      <CostRow label="Projected runtime" value={formatDuration(estimate.runtimeSeconds)} />
      <CostRow label="Proxy bandwidth" value={formatBandwidth(estimate.bandwidthMb)} />
      {overLimit && (
        <InlineWarning tone="pink" fontSize={10} fontWeight={700}>
          Exceeds the {maxTargets.toLocaleString()}-target per-job limit
        </InlineWarning>
      )}
    </div>
  );
}

function CostRow({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div>
      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.42px", textTransform: "uppercase", color: color.ink60 }}>
        {label}
      </p>
      <p style={{ margin: 0, fontFamily: font.head, fontSize: 22, color: danger ? color.pink : color.ink }}>{value}</p>
    </div>
  );
}

export function WizardFooter({
  onBack,
  onNext,
  backDisabled,
  nextLabel,
  nextDisabled,
  nextLoading,
}: {
  onBack?: () => void;
  onNext: () => void;
  backDisabled?: boolean;
  nextLabel: string;
  nextDisabled?: boolean;
  nextLoading?: boolean;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", borderTop: `2px solid ${color.rule}`, paddingTop: 16, marginTop: 24 }}>
      <NeoButton variant="secondary" onClick={onBack} disabled={backDisabled}>
        Back
      </NeoButton>
      <NeoButton variant="primary" onClick={onNext} disabled={nextDisabled} loading={nextLoading}>
        {nextLabel}
      </NeoButton>
    </div>
  );
}
