// One consistent colour per job/target/export status, used by the jobs table, the
// target list and the export panel so "running" looks the same everywhere.

import { Chip, CircularProgress } from "@mui/material";
import type { ChipProps } from "@mui/material";

const COLORS: Record<string, ChipProps["color"]> = {
  queued: "default",
  // Not a backend status: the target list splits "queued" into handed-to-a-worker
  // and still behind the concurrency limit, and this is the latter.
  waiting: "default",
  pending: "default",
  running: "info",
  // Held by the user, not by the system — warning rather than default, because a
  // paused job looks idle and the reason it is idle is the point.
  paused: "warning",
  done: "success",
  // Deliberately stopped. Kept visually distinct from "error": one is a decision,
  // the other is a failure, and colouring them the same trains people to ignore red.
  cancelled: "secondary",
  error: "error",
};

// Only "running" spins -- a spinner on "queued" reads as work in progress when
// nothing has been picked up yet.
const SPINNING = new Set(["running"]);

interface Props {
  status: string;
  size?: ChipProps["size"];
}

export default function StatusChip({ status, size = "small" }: Props) {
  return (
    <Chip
      // Remount on status change so the color/border swap has something to
      // transition from instead of a hard cut -- MUI's Chip has no built-in
      // color-change transition.
      key={status}
      size={size}
      variant="outlined"
      color={COLORS[status] ?? "default"}
      label={status}
      icon={SPINNING.has(status) ? <CircularProgress size={12} sx={{ ml: 1 }} /> : undefined}
      sx={{ transition: "background-color 160ms ease, border-color 160ms ease, color 160ms ease" }}
      className="neo-pop"
    />
  );
}
