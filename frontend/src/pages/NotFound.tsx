// 404 screen (Figma [SCREEN] not-found — 404, SCREENLIST.md §23). Outside
// AppLayout, same as Login and the 500 boundary below -- rendered by
// App.tsx's catch-all route instead of the silent redirect-to-/ that was
// there before.
//
// Brand mark added (small, top-left) -- Figma's own live canvas shows 404
// with none at all while 500 and Login both have one; user confirmed
// matching 500/Login's treatment rather than 1:1 mirroring 404's bare canvas.

import { useLocation, useNavigate } from "react-router-dom";
import NeoButton from "../components/neo/NeoButton";
import { color, font, shadow } from "../theme/neobrutalist";

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

export default function NotFound() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <div style={{ minHeight: "100vh", background: color.bg, display: "grid", placeItems: "center" }}>
      <BrandMark />
      <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: shadow.md, padding: "40px 48px", display: "flex", flexDirection: "column", alignItems: "center", gap: 12, maxWidth: 560 }}>
        <div style={{ transform: "rotate(6deg)" }}>
          <div style={{ width: 64, height: 64, background: color.yellow, border: `3px solid ${color.ink}` }} />
        </div>
        <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 32, color: color.ink, textAlign: "center" }}>
          404 — PAGE NOT FOUND
        </h1>
        <div style={{ background: color.sand, border: `2px solid ${color.ink}`, padding: "8px 12px", maxWidth: "100%", boxSizing: "border-box" }}>
          <span style={{ fontFamily: font.mono, fontSize: 13, color: color.ink, wordBreak: "break-all" }}>
            {location.pathname}
          </span>
        </div>
        <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink60 }}>
          That route does not match anything in MapScrape.
        </p>
        {/* NeoButton already renders a single clean border+shadow -- the
            duplicate stray stroke SCREENLIST flags on this button only
            showed up in Figma's own hand-drawn instance, not here. */}
        <NeoButton variant="primary" onClick={() => navigate("/")}>
          Back to dashboard
        </NeoButton>
      </div>
    </div>
  );
}
