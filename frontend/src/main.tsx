import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import AppErrorBoundary from "./components/AppErrorBoundary";
import { ColorModeProvider } from "./ColorModeContext";
import { AuthProvider } from "./auth/AuthContext";
import { JobDraftProvider } from "./state/JobDraftContext";
// Installs the console.error/window.onerror capture the 500 screen's "last 3
// console errors" disclosure reads from -- must run before anything else can
// log, so imported for its side effect only, first.
import "./errorLog";
import "./animations.css";
import "./responsive.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A 401 clears the session (api/client.ts) — retrying it just burns requests
      // on a token the server has already rejected.
      retry: (failureCount, error) =>
        !(error instanceof Error && error.name === "ApiError") && failureCount < 2,
      refetchOnWindowFocus: false,
    },
  },
});

// AuthProvider uses useQuery, so QueryClientProvider has to sit outside it.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <ColorModeProvider>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <AuthProvider>
              <JobDraftProvider>
                <App />
              </JobDraftProvider>
            </AuthProvider>
          </BrowserRouter>
        </QueryClientProvider>
      </ColorModeProvider>
    </AppErrorBoundary>
  </React.StrictMode>,
);
