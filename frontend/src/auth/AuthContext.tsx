// Session state: who's signed in, their license, and the token every request
// carries. The token lives in localStorage so a refresh doesn't sign you out;
// `setUnauthorizedHandler` wires the API client's 401s back here so an expired
// token clears the session instead of leaving the UI stuck on failing requests.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, clearToken, getToken, setToken, setUnauthorizedHandler } from "../api/client";
import type { CurrentUser, License } from "../types";

/** Result of `signIn`: either the session is live, or a TOTP code is needed next. */
export type SignInResult = { totpRequired: false } | { totpRequired: true; loginToken: string };

interface AuthContextValue {
  token: string | null;
  user: CurrentUser | null;
  license: License | null;
  /** True once /api/auth/me has answered — gates the redirect in RequireAuth. */
  ready: boolean;
  signIn: (email: string, password: string) => Promise<SignInResult>;
  verifyTotp: (loginToken: string, code: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const queryClient = useQueryClient();

  const signOut = useCallback(() => {
    clearToken();
    setTokenState(null);
    // Everything cached is scoped to the signed-out user — jobs, results, license.
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    setUnauthorizedHandler(signOut);
    return () => setUnauthorizedHandler(null);
  }, [signOut]);

  const userQuery = useQuery({
    queryKey: ["auth", "me", token],
    queryFn: () => api.get<CurrentUser>("/api/auth/me"),
    enabled: !!token,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const licenseQuery = useQuery({
    queryKey: ["auth", "license", token],
    queryFn: () => api.get<License>("/api/auth/license"),
    enabled: !!token,
    retry: false,
  });

  const signIn = useCallback(async (email: string, password: string): Promise<SignInResult> => {
    const result = await api.login(email, password);
    if ("totp_required" in result) {
      return { totpRequired: true, loginToken: result.login_token };
    }
    setToken(result.access_token);
    setTokenState(result.access_token);
    return { totpRequired: false };
  }, []);

  const verifyTotp = useCallback(async (loginToken: string, code: string) => {
    const { access_token } = await api.verifyTotp(loginToken, code);
    setToken(access_token);
    setTokenState(access_token);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user: userQuery.data ?? null,
      license: licenseQuery.data ?? null,
      ready: !token || !userQuery.isLoading,
      signIn,
      verifyTotp,
      signOut,
    }),
    [token, userQuery.data, userQuery.isLoading, licenseQuery.data, signIn, verifyTotp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
