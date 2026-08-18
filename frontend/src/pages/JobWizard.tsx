// New Job Wizard (Figma [SCREEN] job-new). 4-step flow: Keywords -> Areas ->
// Enrichment -> Review & schedule. Reuses the same JobDraftContext, category
// suggestions, and geo cascade as the standalone Categories/Locations pages
// rather than re-implementing keyword/area logic -- this is a second UI over
// the same draft, not a new data flow.
//
// Scope cut after review: Category Packs and Synonym Suggestions (Figma step 1)
// have no backend (no pack registry, no synonym-expansion service) and are
// omitted rather than faked. Radius/Polygon area modes (step 2) have no backend
// (no GeoJSON/radius geo search) -- only Cascade and Type-an-area are wired,
// matching the existing Locations page. Email Verification / Tech Fingerprint /
// Adaptive Subdivision Depth (step 3) have no backend at all and render
// disabled. Attach-schedule (step 4) has no backend (Schedules is a separate,
// unbuilt screen) and renders disabled. Save-as-template is real, wired to
// POST /api/templates once the Templates screen added that backend.
// Quota-exceeded (a third blocking state in the Figma mock) is omitted --  the
// Dashboard cycle already established there's no real quota/usage subsystem.

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import NeoButton from "../components/neo/NeoButton";
import ZipCascadeSelect from "../components/ZipCascadeSelect";
import { KEYWORD_SEPARATORS, useJobDraft } from "../state/JobDraftContext";
import { color, font } from "../theme/neobrutalist";
import type { AppSettings, Job, LocationTarget } from "../types";
import {
  BlockingBanner,
  CostPanel,
  FieldLabel,
  HelpText,
  StepPanel,
  Stepper,
  WizardFooter,
  estimateCost,
  type StepIndex,
} from "./wizard/WizardShared";

function ChipInput({
  values,
  onAdd,
  onRemove,
  placeholder,
}: {
  values: string[];
  onAdd: (raw: string) => void;
  onRemove: (value: string) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = useState("");
  return (
    <div
      style={{
        border: `3px solid ${color.ink}`,
        minHeight: 40,
        display: "flex",
        flexWrap: "wrap",
        gap: 6,
        alignItems: "center",
        padding: "6px 12px",
        background: color.white,
        boxSizing: "border-box",
      }}
    >
      {values.map((value) => (
        <span
          key={value}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            border: `2px solid ${color.ink}`,
            background: color.white,
            padding: "3px 8px",
            fontFamily: font.body,
            fontSize: "12.5px",
            color: color.ink,
          }}
        >
          {value.toUpperCase()}
          <button
            type="button"
            onClick={() => onRemove(value)}
            style={{ border: "none", background: "transparent", padding: 0, cursor: "pointer", fontSize: 10, color: color.ink }}
          >
            ✕
          </button>
        </span>
      ))}
      <input
        value={draft}
        placeholder={values.length === 0 ? placeholder : ""}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key !== "Enter") return;
          if (!draft.trim()) return;
          onAdd(draft);
          setDraft("");
        }}
        style={{ border: "none", outline: "none", fontFamily: font.body, fontSize: 13, flex: 1, minWidth: 120 }}
      />
    </div>
  );
}

