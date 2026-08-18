# Backend Gap Policy

The agent is allowed to build backend functionality, but only when the screen
requires functionality that genuinely does not exist.

## Decision tree

### A. Does an API already exist?

If yes:
- reuse it;
- fix frontend wiring first.

### B. Does an API exist but return insufficient data?

If yes:
- extend the existing endpoint/service minimally;
- preserve compatibility where practical.

### C. Is the operation represented by an existing service/model but not exposed?

If yes:
- expose it through the established API architecture.

### D. Is there no model/service/endpoint?

If the Figma interaction requires persistence or server-side business logic:
- add the minimal backend capability.

### E. Is it purely UI state?

Examples:
- opening a drawer;
- tab selection;
- sorting a loaded dataset locally;
- visual validation;
- responsive layout.

Do not add backend work.

## Required backend checklist

When backend changes are justified:

- route/API contract documented;
- authentication enforced;
- authorization checked;
- input validated;
- database migration added if necessary;
- transaction/consistency considered;
- errors mapped to the project's existing error convention;
- tests added where conventions exist;
- frontend integration verified.

## Anti-patterns

Never:

- invent duplicate APIs;
- create a second database model for an existing concept;
- hard-code Figma sample data;
- add a new framework;
- rewrite unrelated backend modules;
- expose admin functionality without authorization;
- silently change existing API semantics just to simplify the UI.
