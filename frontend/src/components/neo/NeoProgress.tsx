// Data/Progress (page "01 — Components", node 29:106). Determinate: 16px bar,
// 3px ink border, sand track, blue fill, percentage outside the bar. Meter
// (quota-style thresholds) isn't used yet -- no screen has real quota data.

import { color, font } from "../../theme/neobrutalist";

interface NeoProgressProps {
  pct: number;
  width?: number;
  showLabel?: boolean;
}

export default function NeoProgress({ pct, width = 100, showLabel = true }: NeoProgressProps) {
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 12 }}>
      <span
        style={{
          display: "block",
          width,
          height: 16,
          border: `3px solid ${color.ink}`,
          background: color.sand,
          position: "relative",
          boxSizing: "border-box",
        }}
      >
        <span
          style={{
            display: "block",
            position: "absolute",
            left: 0,
            top: 0,
            height: 10,
            width: `${clamped}%`,
            background: color.blue,
            // Fill eases toward its new width instead of jumping -- progress
            // that visibly moves reads as "actively updating," a flat jump
            // reads as a static number relabeled.
            transition: "width 280ms cubic-bezier(0.2, 0, 0, 1)",
          }}
        />
      </span>
      {showLabel && (
        <span
          style={{
            fontFamily: font.body,
            fontWeight: 700,
            fontSize: "10.5px",
            letterSpacing: "0.315px",
            textTransform: "uppercase",
            color: color.ink,
            whiteSpace: "nowrap",
          }}
        >
          {Math.round(clamped)}%
        </span>
      )}
    </span>
  );
}