function StepKeywords() {
  const draft = useJobDraft();
  const suggestions = useQuery({
    queryKey: ["categories", "suggestions"],
    queryFn: () => api.get<string[]>("/api/categories/"),
    staleTime: Infinity,
  });

  return (
    <StepPanel
      title="Keywords"
      copy="Type keywords or upload a CSV. Comma, semicolon, and newline all split into separate keywords."
    >
      <div>
        <FieldLabel>Keywords</FieldLabel>
        <div style={{ marginTop: 6 }}>
          <ChipInput
            values={draft.keywords}
            onAdd={(raw) => draft.addKeywords(raw.split(KEYWORD_SEPARATORS))}
            onRemove={draft.removeKeyword}
            placeholder="plumber, roofing contractor"
          />
        </div>
        <div style={{ marginTop: 6 }}>
          <HelpText>Comma, semicolon or newline separated</HelpText>
        </div>
      </div>

      {suggestions.data && suggestions.data.length > 0 && (
        <div>
          <FieldLabel>Suggestions</FieldLabel>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 6 }}>
            {suggestions.data.slice(0, 10).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => draft.addKeywords([s])}
                style={{
                  border: `2px solid ${color.ink}`,
                  background: color.white,
                  padding: "3px 8px",
                  fontFamily: font.body,
                  fontSize: "12.5px",
                  color: color.ink,
                  cursor: "pointer",
                }}
              >
                + {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <p style={{ margin: 0, fontFamily: font.head, fontSize: 14, letterSpacing: "0.28px", textTransform: "uppercase", color: color.ink }}>
          Keyword list ({draft.keywords.length})
        </p>
        {draft.keywords.length > 0 && (
          <NeoButton variant="ghost" size="sm" onClick={draft.clearKeywords}>
            Clear all
          </NeoButton>
        )}
      </div>
      {draft.keywords.length === 0 ? (
        <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
          No keywords yet — type above or upload a CSV on the Categories page.
        </p>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {draft.keywords.map((k) => (
            <span
              key={k}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                border: `2px solid ${color.ink}`,
                padding: "4px 12px",
                fontFamily: font.body,
                fontSize: "12.5px",
                color: color.ink,
              }}
            >
              {k.toUpperCase()}
              <button
                type="button"
                onClick={() => draft.removeKeyword(k)}
                style={{ border: "none", background: "transparent", padding: 0, cursor: "pointer", fontSize: 11, color: color.ink }}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}
    </StepPanel>
  );
}

const AREA_MODES = ["Cascade", "Type an area"] as const;

function StepAreas() {
  const draft = useJobDraft();
  const [mode, setMode] = useState<(typeof AREA_MODES)[number]>("Cascade");
  const [selected, setSelected] = useState<LocationTarget[]>([]);
  const [typed, setTyped] = useState("");

  function queueSelected() {
    draft.addLocations(selected, "append");
    setSelected([]);
  }

  return (
    <StepPanel title="Areas" copy="Cascade picker or a hand-typed area — builds the area queue this job runs over.">
      <div style={{ display: "flex", gap: 8 }}>
        {AREA_MODES.map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            style={{
              padding: "8px 16px",
              fontFamily: font.body,
              fontSize: 12,
              fontWeight: 700,
              textTransform: "uppercase",
              background: mode === m ? color.ink : color.white,
              color: mode === m ? color.white : color.ink,
              border: mode === m ? "none" : `2px solid ${color.ink}`,
              cursor: "pointer",
            }}
          >
            {m}
          </button>
        ))}
        <span style={{ fontFamily: font.body, fontSize: 11, color: color.ink60, alignSelf: "center", marginLeft: 8 }}>
          Radius / Polygon aren&rsquo;t available yet — no geo-shape search exists.
        </span>
      </div>

      {mode === "Cascade" ? (
        <>
          <ZipCascadeSelect onChange={setSelected} />
          <div>
            <NeoButton variant="primary" size="sm" disabled={selected.length === 0} onClick={queueSelected}>
              Add {selected.length || ""} to queue
            </NeoButton>
          </div>
        </>
      ) : (
        <div style={{ display: "flex", gap: 8 }}>
          <div style={{ flex: 1 }}>
            <FieldLabel>Type an area</FieldLabel>
            <div style={{ marginTop: 6 }}>
              <input
                value={typed}
                placeholder="Austin, TX"
                onChange={(e) => setTyped(e.target.value)}
                style={{ width: "100%", height: 40, boxSizing: "border-box", border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, fontSize: 13 }}
              />
            </div>
          </div>
          <div style={{ alignSelf: "flex-end" }}>
            <NeoButton
              variant="secondary"
              disabled={!typed.trim()}
              onClick={() => {
                draft.addLocations(
                  [{ id: `label:${typed.trim().toLowerCase()}`, label: typed.trim(), zipCode: null, city: null, region: null, country: null }],
                  "append",
                );
                setTyped("");
              }}
            >
              Add
            </NeoButton>
          </div>
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <p style={{ margin: 0, fontFamily: font.head, fontSize: 14, letterSpacing: "0.28px", textTransform: "uppercase", color: color.ink }}>
          Area queue ({draft.locations.length})
        </p>
        {draft.locations.length > 0 && (
          <NeoButton variant="ghost" size="sm" onClick={draft.clearLocations}>
            Clear all
          </NeoButton>
        )}
      </div>
      {draft.locations.length === 0 ? (
        <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
          Nothing queued yet — search down to a city above and take some or all of its ZIP codes.
        </p>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {draft.locations.slice(0, 40).map((l) => (
            <span
              key={l.id}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                border: `2px solid ${color.ink}`,
                background: color.sand,
                padding: "4px 12px",
                fontFamily: font.body,
                fontSize: 12,
                color: color.ink,
              }}
            >
              {l.zipCode ? `${l.zipCode} · ${l.city}` : l.label}
              <button
                type="button"
                onClick={() => draft.removeLocation(l.id)}
                style={{ border: "none", background: "transparent", padding: 0, cursor: "pointer", fontSize: 11, color: color.ink }}
              >
                ✕
              </button>
            </span>
          ))}
          {draft.locations.length > 40 && (
            <span style={{ fontFamily: font.body, fontSize: 12, color: color.ink60, alignSelf: "center" }}>
              +{draft.locations.length - 40} more
            </span>
          )}
        </div>
      )}
    </StepPanel>
  );
}

function ToggleRow({
  title,
  copy,
  checked,
  onChange,
  disabled,
  disabledNote,
}: {
  title: string;
  copy: string;
  checked: boolean;
  onChange?: (v: boolean) => void;
  disabled?: boolean;
  disabledNote?: string;
}) {
  return (
    <div style={{ border: `1px solid ${color.rule}`, background: color.white, padding: 16, display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start" }}>
      <div style={{ flex: 1 }}>
        <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 13, color: disabled ? color.ink60 : color.ink }}>{title}</p>
        <p style={{ margin: "4px 0 0", fontFamily: font.body, fontSize: 12, color: color.ink60 }}>{copy}</p>
        {disabled && disabledNote && (
          <p style={{ margin: "4px 0 0", fontFamily: font.body, fontWeight: 700, fontSize: 10, textTransform: "uppercase", color: color.ink60 }}>
            {disabledNote}
          </p>
        )}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange?.(!checked)}
        style={{
          width: 44,
          height: 24,
          border: `3px solid ${color.ink}`,
          background: disabled ? color.rule : checked ? color.green : color.sand,
          position: "relative",
          flexShrink: 0,
          cursor: disabled ? "default" : "pointer",
          opacity: disabled ? 0.6 : 1,
        }}
      >
        <span
          style={{
            position: "absolute",
            top: 1,
            left: checked ? 22 : 1,
            width: 16,
            height: 16,
            background: color.ink,
          }}
        />
      </button>
    </div>
  );
}

