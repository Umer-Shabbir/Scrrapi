# Figma MCP Protocol

Use the Figma MCP available in the Claude Code environment when possible.

## For every screen

1. Open the exact Figma node from `SCREENLIST.md`.
2. Inspect the frame hierarchy.
3. Inspect shared component instances.
4. Inspect typography and token values.
5. Inspect responsive frames.
6. Inspect relevant state frames.
7. Check whether any node is an orphan/mis-filed state.
8. Compare implementation against the live canvas, not an old screenshot.

The handoff says live node IDs were pulled from the current Figma canvas and should
supersede stale audit claims when they conflict. fileciteturn0file0L34-L38

## Canvas placement

When creating or updating Figma frames:

- do not use Section wrappers;
- use the existing page/canvas namespace;
- use `SCREEN/<id>/<state>/<breakpoint>` naming where applicable;
- never overlap newly placed frames;
- determine a free bounding-box location before creating a frame;
- keep a consistent grid/gutter.

## Visual implementation

Prefer exact:

- spacing;
- typography;
- borders;
- hard shadows;
- iconography;
- component states;
- responsive reflow.

Do not approximate a component when a shared Figma component already exists.

## Known shared issues

The supplied handoff identifies 12 cross-cutting issues and explicitly recommends
fixing them at the shared-component level first. fileciteturn0file0L73-L118

The handoff also states that 768px is the largest remaining design gap and that
only a small subset of screens currently has 768 frames. fileciteturn1file0L69-L76

Treat missing 768 designs as a product/design gap rather than inventing arbitrary
Figma screens. Implement responsive behavior only where the design provides a
clear rule or the user explicitly asks for it.
