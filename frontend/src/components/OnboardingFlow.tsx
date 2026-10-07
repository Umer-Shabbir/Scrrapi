// First-run / Compliance (Onboarding) — SCREENLIST.md §22. Mounted once in
// AppLayout, over every authenticated route. Two halves of one 6-step flow:
//
// 1-3: Compliance (centered modal, full 70% ink scrim, segmented step bar).
    //      Each pane's "I UNDERSTAND"/"START TOUR →" writes its own audit row
    //      (POST /api/auth/compliance/ack); pane 3 also sets
    //      users.compliance_ack_at, which is what actually dismisses this modal
    //      on future loads — see backend/app/api/routers/auth.py.
    // 4-13: Product tour (anchored callouts near the items.
    //      Optional and skippable — tracked in localStorage only
//      (onboarding.tourDone), same precedent as this app's other client-only
//      convenience flags (theme, job-draft, saved location/category
//      presets) rather than a second server column for something with no
//      legal weight.
//
// compliance-1's Figma mock overlays the real, fully-populated Dashboard —
// misleading for what's meant to be a first-run screen (SCREENLIST's own
// flagged bug). This renders its own static placeholder backdrop instead of
// mounting over the real page underneath, so a first-run user never sees
// fabricated activity/stats before they've done anything.

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import NeoButton from "./neo/NeoButton";
import { color, font, shadow } from "../theme/neobrutalist";

const TOUR_DONE_KEY = "onboarding.tourDone";

const COMPLIANCE_PANES = [
  {
    title: "WHAT MAPSCRAPE COLLECTS",
    body: "MapScrape scrapes publicly listed business data from Google Maps — name, category, address, phone, website, rating, review count and opening hours. When enabled, it also enriches this with emails found on the business's own website and technology signals from its page source. It never scrapes personal profiles, private listings, or anything behind a login.",
    cta: "I UNDERSTAND",
  },
  {
    title: "ROBOTS.TXT COMPLIANCE",
    body: "MapScrape checks robots.txt before crawling any website for enrichment and respects disallow rules and crawl-delay directives. This covers automated crawling — it does not cover the legality of storing or using the data you collect, which robots.txt has no authority over. Compliance with data protection law is your responsibility, not the crawler's.",
    cta: "I UNDERSTAND",
  },
  {
    title: "YOUR OBLIGATIONS",
    body: "Scraped and enriched data may include personal data under GDPR and CCPA — names, emails and phone numbers tied to an identifiable person. You are the data controller for what you collect and store. That means honoring deletion and access requests, keeping a lawful basis for outreach, and not retaining data longer than the purpose requires. MapScrape gives you suppression, retention limits and an audit log — it does not make these decisions for you.",
    cta: "START TOUR →",
    note: "Confirming writes a timestamped row to the audit log under your account.",
  },
];

const TOUR_STEPS: { anchor: "jobs" | "categories" | "locations" | "templates" | "schedules" | "suppression" | "proxies" | "integrations" | "team" | "settings"; title: string; body: string }[] = [
  {
    anchor: "categories",
    title: "1. Define Categories",
    body: 'Start by listing the kinds of businesses you want to target (e.g. "Roofers", "HVAC").',
  },
  {
    anchor: "locations",
    title: "2. Pick Locations",
    body: "Add the areas to search — cities, zip codes, or global radius options.",
  },
  {
    anchor: "jobs",
    title: "3. Run Jobs",
    body: "Combine your categories and locations into a job and start scraping Google or Bing Maps.",
  },
  {
    anchor: "templates",
    title: "4. Create Templates",
    body: "Save your favorite category and location combinations into a template to reuse later.",
  },
  {
    anchor: "schedules",
    title: "5. Automate with Schedules",
    body: "Set up automatic scraping jobs running daily, weekly, or at custom intervals.",
  },
  {
    anchor: "suppression",
    title: "6. Supression Lists",
    body: "Keep track of businesses you’ve already contacted so they are filtered out dynamically.",
  },
  {
    anchor: "proxies",
    title: "7. Add Proxies",
    body: "Enhance your scraping throughput by setting up proxy pools for headless instances.",
  },
  {
    anchor: "integrations",
    title: "8. Push to CRM",
    body: "Connect your HubSpot, GoHighLevel, or Pipedrive for automatic two-way lead updates.",
  },
  {
    anchor: "team",
    title: "9. Invite your Team",
    body: "Add operators to help manage data pipelines or restrict access for teammates.",
  },
  {
    anchor: "settings",
    title: "10. Enrichment Settings",
    body: "Turn on Deep Site Crawling or Waterfall Enrichment to get personal emails and decision makers.",
  }
];

function StepBar({ total, current }: { total: number; current: number }) {
  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
      {Array.from({ length: total }, (_, i) => (
        <div
          key={i}
          style={{
            width: 28,
            height: current <= 3 ? 6 : 4,
            border: current <= 3 ? `2px solid ${color.ink}` : "none",
            background: i + 1 < current ? color.ink : i + 1 === current ? color.yellow : color.sand,
          }}
        />
      ))}
      <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 11, color: current <= 3 ? color.ink60 : color.blue, whiteSpace: "nowrap", marginLeft: 4 }}>
        STEP {current} OF {total}
      </span>
    </div>
  );
}