function StepEnrichment() {
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<AppSettings>("/api/settings/"),
  });
  const save = useMutation({
    mutationFn: (patch: Partial<AppSettings>) => api.patch<AppSettings>("/api/settings/", patch),
  });

  return (
    <StepPanel title="Enrichment" copy="Optional passes that run after a place is found. Each adds proxy bandwidth and runtime.">
      <ToggleRow
        title="Deep crawl"
        copy="Follow internal links to find contact and about pages beyond the landing page. Installation-wide setting — applies to every job, not just this one."
        checked={settingsQuery.data?.deepCrawlEnabled ?? false}
        onChange={(v) => save.mutate({ deepCrawlEnabled: v })}
      />
      <ToggleRow
        title="Email verification"
        copy="Confirm scraped emails actually accept mail before scoring them as high-quality leads."
        checked={false}
        disabled
        disabledNote="Not yet available"
      />
      <ToggleRow
        title="Tech fingerprint"
        copy="Detect CMS, analytics, and ad-tech stack from each site's page source."
        checked={false}
        disabled
        disabledNote="Not yet available"
      />
      <ToggleRow
        title="Adaptive subdivision depth"
        copy="How aggressively dense areas are split into smaller sub-searches to avoid missing places."
        checked={false}
        disabled
        disabledNote="Not yet available"
      />
    </StepPanel>
  );
}

interface StepReviewProps {
  name: string;
  onNameChange: (v: string) => void;
  runChoice: "now" | "schedule" | "template";
  onRunChoiceChange: (v: "now" | "schedule" | "template") => void;
  saveAsTemplate: boolean;
  onSaveAsTemplateChange: (v: boolean) => void;
}

