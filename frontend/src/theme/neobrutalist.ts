// Design tokens for the neobrutalist Figma system (page "00 — Foundations",
// node 0:1). Not merged into the MUI theme in theme.ts -- screens are being
// migrated one at a time (see CLAUDE.md), so this coexists with the default
// MUI palette until every screen using AppLayout has been rebuilt.

export const color = {
  ink: "#111111",
  white: "#ffffff",
  ink60: "#6b6b63",
  blue: "#4d7fff",
  pink: "#ff5c8a",
  yellow: "#ffd23f",
  green: "#3ddc84",
  purple: "#b18cff",
  orange: "#ff8a3d",
  sand: "#f2eedd",
  rule: "#e4dcc4",
  bg: "#fff9ec",
} as const;

export const font = {
  head: "'Archivo Black', sans-serif",
  body: "'Space Grotesk', sans-serif",
  mono: "'JetBrains Mono', monospace",
} as const;

export const shadow = {
  sm: `4px 4px 0px ${color.ink}`,
  md: `6px 6px 0px ${color.ink}`,
  // Drawers offset toward their content rather than away from it (Figma:
  // Feedback/Drawer, e.g. lead-detail's right-edge drawer shadows left).
  lg: `-10px 10px 0px ${color.ink}`,
} as const;

export const space = {
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 20,
  6: 24,
  8: 32,
} as const;

// Responsive breakpoints (Figma frames are authored at 1440/1024/768 --
// SCREENLIST.md cross-cutting #4: 768 was attempted on only 5/23 screens and
// broken wherever it was). Max-width, mobile-first cascade: rules at a
// smaller breakpoint override the wider one below them in source order.
export const breakpoint = {
  tablet: 1024,
  mobile: 768,
} as const;

export const mq = {
  tablet: `(max-width: ${breakpoint.tablet}px)`,
  mobile: `(max-width: ${breakpoint.mobile}px)`,
} as const;

// Flat 70% ink scrim, the one convention every modal/drawer/menu backdrop in
// this system shares (cross-cutting #8 -- found short of spec, reading as a
// ~35-50% wash, on templates' delete-confirm, settings' purge-confirm, all 6
// onboarding frames, plus ad hoc copies in LeadDetailDrawer/JobControls that
// happened to already match this value by coincidence, not by sharing a
// token). Single source of truth so a future spec change is a one-line edit.
export const scrim = "rgba(17,17,17,0.7)";