function ComplianceModal({ pane, onNext, pending }: { pane: number; onNext: () => void; pending: boolean }) {
  const spec = COMPLIANCE_PANES[pane - 1];
  return (
    <>
      {/* Static placeholder backdrop -- never the real Dashboard, see file header. */}
      <div style={{ position: "fixed", inset: 0, background: color.bg, zIndex: 900, padding: 32 }}>
        <div style={{ marginBottom: 24 }}>
          <div style={{ height: 24, width: 120, background: color.rule }} />
          <div style={{ height: 13, width: 320, background: color.rule, marginTop: 8 }} />
        </div>
        <div style={{ display: "flex", gap: 16 }}>
          {[color.yellow, color.green, color.pink, color.purple].map((c, i) => (
            <div key={i} style={{ flex: 1, height: 108, background: c, border: `3px solid ${color.ink}`, opacity: 0.35 }} />
          ))}
        </div>
      </div>
      <div style={{ position: "fixed", inset: 0, background: "rgba(17,17,17,0.7)", zIndex: 1000, display: "grid", placeItems: "center" }}>
        <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: shadow.md, width: 640 }}>
          <div style={{ borderBottom: `3px solid ${color.ink}`, background: color.ink, padding: "16px 20px" }}>
            <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 15, letterSpacing: "0.15px", color: color.white }}>
              BEFORE YOU START
            </span>
          </div>
          <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
            <StepBar total={COMPLIANCE_PANES.length + TOUR_STEPS.length} current={pane} />
            <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>{spec.title}</h2>
            <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink }}>{spec.body}</p>
            {spec.note && (
              <p style={{ margin: 0, fontFamily: font.body, fontWeight: 500, fontSize: 10.5, color: color.ink60 }}>{spec.note}</p>
            )}
          </div>
          <div style={{ padding: "16px 24px 20px", display: "flex", gap: 12, justifyContent: "flex-end" }}>
            <NeoButton variant="primary" onClick={onNext} loading={pending}>{spec.cta}</NeoButton>
          </div>
        </div>
      </div>
    </>
  );
}

function TourCallout({ step, index, onNext, onSkip, isLast }: { step: (typeof TOUR_STEPS)[number]; index: number; onNext: () => void; onSkip: () => void; isLast: boolean }) {
  const [rect, setRect] = useState<{ top: number; left: number; height: number } | null>(null);

  useEffect(() => {
    const el = document.querySelector<HTMLElement>(`[data-tour-anchor="${step.anchor}"]`);
    if (!el) {
      setRect(null);
      return;
    }
    const update = () => {
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.right, height: r.height });
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [step.anchor]);

  // No matching nav item found (route removed/renamed) -- fall back to a
  // centered callout rather than silently vanishing mid-tour.
  const position: React.CSSProperties = rect
    ? { position: "fixed", top: rect.top + rect.height / 2 - 90, left: rect.left + 16, zIndex: 1000 }
    : { position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", zIndex: 1000 };

  return (
    <div style={{ ...position, background: color.white, border: `3px solid ${color.ink}`, boxShadow: shadow.sm, width: 280, padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
      {/* 3 previously built compliance steps + the amount of tour steps */}
      <StepBar total={COMPLIANCE_PANES.length + TOUR_STEPS.length} current={index + COMPLIANCE_PANES.length + 1} />
      <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 13, color: color.ink }}>{step.title}</span>
      <p style={{ margin: 0, fontFamily: font.body, fontSize: 11.5, color: color.ink }}>{step.body}</p>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {!isLast && (
          <button type="button" onClick={onSkip} style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 700, fontSize: 10.5, color: color.ink }}>
            SKIP TOUR
          </button>
        )}
        <div style={{ flex: 1 }} />
        <NeoButton variant="primary" size="sm" onClick={onNext}>{isLast ? "FINISH TOUR" : "NEXT"}</NeoButton>
      </div>
    </div>
  );
}

export default function OnboardingFlow() {
  const { user, token } = useAuth();
  const queryClient = useQueryClient();
  const [pane, setPane] = useState(1);
  const [acking, setAcking] = useState(false);
  const [tourStep, setTourStep] = useState(0);
  const [tourActive, setTourActive] = useState(false);
  const startedTour = useRef(false);

  const needsCompliance = !!user && !user.complianceAckAt;

  useEffect(() => {
    // Only start the tour if the user exists and compliance is out of the way
    if (!user || needsCompliance || startedTour.current) return;
    startedTour.current = true;
    if (localStorage.getItem(TOUR_DONE_KEY) !== "true") {
      setTourActive(true);
    }
  }, [user, needsCompliance]);

  if (!user) return null;

  if (needsCompliance) {
    return (
      <ComplianceModal
        pane={pane}
        pending={acking}
        onNext={async () => {
          setAcking(true);
          const result = await api.post<{ complianceAckAt: string | null }>("/api/auth/compliance/ack", { pane });
          setAcking(false);
          if (result.complianceAckAt) {
            queryClient.setQueryData(["auth", "me", token], { ...user, complianceAckAt: result.complianceAckAt });
          } else {
            setPane((p) => p + 1);
          }
        }}
      />
    );
  }

  if (!tourActive) return null;

  const finishTour = () => {
    localStorage.setItem(TOUR_DONE_KEY, "true");
    setTourActive(false);
  };

  return (
    <TourCallout
      step={TOUR_STEPS[tourStep]}
      index={tourStep}
      isLast={tourStep === TOUR_STEPS.length - 1}
      onSkip={finishTour}
      onNext={() => {
        if (tourStep === TOUR_STEPS.length - 1) {
          finishTour();
        } else {
          setTourStep((s) => s + 1);
        }
      }}
    />
  );
}
