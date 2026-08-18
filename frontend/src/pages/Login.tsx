// Sign-in. There's no self-serve signup by design -- `licenses` is the paid gate,
// so accounts come from `backend/scripts/create_user.py` (which `npm run dev` runs
// for you on first boot).
//
// Neobrutalist per Figma [SCREEN] login (node 50:2 and sibling state frames) --
// hard ink borders/shadow, flat accent fills, no rounded corners. Scoped to this
// screen only: the rest of the app is still the default MUI theme.

import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent, ClipboardEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Box, Link as MuiLink } from "@mui/material";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";

interface LocationState {
  from?: string;
}

const ink = "#111111";
const white = "#ffffff";
const ink60 = "#6b6b63";
const blue = "#4d7fff";
const pink = "#ff5c8a";
const sand = "#f2eedd";
const rule = "#e4dcc4";
const yellow = "#ffd23f";
const bg = "#fff9ec";

const fontBody = "'Space Grotesk', sans-serif";
const fontHead = "'Archivo Black', sans-serif";
const fontMono = "'JetBrains Mono', monospace";

const hardShadow = `4px 4px 0px ${ink}`;
const cardShadow = `6px 6px 0px ${ink}`;

type Step = "credentials" | "totp";

/** account_locked/invalid_credentials come from the API as ApiError.code; a
 * fetch that never reached the server (offline) throws a plain TypeError. */
type FieldError = { code?: string; message: string; lockedUntil?: string } | null;

function BrandHeader() {
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: "12px", width: "100%" }}>
      <Box sx={{ width: "39.566px", height: "39.566px", display: "grid", placeItems: "center" }}>
        <Box
          sx={{
            width: 36,
            height: 36,
            bgcolor: yellow,
            border: `3px solid ${ink}`,
            transform: "rotate(6deg)",
          }}
        />
      </Box>
      <Box component="p" sx={{ m: 0, fontFamily: fontHead, fontSize: 24, lineHeight: "28px", color: ink }}>
        MAPSCRAPE
      </Box>
    </Box>
  );
}

function FooterNote() {
  return (
    <Box
      component="p"
      sx={{ m: 0, fontFamily: fontBody, fontWeight: 500, fontSize: 11, lineHeight: "15px", color: ink60, textAlign: "center", width: "100%" }}
    >
      No signup — accounts are provisioned via the CLI. API reference at{" "}
      <MuiLink href="/docs" target="_blank" rel="noreferrer" sx={{ color: blue, textDecoration: "underline" }}>
        /docs
      </MuiLink>
      .
    </Box>
  );
}

interface FieldProps {
  label: string;
  help: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  autoComplete?: string;
  autoFocus?: boolean;
  disabled?: boolean;
  error?: boolean;
  errorMessage?: string;
}

function Field({
  label,
  help,
  placeholder,
  value,
  onChange,
  type = "text",
  autoComplete,
  autoFocus,
  disabled,
  error,
  errorMessage,
}: FieldProps) {
  const [focused, setFocused] = useState(false);
  const borderColor = error ? pink : ink;
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: "6px", width: "100%" }}>
      <Box
        component="label"
        sx={{ fontFamily: fontBody, fontWeight: 700, fontSize: "10.5px", letterSpacing: "0.3675px", textTransform: "uppercase", color: ink }}
      >
        {label}
      </Box>
      <Box
        sx={{
          border: `3px solid ${focused ? yellow : "transparent"}`,
          p: "2px",
          width: "100%",
          boxSizing: "border-box",
        }}
      >
        <Box
          component="input"
          type={type}
          value={value}
          disabled={disabled}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          onChange={(e) => onChange((e.target as HTMLInputElement).value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          sx={{
            width: "100%",
            height: "40px",
            boxSizing: "border-box",
            border: `3px solid ${borderColor}`,
            bgcolor: disabled ? sand : white,
            px: "12px",
            fontFamily: fontBody,
            fontWeight: 500,
            fontSize: 13,
            color: ink,
            outline: "none",
            "&::placeholder": { color: ink60 },
            "&:disabled": { borderColor: rule, color: ink60 },
          }}
        />
      </Box>
      <Box
        component="p"
        sx={{
          m: 0,
          fontFamily: fontBody,
          fontWeight: 700,
          fontSize: 10,
          letterSpacing: "0.4px",
          textTransform: "uppercase",
          color: error ? pink : ink60,
          display: "flex",
          alignItems: "center",
          gap: "4px",
        }}
      >
        {error && <WarningAmberIcon sx={{ fontSize: 12 }} />}
        {error ? errorMessage : help}
      </Box>
    </Box>
  );
}

