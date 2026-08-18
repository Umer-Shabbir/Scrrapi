// System Health screen (Figma [SCREEN] system, SCREENLIST.md §19). "The
// honest version of a status page, for the operator running the box."
//
// Figma's mock shows 7 component tiles (incl. BROWSER POOL/OBJECT STORE) and
// a RUN SEED button. This app has neither a persistent browser pool
// (Playwright launches a fresh Chromium per scrape task) nor an object store
// (exports write to local disk) -- both tiles are omitted rather than faked.
// RUN SEED is omitted too: scripts/seed_geo.py is a multi-minute, ~35MB-
// download job with no API-triggerable wrapper. See backend/app/api/routers
// /system.py for the full reasoning. Geo seed counts are real, live reads.
//
// Bug fix applied from SCREENLIST.md: the empty state only replaces the
// queue/workers/geo-seed panels (which genuinely have no history yet) --
// component status tiles stay visible and real, since they check live infra
// health independent of whether any job has ever run. Figma's own empty
// frame kept them fully populated with fake incident data while claiming
// "no monitoring data" elsewhere; this scopes the empty state correctly
// instead of repeating that mismatch.

import { useQuery } from "@tanstack/react-query";
import NeoButton from "../components/neo/NeoButton";
import { api, ApiError } from "../api/client";
import { color, font } from "../theme/neobrutalist";
import type { ComponentStatus, SystemHealthResponse } from "../types";

const COMPONENT_LABELS: [keyof SystemHealthResponse["components"], string][] = [
  ["api", "API"],
  ["appDb", "APP DB"],
  ["geoDb", "GEO DB"],
  ["redis", "REDIS"],
  ["celeryWorkers", "CELERY WORKERS"],
];

function ComponentTile({ label, status }: { label: string; status: ComponentStatus }) {
  const up = status.status === "up";
  return (
    <div style={{ background: color.white, border: `3px solid ${color.ink}`, padding: 14, display: "flex", flexDirection: "column", gap: 6, width: 240 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 12, letterSpacing: "0.24px", color: color.ink }}>{label}</span>
        <div style={{ flex: 1 }} />
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: up ? color.green : color.pink, display: "inline-block" }} />
      </div>
      <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 11, color: color.ink }}>{up ? "UP" : "DOWN"}</span>
      {status.error && (
        <span style={{ fontFamily: font.mono, fontSize: 9.5, color: color.pink, wordBreak: "break-word" }}>{status.error}</span>
      )}
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: "6px 6px 0px 0px black", padding: 16, display: "flex", flexDirection: "column", gap: 8, width: 240 }}>
      <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 11, letterSpacing: "0.33px", textTransform: "uppercase", color: color.ink }}>{label}</span>
      <span style={{ fontFamily: font.head, fontSize: 24, color: color.ink }}>{value}</span>
    </div>
  );
}

