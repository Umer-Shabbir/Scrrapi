import { Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import RequireAuth from "./components/RequireAuth";
import Account from "./pages/Account";
import ApiKeys from "./pages/ApiKeys";
import AuditLog from "./pages/AuditLog";
import System from "./pages/System";
import Categories from "./pages/Categories";
import Dashboard from "./pages/Dashboard";
import ExportPage from "./pages/Export";
import Integrations from "./pages/Integrations";
import JobWizard from "./pages/JobWizard";
import Locations from "./pages/Locations";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Proxies from "./pages/Proxies";
import Results from "./pages/Results";
import ScheduleDetail from "./pages/ScheduleDetail";
import Schedules from "./pages/Schedules";
import Settings from "./pages/Settings";
import Suppression from "./pages/Suppression";
import Team from "./pages/Team";
import Templates from "./pages/Templates";
import WebhookDeliveryLog from "./pages/WebhookDeliveryLog";

export default function App() {
  return (
    <Routes>
      {/* Outside the shell: no nav to show until there's a session. */}
      <Route path="/login" element={<Login />} />

      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/jobs/new" element={<JobWizard />} />
        <Route path="/categories" element={<Categories />} />
        <Route path="/locations" element={<Locations />} />
        <Route path="/templates" element={<Templates />} />
        <Route path="/schedules" element={<Schedules />} />
        <Route path="/schedules/:id" element={<ScheduleDetail />} />
        <Route path="/results/:jobId" element={<Results />} />
        <Route path="/results/:jobId/lead/:leadId" element={<Results />} />
        <Route path="/export/:jobId" element={<ExportPage />} />
        <Route path="/suppression" element={<Suppression />} />
        <Route path="/proxies" element={<Proxies />} />
        <Route path="/integrations" element={<Integrations />} />
        <Route path="/integrations/webhooks/:id" element={<WebhookDeliveryLog />} />
        <Route path="/integrations/:provider" element={<Integrations />} />
        <Route path="/team" element={<Team />} />
        <Route path="/api-keys" element={<ApiKeys />} />
        <Route path="/audit" element={<AuditLog />} />
        <Route path="/system" element={<System />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/account" element={<Account />} />
      </Route>

      {/* Outside the shell, same as /login -- SCREENLIST.md §23. Previously
          a silent redirect to "/" instead of a real 404. */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