interface PrimaryButtonProps {
  label: string;
  loading?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  type?: "button" | "submit";
}

function PrimaryButton({ label, loading, disabled, onClick, type = "submit" }: PrimaryButtonProps) {
  const inactive = disabled || loading;
  return (
    <Box
      component="button"
      type={type}
      onClick={onClick}
      disabled={inactive}
      sx={{
        width: "100%",
        height: "48px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        px: "24px",
        border: `3px solid ${ink}`,
        bgcolor: inactive ? sand : blue,
        boxShadow: inactive ? "none" : hardShadow,
        cursor: inactive ? "default" : "pointer",
        fontFamily: fontBody,
        fontWeight: 700,
        fontSize: 13,
        textTransform: "uppercase",
        color: inactive ? ink60 : white,
      }}
    >
      {loading ? (
        <Box sx={{ display: "flex", gap: "4px" }}>
          {[0, 1, 2].map((i) => (
            <Box key={i} sx={{ width: 6, height: 6, bgcolor: white }} />
          ))}
        </Box>
      ) : (
        label
      )}
    </Box>
  );
}

function Banner({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <Box
      sx={{
        bgcolor: pink,
        border: `3px solid ${ink}`,
        p: "12px",
        width: "100%",
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        gap: "4px",
        color: ink,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: "6px", fontFamily: fontBody, fontWeight: 700, fontSize: 13 }}>
        <WarningAmberIcon sx={{ fontSize: 16 }} />
        {title}
      </Box>
      <Box component="p" sx={{ m: 0, fontFamily: fontMono, fontWeight: 700, fontSize: 12 }}>
        {subtitle}
      </Box>
    </Box>
  );
}

