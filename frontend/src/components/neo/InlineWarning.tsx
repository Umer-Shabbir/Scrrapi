// Cross-cutting #12 (SCREENLIST.md): the "!" warning glyph was a typed
// character standing in for an icon, on login and (once audited further)
// nearly every inline error/warning banner sitewide -- one shared component
// so every one of those sites gets a real icon in a single pass instead of
// per-file glyph swaps.

import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import { color as colorTokens, font } from "../../theme/neobrutalist";

interface InlineWarningProps {
  children: React.ReactNode;
  /** Matches the text color the call site used to hand-set on its own `<p>`
   * -- ink for a neutral note, pink for a hard failure. */
  tone?: "ink" | "pink";
  fontSize?: number;
  fontWeight?: 400 | 500 | 700;
}

export default function InlineWarning({ children, tone = "pink", fontSize = 12, fontWeight = 700 }: InlineWarningProps) {
  const textColor = tone === "pink" ? colorTokens.pink : colorTokens.ink;
  return (
    <p
      style={{
        margin: 0,
        display: "flex",
        alignItems: "center",
        gap: 6,
        fontFamily: font.body,
        fontWeight,
        fontSize,
        color: textColor,
      }}
    >
      <WarningAmberIcon sx={{ fontSize: fontSize + 4, color: textColor, flexShrink: 0 }} />
      <span>{children}</span>
    </p>
  );
}
