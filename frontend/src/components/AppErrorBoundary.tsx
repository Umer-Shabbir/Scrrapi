// 500 / crash boundary (Figma [SCREEN] not-found — 500, SCREENLIST.md §23).
// Genuinely missing before this cycle -- no React error boundary existed
// anywhere in the app, so an uncaught render error previously blanked the
// page to nothing (React unmounts the tree past the nearest boundary; with
// none, that's everything) rather than showing this screen.
//
// Wraps the whole app in main.tsx, outside AuthProvider/QueryClientProvider/
// the router -- a crash inside any of those needs to still render this, not
// disappear with them.
//
// Figma's own copy names a specific view ("THE LEAD DETAIL VIEW CRASHED").
// This boundary is app-wide (one instance, wrapping everything), so it has
// no reliable way to know which view was rendering when a child threw --
// naming a view here would mean guessing. Generic wording instead
// ("something in the app" rather than the banned "SOMETHING WENT WRONG"
// placeholder-style non-answer) -- still names what happened (a render
// crash), just not which screen, which is the honest scope of what one
// top-level boundary can know.

import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { newErrorId, recentConsoleErrors } from "../errorLog";
import NeoButton from "./neo/NeoButton";
import { color, font } from "../theme/neobrutalist";

interface State {
  errorId: string | null;
  consoleErrors: string[];
  disclosureOpen: boolean;
}

function BrandMark() {
  return (
    <div style={{ position: "fixed", top: 28, left: 32, display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ transform: "rotate(6deg)" }}>
        <div style={{ width: 20, height: 20, background: color.sand, border: `2px solid ${color.ink}` }} />
      </div>
      <span style={{ fontFamily: font.head, fontSize: 16, color: color.ink }}>MAPSCRAPE</span>
    </div>
  );
}

export default class AppErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { errorId: null, consoleErrors: [], disclosureOpen: true };

  static getDerivedStateFromError() {
    return { errorId: newErrorId() };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Deliberately still logged -- errorLog.ts's console.error wrapper
    // captures this into the same buffer read from below.
    console.error(error, info.componentStack);
    this.setState({ consoleErrors: recentConsoleErrors() });
  }

  private reload = () => window.location.reload();
  private goHome = () => { window.location.href = "/"; };
  private toggleDisclosure = () => this.setState((s) => ({ disclosureOpen: !s.disclosureOpen }));

  render() {
    const { errorId, consoleErrors, disclosureOpen } = this.state;
    if (!errorId) return this.props.children;

    return (
      <div style={{ minHeight: "100vh", background: color.bg }}>
        <BrandMark />
        <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 14, padding: "80px 24px" }}>
          <div style={{ transform: "rotate(6deg)" }}>
            <div style={{ width: 64, height: 64, background: color.pink, border: `3px solid ${color.ink}` }} />
          </div>
          <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 32, color: color.ink, textAlign: "center" }}>
            SOMETHING IN THE APP CRASHED
          </h1>
          <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 460 }}>
            The app hit an error it couldn't recover from. Reloading usually fixes it — if it
            keeps happening, quote the error id below in a bug report.
          </p>
          <div style={{ background: color.sand, border: `2px solid ${color.ink}`, padding: "8px 12px" }}>
            <span style={{ fontFamily: font.mono, fontSize: 13, color: color.ink }}>{errorId}</span>
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <NeoButton variant="primary" onClick={this.reload}>Reload</NeoButton>
            <NeoButton variant="secondary" onClick={this.goHome}>Back to dashboard</NeoButton>
          </div>

          {consoleErrors.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, width: 560, maxWidth: "100%" }}>
              <button
                type="button"
                onClick={this.toggleDisclosure}
                style={{ display: "flex", alignItems: "center", gap: 6, border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 700, fontSize: 11.5, letterSpacing: "0.23px", color: color.ink }}
              >
                <span>{disclosureOpen ? "▾" : "▸"}</span>
                <span>LAST {consoleErrors.length} CONSOLE ERROR{consoleErrors.length === 1 ? "" : "S"}</span>
              </button>
              {disclosureOpen && (
                <div style={{ background: color.white, border: `2px solid ${color.ink}`, padding: "12px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
                  {/* Pink text on white is ~2.9:1 contrast, well under WCAG AA
                      (SCREENLIST's flagged concern, confirmed) -- a pink dot
                      marker carries the "this is an error" signal instead,
                      same fix Status/Badge already documents for this exact
                      failure mode ("text stays ink-colored on every fill"). */}
                  {consoleErrors.map((line, i) => (
                    <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                      <span style={{ color: color.pink, fontSize: 10, lineHeight: "16px" }}>●</span>
                      <span style={{ fontFamily: font.mono, fontSize: 10.5, color: color.ink, wordBreak: "break-word", flex: 1 }}>
                        {line}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }
}
