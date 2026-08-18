// Team & Roles screen (Figma [SCREEN] team, SCREENLIST.md §16). Role matrix
// (static reference table) + seat counter + member table + invite drawer.
//
// This app has no multi-tenancy -- every row in `users` already IS the one
// workspace's member list (backend/app/db/models/user.py), so "team" needed
// no new org/workspace concept. There's also no email/self-signup anywhere
// in the app (login screen spec: "accounts via CLI"), so Invite Member
// provisions the account directly and shows a one-time temp password --
// same shape as the API Keys screen's one-time-reveal panel -- rather than
// pretending an email went out.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import NeoButton from "../components/neo/NeoButton";
import NeoRadio from "../components/neo/NeoRadio";
import InlineWarning from "../components/neo/InlineWarning";
import { useAuth } from "../auth/AuthContext";
import { api, ApiError } from "../api/client";
import { color, font, shadow } from "../theme/neobrutalist";
import type { InviteMemberResponse, TeamMember, TeamResponse, TeamRole } from "../types";

const ROLE_LABEL: Record<TeamRole, string> = { owner: "Owner", operator: "Operator", viewer: "Viewer" };

function lastSeenLabel(m: TeamMember): string {
  if (m.onlineNow) return "Online now";
  if (!m.lastSeenAt) return "Never";
  const diffMs = Date.now() - new Date(m.lastSeenAt).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

const ROLE_OPTIONS: { role: TeamRole; description: string }[] = [
  { role: "owner", description: "Full access, including billing and team management." },
  { role: "operator", description: "Create and run jobs, manage proxies and integrations." },
  { role: "viewer", description: "Read-only access to jobs, results and dashboards." },
];

function MemberStatusChip({ status }: { status: TeamMember["status"] }) {
  const active = status === "active";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "3px 8px",
        border: `2px solid ${color.ink}`,
        background: active ? color.green : color.sand,
        fontFamily: font.body,
        fontWeight: 700,
        fontSize: 10,
        color: color.ink,
        whiteSpace: "nowrap",
      }}
    >
      {active ? "✓ ACTIVE" : "✕ DISABLED"}
    </span>
  );
}

