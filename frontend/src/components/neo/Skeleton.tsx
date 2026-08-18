// Feedback/Skeleton (page "01 — Components", node 34:86). Cross-cutting #9:
// loading placeholders across the app were flat, unshaped grey blocks (a bare
// `<div className="neo-skeleton" style={{ height }} />`) that don't read as
// "a table is loading" or "a card grid is loading" the way the rest of this
// system's bold-border/hard-shadow language does everywhere else. These
// variants wrap the same `.neo-skeleton` shimmer (animations.css) in the
// actual shape of the content they stand in for, ink-bordered like every
// other surface in the system.

import { color } from "../../theme/neobrutalist";

/** A single table row's worth of skeleton cells, ink rule between rows same
 * as a real `<tr>` -- for Data/Table loading states (categories, api-keys,
 * audit, team, ...). */
export function SkeletonRow({ columns = 5, height = 14 }: { columns?: number; height?: number }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "10px 12px",
        borderTop: `1px solid ${color.rule}`,
      }}
    >
      {Array.from({ length: columns }).map((_, i) => (
        <div
          key={i}
          className="neo-skeleton"
          style={{ height, flex: i === 0 ? 2 : 1, minWidth: 0 }}
        />
      ))}
    </div>
  );
}

/** A stack of SkeletonRow, for a whole table body -- pass the same column
 * count the real table renders. */
export function SkeletonTable({ rows = 6, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <div style={{ border: `3px solid ${color.ink}`, background: color.white }}>
      <div style={{ height: 36, background: color.sand, borderBottom: `3px solid ${color.ink}` }} />
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonRow key={i} columns={columns} />
      ))}
    </div>
  );
}

/** One card-shaped block -- ink border + hard shadow like a real
 * Card/TemplateCard or Card/StatTile, for grid/card-layout loading states
 * (integrations' provider cards, system's component tiles). */
export function SkeletonCard({ height = 120 }: { height?: number }) {
  return (
    <div
      style={{
        height,
        border: `3px solid ${color.ink}`,
        boxShadow: "6px 6px 0px 0px #111",
        background: color.white,
        padding: 14,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        boxSizing: "border-box",
      }}
    >
      <div className="neo-skeleton" style={{ height: 14, width: "60%" }} />
      <div className="neo-skeleton" style={{ height: 10, width: "40%" }} />
      <div style={{ flex: 1 }} />
      <div className="neo-skeleton" style={{ height: 24, width: "50%" }} />
    </div>
  );
}

/** Card/StatTile shape -- ink border + hard shadow, label-line then a bigger
 * value-line, for stat-row loading states (system's service-status cards). */
export function SkeletonStatTile() {
  return (
    <div
      style={{
        flex: 1,
        border: `3px solid ${color.ink}`,
        boxShadow: "6px 6px 0px 0px #111",
        background: color.white,
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        boxSizing: "border-box",
      }}
    >
      <div className="neo-skeleton" style={{ height: 11, width: "70%" }} />
      <div className="neo-skeleton" style={{ height: 24, width: "45%" }} />
    </div>
  );
}

/** A row of SkeletonStatTile -- drop-in for a stat-tile grid's loading state. */
export function SkeletonStatRow({ count = 4 }: { count?: number }) {
  return (
    <div style={{ display: "flex", gap: 16, width: "100%" }}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonStatTile key={i} />
      ))}
    </div>
  );
}
