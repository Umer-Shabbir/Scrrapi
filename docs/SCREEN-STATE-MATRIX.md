# Screen / State Matrix

Treat each numbered screen in `SCREENLIST.md` as one implementation unit.

Within that unit, states are part of the same screen cycle.

Example:

Screen:
    Results

Cycle scope:
    loaded + empty + loading + error + supplied responsive variants

NOT allowed:
    implement loaded Results now and automatically move to Lead Detail.

The supplied handoff contains 23 numbered screens, each with route, priority,
Figma node IDs, states, breakpoints, components, spec, and bugs. The handoff says
all 23 are design-complete. fileciteturn0file0L6-L18

### Recommended order

Use the priority order in `SCREENLIST.md`.

1. Login
2. Jobs / Dashboard
3. New Job Wizard
4. Categories
5. Locations
6. Job Templates
7. Schedules
8. Schedule & Monitoring
9. Results
10. Lead Detail
11. Export
12. Suppression
13. Proxies
14. Integrations
15. Webhook Delivery Log
16. Team & Roles
17. API Keys
18. Audit Log
19. System Health
20. Settings
21. Account & Billing
22. First-run / Compliance
23. Not Found / Error

The exact route and node IDs must always be taken from the supplied screen list,
not invented.