function RoleMatrixPanel({ rows }: { rows: TeamResponse["roleMatrix"] }) {
  return (
    <div style={{ background: color.white, border: `3px solid ${color.ink}`, padding: 16, display: "flex", flexDirection: "column", gap: 10, marginBottom: 24, maxWidth: 1126 }}>
      <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", color: color.ink }}>
        ROLE MATRIX
      </p>
      <div style={{ display: "flex", background: color.sand, border: `3px solid ${color.ink}`, height: 32 }}>
        {["CAPABILITY", "OWNER", "OPERATOR", "VIEWER"].map((h, i) => (
          <div key={h} style={{ display: "flex", alignItems: "center", padding: "0 12px", width: i === 0 ? 350 : 250 }}>
            <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.21px", color: color.ink }}>{h}</span>
          </div>
        ))}
      </div>
      {rows.map((row) => (
        <div key={row.capability} style={{ display: "flex", height: 34, border: `3px solid ${color.rule}`, alignItems: "center" }}>
          <div style={{ padding: "0 12px", width: 350 }}>
            <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12, color: color.ink }}>{row.capability}</span>
          </div>
          {([row.owner, row.operator, row.viewer] as const).map((flag, i) => (
            <div key={i} style={{ padding: "0 12px", width: 250 }}>
              <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 13, color: flag ? color.green : color.ink60 }}>
                {flag ? "✓" : "—"}
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function MemberTable({
  members,
  isOwner,
  currentUserId,
  onChangeRole,
  onDisable,
  onEnable,
  onRemove,
  pendingId,
}: {
  members: TeamMember[];
  isOwner: boolean;
  currentUserId: string | undefined;
  onChangeRole: (m: TeamMember) => void;
  onDisable: (m: TeamMember) => void;
  onEnable: (m: TeamMember) => void;
  onRemove: (m: TeamMember) => void;
  pendingId: string | null;
}) {
  return (
    <div style={{ background: color.white, border: `3px solid ${color.ink}`, maxWidth: 1126, overflowX: "auto" }}>
      <div style={{ display: "flex", background: color.sand, borderBottom: `3px solid ${color.ink}`, height: 36 }}>
        {[["EMAIL", 280], ["ROLE", 130], ["LAST SEEN", 150], ["STATUS", 110], ["ACTIONS", 0]].map(([h, w]) => (
          <div key={h as string} style={{ display: "flex", alignItems: "center", padding: "0 12px", width: (w as number) || undefined, flex: w ? undefined : 1 }}>
            <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.21px", color: color.ink }}>{h}</span>
          </div>
        ))}
      </div>
      {members.map((m, i) => {
        const isSelf = m.id === currentUserId;
        const disabled = m.status === "disabled";
        return (
          <div
            key={m.id}
            className="neo-row-enter"
            style={{ display: "flex", borderBottom: `3px solid ${color.rule}`, height: 40, alignItems: "center", opacity: disabled ? 0.6 : 1, ["--neo-delay" as string]: `${Math.min(i, 12) * 24}ms` }}
          >
            <div style={{ padding: "0 12px", width: 280 }}>
              <span style={{ fontFamily: font.mono, fontSize: 11.5, color: color.ink }}>{m.email}</span>
            </div>
            <div style={{ padding: "0 12px", width: 130 }}>
              <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink }}>{ROLE_LABEL[m.role]}</span>
            </div>
            <div style={{ padding: "0 12px", width: 150 }}>
              <span style={{ fontFamily: font.body, fontWeight: 500, fontSize: 12.5, color: color.ink }}>{lastSeenLabel(m)}</span>
            </div>
            <div style={{ padding: "0 12px", width: 110 }}>
              <MemberStatusChip status={m.status} />
            </div>
            <div style={{ padding: "0 12px", flex: 1, display: "flex", gap: 8, alignItems: "center" }}>
              {isOwner && !isSelf ? (
                <>
                  <button type="button" onClick={() => onChangeRole(m)} disabled={pendingId === m.id} style={linkBtnStyle}>
                    CHANGE ROLE
                  </button>
                  <span style={{ color: color.ink60 }}>·</span>
                  {disabled ? (
                    <button type="button" onClick={() => onEnable(m)} disabled={pendingId === m.id} style={linkBtnStyle}>
                      ENABLE
                    </button>
                  ) : (
                    <button type="button" onClick={() => onDisable(m)} disabled={pendingId === m.id} style={linkBtnStyle}>
                      DISABLE
                    </button>
                  )}
                  <span style={{ color: color.ink60 }}>·</span>
                  <button type="button" onClick={() => onRemove(m)} disabled={pendingId === m.id} style={{ ...linkBtnStyle, color: color.pink }}>
                    REMOVE
                  </button>
                </>
              ) : (
                <span style={{ fontFamily: font.body, fontSize: 11, color: color.ink60 }}>
                  {isSelf ? "This is you" : "—"}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

const linkBtnStyle: React.CSSProperties = {
  border: "none",
  background: "transparent",
  cursor: "pointer",
  padding: 0,
  fontFamily: font.body,
  fontWeight: 500,
  fontSize: 12.5,
  color: color.blue,
};

function InviteDrawer({ onClose, onInvited }: { onClose: () => void; onInvited: (res: InviteMemberResponse) => void }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<TeamRole>("operator");

  const invite = useMutation({
    mutationFn: () => api.post<InviteMemberResponse>("/api/team/invite", { email, role }),
    onSuccess: (data) => onInvited(data),
  });

  const cliSnippet = `mapscrape team invite --email ${email || "colleague@company.com"} --role ${role}`;

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(17,17,17,0.7)", display: "flex", justifyContent: "flex-end", zIndex: 1000 }}>
      <div style={{ background: color.white, width: 450, height: "100%", boxShadow: shadow.lg, display: "flex", flexDirection: "column" }}>
        <div style={{ background: color.ink, color: color.white, padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontFamily: font.body, fontWeight: 700, fontSize: 14, letterSpacing: "0.28px", textTransform: "uppercase" }}>
            Invite member
          </span>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", color: color.white, cursor: "pointer", fontSize: 16 }}>✕</button>
        </div>
        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 18, overflowY: "auto", flex: 1 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3675px", color: color.ink, textTransform: "uppercase" }}>
              Email
            </label>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              style={{ height: 40, padding: "0 12px", border: `3px solid ${color.ink}`, fontFamily: font.body, fontSize: 13, color: color.ink }}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <label style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3675px", color: color.ink, textTransform: "uppercase" }}>
              Role
            </label>
            {ROLE_OPTIONS.map((opt) => (
              <button
                key={opt.role}
                type="button"
                onClick={() => setRole(opt.role)}
                style={{
                  display: "flex",
                  gap: 10,
                  alignItems: "flex-start",
                  padding: 10,
                  background: role === opt.role ? color.sand : "transparent",
                  border: "none",
                  cursor: "pointer",
                  textAlign: "left",
                }}
              >
                <NeoRadio checked={role === opt.role} onChange={() => setRole(opt.role)} />
                <div>
                  <p style={{ margin: 0, fontFamily: font.body, fontWeight: 700, fontSize: 12, letterSpacing: "0.24px", color: color.ink, textTransform: "uppercase" }}>
                    {opt.role}
                  </p>
                  <p style={{ margin: 0, fontFamily: font.body, fontSize: 11.5, color: color.ink60 }}>{opt.description}</p>
                </div>
              </button>
            ))}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontFamily: font.body, fontWeight: 700, fontSize: 10.5, letterSpacing: "0.3675px", color: color.ink, textTransform: "uppercase" }}>
              Or provision from the terminal
            </label>
            <pre style={{ margin: 0, background: color.sand, border: `3px solid ${color.ink}`, padding: 12, fontFamily: font.mono, fontSize: 11.5, color: color.ink, whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
              {cliSnippet}
            </pre>
          </div>

          {invite.isError && (
            <InlineWarning tone="pink" fontSize={12} fontWeight={700}>
              {invite.error instanceof ApiError ? invite.error.message : "Couldn't send that invite"}
            </InlineWarning>
          )}
        </div>
        <div style={{ padding: 20, display: "flex", gap: 12 }}>
          <NeoButton variant="primary" onClick={() => invite.mutate()} loading={invite.isPending} disabled={!email.trim()}>
            Send invite
          </NeoButton>
          <NeoButton variant="secondary" onClick={onClose} disabled={invite.isPending}>
            Cancel
          </NeoButton>
        </div>
      </div>
    </div>
  );
}

function InvitedRevealModal({ result, onClose }: { result: InviteMemberResponse; onClose: () => void }) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(17,17,17,0.7)", display: "grid", placeItems: "center", zIndex: 1100 }}>
      <div style={{ background: color.white, border: `3px solid ${color.ink}`, boxShadow: shadow.md, width: 460, padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
        <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>MEMBER INVITED</h2>
        <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60 }}>
          There's no email delivery in this app -- share this temp password with{" "}
          <strong style={{ color: color.ink }}>{result.email}</strong> directly. It won't be shown again.
        </p>
        <div style={{ background: color.sand, border: `3px solid ${color.ink}`, padding: "10px 12px" }}>
          <span style={{ fontFamily: font.mono, fontSize: 14, color: color.ink }}>{result.tempPassword}</span>
        </div>
        <NeoButton variant="primary" onClick={onClose}>
          Done
        </NeoButton>
      </div>
    </div>
  );
}

export default function Team() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [invited, setInvited] = useState<InviteMemberResponse | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const teamQuery = useQuery({
    queryKey: ["team"],
    queryFn: () => api.get<TeamResponse>("/api/team/"),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["team"] });

  const changeRole = useMutation({
    mutationFn: ({ id, role }: { id: string; role: TeamRole }) => api.patch(`/api/team/${id}/role`, { role }),
    onSettled: () => setPendingId(null),
    onSuccess: invalidate,
  });
  const disable = useMutation({
    mutationFn: (id: string) => api.post(`/api/team/${id}/disable`),
    onSettled: () => setPendingId(null),
    onSuccess: invalidate,
  });
  const enable = useMutation({
    mutationFn: (id: string) => api.post(`/api/team/${id}/enable`),
    onSettled: () => setPendingId(null),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.del(`/api/team/${id}`),
    onSettled: () => setPendingId(null),
    onSuccess: invalidate,
  });

  const isOwner = user?.role === "owner";
  const seatsFull = teamQuery.data ? teamQuery.data.seats.used >= teamQuery.data.seats.total : false;

  function handleChangeRole(m: TeamMember) {
    const next = window.prompt(`New role for ${m.email} (owner/operator/viewer):`, m.role);
    if (!next || !["owner", "operator", "viewer"].includes(next)) return;
    setPendingId(m.id);
    changeRole.mutate({ id: m.id, role: next as TeamRole });
  }

  return (
    <div>
      <div className="neo-responsive-header" style={{ display: "flex", alignItems: "flex-end", marginBottom: 24, gap: 16 }}>
        <div>
          <h1 style={{ margin: 0, fontFamily: font.head, fontSize: 24, color: color.ink }}>TEAM &amp; ROLES</h1>
          <p style={{ margin: "4px 0 0", fontFamily: font.body, fontWeight: 500, fontSize: 13, color: color.ink60 }}>
            Who can access this workspace, and what they can do.
          </p>
        </div>
        <div style={{ flex: 1 }} />
        {teamQuery.data && (
          <div style={{ display: "flex", flexDirection: "column", gap: 4, alignItems: "flex-end" }}>
            <div style={{ display: "flex", gap: 8, fontFamily: font.body, fontWeight: 700, fontSize: 11 }}>
              <span style={{ color: color.ink, letterSpacing: "0.22px" }}>SEATS</span>
              <span style={{ color: seatsFull ? color.pink : color.green, fontWeight: 400, fontSize: 12 }}>
                {teamQuery.data.seats.used} / {teamQuery.data.seats.total} used
              </span>
            </div>
            <div style={{ width: 220, height: 16, border: `3px solid ${color.ink}`, background: color.sand, overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${teamQuery.data.seats.total ? Math.min(100, (teamQuery.data.seats.used / teamQuery.data.seats.total) * 100) : 0}%`,
                  background: seatsFull ? color.pink : color.green,
                }}
              />
            </div>
          </div>
        )}
      </div>

      {isOwner && (
        <div style={{ marginBottom: 24 }}>
          <NeoButton variant="primary" onClick={() => setInviteOpen(true)} disabled={seatsFull}>
            Invite member
          </NeoButton>
          {seatsFull && (
            <span style={{ marginLeft: 12, fontFamily: font.body, fontSize: 12.5, color: color.pink }}>
              Seats are full — remove a member or upgrade your license to invite more.
            </span>
          )}
        </div>
      )}

      {teamQuery.isLoading && (
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ maxWidth: 1126, display: "flex", flexDirection: "column", gap: 4 }}>
            {Array.from({ length: 7 }, (_, i) => (
              <div key={i} className="neo-skeleton" style={{ height: 34, border: `3px solid ${color.ink}` }} />
            ))}
          </div>
          <div style={{ maxWidth: 1126, display: "flex", flexDirection: "column", gap: 4 }}>
            {Array.from({ length: 5 }, (_, i) => (
              <div key={i} className="neo-skeleton" style={{ height: 34, border: `3px solid ${color.ink}` }} />
            ))}
          </div>
        </div>
      )}

      {teamQuery.isError && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "48px 0" }}>
          <div style={{ width: 64, height: 64, background: color.pink, border: `3px solid ${color.ink}`, transform: "rotate(6deg)" }} />
          <h2 style={{ margin: 0, fontFamily: font.head, fontSize: 18, color: color.ink }}>TEAM MEMBERS FAILED TO LOAD</h2>
          <p style={{ margin: 0, fontFamily: font.body, fontSize: 13, color: color.ink60, textAlign: "center", maxWidth: 400 }}>
            The member list and role matrix could not be fetched.
          </p>
          <p style={{ margin: 0, fontFamily: font.mono, fontSize: 12, color: color.ink60 }}>
            {teamQuery.error instanceof ApiError ? teamQuery.error.message : "ERR_TEAM_FETCH_FAILED"}
          </p>
          <NeoButton variant="destructive" onClick={() => teamQuery.refetch()}>
            Retry
          </NeoButton>
        </div>
      )}

      {teamQuery.data && (
        <>
          <RoleMatrixPanel rows={teamQuery.data.roleMatrix} />
          <MemberTable
            members={teamQuery.data.members}
            isOwner={isOwner}
            currentUserId={user?.id}
            onChangeRole={handleChangeRole}
            onDisable={(m) => { setPendingId(m.id); disable.mutate(m.id); }}
            onEnable={(m) => { setPendingId(m.id); enable.mutate(m.id); }}
            onRemove={(m) => {
              if (!window.confirm(`Remove ${m.email} from the workspace? This cannot be undone.`)) return;
              setPendingId(m.id);
              remove.mutate(m.id);
            }}
            pendingId={pendingId}
          />
        </>
      )}

      {inviteOpen && (
        <InviteDrawer
          onClose={() => setInviteOpen(false)}
          onInvited={(res) => {
            setInviteOpen(false);
            setInvited(res);
            invalidate();
          }}
        />
      )}

      {invited && <InvitedRevealModal result={invited} onClose={() => setInvited(null)} />}
    </div>
  );
}
