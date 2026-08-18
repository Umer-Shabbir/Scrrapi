// Persistent shell: Shell/TopBar + Shell/Sidebar (neobrutalist Figma system,
// page "02 — App Shell", nodes 35:2 / 37:47) + routed page. Drawn once here,
// never redrawn per screen, per the Figma component doc on Shell/TopBar.
//
// Sidebar only lists routes that exist today (Jobs/Categories/Locations/
// Templates/Settings/Account) rather than the full 23-screen nav table in the
// design -- the rest are future screen cycles, and a nav item with no route
// behind it is a dead link.

import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import DarkModeIcon from "@mui/icons-material/DarkMode";
import LightModeIcon from "@mui/icons-material/LightMode";
import MenuIcon from "@mui/icons-material/Menu";
import WorkOutlineIcon from "@mui/icons-material/WorkOutline";
import CategoryIcon from "@mui/icons-material/Category";
import PlaceIcon from "@mui/icons-material/Place";
import DescriptionIcon from "@mui/icons-material/Description";
import ScheduleIcon from "@mui/icons-material/Schedule";
import BlockIcon from "@mui/icons-material/Block";
import DnsIcon from "@mui/icons-material/Dns";
import ExtensionIcon from "@mui/icons-material/Extension";
import GroupIcon from "@mui/icons-material/Group";
import VpnKeyIcon from "@mui/icons-material/VpnKey";
import FactCheckIcon from "@mui/icons-material/FactCheck";
import MonitorHeartIcon from "@mui/icons-material/MonitorHeart";
import TuneIcon from "@mui/icons-material/Tune";
import PersonIcon from "@mui/icons-material/Person";
import type { SvgIconComponent } from "@mui/icons-material";
import { useAuth } from "../auth/AuthContext";
import { useColorMode } from "../ColorModeContext";
import OnboardingFlow from "./OnboardingFlow";
import { useJobDraft } from "../state/JobDraftContext";
import { color, font, shadow, mq, scrim } from "../theme/neobrutalist";
import { useMediaQuery } from "../hooks/useMediaQuery";

// Cross-cutting #4 (SCREENLIST.md): at <=768px the sidebar must collapse
// behind a hamburger trigger and open as a scrimmed overlay drawer instead
// of squeezing the 250px rail into the viewport -- confirmed against the
// live Figma 768 dashboard frame (node 175:7021), which shows a single
// Button/Icon hamburger in TopBar's left slot and no persistent rail at all.
const MOBILE_BREAKPOINT = mq.mobile;
// Between mobile and desktop, the rail stays mounted but narrows to
// icon-only (no labels/badges) -- same tradeoff Figma's 1024 dashboard frame
// makes rather than squeezing the full 250px rail into a tablet viewport.
const TABLET_BREAKPOINT = mq.tablet;

interface NavItem {
  label: string;
  to: string;
  group: "RUN" | "DATA" | "ADMIN";
  badge?: number;
  /** Anchors the product tour (First-run / Compliance, SCREENLIST.md §22)
   * to this nav item's real DOM position, read via getBoundingClientRect --
   * not a fixed pixel offset, so a callout still lands on its target if the
   * sidebar ever reflows. */
  tourAnchor?: "categories" | "locations" | "jobs";
  /** Cross-cutting #1: nav icons were rendering as blank placeholder squares
   * sitewide -- a real 17px outline icon per item, not a Figma-matching
   * blank box. */
  icon: SvgIconComponent;
}

function useNavItems(): NavItem[] {
  const { keywords, locations } = useJobDraft();
  return [
    { label: "Jobs", to: "/", group: "RUN", tourAnchor: "jobs", icon: WorkOutlineIcon },
    { label: "Categories", to: "/categories", group: "RUN", badge: keywords.length || undefined, tourAnchor: "categories", icon: CategoryIcon },
    { label: "Locations", to: "/locations", group: "RUN", badge: locations.length || undefined, tourAnchor: "locations", icon: PlaceIcon },
    { label: "Templates", to: "/templates", group: "RUN", icon: DescriptionIcon },
    { label: "Schedules", to: "/schedules", group: "RUN", icon: ScheduleIcon },
    { label: "Suppression", to: "/suppression", group: "DATA", icon: BlockIcon },
    { label: "Proxies", to: "/proxies", group: "ADMIN", icon: DnsIcon },
    { label: "Integrations", to: "/integrations", group: "ADMIN", icon: ExtensionIcon },
    { label: "Team", to: "/team", group: "ADMIN", icon: GroupIcon },
    { label: "API Keys", to: "/api-keys", group: "ADMIN", icon: VpnKeyIcon },
    { label: "Audit", to: "/audit", group: "ADMIN", icon: FactCheckIcon },
    { label: "System", to: "/system", group: "ADMIN", icon: MonitorHeartIcon },
    { label: "Settings", to: "/settings", group: "ADMIN", icon: TuneIcon },
    { label: "Account", to: "/account", group: "ADMIN", icon: PersonIcon },
  ];
}

