// Live cross-job event feed for the Dashboard's log panel. Backend:
// WS /api/system/events/stream (see backend/app/api/routers/system.py).
//
// Same frame shape as the per-job activity stream (see useJobSocket.ts's
// JobActivityEvent) plus `jobId`, since a line here isn't scoped to a job the
// page already knows about. Deliberately its own hook rather than reusing
// useJobSocket with an optional jobId -- that hook's `progress` half (status,
// results/places counts) has no cross-job equivalent, so sharing the type
// would mean every consumer handling a `progress` case that can never fire
// here.

import { useEffect, useRef, useState } from "react";
import { getToken } from "../api/client";
import type { JobActivityEvent } from "./useJobSocket";

function wsBaseUrl(): string {
  const configured = import.meta.env.VITE_WS_BASE_URL;
  if (configured) return configured;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}`;
}

export interface SystemLogEntry extends JobActivityEvent {
  jobId: string;
  /** Client-side sequence number; the stream carries no id of its own. */
  seq: number;
  receivedAt: number;
}

// A live view, not an audit log -- same reasoning and cap as ActivityFeed's
// MAX_ACTIVITY, just wider since it's aggregating every job at once.
const MAX_ENTRIES = 500;

export interface SystemLogSocketState {
  entries: SystemLogEntry[];
  connected: boolean;
}

// Same reconnect-with-backoff reasoning as useJobSocket -- a dropped socket must
// not mean "log panel is frozen until you refresh the page."
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 15000;

export function useSystemLogSocket(enabled: boolean): SystemLogSocketState {
  const [entries, setEntries] = useState<SystemLogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    if (!enabled) return;

    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let stopped = false;

    const connect = () => {
      const token = getToken() ?? "";
      socket = new WebSocket(
        `${wsBaseUrl()}/api/system/events/stream?token=${encodeURIComponent(token)}`,
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
        const frame = JSON.parse(event.data) as JobActivityEvent & { jobId: string };
        const entry: SystemLogEntry = { ...frame, seq: seq.current++, receivedAt: Date.now() };
        setEntries((previous) => [entry, ...previous].slice(0, MAX_ENTRIES));
      };
    };

    connect();

    return () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (!socket) return;
      socket.onclose = null;
      if (socket.readyState === WebSocket.CONNECTING) {
        socket.onopen = () => socket?.close();
      } else {
        socket.close();
      }
      setConnected(false);
    };
  }, [enabled]);

  return { entries, connected };
}
