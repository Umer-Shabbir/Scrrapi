// App theme. Light and dark are the same palette with the surface colours flipped,
// so the mode toggle in the app bar doesn't change how anything is laid out.

import { createTheme } from "@mui/material";
import type { PaletteMode, Theme } from "@mui/material";

export const MODE_STORAGE_KEY = "color_mode";

export function loadMode(): PaletteMode {
  const stored = localStorage.getItem(MODE_STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function buildTheme(mode: PaletteMode): Theme {
  const dark = mode === "dark";
  return createTheme({
    palette: {
      mode,
      primary: { main: dark ? "#7aa2f7" : "#2f5bd7" },
      secondary: { main: dark ? "#bb9af7" : "#7048c4" },
      success: { main: dark ? "#7bcf8e" : "#2e7d4f" },
      warning: { main: dark ? "#e0af68" : "#a86b12" },
      error: { main: dark ? "#f7768e" : "#c62839" },
      background: {
        default: dark ? "#11141c" : "#f5f6f9",
        paper: dark ? "#181c26" : "#ffffff",
      },
    },
    shape: { borderRadius: 10 },
    typography: {
      fontFamily:
        '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      h5: { fontWeight: 600 },
      h6: { fontWeight: 600 },
      subtitle2: { fontWeight: 600 },
    },
    components: {
      // Inline <code> shows up in a fair few hints ("run npm run seed"), and
      // unstyled it just reads as oddly-spaced prose.
      MuiCssBaseline: {
        styleOverrides: {
          code: {
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
            fontSize: "0.85em",
            padding: "1px 5px",
            borderRadius: 4,
            backgroundColor: dark ? "rgba(255,255,255,0.09)" : "rgba(0,0,0,0.06)",
          },
        },
      },
      MuiButton: { defaultProps: { disableElevation: true } },
      MuiTextField: { defaultProps: { size: "small" } },
      MuiSelect: { defaultProps: { size: "small" } },
    },
  });
}
