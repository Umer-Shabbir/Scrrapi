// Cross-job live log panel for the Dashboard. Not a Figma screen -- there is
// no design frame for this; built freehand at the user's explicit request to
// see what every worker is doing at once without tailing a terminal that was
// crashing under the log volume (see backend/app/core/logging.py's console
// noise fix, the other half of that same request).
//
// Same visual language as ActivityFeed (ink-border card, tone-dot rows) and
// the same describeActivity() line logic, since this is that panel widened to
// every job instead of one -- the only real difference is each row also names
// which job it belongs to.

import { color, font } from "../theme/neobrutalist";
import type { SystemLogEntry } from "../hooks/useSystemLogSocket";
import { TONE_COLOR, clockTime, describeActivity } from "./activityDescribe";

interface Props {
  entries: SystemLogEntry[];
  connected: boolean;
}

export default function SystemLogPanel({ entries, connected }: Props) {
  return (
    <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: "6px 6px 0px 0px #111" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 16px", borderBottom: `2px solid ${color.rule}` }}>
        <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink, textTransform: "uppercase" }}>
          Live log
        </p>
        <span
          className={connected ? "neo-pulse-square" : undefined}
          style={{ fontFamily: font.body, fontWeight: 500, fontSize: 11, color: color.ink60 }}
        >
          {connected ? "connected" : "reconnecting…"}
        </span>
      </div>
      <div style={{ maxHeight: 360, overflowY: "auto" }}>
        {entries.length === 0 ? (
          <p style={{ margin: 0, padding: "16px", fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
            Nothing running right now — this fills in the moment a job starts.
          </p>
        ) : (
          entries.map((entry) => {
            const line = describeActivity(entry);
            return (
              <div
                key={entry.seq}
                style={{ display: "flex", gap: 12, padding: "8px 16px", borderTop: `1px solid ${color.rule}`, alignItems: "flex-start" }}
              >
                <span style={{ fontFamily: font.mono, fontSize: 11, color: color.ink60, whiteSpace: "nowrap", marginTop: 2, flexShrink: 0 }}>
                  {clockTime(entry.receivedAt)}
                </span>
                <span
                  style={{
                    fontFamily: font.mono,
                    fontSize: 11,
                    color: color.ink60,
                    whiteSpace: "nowrap",
                    marginTop: 2,
                    flexShrink: 0,
                  }}
                  title={entry.jobId}
                >
                  #{entry.jobId.slice(0, 8)}
                </span>
                <div style={{ minWidth: 0 }}>
                  <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink }}>
                    <span style={{ display: "inline-block", width: 8, height: 8, background: TONE_COLOR[line.tone], border: `1px solid ${color.ink}`, marginRight: 8, verticalAlign: "middle" }} />
                    {line.title}
                  </p>
                  {line.detail && (
                    <p
                      style={{
                        margin: "3px 0 0",
                        fontFamily: line.detail.startsWith("http") ? font.mono : font.body,
                        fontSize: 12,
                        color: color.ink60,
                        overflowWrap: "anywhere",
                      }}
                    >
                      {line.detail}
                    </p>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
