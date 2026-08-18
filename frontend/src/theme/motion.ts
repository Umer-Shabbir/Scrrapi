// Motion tokens for the neobrutalist system. No motion spec exists in Figma
// (page "00 — Foundations" has color/font/shadow/space only) -- these are a
// deliberately small, consistent set added for app-wide UI feedback: hover/
// press states, state transitions, list mount-in, route change. Kept snappy
// and mechanical (linear/step easing over soft ease-in-out) to match the
// neobrutalist system's flat, hard-edged visual language rather than
// introducing a softer motion language that would clash with it.

export const duration = {
  instant: "80ms",
  fast: "120ms",
  base: "180ms",
  slow: "280ms",
} as const;

export const easing = {
  // Snappy, mechanical -- matches the system's hard shadows/borders better
  // than a soft cubic ease.
  standard: "cubic-bezier(0.2, 0, 0, 1)",
  out: "cubic-bezier(0, 0, 0, 1)",
} as const;

/** Shared button/interactive-control transition -- hover lift, press, focus. */
export const controlTransition = `transform ${duration.fast} ${easing.out}, box-shadow ${duration.fast} ${easing.out}, background ${duration.base} ${easing.standard}, border-color ${duration.base} ${easing.standard}`;

/** Fill/width transitions for bars and meters. */
export const fillTransition = `width ${duration.slow} ${easing.standard}`;
