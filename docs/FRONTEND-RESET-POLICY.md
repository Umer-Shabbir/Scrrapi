# Frontend Reset Policy

The goal is replacement, not layering.

## Before deletion

For every old component/page:

1. Find imports/references.
2. Check route registration.
3. Check shared component usage.
4. Check CSS/module/style usage.
5. Check tests/stories if present.

## Safe replacement

Prefer:

- replace old page implementation at the existing route;
- keep API/service contracts;
- reuse shared infrastructure;
- delete obsolete page-specific styling;
- delete dead imports.

## Shared component changes

If the old component is used by multiple screens:

- fix the shared component if the Figma system requires it;
- preserve compatibility;
- verify current screen;
- record affected screens but do not implement them.

## Do not create

- `/new-screen` while `/screen` remains live unless explicitly required;
- duplicate `ButtonV2`, `TableV2`, etc. without a demonstrated need;
- hidden legacy pages;
- unreachable dead routes;
- CSS overrides whose only purpose is to fight the old UI.

## Completion condition

The selected route must render the new implementation without requiring the old
UI to exist underneath it.
