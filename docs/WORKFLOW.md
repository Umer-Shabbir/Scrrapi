# Operating Procedure

## Phase A — Discovery

Before touching UI:

1. Read `SCREENLIST.md`.
2. Determine the current screen by priority/state.
3. Inspect repository structure.
4. Inspect frontend routes.
5. Inspect backend routes/controllers/services/models.
6. Find the existing API client.
7. Find the shared design system/components.
8. Inspect git status.
9. Identify verification commands.

Create a concise internal implementation plan before editing.

## Phase B — Screen contract

For the selected screen record:

- route;
- Figma page;
- Figma node IDs;
- states;
- breakpoints;
- components;
- data requirements;
- actions;
- backend dependencies;
- known QA bugs.

The screen contract is the boundary of the current cycle.

## Phase C — Backend capability audit

For every functional interaction in the Figma screen, trace it to:

`UI action -> frontend service/hook -> API -> controller/handler -> service -> model/database`

Classify each requirement:

- EXISTING — already works;
- PARTIAL — API exists but lacks data/behavior;
- MISSING — no backend capability;
- FRONTEND-ONLY — local state/presentation;
- DESIGN-ONLY — visual treatment.

Only PARTIAL/MISSING requirements may trigger backend changes.

## Phase D — Frontend cleanup

Find all code responsible for the old screen.

Check route imports and dependency usage.

Remove or replace old UI cleanly. Keep:

- business logic;
- backend contracts;
- authentication;
- API clients;
- reusable primitives.

Delete dead CSS/components/routes only when no longer referenced.

## Phase E — Implementation

Implement from outer structure inward:

1. page shell/layout;
2. responsive layout;
3. shared components/tokens;
4. content blocks;
5. data binding;
6. interactions;
7. loading/empty/error states;
8. modals/drawers;
9. accessibility/keyboard behavior;
10. visual polish.

Do not build future screens.

## Phase F — Integration

Connect the screen to real APIs.

For each request verify:

- URL/method;
- auth;
- payload;
- response shape;
- loading;
- error;
- empty;
- optimistic/pessimistic behavior where relevant;
- retry behavior where relevant.

## Phase G — QA

Use `docs/QA-GATE.md`.

If a Figma issue is documented as a known bug, fix it as part of this screen if
the fix is in scope.

Cross-cutting issues should be fixed at the shared component/token level, not
copied into individual screens.

## Phase H — Stop

After QA:

- update `.claude/workflow-state.json`;
- provide completion report;
- STOP.

No automatic next screen.
