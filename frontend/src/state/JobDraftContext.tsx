// The keyword list and the location queue are built on two separate pages but
// consumed by a third (Dashboard, which crosses them into JobTargets). Neither is
// persisted server-side -- `categories.py` only supplies suggestions and parses
// uploads, and there's no locations table -- so the working draft lives here and
// is mirrored to localStorage so a refresh mid-setup doesn't lose it.
//
// Locations are ZIP-scoped objects rather than plain strings: one search runs per
// postal code, and the ZIP has to survive all the way to `create_job` so the
// results it produces can be attributed back to it.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { JobSource, LocationTarget } from "../types";

const STORAGE_KEY = "job_draft";

/** Append to what's queued, or throw the queue away and start from this batch. */
export type QueueMode = "append" | "replace";

export interface JobDraft {
  keywords: string[];
  locations: LocationTarget[];
  /** Which maps provider the job runs against. Defaults to "google" -- the
   * only option before the Bing scraper existed, and still the safer default
   * since Bing's feed scroller carries a "run it manually first" warning. */
  source: JobSource;
}

interface JobDraftContextValue extends JobDraft {
  /** Adds trimmed, case-insensitively deduplicated entries. Returns how many landed. */
  addKeywords: (values: string[]) => number;
  /**
   * Queues search areas. `mode` is the append-or-replace choice made on the
   * Locations page; "replace" returns the whole incoming count, since nothing
   * was there to collide with.
   */
  addLocations: (values: LocationTarget[], mode?: QueueMode) => number;
  removeKeyword: (value: string) => void;
  /** By `LocationTarget.id`, not by label — two labels can read alike. */
  removeLocation: (id: string) => void;
  clearKeywords: () => void;
  clearLocations: () => void;
  setSource: (source: JobSource) => void;
  /** Keyword x location -- the number of JobTargets a job would create right now. */
  targetCount: number;
}

const JobDraftContext = createContext<JobDraftContextValue | null>(null);

function mergeKeywords(existing: string[], incoming: string[]): string[] {
  const seen = new Set(existing.map((v) => v.toLowerCase()));
  const merged = [...existing];
  for (const raw of incoming) {
    const value = raw.trim();
    if (!value) continue;
    const key = value.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(value);
  }
  return merged;
}

function mergeLocations(existing: LocationTarget[], incoming: LocationTarget[]): LocationTarget[] {
  // Keyed on the label rather than the id: the same ZIP reached through a
  // city-level and a state-level listing is the same search either way.
  const seen = new Set(existing.map((l) => l.label.toLowerCase()));
  const merged = [...existing];
  for (const entry of incoming) {
    const label = entry.label.trim();
    if (!label) continue;
    const key = label.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push({ ...entry, label });
  }
  return merged;
}

/** A typed-in location: a label with no ZIP under it. Kept usable before `npm run seed`. */
export function labelToLocation(raw: string): LocationTarget {
  const label = raw.trim();
  return { id: `label:${label.toLowerCase()}`, label, zipCode: null, city: null, region: null, country: null };
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

/**
 * Locations used to be `string[]`. A draft saved by that version is still in
 * localStorage on every existing install, so read it back as label-only targets
 * rather than dropping someone's queue on upgrade.
 */
function parseLocations(raw: unknown): LocationTarget[] {
  if (!Array.isArray(raw)) return [];
  const out: LocationTarget[] = [];
  for (const entry of raw) {
    if (isString(entry)) {
      if (entry.trim()) out.push(labelToLocation(entry));
      continue;
    }
    if (!entry || typeof entry !== "object") continue;
    const candidate = entry as Partial<LocationTarget>;
    if (!isString(candidate.label) || !candidate.label.trim()) continue;
    out.push({
      id: isString(candidate.id) ? candidate.id : `label:${candidate.label.toLowerCase()}`,
      label: candidate.label.trim(),
      zipCode: isString(candidate.zipCode) ? candidate.zipCode : null,
      city: isString(candidate.city) ? candidate.city : null,
      region: isString(candidate.region) ? candidate.region : null,
      country: isString(candidate.country) ? candidate.country : null,
    });
  }
  return out;
}

function loadDraft(): JobDraft {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { keywords: [], locations: [], source: "google" };
    const parsed = JSON.parse(raw) as Partial<JobDraft>;
    return {
      keywords: Array.isArray(parsed.keywords) ? parsed.keywords.filter(isString) : [],
      locations: parseLocations(parsed.locations),
      // A draft saved before the source toggle existed has no `source` key --
      // default it to "google" rather than dropping the rest of the draft.
      source: parsed.source === "bing" ? "bing" : "google",
    };
  } catch {
    return { keywords: [], locations: [], source: "google" };
  }
}

export function JobDraftProvider({ children }: { children: ReactNode }) {
  const [draft, setDraft] = useState<JobDraft>(loadDraft);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
  }, [draft]);

  // Each adder returns the count actually added so the calling page can say
  // "added 3 of 10" rather than claiming it took everything in the file.
  const addKeywords = useCallback((values: string[]) => {
    let added = 0;
    setDraft((prev) => {
      const keywords = mergeKeywords(prev.keywords, values);
      added = keywords.length - prev.keywords.length;
      return { ...prev, keywords };
    });
    return added;
  }, []);

  const addLocations = useCallback((values: LocationTarget[], mode: QueueMode = "append") => {
    let added = 0;
    setDraft((prev) => {
      const base = mode === "replace" ? [] : prev.locations;
      const locations = mergeLocations(base, values);
      added = locations.length - base.length;
      return { ...prev, locations };
    });
    return added;
  }, []);

  const value = useMemo<JobDraftContextValue>(
    () => ({
      ...draft,
      addKeywords,
      addLocations,
      removeKeyword: (v) =>
        setDraft((prev) => ({ ...prev, keywords: prev.keywords.filter((k) => k !== v) })),
      removeLocation: (id) =>
        setDraft((prev) => ({ ...prev, locations: prev.locations.filter((l) => l.id !== id) })),
      clearKeywords: () => setDraft((prev) => ({ ...prev, keywords: [] })),
      clearLocations: () => setDraft((prev) => ({ ...prev, locations: [] })),
      setSource: (source) => setDraft((prev) => ({ ...prev, source })),
      targetCount: draft.keywords.length * draft.locations.length,
    }),
    [draft, addKeywords, addLocations],
  );

  return <JobDraftContext.Provider value={value}>{children}</JobDraftContext.Provider>;
}

export function useJobDraft(): JobDraftContextValue {
  const ctx = useContext(JobDraftContext);
  if (!ctx) throw new Error("useJobDraft must be used inside <JobDraftProvider>");
  return ctx;
}

/** Splits pasted keyword text on commas, semicolons and newlines. */
export const KEYWORD_SEPARATORS = /[,;\n\r]+/;

/**
 * Locations keep their commas -- "Austin, TX" is one location, not two -- so only
 * newlines and semicolons separate them.
 */
export const LOCATION_SEPARATORS = /[;\n\r]+/;
