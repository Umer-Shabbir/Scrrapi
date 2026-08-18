// Live job progress over WebSocket. Backend: WS /api/jobs/{id}/stream (see
// backend/app/api/routers/jobs.py).
//
// The socket carries two kinds of frame:
//
//   {kind: "progress", ...}  counts, on every change -- status, results, places
//   {kind: "activity", ...}  one line per thing a worker just did
//
// Progress is a snapshot (keep the latest); activity is a log (append). The
// activity frames are what make the run legible while it's happening: which
// place is open right now, what came off it, what got retried and for how long.

import { useEffect, useRef, useState } from "react";
import { getToken } from "../api/client";
import type { JobTarget } from "../types";

/**
 * Same-origin by default, so the dev server's and nginx's /api proxies carry the
 * socket alongside the REST calls. VITE_WS_BASE_URL overrides it for deployments
 * where the API really is on another host.
 */
function wsBaseUrl(): string {
  const configured = import.meta.env.VITE_WS_BASE_URL;
  if (configured) return configured;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}`;
}

export interface JobProgressEvent {
  jobId: string;
  status: string;
  resultsCount: number;
  placesFound: number;
  placesDone: number;
  targetsTotal: number;
  targetsDone: number;
  /** Areas not started yet because the concurrency limit is full. */
  targetsWaiting: number;
  targets: JobTarget[];
}

/** One worker action. `type` is the discriminator; the rest is free-form. */
export interface JobActivityEvent {
  type: string;
  targetId?: string;
  keyword?: string;
  location?: string;
  placeUrl?: string;
  searchUrl?: string;
  name?: string;
  category?: string;
  address?: string;
  phone?: string;
  email?: string | null;
  website?: string | null;
  placesFound?: number;
  resultsCount?: number;
  reason?: string;
  error?: string;
  status?: string;
  attempt?: number;
  maxRetries?: number;
  countdownS?: number;
  rateLimited?: boolean;
  // `site_crawled`: what the deep website crawl read and found, published once
  // per place, between `place_detail` and `result`.
  pagesCrawled?: number;
  pagesDiscovered?: number;
  truncated?: boolean;
  emailsFound?: number;
  phonesFound?: number;
  networks?: string[];
  // `job_paused` / `job_resumed` / `job_cancelled`: published by the control
  // endpoints, not by a worker, so a pause shows up in the feed alongside the
  // scraping it interrupted.
  released?: number;
  stillRunning?: number;
  dispatched?: number;
  targetsCancelled?: number;
  result?: {
    id: string;
    name: string | null;
    category: string | null;
    address: string | null;
    phone: string | null;
    email: string | null;
    website: string | null;
    /** `{network: [url, ...]}` — only present when the crawler is on. */
    socials?: Record<string, string[]>;
    scrapedAt: string;
  };
}

export interface JobActivityEntry extends JobActivityEvent {
  /** Client-side sequence number; the stream carries no id of its own. */
  seq: number;
  receivedAt: number;
}

// The feed is a live view, not an audit log -- older lines are dropped rather
// than growing the array without bound on a job with thousands of places.
const MAX_ACTIVITY = 300;

export interface JobSocketState {
  progress: JobProgressEvent | null;
  activity: JobActivityEntry[];
  connected: boolean;
}

// Reconnect backoff for a dropped socket -- network blip, backend restart, laptop
// sleep. Without this a closed socket left the page frozen on its last snapshot
// until a manual refresh, which is the single biggest cause of "stats aren't
// updating live." Capped, with jitter, so a real outage doesn't hammer the API.
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 15000;

export function useJobSocket(jobId: string | undefined): JobSocketState {
  const [progress, setProgress] = useState<JobProgressEvent | null>(null);
  const [activity, setActivity] = useState<JobActivityEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    if (!jobId) return;

    setProgress(null);
    setActivity([]);
    seq.current = 0;

    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let stopped = false;

    const connect = () => {
      // Browsers can't set an Authorization header on a WS handshake -- token
      // rides in as a query param instead (backend: _authenticate_ws). Re-read
      // fresh on every (re)connect so a token refreshed mid-session is picked up.
      const token = getToken() ?? "";
      socket = new WebSocket(
        `${wsBaseUrl()}/api/jobs/${jobId}/stream?token=${encodeURIComponent(token)}`,
      );

      socket.onopen = () => {
        attempt = 0;
        setConnected(true);
      };

      socket.onclose = () => {
        setConnected(false);
        if (stopped) return;
        const delay = Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * 2 ** attempt) * (0.75 + Math.random() * 0.5);
        attempt += 1;
        reconnectTimer = setTimeout(connect, delay);
      };

      socket.onmessage = (event) => {
        const frame = JSON.parse(event.data) as { kind?: string } & Record<string, unknown>;
        if (frame.kind === "activity") {
          const entry: JobActivityEntry = {
            ...(frame as unknown as JobActivityEvent),
            seq: seq.current++,
            receivedAt: Date.now(),
          };
          setActivity((previous) => [entry, ...previous].slice(0, MAX_ACTIVITY));
          return;
        }
        // Anything else is a progress snapshot (older backends sent it untagged).
        setProgress(frame as unknown as JobProgressEvent);
      };
    };

    connect();

    return () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (!socket) return;
      socket.onclose = null;
      // Closing a socket still in CONNECTING throws in some browsers; wait for the
      // handshake to land, then close immediately.
      if (socket.readyState === WebSocket.CONNECTING) {
        socket.onopen = () => socket?.close();
      } else {
        socket.close();
      }
      setConnected(false);
    };
  }, [jobId]);

  return { progress, activity, connected };
}