function formatCountdown(msRemaining: number): string {
  const totalSeconds = Math.max(0, Math.ceil(msRemaining / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export default function Login() {
  const { token, signIn, verifyTotp } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [step, setStep] = useState<Step>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [fieldError, setFieldError] = useState<FieldError>(null);
  const [offline, setOffline] = useState(false);

  const [loginToken, setLoginToken] = useState<string | null>(null);
  const [totpDigits, setTotpDigits] = useState<string[]>(["", "", "", "", "", ""]);
  const [totpError, setTotpError] = useState<string | null>(null);
  const totpRefs = useRef<Array<HTMLInputElement | null>>([]);

  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (fieldError?.code !== "account_locked") return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [fieldError?.code]);

  if (token) return <Navigate to="/" replace />;

  const locked = fieldError?.code === "account_locked";
  const lockedUntilMs = fieldError?.lockedUntil ? new Date(fieldError.lockedUntil).getTime() : 0;
  const lockRemainingMs = lockedUntilMs - now;
  if (locked && lockRemainingMs <= 0 && fieldError) {
    // Cooldown elapsed client-side -- let the next real submit re-check with the server.
    setFieldError(null);
  }

  async function handleCredentialsSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFieldError(null);
    setOffline(false);
    try {
      const result = await signIn(email.trim(), password);
      if (result.totpRequired) {
        setLoginToken(result.loginToken);
        setStep("totp");
        return;
      }
      navigate((location.state as LocationState | null)?.from ?? "/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setFieldError({
          code: err.code,
          message: err.message,
          lockedUntil: err.extra?.locked_until as string | undefined,
        });
      } else {
        setOffline(true);
      }
    } finally {
      setBusy(false);
    }
  }

  function handleTotpChange(index: number, raw: string) {
    const digit = raw.replace(/\D/g, "").slice(-1);
    setTotpDigits((prev) => {
      const next = [...prev];
      next[index] = digit;
      return next;
    });
    if (digit && index < 5) totpRefs.current[index + 1]?.focus();
  }

  function handleTotpKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace" && !totpDigits[index] && index > 0) {
      totpRefs.current[index - 1]?.focus();
    }
  }

  function handleTotpPaste(event: ClipboardEvent<HTMLInputElement>) {
    const pasted = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (!pasted) return;
    event.preventDefault();
    setTotpDigits((prev) => {
      const next = [...prev];
      for (let i = 0; i < 6; i++) next[i] = pasted[i] ?? "";
      return next;
    });
    totpRefs.current[Math.min(pasted.length, 5)]?.focus();
  }

  async function handleTotpSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!loginToken) return;
    setBusy(true);
    setTotpError(null);
    try {
      await verifyTotp(loginToken, totpDigits.join(""));
      navigate((location.state as LocationState | null)?.from ?? "/", { replace: true });
    } catch (err) {
      setTotpError(err instanceof ApiError ? err.message : "Couldn't reach the API server");
    } finally {
      setBusy(false);
    }
  }

  function handleBackToCredentials() {
    setStep("credentials");
    setLoginToken(null);
    setTotpDigits(["", "", "", "", "", ""]);
    setTotpError(null);
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        bgcolor: bg,
        p: 2,
      }}
    >
      <Box
        sx={{
          bgcolor: white,
          border: `3px solid ${ink}`,
          boxShadow: cardShadow,
          p: "40px",
          width: "100%",
          maxWidth: 440,
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
          gap: "24px",
        }}
      >
        <BrandHeader />

        {step === "credentials" ? (
          <>
            <Box component="p" sx={{ m: 0, fontFamily: fontBody, fontWeight: 500, fontSize: 13, lineHeight: "18px", color: ink60, width: "100%" }}>
              Sign in with the account your administrator provisioned.
            </Box>

            {offline && <Banner title="Can't reach the API server" subtitle="Check your connection and retry." />}
            {locked && (
              <Banner
                title={fieldError?.message ?? "Account locked"}
                subtitle={`Try again in ${formatCountdown(lockRemainingMs)}`}
              />
            )}

            <Box component="form" onSubmit={handleCredentialsSubmit} sx={{ display: "flex", flexDirection: "column", gap: "24px", width: "100%" }}>
              <Field
                label="Email"
                help="Provisioned by your administrator"
                placeholder="you@company.com"
                value={email}
                onChange={setEmail}
                type="email"
                autoComplete="username"
                autoFocus
                disabled={locked}
                error={fieldError?.code === "invalid_credentials"}
                errorMessage={fieldError?.code === "invalid_credentials" ? fieldError.message : undefined}
              />
              <Field
                label="Password"
                help="Case-sensitive"
                placeholder="Enter your password"
                value={password}
                onChange={setPassword}
                type="password"
                autoComplete="current-password"
                disabled={locked}
                error={fieldError?.code === "invalid_credentials"}
                errorMessage={fieldError?.code === "invalid_credentials" ? fieldError.message : undefined}
              />
              <PrimaryButton label={offline ? "RETRY" : "SIGN IN"} loading={busy} disabled={locked} />
            </Box>
          </>
        ) : (
          <>
            <Box component="p" sx={{ m: 0, fontFamily: fontBody, fontWeight: 500, fontSize: 13, lineHeight: "18px", color: ink60, width: "100%" }}>
              Enter the 6-digit code from your authenticator app.
            </Box>

            <Box component="form" onSubmit={handleTotpSubmit} sx={{ display: "flex", flexDirection: "column", gap: "16px", width: "100%" }}>
              <Box sx={{ display: "flex", gap: "8px", justifyContent: "center", width: "100%" }}>
                {totpDigits.map((digit, i) => (
                  <Box
                    key={i}
                    component="input"
                    ref={(el: HTMLInputElement | null) => {
                      totpRefs.current[i] = el;
                    }}
                    value={digit}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleTotpChange(i, e.target.value)}
                    onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => handleTotpKeyDown(i, e)}
                    onPaste={handleTotpPaste}
                    autoFocus={i === 0}
                    inputMode="numeric"
                    maxLength={1}
                    sx={{
                      width: 56,
                      height: 56,
                      textAlign: "center",
                      border: `3px solid ${totpError ? pink : ink}`,
                      bgcolor: white,
                      fontFamily: fontBody,
                      fontWeight: 700,
                      fontSize: 20,
                      color: ink,
                      outline: "none",
                    }}
                  />
                ))}
              </Box>
              {totpError && (
                <Box sx={{ display: "flex", alignItems: "center", gap: "4px", fontFamily: fontBody, fontWeight: 700, fontSize: 10, textTransform: "uppercase", color: pink, justifyContent: "center" }}>
                  <WarningAmberIcon sx={{ fontSize: 12 }} />
                  {totpError}
                </Box>
              )}
              <PrimaryButton label="VERIFY" loading={busy} disabled={totpDigits.some((d) => !d)} />
            </Box>

            <Box sx={{ display: "flex", justifyContent: "space-between", width: "100%" }}>
              <Box
                component="button"
                type="button"
                onClick={handleBackToCredentials}
                sx={{ border: "none", bgcolor: "transparent", p: 0, cursor: "pointer", fontFamily: fontBody, fontWeight: 700, fontSize: 11, color: ink60 }}
              >
                BACK
              </Box>
              <Box
                component="button"
                type="button"
                sx={{ border: "none", bgcolor: "transparent", p: 0, cursor: "pointer", fontFamily: fontBody, fontWeight: 700, fontSize: 11, color: blue }}
              >
                RESEND CODE
              </Box>
            </Box>
          </>
        )}

        <FooterNote />
      </Box>
    </Box>
  );
}