// Results and Export are both job-scoped drill-downs (`/results/:jobId`,
// `/export/:jobId`) with no job-independent route to point a top-level nav
// item at -- same reason Results has none either. Figma's Nav column lists
// both anyway (the design assumes a job-list-aware nav Section this app
// doesn't have yet); adding a nav item that 404s without a jobId would be
// worse than the gap.

function Brand({ size = "md" }: { size?: "md" | "sm" }) {
  const mark = size === "sm" ? 20 : 36;
  const wrap = size === "sm" ? 21.981 : 39.566;
  const text = size === "sm" ? 18 : 24;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: size === "sm" ? 8 : 12 }}>
      <div style={{ width: wrap, height: wrap, display: "grid", placeItems: "center" }}>
        <div style={{ transform: "rotate(6deg)" }}>
          <div style={{ width: mark, height: mark, background: color.yellow, border: `3px solid ${color.ink}` }} />
        </div>
      </div>
      <span style={{ fontFamily: font.head, fontSize: text, color: color.ink, whiteSpace: "nowrap" }}>
        MAPSCRAPE
      </span>
    </div>
  );
}

function TopBar({ isMobile, onMenuClick }: { isMobile: boolean; onMenuClick: () => void }) {
  const { user, license, signOut } = useAuth();
  const { mode, toggle } = useColorMode();
  const navigate = useNavigate();

  return (
    <div
      style={{
        height: 64,
        borderBottom: `3px solid ${color.ink}`,
        background: color.white,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: isMobile ? "0 12px" : "0 24px",
        gap: isMobile ? 8 : 24,
        flexShrink: 0,
        overflow: "hidden",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        {isMobile && (
          <button
            type="button"
            onClick={onMenuClick}
            title="Open navigation"
            style={{
              width: 32,
              height: 32,
              border: `3px solid ${color.ink}`,
              background: color.white,
              display: "grid",
              placeItems: "center",
              cursor: "pointer",
              flexShrink: 0,
            }}
          >
            <MenuIcon sx={{ fontSize: 17 }} />
          </button>
        )}
        <Brand size="sm" />
      </div>

      <div style={{ flex: 1, maxWidth: 480, minWidth: 0 }} />

      <div style={{ display: "flex", alignItems: "center", gap: isMobile ? 10 : 20, minWidth: 0 }}>
        {/* Full "LICENSED"/"NO LICENSE" label reads fine down to 1024, but at
            768 it's the item most likely to force the horizontal scroll that
            clipped the top-bar's right quarter (cross-cutting #4) -- shrink
            to just the glyph once mobile, the color still carries the state. */}
        {license && (
          <button
            type="button"
            onClick={() => navigate("/account")}
            title="Account & billing"
            style={{
              display: "inline-flex",
              alignItems: "center",
              height: 18,
              padding: "0 8px",
              border: `2px solid ${color.ink}`,
              background: license.active ? color.green : color.pink,
              fontFamily: font.body,
              fontWeight: 700,
              fontSize: "10.5px",
              letterSpacing: "0.42px",
              textTransform: "uppercase",
              whiteSpace: "nowrap",
              cursor: "pointer",
              flexShrink: 0,
            }}
          >
            {isMobile
              ? license.active ? "✓" : "✕"
              : license.active ? "✓ LICENSED" : "✕ NO LICENSE"}
          </button>
        )}

        <button
          type="button"
          onClick={toggle}
          title={`Switch to ${mode === "dark" ? "light" : "dark"} mode`}
          style={{
            width: 32,
            height: 32,
            border: `3px solid ${color.ink}`,
            background: color.white,
            display: "grid",
            placeItems: "center",
            cursor: "pointer",
          }}
        >
          {mode === "dark" ? <LightModeIcon sx={{ fontSize: 17 }} /> : <DarkModeIcon sx={{ fontSize: 17 }} />}
        </button>

        <button
          type="button"
          onClick={signOut}
          title={user ? `Sign out ${user.email}` : "Sign out"}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            border: "none",
            background: "transparent",
            cursor: "pointer",
            padding: 0,
          }}
        >
          <span style={{ width: 28, height: 28, background: color.purple, border: `3px solid ${color.ink}`, flexShrink: 0 }} />
          {/* Email label drops at mobile -- the avatar square plus this
              button's own title tooltip already carry "who's signed in";
              full-width nowrap text here was the other main overflow source
              behind cross-cutting #4's clipped top-bar. */}
          {!isMobile && (
            <span
              style={{
                fontFamily: font.body,
                fontWeight: 700,
                fontSize: "10.5px",
                letterSpacing: "0.315px",
                textTransform: "uppercase",
                color: color.ink,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                maxWidth: 160,
              }}
            >
              {user?.email ?? "—"}
            </span>
          )}
        </button>
      </div>
    </div>
  );
}

