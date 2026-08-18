// Status/Badge (page "01 — Components", node 17:34). 2px ink border, flat
// semantic fill, uppercase text with a 1-char glyph prefix so state survives
// grayscale. Text stays ink-colored on every fill, including pink, per spec
// (badge text is below the size threshold for safe white-on-pink).

import { color, font } from "../../theme/neobrutalist";
import type { JobStatus } from "../../types";

const FILL: Record<JobStatus, string> = {
  queued: color.sand,
  running: color.blue,
  paused: color.yellow,
  done: color.green,
  error: color.pink,
  cancelled: color.sand,
};

const GLYPH: Record<JobStatus, string> = {
  queued: "•",
  running: "●",
  paused: "!",
  done: "✓",
  error: "✕",
  cancelled: "✕",
};

export default function NeoStatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      key={status}
      className="neo-pop"
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        height: 18,
        minWidth: 80,
        padding: "0 8px",
        border: `2px solid ${color.ink}`,
        background: FILL[status] ?? color.sand,
        fontFamily: font.body,
        fontWeight: 700,
        fontSize: "10.5px",
        letterSpacing: "0.42px",
        textTransform: "uppercase",
        color: color.ink,
        whiteSpace: "nowrap",
        transition: "background 160ms cubic-bezier(0.2, 0, 0, 1)",
      }}
    >
      <span className={status === "running" ? "neo-pulse-square" : undefined} style={{ display: "inline-block" }}>
        {GLYPH[status] ?? "•"}
      </span>{" "}
      {status}
    </span>
  );
}
