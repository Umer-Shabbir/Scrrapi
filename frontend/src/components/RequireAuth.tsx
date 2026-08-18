// Route guard. Bounces to /login when there's no usable session, remembering
// where the user was headed so sign-in can send them back there.

import { Box, CircularProgress } from "@mui/material";
import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { token, ready } = useAuth();
  const location = useLocation();

  // A token in localStorage isn't proof of a live session -- wait for /api/auth/me
  // before rendering, or a stale token flashes the app then throws everyone out.
  if (token && !ready) {
    return (
      <Box sx={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }

  return <>{children}</>;
}