function RadioRow({
  label,
  copy,
  checked,
  disabled,
  onSelect,
}: {
  label: string;
  copy: string;
  checked: boolean;
  disabled?: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      disabled={disabled}
      onClick={onSelect}
      style={{
        flex: 1,
        textAlign: "left",
        display: "flex",
        gap: 10,
        alignItems: "flex-start",
        padding: 16,
        background: checked ? color.sand : color.white,
        border: `3px solid ${color.ink}`,
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.6 : 1,
      }}
    >
      <span style={{ width: 18, height: 18, border: `3px solid ${color.ink}`, display: "grid", placeItems: "center", flexShrink: 0, marginTop: 2 }}>
        {checked && <span style={{ width: 8, height: 8, background: color.ink }} />}
      </span>
      <span>
        <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink }}>{label}</p>
        <p style={{ margin: "2px 0 0", fontFamily: font.body, fontSize: 12, color: color.ink60 }}>{copy}</p>
        {disabled && (
          <p style={{ margin: "4px 0 0", fontFamily: font.body, fontWeight: 700, fontSize: 10, textTransform: "uppercase", color: color.ink60 }}>
            Coming soon
          </p>
        )}
      </span>
    </button>
  );
}

function StepReview({ name, onNameChange, runChoice, onRunChoiceChange, saveAsTemplate, onSaveAsTemplateChange }: StepReviewProps) {
  const draft = useJobDraft();

  return (
    <StepPanel title="Review & schedule" copy="Name the job, then run it now.">
      <div>
        <FieldLabel>Job name</FieldLabel>
        <div style={{ marginTop: 6 }}>
          <input
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="Plumbers & HVAC — TX/OK"
            style={{ width: "100%", height: 44, boxSizing: "border-box", border: `3px solid ${color.ink}`, padding: "0 12px", fontFamily: font.body, fontSize: 14 }}
          />
        </div>
      </div>

      <div>
        <FieldLabel>Source</FieldLabel>
        <div role="radiogroup" style={{ display: "flex", gap: 16, marginTop: 6 }}>
          <RadioRow
            label="Google Maps"
            copy="Proven scrape path — the default for every job so far."
            checked={draft.source === "google"}
            onSelect={() => draft.setSource("google")}
          />
          <RadioRow
            label="Bing Maps"
            copy="Same keyword/area targeting, run against Bing's map listings instead."
            checked={draft.source === "bing"}
            onSelect={() => draft.setSource("bing")}
          />
        </div>
      </div>

      <div>
        <FieldLabel>When to run</FieldLabel>
        <div role="radiogroup" style={{ display: "flex", gap: 16, marginTop: 6 }}>
          <RadioRow
            label="Run now"
            copy="Start immediately after saving. Uses today's proxy allowance."
            checked={runChoice === "now"}
            onSelect={() => onRunChoiceChange("now")}
          />
          <RadioRow
            label="Attach a schedule"
            copy="Pick an existing schedule or create one after saving this job."
            checked={runChoice === "schedule"}
            disabled
            onSelect={() => {}}
          />
        </div>
      </div>

      <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
        <span
          onClick={() => onSaveAsTemplateChange(!saveAsTemplate)}
          style={{ width: 18, height: 18, border: `3px solid ${color.ink}`, display: "grid", placeItems: "center", flexShrink: 0 }}
        >
          {saveAsTemplate && <span style={{ width: 8, height: 8, background: color.ink }} />}
        </span>
        <span style={{ fontFamily: font.body, fontSize: 13, color: color.ink }}>
          Save this configuration as a reusable template
        </span>
        <input type="checkbox" checked={saveAsTemplate} onChange={(e) => onSaveAsTemplateChange(e.target.checked)} style={{ display: "none" }} />
      </label>

      <div style={{ background: color.sand, border: `2px solid ${color.ink}`, padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        <SummaryRow label="Source" value={draft.source === "bing" ? "Bing Maps" : "Google Maps"} />
        <SummaryRow label="Keywords" value={draft.keywords.length ? draft.keywords.join(", ") : "None"} />
        <SummaryRow
          label="Areas"
          value={
            draft.locations.length
              ? `${draft.locations.length} area(s) across ${new Set(draft.locations.map((l) => l.region ?? l.label)).size} region(s)`
              : "None"
          }
        />
      </div>
    </StepPanel>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.42px", textTransform: "uppercase", color: color.ink60 }}>
        {label}
      </p>
      <p style={{ margin: "2px 0 0", fontFamily: font.body, fontSize: 13, color: color.ink }}>{value}</p>
    </div>
  );
}

export default function JobWizard() {
  const navigate = useNavigate();
  const draft = useJobDraft();
  const { license } = useAuth();
  const [step, setStep] = useState<StepIndex>(0);
  const [jobName, setJobName] = useState("");
  const [runChoice, setRunChoice] = useState<"now" | "schedule" | "template">("now");
  const [saveAsTemplate, setSaveAsTemplate] = useState(false);

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<AppSettings>("/api/settings/"),
  });

  const estimate = useMemo(
    () => estimateCost(draft.keywords.length, draft.locations.length, settingsQuery.data?.deepCrawlEnabled ?? false),
    [draft.keywords.length, draft.locations.length, settingsQuery.data?.deepCrawlEnabled],
  );

  const maxTargets = 2000; // mirrors backend Settings.max_job_targets default; server is authoritative
  const overLimit = estimate.targets > maxTargets;
  const licenseBlocked = license !== null && !license.active;

  const createJob = useMutation({
    mutationFn: async () => {
      const locations = draft.locations.map(({ label, zipCode, city, region, country }) => ({
        label,
        zipCode,
        city,
        region,
        country,
      }));
      if (saveAsTemplate) {
        await api.post("/api/templates/", {
          name: jobName.trim() || "Untitled template",
          keywords: draft.keywords,
          locations,
          source: draft.source,
        });
      }
      return api.post<Job>("/api/jobs/", {
        keywords: draft.keywords,
        locations,
        source: draft.source,
        name: jobName.trim() || undefined,
      });
    },
    onSuccess: (job) => {
      draft.clearKeywords();
      draft.clearLocations();
      navigate(`/results/${job.id}`);
    },
  });

  const canLeaveStep1 = draft.keywords.length > 0;
  const canLeaveStep2 = draft.locations.length > 0;

  function goNext() {
    if (step < 3) setStep((s) => (s + 1) as StepIndex);
  }
  function goBack() {
    if (step > 0) setStep((s) => (s - 1) as StepIndex);
  }

  const blockingBanner = licenseBlocked ? (
    <BlockingBanner
      title="No active license"
      body="Your organization's MapScrape license is inactive or expired. Extend it from the CLI, or contact your account admin."
      code="npm run license -- extend"
    />
  ) : overLimit ? (
    <BlockingBanner
      title="Target limit exceeded"
      body={`${estimate.targets.toLocaleString()} targets (${draft.keywords.length} keywords x ${draft.locations.length} areas) exceeds the ${maxTargets.toLocaleString()} per-job limit — remove keywords or narrow the area queue before continuing.`}
    />
  ) : null;

  return (
    <div>
      <div className="neo-responsive-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <div>
          <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>NEW JOB</h1>
          <p style={{ margin: "4px 0 20px", fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
            Configure keywords, areas, and enrichment before starting.
          </p>
        </div>
        <NeoButton variant="ghost" onClick={() => navigate("/")}>
          Cancel
        </NeoButton>
      </div>

      <Stepper current={step} />

      {blockingBanner && <div style={{ marginBottom: 20 }}>{blockingBanner}</div>}

      {createJob.isError && (
        <div style={{ marginBottom: 20 }}>
          <BlockingBanner
            title="Couldn't start job"
            body={createJob.error instanceof ApiError ? createJob.error.message : "Couldn't reach the API server"}
          />
        </div>
      )}

      <div className="neo-responsive-row" style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
        {step === 0 && <StepKeywords />}
        {step === 1 && <StepAreas />}
        {step === 2 && <StepEnrichment />}
        {step === 3 && (
          <StepReview
            name={jobName}
            onNameChange={setJobName}
            runChoice={runChoice}
            onRunChoiceChange={setRunChoice}
            saveAsTemplate={saveAsTemplate}
            onSaveAsTemplateChange={setSaveAsTemplate}
          />
        )}
        <CostPanel estimate={estimate} overLimit={overLimit} maxTargets={maxTargets} />
      </div>

      <WizardFooter
        onBack={goBack}
        backDisabled={step === 0}
        onNext={step === 3 ? () => createJob.mutate() : goNext}
        nextLabel={step === 3 ? "Save & run job" : `Next: ${["Areas", "Enrichment", "Review", ""][step]}`}
        nextDisabled={
          licenseBlocked ||
          overLimit ||
          (step === 0 && !canLeaveStep1) ||
          (step === 1 && !canLeaveStep2) ||
          (step === 3 && createJob.isPending)
        }
        nextLoading={step === 3 && createJob.isPending}
      />
    </div>
  );
}
