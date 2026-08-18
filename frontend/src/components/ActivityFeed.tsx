// Live worker activity for one job, newest first. Neobrutalist rebuild --
// replaces the legacy MUI (Paper/List/Divider/Box/Typography) with the same
// ink-border-card + plain-list pattern used elsewhere on Results.
//
// The results grid answers "what did we get"; this answers "what is it doing
// right now" -- the place currently open, the fields that came off it, a target
// that finished, a retry and how long it's backing off for. Fed by the activity
// frames on the job WebSocket (see hooks/useJobSocket.ts).

import { color, font } from "../theme/neobrutalist";
import type { JobActivityEntry } from "../hooks/useJobSocket";
import { TONE_COLOR, clockTime, describeActivity } from "./activityDescribe";

interface Props {
  entries: JobActivityEntry[];
  connected: boolean;
  live: boolean;
}

export default function ActivityFeed({ entries, connected, live }: Props) {
  return (
    <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: "6px 6px 0px 0px #111" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 16px", borderBottom: `2px solid ${color.rule}` }}>
        <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink, textTransform: "uppercase" }}>
          Live activity
        </p>
        <span
          className={connected ? "neo-pulse-square" : undefined}
          style={{ fontFamily: font.body, fontWeight: 500, fontSize: 11, color: color.ink60 }}
        >
          {connected ? "connected" : live ? "reconnecting…" : "stream closed"}
        </span>
      </div>
      <div style={{ maxHeight: 320, overflowY: "auto" }}>
        {entries.length === 0 ? (
          <p style={{ margin: 0, padding: "16px", fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
            {live ? "Waiting for the worker to pick the job up…" : "No activity recorded."}
          </p>
        ) : (
          entries.map((entry) => {
            const line = describeActivity(entry);
            return (
              <div
                key={entry.seq}
                style={{ display: "flex", gap: 12, padding: "10px 16px", borderTop: `1px solid ${color.rule}`, alignItems: "flex-start" }}
              >
                <span style={{ fontFamily: font.mono, fontSize: 11, color: color.ink60, whiteSpace: "nowrap", marginTop: 2, flexShrink: 0 }}>
                  {clockTime(entry.receivedAt)}
                </span>
                <div style={{ minWidth: 0 }}>
                  <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 13, color: TONE_COLOR[line.tone] === color.ink60 ? color.ink : color.ink }}>
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
