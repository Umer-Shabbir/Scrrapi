// Integrations screen (Figma [SCREEN] integrations, SCREENLIST.md §14). Card
// grid of 6 providers with CONNECTED/NOT CONNECTED state, drilling into a
// full config panel for Webhooks -- the only provider with a real backend
// flow (see backend/app/db/models/integration.py: Slack/HubSpot/Pipedrive/
// Generic REST need an OAuth or API-key exchange this app doesn't have, and
// Google Sheets has no writer yet). Their Connect button stays disabled with
// an explanatory title rather than faking a connection on click (CLAUDE.md
// §9: no fake backend data as a substitute for a missing capability).

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import NeoButton from "../components/neo/NeoButton";
import NeoCheckbox from "../components/neo/NeoCheckbox";
import InlineWarning from "../components/neo/InlineWarning";
import { api, ApiError } from "../api/client";
import { color, font } from "../theme/neobrutalist";
import type { IntegrationCard, IntegrationProvider, WebhookConfig, WebhookSecretResponse } from "../types";

const PROVIDER_LABEL: Record<IntegrationProvider, string> = {
  webhooks: "Webhooks",
  slack: "Slack",
  hubspot: "HubSpot",
  pipedrive: "Pipedrive",
  rest: "Generic REST",
  sheets: "Google Sheets",
};

const PROVIDER_DESCRIPTION: Record<IntegrationProvider, string> = {
  webhooks: "POST job and lead events to any endpoint.",
  slack: "Post run summaries to a channel.",
  hubspot: "Push leads as contacts with field mapping.",
  pipedrive: "Push leads as deals with field mapping.",
  rest: "Push leads to any REST endpoint you map.",
  sheets: "Append or overwrite a spreadsheet on each run.",
};

const EVENT_LABEL: Record<string, string> = {
  "job.started": "Job started",
  "job.completed": "Job completed",
  "job.failed": "Job failed",
  "lead.found": "New lead found",
  "suppression.triggered": "Suppression rule triggered",
};

function lastActivityCaption(card: IntegrationCard): string {
  if (card.status !== "connected") return "Never connected";
  if (!card.lastEventSummary) return "Connected · no activity yet";
  const when = card.lastEventAt ? new Date(card.lastEventAt).toLocaleString() : "unknown time";
  return `${when} · ${card.lastEventSummary}`;
}

function IntegrationStateChip({ status }: { status: IntegrationCard["status"] }) {
  const connected = status === "connected";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: 20,
        padding: "3px 8px",
        border: `2px solid ${color.ink}`,
        background: connected ? color.green : color.sand,
        fontFamily: font.body,
        fontWeight: 700,
        fontSize: 9.5,
        color: color.ink,
        whiteSpace: "nowrap",
      }}
    >
      {connected ? "✓ CONNECTED" : "• NOT CONNECTED"}
    </span>
  );
}

function IntegrationCardTile({
  card,
  onConfigure,
  rowIndex,
}: {
  card: IntegrationCard;
  onConfigure: (provider: IntegrationProvider) => void;
  rowIndex: number;
}) {
  return (
    <div
      className="neo-row-enter"
      style={{
        background: color.white,
        border: `3px solid ${color.ink}`,
        padding: 16,
        height: 168,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        ["--neo-delay" as string]: `${Math.min(rowIndex, 12) * 24}ms`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", width: "100%" }}>
        <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>
          {PROVIDER_LABEL[card.provider].toUpperCase()}
        </span>
        <div style={{ flex: 1 }} />
        <IntegrationStateChip status={card.status} />
      </div>
      <p style={{ margin: 0, fontFamily: font.body, fontSize: 12, color: color.ink60 }}>
        {PROVIDER_DESCRIPTION[card.provider]}
      </p>
      <p style={{ margin: 0, fontFamily: font.body, fontSize: 11, color: color.ink60 }}>
        {lastActivityCaption(card)}
      </p>
      <div style={{ flex: 1 }} />
      {card.configurable ? (
        <NeoButton variant="ghost" onClick={() => onConfigure(card.provider)}>
          {card.status === "connected" ? "Configure" : "Connect"}
        </NeoButton>
      ) : (
        <span title="Not available yet -- no API credentials configured for this provider">
          <NeoButton variant="primary" disabled>
            Connect
          </NeoButton>
        </span>
      )}
    </div>
  );
}

function CardGridSkeleton() {
  return (
    <div className="neo-responsive-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, maxWidth: 1126 }}>
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} style={{ background: color.white, border: `3px solid ${color.ink}`, height: 168, padding: 16, position: "relative" }}>
          <div className="neo-skeleton" style={{ position: "absolute", left: 13, top: 13, width: 120, height: 18 }} />
          <div className="neo-skeleton" style={{ position: "absolute", left: "auto", right: 13, top: 13, width: 80, height: 18 }} />
          <div className="neo-skeleton" style={{ position: "absolute", left: 13, top: 39, width: 280, height: 15 }} />
          <div className="neo-skeleton" style={{ position: "absolute", left: 13, top: 62, width: 160, height: 14 }} />
          <div className="neo-skeleton" style={{ position: "absolute", left: 13, top: 109, width: 100, height: 40, border: `2px solid ${color.ink}` }} />
        </div>
      ))}
    </div>
  );
}