function WorkerTable({ workers }: { workers: SystemHealthResponse["workers"] }) {
  if (workers.length === 0) {
    return (
      <div style={{ background: color.white, border: `3px solid ${color.ink}`, padding: 24, maxWidth: 750 }}>
        <span style={{ fontFamily: font.body, fontSize: 13, color: color.ink60 }}>No workers responded.</span>
      </div>
    );
  }
  return (
    <div style={{ background: color.white, border: `3px solid ${color.ink}`, maxWidth: 750, overflowX: "auto" }}>
      <div style={{ display: "flex", background: color.sand, borderBottom: `3px solid ${color.ink}`, height: 36 }}>
        {[["HOSTNAME", 220], ["ACTIVE TASKS", 130], ["LAST HEARTBEAT", 160], ["STATUS", 110]].map(([h, w]) => (
          <div key={h as string} style={{ display: "flex", alignItems: "center", padding: "0 12px", width: w as number, flexShrink: 0 }}>
            <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10, letterSpacing: "0.2px", color: color.ink }}>{h}</span>
          </div>
        ))}
      </div>
      {workers.map((w, i) => (
        <div
          key={w.hostname}
          className="neo-row-enter"
          style={{ display: "flex", height: 40, borderBottom: `3px solid ${color.rule}`, alignItems: "center", ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms` }}
        >
          <div style={{ padding: "0 12px", width: 220, flexShrink: 0 }}>
            <span style={{ fontFamily: font.mono, fontSize: 11, color: color.ink }}>{w.hostname}</span>
          </div>
          <div style={{ padding: "0 12px", width: 130, flexShrink: 0 }}>
            <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink }}>{w.activeTasks}</span>
          </div>
          <div style={{ padding: "0 12px", width: 160, flexShrink: 0 }}>
            <span style={{ fontFamily: font.mono, fontSize: 11, color: color.ink }}>
              {new Date(w.lastHeartbeat).toLocaleTimeString()}
            </span>
          </div>
          <div style={{ padding: "0 12px", width: 110, flexShrink: 0 }}>
            <span
              style={{
                display: "inline-flex", alignItems: "center", padding: "3px 8px",
                border: `2px solid ${color.ink}`, background: w.online ? color.green : color.pink,
                fontFamily: font.body, fontWeight: 700, fontSize: 10, color: color.ink, whiteSpace: "nowrap",
              }}
            >
              {w.online ? "✓ ONLINE" : "✕ UNRESPONSIVE"}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function GeoSeedPanel({ geoSeed }: { geoSeed: SystemHealthResponse["geoSeed"] }) {
  const rows: [string, number][] = [
    ["countries", geoSeed.countries],
    ["states", geoSeed.states],
    ["cities", geoSeed.cities],
    ["postal_codes", geoSeed.postalCodes],
  ];
  return (
    <div style={{ background: color.white, border: `3px solid ${color.ink}`, padding: 14, display: "flex", flexDirection: "column", gap: 8, width: 352 }}>
      {rows.map(([label, count]) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink }}>{label}</span>
          <div style={{ flex: 1 }} />
          <span style={{ fontFamily: font.mono, fontSize: 12, color: count > 0 ? color.green : color.ink60 }}>
            {count.toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}

function VersionPanel({ version }: { version: SystemHealthResponse["version"] }) {
  const rows: [string, string][] = [
    ["API", version.api],
    ["Playwright", version.playwright],
  ];
  return (
    <div style={{ background: color.white, border: `3px solid ${color.ink}`, padding: 14, display: "flex", flexDirection: "column", gap: 6, width: 352 }}>
      {rows.map(([label, value]) => (
        <div key={label} style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
          <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink60 }}>{label}</span>
          <div style={{ flex: 1 }} />
          <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink }}>{value}</span>
        </div>
      ))}
    </div>
  );
}

function TilesSkeleton() {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 14, maxWidth: 1020 }}>
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} className="neo-skeleton" style={{ width: 240, height: 108, border: `3px solid ${color.ink}` }} />
      ))}
    </div>
  );
}

export default function System() {
  const query = useQuery({
    queryKey: ["system-health"],
    queryFn: () => api.get<SystemHealthResponse>("/api/system/"),
    // Live infra status goes stale fast -- refetch periodically rather than
    // once on mount, same reasoning as Dashboard's recent-jobs polling.
    refetchInterval: 10_000,
  });

  const data = query.data;
  const hasHistory = !!data && (
    data.queueDepth.queued > 0 || data.queueDepth.dispatched > 0 ||
    data.queueDepth.running > 0 || data.queueDepth.waiting > 0 ||
    data.workers.length > 0 ||
    data.geoSeed.countries > 0 || data.geoSeed.states > 0 ||
    data.geoSeed.cities > 0 || data.geoSeed.postalCodes > 0
  );

  return (
    <div>
      <div className="neo-responsive-header" style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>SYSTEM HEALTH</h1>
        <p style={{ margin: "4px 0 0", fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink60 }}>
          The honest version of a status page, for the operator running the box.
        </p>
      </div>

      {query.isLoading && <TilesSkeleton />}

      {query.isError && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "48px 0" }}>
          <div style={{ width: 64, height: 64, background: color.pink, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>SYSTEM HEALTH CHECK FAILED</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 400 }}>
            The monitoring API did not respond. Component status could not be verified.
          </p>
          <p style={{ margin: 0, fontFamily: font.mono, fontSize: 12, color: color.ink60 }}>
            {query.error instanceof ApiError ? query.error.message : "ERR_HEALTHCHECK_TIMEOUT"}
          </p>
          <NeoButton variant="destructive" onClick={() => query.refetch()}>
            Retry
          </NeoButton>
        </div>
      )}

      {data && (
        <>
          <div className="neo-responsive-stats" style={{ display: "flex", flexWrap: "wrap", gap: 14, marginBottom: 24, maxWidth: 1020 }}>
            {COMPONENT_LABELS.map(([key, label]) => (
              <ComponentTile key={key} label={label} status={data.components[key]} />
            ))}
          </div>

          {!hasHistory ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "48px 0" }}>
              <div style={{ width: 64, height: 64, background: color.yellow, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
              <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>NO MONITORING DATA YET</h2>
              <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 420 }}>
                Queue depth, worker activity, and geo seed status will appear once jobs start running.
              </p>
              <NeoButton variant="primary" onClick={() => (window.location.href = "/jobs/new")}>
                Start a job
              </NeoButton>
            </div>
          ) : (
            <>
              <p style={{ margin: "0 0 12px", fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>
                QUEUE DEPTH
              </p>
              <div className="neo-responsive-stats" style={{ display: "flex", gap: 14, marginBottom: 24, maxWidth: 1020 }}>
                <StatTile label="Queued" value={data.queueDepth.queued} />
                <StatTile label="Dispatched" value={data.queueDepth.dispatched} />
                <StatTile label="Running" value={data.queueDepth.running} />
                <StatTile label="Waiting" value={data.queueDepth.waiting} />
              </div>

              <div className="neo-responsive-row" style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
                <div>
                  <p style={{ margin: "0 0 12px", fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>
                    WORKERS
                  </p>
                  <WorkerTable workers={data.workers} />
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
                  <div>
                    <p style={{ margin: "0 0 12px", fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>
                      GEO SEED STATUS
                    </p>
                    <GeoSeedPanel geoSeed={data.geoSeed} />
                  </div>
                  <div>
                    <p style={{ margin: "0 0 12px", fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>
                      VERSION
                    </p>
                    <VersionPanel version={data.version} />
                  </div>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
