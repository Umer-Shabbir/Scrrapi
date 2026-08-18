# Screen QA Gate

A screen is complete only when the following are checked.

## Functional

- [ ] route loads;
- [ ] authentication/session behavior works;
- [ ] API calls use real backend data;
- [ ] primary actions work;
- [ ] secondary actions work;
- [ ] validation works;
- [ ] loading works;
- [ ] empty works where specified;
- [ ] error works where specified;
- [ ] modal/drawer interactions work;
- [ ] navigation works.

## Visual

- [ ] correct Figma frame used;
- [ ] layout matches;
- [ ] typography matches;
- [ ] colors/tokens match;
- [ ] border widths match;
- [ ] shadows match;
- [ ] icons are actual icon components where required;
- [ ] radios/checkboxes follow the design system;
- [ ] badges include correct semantic glyphs;
- [ ] spacing is consistent;
- [ ] no clipping/overflow;
- [ ] responsive breakpoint matches supplied design.

## Engineering

- [ ] no duplicate old UI;
- [ ] no dead imports;
- [ ] no unnecessary new architecture;
- [ ] no fake production data;
- [ ] no console errors;
- [ ] build passes;
- [ ] lint/typecheck passes where available;
- [ ] tests pass where available.

## Stop condition

If a non-critical issue remains, document it.

If a critical functional failure remains, do not claim completion. Fix it before
stopping or clearly report the blocking reason.
