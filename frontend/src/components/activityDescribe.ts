// Shared "turn one activity event into a human-readable line" logic, used by
// both ActivityFeed (one job) and SystemLogPanel (every job, on the
// Dashboard). Split out of ActivityFeed.tsx rather than duplicated so the two
// panels can never drift on what a given event `type` means.

import { color } from "../theme/neobrutalist";
import type { JobActivityEvent } from "../hooks/useJobSocket";

export type Tone = "info" | "success" | "warning" | "error" | "muted";

export const TONE_COLOR: Record<Tone, string> = {
  info: color.blue,
  success: color.green,
  warning: color.orange,
  error: color.pink,
  muted: color.ink60,
};

export interface Line {
  title: string;
  detail?: string;
  tone: Tone;
}

/** Join the fields a place actually yielded, so an empty one is visibly empty. */
function fieldSummary(entry: JobActivityEvent): string {
  const source = entry.result ?? entry;
  const parts = [
    source.phone && `☎ ${source.phone}`,
    source.email && `✉ ${source.email}`,
    source.website && `🌐 ${hostOf(String(source.website))}`,
    source.address && String(source.address).replace(/\s+/g, " "),
  ].filter(Boolean) as string[];
  return parts.length ? parts.join("  ·  ") : "no contact details found";
}

function hostOf(url: string): string {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function describeActivity(entry: JobActivityEvent): Line {
  switch (entry.type) {
    case "target_started":
      return {
        title: `Searching "${entry.keyword}" in ${entry.location}`,
        detail: entry.searchUrl,
        tone: "info",
      };
    case "feed_done":
      return {
        title: `Found ${entry.placesFound} place${entry.placesFound === 1 ? "" : "s"} for "${entry.keyword}"`,
        detail: entry.placesFound ? "scraping each one now" : "the search returned nothing",
        tone: entry.placesFound ? "info" : "warning",
      };
    case "place_started":
      return { title: "Opening place page", detail: entry.placeUrl, tone: "muted" };
    case "place_detail":
      return {
        title: entry.name ?? "Place page loaded",
        detail: `${fieldSummary(entry)} — looking for a website and email…`,
        tone: "info",
      };
    case "site_crawled": {
      const found = [
        `${entry.emailsFound ?? 0} email${entry.emailsFound === 1 ? "" : "s"}`,
        `${entry.phonesFound ?? 0} phone${entry.phonesFound === 1 ? "" : "s"}`,
        entry.networks?.length ? entry.networks.join(", ") : null,
      ]
        .filter(Boolean)
        .join("  ·  ");
      return {
        title: `Crawled ${entry.pagesCrawled ?? 0} page${entry.pagesCrawled === 1 ? "" : "s"} of the website`,
        // "12 of 340" is the honest reading when the page budget cut the crawl
        // short — otherwise the count reads as "that was the whole site".
        detail: entry.truncated
          ? `${found} — stopped at the page budget (${entry.pagesDiscovered ?? 0} pages seen)`
          : found,
        tone: (entry.emailsFound ?? 0) + (entry.phonesFound ?? 0) > 0 ? "success" : "muted",
      };
    }
    case "result":
      return {
        title: `${entry.result?.name ?? "Lead"} saved`,
        detail: fieldSummary(entry),
        tone: "success",
      };
    case "place_skipped":
      return { title: "Skipped a place", detail: entry.reason, tone: "warning" };
    case "retry":
      return {
        title: entry.rateLimited
          ? `Rate limited — backing off ${entry.countdownS}s`
          : `Retrying in ${entry.countdownS}s (attempt ${entry.attempt}/${entry.maxRetries})`,
        detail: entry.error,
        tone: "warning",
      };
    case "place_error":
      return { title: "Place failed", detail: entry.error, tone: "error" };
    case "target_error":
      return {
        title: `Search failed for "${entry.keyword}" in ${entry.location}`,
        detail: entry.error,
        tone: "error",
      };
    case "target_done":
      return {
        title: `Finished "${entry.keyword}" in ${entry.location}`,
        detail: `${entry.placesFound} place${entry.placesFound === 1 ? "" : "s"} scraped`,
        tone: "success",
      };
    case "job_done":
      return {
        title: `Job ${entry.status}`,
        detail: `${entry.resultsCount} lead${entry.resultsCount === 1 ? "" : "s"} in total`,
        tone: entry.status === "error" ? "error" : "success",
      };
    // The three below come from the control endpoints rather than a worker. The
    // pause line spells out that running areas are still going, because the feed
    // carrying on afterwards is otherwise the first thing that looks broken.
    case "job_paused":
      return {
        title: "Paused by you",
        detail: entry.stillRunning
          ? `${entry.released ?? 0} queued area(s) taken off the queue · ${entry.stillRunning} still scraping and will finish`
          : `${entry.released ?? 0} queued area(s) taken off the queue`,
        tone: "warning",
      };
    case "job_resumed":
      return {
        title: "Resumed",
        detail: entry.dispatched
          ? `${entry.dispatched} area(s) started`
          : "waiting for a free slot",
        tone: "info",
      };
    case "job_cancelled":
      return {
        title: "Cancelled by you",
        detail: `${entry.targetsCancelled ?? 0} unfinished area(s) dropped — leads already collected are kept`,
        tone: "warning",
      };
    default:
      return { title: entry.type, tone: "muted" };
  }
}

export function clockTime(ms: number): string {
  return new Date(ms).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