function IntegrationsList() {
  const navigate = useNavigate();
  const cardsQuery = useQuery({
    queryKey: ["integrations"],
    queryFn: () => api.get<IntegrationCard[]>("/api/integrations/"),
  });

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>INTEGRATIONS</h1>
        <p style={{ margin: "4px 0 0", fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink60 }}>
          Send results and events to the tools your team already uses.
        </p>
      </div>

      {cardsQuery.isLoading && <CardGridSkeleton />}

      {cardsQuery.isError && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "48px 0" }}>
          <div style={{ width: 64, height: 64, background: color.pink, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>INTEGRATIONS FAILED TO LOAD</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 400 }}>
            Your connected integrations could not be fetched from the database.
          </p>
          <p style={{ margin: 0, fontFamily: font.mono, fontSize: 12, color: color.ink60 }}>
            {cardsQuery.error instanceof ApiError ? cardsQuery.error.message : "ERR_INTEGRATIONS_FETCH_FAILED"}
          </p>
          <NeoButton variant="destructive" onClick={() => cardsQuery.refetch()}>
            Retry
          </NeoButton>
        </div>
      )}

      {cardsQuery.data && cardsQuery.data.every((c) => c.status !== "connected") && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "80px 0" }}>
          <div style={{ width: 64, height: 64, background: color.yellow, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 32, color: color.ink }}>NO INTEGRATIONS CONNECTED</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 400 }}>
            Send job results and events to the tools your team already uses.
          </p>
          <NeoButton variant="primary" onClick={() => navigate("/integrations/webhooks")}>
            Connect a tool
          </NeoButton>
        </div>
      )}

      {cardsQuery.data && cardsQuery.data.some((c) => c.status === "connected") && (
        <div className="neo-responsive-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, maxWidth: 1126 }}>
          {cardsQuery.data.map((card, i) => (
            <IntegrationCardTile key={card.provider} card={card} onConfigure={(p) => navigate(`/integrations/${p}`)} rowIndex={i} />
          ))}
        </div>
      )}
    </div>
  );
}