function Sidebar({
  isMobile,
  isTablet,
  open,
  onClose,
}: {
  isMobile: boolean;
  isTablet: boolean;
  open: boolean;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const items = useNavItems();
  const isActive = (to: string) => (to === "/" ? pathname === "/" : pathname.startsWith(to));

  const groups: NavItem["group"][] = ["RUN", "DATA", "ADMIN"];

  const go = (to: string) => {
    navigate(to);
    if (isMobile) onClose();
  };

  // Mobile: render as a fixed-position overlay drawer with the same 70%-ink
  // scrim convention LeadDetailDrawer already uses (rule #7: reuse before
  // duplication), not a second squeezed-in-place rail. Unmounted entirely
  // when closed so it can't intercept clicks or show up in the tab order.
  if (isMobile && !open) return null;

  // Tablet (>768px, <=1024px): rail stays mounted but collapses to icon-only
  // -- labels/badges/tooltips are real info loss (SCREENLIST §"Categories"
  // 1024 finding), so every icon keeps a title tooltip and an aria-label as
  // the accessible name in place of the now-hidden visible label.
  const iconOnly = isTablet && !isMobile;

  const rail = (
    <div
      // Only the mobile overlay drawer slides in -- the desktop rail is
      // always-mounted chrome, sliding it in on every app load would just be
      // motion for its own sake.
      className={isMobile ? "neo-slide-enter" : undefined}
      style={{
        width: iconOnly ? 64 : 250,
        flexShrink: 0,
        borderRight: `3px solid ${color.ink}`,
        background: color.bg,
        padding: iconOnly ? "16px 8px" : "16px 12px",
        display: "flex",
        flexDirection: "column",
        gap: 4,
        overflowY: "auto",
        transition: "width 160ms cubic-bezier(0.2, 0, 0, 1)",
        ...(isMobile
          ? {
              position: "fixed" as const,
              top: 0,
              left: 0,
              bottom: 0,
              zIndex: 1001,
              boxShadow: shadow.lg,
              ["--neo-slide-from" as string]: "translateX(-100%)",
            }
          : {}),
      }}
    >
      {groups.map((group) => {
        const groupItems = items.filter((item) => item.group === group);
        if (groupItems.length === 0) return null;
        return (
          <div key={group} style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: group !== "RUN" ? 12 : 0 }}>
            {!iconOnly && (
              <p
                style={{
                  margin: 0,
                  fontFamily: font.body,
                  fontWeight: 700,
                  fontSize: 10,
                  letterSpacing: "0.4px",
                  textTransform: "uppercase",
                  color: color.ink60,
                }}
              >
                {group}
              </p>
            )}
            {groupItems.map((item) => {
              const active = isActive(item.to);
              const Icon = item.icon;
              return (
                <button
                  key={item.to}
                  type="button"
                  data-tour-anchor={item.tourAnchor}
                  onClick={() => go(item.to)}
                  title={iconOnly ? item.label : undefined}
                  aria-label={item.label}
                  style={{
                    height: 36,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: iconOnly ? "center" : "space-between",
                    padding: iconOnly ? 0 : "0 10px",
                    border: `3px solid ${active ? color.ink : "transparent"}`,
                    background: active ? color.yellow : "transparent",
                    boxShadow: active ? "2px 2px 0px 0px #111" : "none",
                    cursor: "pointer",
                    width: "100%",
                    textAlign: "left",
                    transition:
                      "background 140ms cubic-bezier(0.2, 0, 0, 1), border-color 140ms cubic-bezier(0.2, 0, 0, 1), box-shadow 140ms cubic-bezier(0.2, 0, 0, 1)",
                  }}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                    <Icon sx={{ fontSize: 17, color: color.ink, flexShrink: 0 }} />
                    {!iconOnly && (
                      <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: "12.5px", color: color.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {item.label}
                      </span>
                    )}
                  </span>
                  {!!item.badge && !iconOnly && (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        padding: "2px 6px",
                        border: `2px solid ${color.ink}`,
                        background: color.blue,
                        fontFamily: font.body,
                        fontWeight: 700,
                        fontSize: 10,
                        color: color.ink,
                      }}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        );
      })}
    </div>
  );

  if (!isMobile) return rail;

  return (
    <>
      <div
        onClick={onClose}
        className="neo-scrim-enter"
        style={{ position: "fixed", inset: 0, background: scrim, zIndex: 1000 }}
      />
      {rail}
    </>
  );
}

export default function AppLayout() {
  const isMobile = useMediaQuery(MOBILE_BREAKPOINT);
  const isTablet = useMediaQuery(TABLET_BREAKPOINT);
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();

  // A resize back to desktop (or a route change on mobile via `go` above)
  // must not leave the drawer's fixed-position markup mounted with stale
  // open state -- collapse it whenever the breakpoint itself changes.
  useEffect(() => {
    setNavOpen(false);
  }, [isMobile]);

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh", background: color.bg }}>
      <TopBar isMobile={isMobile} onMenuClick={() => setNavOpen(true)} />
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <Sidebar isMobile={isMobile} isTablet={isTablet} open={navOpen} onClose={() => setNavOpen(false)} />
        {/* key={pathname} forces a remount per route so neo-page-enter's
            mount animation replays on every navigation, not just first
            load. */}
        <div
          key={location.pathname}
          className="neo-page-enter"
          style={{ flex: 1, minWidth: 0, padding: isTablet ? (isMobile ? 16 : 24) : 32 }}
        >
          <Outlet />
        </div>
      </div>
      <OnboardingFlow />
    </div>
  );
}