function WebhookConfigPanel() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState<string | null>(null);
  const [events, setEvents] = useState<string[] | null>(null);
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);

  const configQuery = useQuery({
    queryKey: ["integrations", "webhooks"],
    queryFn: () => api.get<WebhookConfig>("/api/integrations/webhooks"),
  });

  const config = configQuery.data;
  const effectiveUrl = url ?? config?.url ?? "";
  const effectiveEvents = events ?? config?.events ?? [];

  const save = useMutation({
    mutationFn: () => api.put<WebhookConfig>("/api/integrations/webhooks", { url: effectiveUrl, events: effectiveEvents }),
    onSuccess: (data) => {
      queryClient.setQueryData(["integrations", "webhooks"], data);
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      setUrl(null);
      setEvents(null);
    },
  });

  const rotate = useMutation({
    mutationFn: () => api.post<WebhookSecretResponse>("/api/integrations/webhooks/rotate"),
    onSuccess: (data) => {
      queryClient.setQueryData(["integrations", "webhooks"], data);
      setRevealedSecret(data.signingSecret);
    },
  });

  const sendTest = useMutation({
    mutationFn: () => api.post<WebhookConfig>("/api/integrations/webhooks/test"),
    onSuccess: (data) => {
      queryClient.setQueryData(["integrations", "webhooks"], data);
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
    },
  });

  function toggleEvent(key: string) {
    const current = effectiveEvents;
    setEvents(current.includes(key) ? current.filter((e) => e !== key) : [...current, key]);
  }

  // Cross-cutting #10: loading/error used to drop this panel's own header +
  // back-link entirely -- render it unconditionally so a failed/slow fetch
  // never strands the user with no way back to the Integrations list.
  const header = (
    <>
      <button
        type="button"
        onClick={() => navigate("/integrations")}
        style={{
          border: "none",
          background: "transparent",
          cursor: "pointer",
          padding: 0,
          marginBottom: 8,
          fontFamily: font.body,
          fontWeight: 700,
          fontSize: 11.5,
          color: color.blue,
          display: "block",
        }}
      >
        ← Back to Integrations
      </button>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>WEBHOOKS</h1>
        <p style={{ margin: "4px 0 0", fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink60 }}>
          Push job and lead events to any HTTPS endpoint.
        </p>
      </div>
    </>
  );

  if (configQuery.isLoading) {
    return (
      <div>
        {header}
        <div className="neo-skeleton" style={{ height: 400, maxWidth: 700 }} />
      </div>
    );
  }

  if (configQuery.isError || !config) {
    return (
      <div>
        {header}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "48px 0" }}>
          <div style={{ width: 64, height: 64, background: color.pink, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>WEBHOOK CONFIG FAILED TO LOAD</h2>
          <p style={{ margin: 0, fontFamily: font.mono, fontSize: 12, color: color.ink60 }}>
            {configQuery.error instanceof ApiError ? configQuery.error.message : "ERR_WEBHOOK_CONFIG_FETCH_FAILED"}
          </p>
          <NeoButton variant="destructive" onClick={() => configQuery.refetch()}>
            Retry
          </NeoButton>
        </div>
      </div>
    );
  }

  return (
    <div>
      {header}

      <div className="neo-responsive-fill" style={{ background: color.white, border: `3px solid ${color.ink}`, padding: 20, width: 700, display: "flex", flexDirection: "column", gap: 18 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3675px", color: color.ink, textTransform: "uppercase" }}>
            Endpoint URL
          </label>
          <input
            value={effectiveUrl}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://hooks.example.com/mapscrape"
            style={{ height: 40, padding: "0 12px", border: `3px solid ${color.ink}`, fontFamily: font.body, fontSize: 13, color: color.ink }}
          />
          <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 10, letterSpacing: "0.4px", color: color.ink60, textTransform: "uppercase" }}>
            Must be HTTPS. We sign every payload with your secret below.
          </p>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 11, letterSpacing: "0.33px", color: color.ink }}>
            EVENTS
          </p>
          {config.availableEvents.map((key) => (
            <div key={key} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <NeoCheckbox checked={effectiveEvents.includes(key)} onChange={() => toggleEvent(key)} />
              <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink }}>
                {EVENT_LABEL[key] ?? key}
              </span>
            </div>
          ))}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 11, letterSpacing: "0.33px", color: color.ink }}>
            SIGNING SECRET
          </p>
          <div style={{ background: color.sand, border: `3px solid ${color.ink}`, padding: "10px 12px", display: "flex", gap: 10, alignItems: "center" }}>
            <span style={{ fontFamily: font.mono, fontSize: 12, color: color.ink, wordBreak: "break-all" }}>
              {revealedSecret ?? config.signingSecretMasked ?? "Not generated yet — Save to create one"}
            </span>
            <div style={{ flex: 1 }} />
            <button
              type="button"
              onClick={() => rotate.mutate()}
              disabled={rotate.isPending}
              style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 700, fontSize: 11.5, color: color.ink }}
            >
              {rotate.isPending ? "…" : "Rotate"}
            </button>
          </div>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 11, color: color.ink60 }}>
            Shown in full only once, right after creation or rotation.
          </p>
        </div>

        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <NeoButton
            variant="primary"
            onClick={() => save.mutate()}
            loading={save.isPending}
            disabled={!effectiveUrl.trim()}
          >
            Save
          </NeoButton>
          <NeoButton
            variant="ghost"
            onClick={() => sendTest.mutate()}
            loading={sendTest.isPending}
            disabled={!config.url}
          >
            Send test event
          </NeoButton>
          {config.lastEventSummary && (
            <span
              style={{
                fontFamily: font.body,
                fontWeight: 500,
                fontSize: 12,
                color: config.lastEventSummary.includes("failed") ? color.pink : color.green,
              }}
            >
              Last delivery: {config.lastEventAt ? new Date(config.lastEventAt).toLocaleTimeString() : "—"} · {config.lastEventSummary}
            </span>
          )}
          {/* Webhook Delivery Log, priority-15 screen -- separate route/data
              from this config panel (backend/app/api/routers/webhook_
              deliveries.py). Only shown once a URL is configured; a webhook
              that's never sent anything has no log worth drilling into. */}
          {config.url && (
            <button
              type="button"
              onClick={() => navigate("/integrations/webhooks/webhooks")}
              style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0, fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.blue }}
            >
              View delivery log →
            </button>
          )}
        </div>

        {(save.isError || rotate.isError || sendTest.isError) && (
          <InlineWarning tone="pink" fontSize={12} fontWeight={700}>
            {[save.error, rotate.error, sendTest.error]
              .filter((e): e is ApiError => e instanceof ApiError)
              .map((e) => e.message)
              .pop() ?? "Something went wrong"}
          </InlineWarning>
        )}
      </div>
    </div>
  );
}

const CONFIGURABLE: Set<string> = new Set(["webhooks"]);

export default function Integrations() {
  const { provider } = useParams<{ provider?: string }>();

  if (provider && CONFIGURABLE.has(provider)) {
    return <WebhookConfigPanel />;
  }
  if (provider) {
    // A non-configurable provider slug (or a typo) was navigated to directly --
    // there's no panel to show, so bounce back rather than render a dead page.
    return <IntegrationsList />;
  }
  return <IntegrationsList />;
}
