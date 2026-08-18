# MapScrape — Neo-Brutalist Design System

A bold, high-contrast design language for the Google Maps scraper dashboard. Built to feel confident, honest, and a little playful — the opposite of a generic SaaS template.

This is the **visual and behavioural** specification. The **Figma production**
rules — frame naming, auto-layout mapping, canvas slots, component sets — live in
[DESIGN-SYSTEM-FIGMA.md](DESIGN-SYSTEM-FIGMA.md). Design agents read both.

---

## 1. Design Principles

1. **Show the structure, don't hide it.** Borders, shadows, and grids are visible on purpose — nothing floats without a visible edge.
2. **Flat color, no gradients.** Every surface is a single flat hue. Depth comes from offset shadows, not blur.
3. **Contrast over subtlety.** Text is always near-black on a light fill, or white on a dark fill. No gray-on-gray.
4. **Function is decoration.** Data (stats, statuses, ratings) gets the boldest color treatment — it's the hero, not the chrome around it.
5. **Slightly imperfect.** Small rotations (-6°) on logo marks/icons keep it from feeling too rigid.
6. **Accent is a signal, not a mood.** A color on screen must mean something. Four yellow blocks that mean four different things is the failure mode this system is most prone to — budget one accent per meaning, per screen.
7. **Density is a feature.** This is an operator tool read in bulk. Compact by default, comfortable on request. Whitespace is earned, not sprayed.
8. **Every state is designed.** Empty, loading, error and confirm are not afterthoughts — a screen shipped with only its happy path is half a screen.

---

## 2. Color Palette

### Core tokens

| Token | Hex | Usage |
|---|---|---|
| `--ink` | `#111111` | All text, all borders, all shadows |
| `--ink-60` | `#6B6B63` | Secondary text ONLY (captions, meta, placeholder). Never a border. |
| `--bg` | `#FFF9EC` | App background (warm off-white, never pure white) |
| `--white` | `#FFFFFF` | Card/panel surfaces, table backgrounds |
| `--sand` | `#F2EEDD` | Table headers, inset wells, disabled fills |
| `--rule` | `#E4DCC4` | Interior dividers (table rows, list separators) |
| `--yellow` | `#FFD23F` | Primary highlight — active nav, primary stat, callout badges, `pending` |
| `--green` | `#3DDC84` | Success / positive, `done`, `valid`, `healthy`, live indicators |
| `--pink` | `#FF5C8A` | Alerts, `failed`, `invalid`, destructive, secondary stat |
| `--blue` | `#4D7FFF` | Primary actions, links, `running`, in-progress |
| `--purple` | `#B18CFF` | Tertiary accent — credits/usage panels, quaternary stat |
| `--orange` | `#FF8A3D` | `risky` / degraded / warning-but-not-failed. The state between yellow and pink. |
| `--teal` | `#2FD6C4` | `new since last run`, diff-add, sixth chart series |

`--orange` and `--teal` are additions to the original five-accent set. They exist
because the app has more distinct states than five colors can carry: without
them, `risky` borrows pink (reads as failed) and `new` borrows green (reads as
done). Do not use them decoratively.

### Semantic mapping — binding

| Meaning | Token | Applies to |
|---|---|---|
| Neutral / queued | `--sand` | Status pills, empty meters |
| In progress / active | `--blue` | Job `running`, nav hover, links, primary buttons |
| Waiting / pending / attention | `--yellow` | Target `waiting`, quota 75–90%, unverified |
| Degraded / risky | `--orange` | Proxy cooling, email `risky`, webhook backing off |
| Success / healthy / verified | `--green` | Job `done`, email `valid`, proxy healthy |
| Failure / destructive | `--pink` | Job `failed`, email `invalid`, delete actions |
| New / added | `--teal` | New-since-last-run, diff additions |
| Metered / quota | `--purple` | Usage panels, seat counters |

One meaning, one color, everywhere. A `failed` chip on Results and a `failed` row
on the webhook log are the same pink.

### Dark mode

Dark mode is a **role swap**, not an inversion. Accents keep their hues (they are
already high-chroma) but the ground and ink trade places.

| Token | Light | Dark |
|---|---|---|
| `--ink` | `#111111` | `#F5F0E3` |
| `--bg` | `#FFF9EC` | `#14140F` |
| `--white` (surface) | `#FFFFFF` | `#1E1E18` |
| `--sand` | `#F2EEDD` | `#2A2A22` |
| `--rule` | `#E4DCC4` | `#3A3A30` |
| `--ink-60` | `#6B6B63` | `#9A9A8C` |
| Accents | as above | unchanged |

Shadows in dark mode use `--ink` (now the light value) at the same offsets — the
hard shadow reads as a light edge rather than a dark one, which is the correct
brutalist translation. Text on accent fills stays near-black (`#111111`) in both
modes, because the accents themselves do not darken.

**Rules:**
- Backgrounds are either `--bg`, `--white`, `--sand`, or one flat accent color — never a tint/shade mix.
- Every colored block gets a `3px solid var(--ink)` border, no exceptions.
- Never use an accent as body-text color on a light ground. Accents are fills.
- Maximum three accent colors visible in one viewport, not counting status pills.

---

## 3. Typography

| Role | Font | Weight | Notes |
|---|---|---|---|
| Display / H1 / brand wordmark | `Archivo Black` | 900 (single weight) | Always uppercase or tight tracking. Used sparingly — page titles, card headers, logo. |
| Body / UI / labels | `Space Grotesk` | 400 / 500 / 700 | Workhorse font for everything else: inputs, table cells, nav, buttons. |
| Numeric / tabular | `Space Grotesk` | 500 / 700, `font-variant-numeric: tabular-nums` | Every column of numbers, every timer, every id. Non-negotiable — proportional digits make a stat column shimmer as it updates. |
| Code / ids / cron | `JetBrains Mono` | 400 / 700 | Job ids, API keys, cron strings, error codes, JSON payloads. |

**Scale:**

| Step | Size / line-height | Font | Use |
|---|---|---|---|
| `display` | 32 / 34 | Archivo Black | Login wordmark, empty-state headline |
| `h1` | 24 / 28 | Archivo Black | Page title |
| `h2` | 18 / 22 | Archivo Black | Section header inside a page |
| `h3` | 14 / 18, uppercase, +0.02em | Space Grotesk 900 | Panel header |
| `stat` | 22–24 / 24 | Archivo Black | Stat tile value |
| `stat-lg` | 34 / 36 | Archivo Black | Hero metric (one per screen, max) |
| `body` | 13 / 18 | Space Grotesk 500 | Paragraphs, descriptions |
| `cell` | 12.5 / 16 | Space Grotesk 500 | Table cells, compact rows |
| `label` | 10.5–11 / 14, uppercase, +0.03–0.04em | Space Grotesk 700 | Eyebrows, field labels, column headers |
| `micro` | 10 / 12, uppercase, +0.04em | Space Grotesk 700 | Badge text, meta |
| `mono` | 12 / 16 | JetBrains Mono 400 | Ids, keys, cron, code |

Labels and eyebrows are **always uppercase**. Body copy is sentence case. Never mix.
Line length caps at **72 characters** for body copy — a description that runs the
full width of a 1440 frame is unreadable.

---

## 4. Borders & Shadows (the signature move)

This system has exactly two elevation states — flat and "hard shadow." No blurred drop-shadows anywhere.

```css
/* Standard border on every discrete element */
border: 3px solid var(--ink);

/* "Hard shadow" — the core brutalist signature */
.hard {
  border: 3px solid var(--ink);
  box-shadow: 6px 6px 0 var(--ink);   /* large elements: panels, sidebar modules */
}

/* Smaller controls use a tighter offset */
.hard-sm {
  border: 3px solid var(--ink);
  box-shadow: 4px 4px 0 var(--ink);   /* buttons, badges */
}

.hard-xs {
  border: 3px solid var(--ink);
  box-shadow: 3px 3px 0 var(--ink);   /* active nav items */
}

/* Overlays sit above everything and get the biggest offset */
.hard-lg {
  border: 3px solid var(--ink);
  box-shadow: 10px 10px 0 var(--ink); /* modals, drawers, popovers */
}
```

**Elevation ladder — there are exactly five levels, and nothing invents a sixth:**

| Level | Treatment | What lives here |
|---|---|---|
| 0 | border only, no shadow | Sidebar, top bar, table rows, inputs at rest |
| 1 | `hard-xs` (3px) | Active nav item, selected chip |
| 2 | `hard-sm` (4px) | Buttons, badges, small controls |
| 3 | `hard` (6px) | Cards, panels, stat tiles |
| 4 | `hard-lg` (10px) | Modals, drawers, dropdowns, toasts |

**Rule of thumb:** shadow offset scales with element size — bigger surface, bigger offset. Never use `border-radius` above `0px`; corners are always square.

Border weights: `3px` for structural edges and every discrete block, `2px` for
badges and inner controls, `1px` never — it disappears against the pattern.

---

## 5. Spacing & Layout

- Base unit: **4px**. Common steps: 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48.
- **Grid:** 12 columns, 24px gutter, 32px outer margin at 1440. Content max-width `1160px` inside the main region; wider screens gain margin, not column width.
- Sidebar width: `250px`, fixed, `3px solid` right border (no shadow — it's structural, not a floating card). Collapses to a `64px` icon rail below 1024.
- Top bar height: `64px`, `3px solid` bottom border.
- Content padding: `24px 32px`.
- Card/panel gaps: `16–20px`.
- Stat row: 4-column grid, `16px` gap.
- Main split view (map + table): flex, `20px` gap, map takes `1fr`, results table takes `1.4fr`.
- Drawer width: `480px` (Lead Detail), `560px` (form drawers).
- Modal widths: `440px` (confirm), `640px` (standard), `880px` (mapping tables).

### Breakpoints

| Name | Width | Changes |
|---|---|---|
| `desktop` | 1440 | Hero frame. Full sidebar, 4-col stat row, split views side by side. |
| `laptop` | 1024 | Sidebar → 64px icon rail with tooltips. Stat row 2×2. Split views stack. |
| `tablet` | 768 | Sidebar → overlay drawer behind a hamburger. Tables → stacked cards, one card per row, label/value pairs. Bulk action bar docks to the bottom. |

Below 768 is out of scope.

---

## 6. Components

### Buttons

| Variant | Fill | Text | Border | Shadow |
|---|---|---|---|---|
| Primary | `--blue` | white | 3px ink | `hard-sm` |
| Secondary | `--white` | ink | 3px ink | none |
| Destructive | `--pink` | white 700 | 3px ink | `hard-sm` |
| Ghost | transparent | ink | 3px transparent | none |
| Icon-only | `--white` | ink | 3px ink | none, `hard-sm` on hover |

- Always uppercase label, `700` weight, `13px`.
- Sizes: `sm` 32px tall / 12px padding-x, `md` 40px / 16px, `lg` 48px / 24px.
- **Interaction physics — the signature:** on hover the button translates
  `-1px, -1px` and the shadow grows to `5px 5px`. On press it translates
  `+3px, +3px` and the shadow collapses to `0 0` — the button visibly *lands*.
  120ms, no easing curve fancier than `ease-out`.
- **Focus:** `3px` yellow outline offset `2px`, in addition to the border. Never
  replace the border with the focus ring.
- **Disabled:** `--sand` fill, `--ink-60` text, `3px solid --rule` border, no
  shadow, no translate. Never reduce opacity — a 40%-opacity brutalist button
  looks broken, not disabled.
- **Loading:** label swaps to a 3-square marching indicator, width is preserved
  so the layout does not jump, button stays disabled.

### Cards / Stat tiles

- One flat accent color per tile (yellow, green, pink, purple — cycle in that order across a stat row).
- Pink tiles get white text; all others keep near-black text for contrast.
- Label (uppercase, 11px) → Value (Archivo Black, 22–24px) → Delta (bold, 11px, colored to match sentiment).
- Delta uses a `▲`/`▼` glyph plus the sign — never color alone.
- A stat tile is **not** clickable unless it carries a visible chevron.

### Navigation

- Inactive items: transparent background, `3px solid transparent` (reserves space so active state doesn't shift layout).
- Hover: `--sand` fill, border stays transparent.
- Active item: `--yellow` fill + `.hard-xs` shadow.
- Icons: 17px, 2.5px stroke weight, no fill — outline style only.
- **Group headers** (`RUN` / `DATA` / `ADMIN`): `micro` type, `--ink-60`, 16px top margin, no border.
- **Badges** in nav sit right-aligned, `micro` type, accent fill, 2px border.
- Collapsed rail: icon centred in a 64px cell, active state is a full-width yellow block with the `hard-xs` shadow, tooltip on hover.

### Badges / Status pills

- Square-ish, `2px solid var(--ink)` border (thinner than cards), flat fill, uppercase 10.5px bold text, 4px/8px padding.
- Fill follows the semantic mapping table in §2. A pill also carries a
  1-character glyph prefix (`●` running, `✓` done, `✕` failed, `!` warning) so
  the state survives grayscale and color-blindness.
- Sizes: `md` 22px tall (default), `sm` 18px (inside table cells).

### Tables

- Header row: `--sand` fill, `3px solid ink` bottom border, uppercase `label` type, sticky on scroll.
- Body rows: `2px solid var(--rule)` divider (lighter than the ink border used elsewhere — reserve full ink weight for structural edges only).
- Row heights: **compact 36px** (default), **comfortable 44px**.
- No zebra striping, no hover blur — hover fills the row with `--sand`; selected
  fills with `--yellow` at full strength and adds a `3px` left ink bar.
- Numeric columns are right-aligned and tabular. Text columns left-aligned.
  Never centre a data column.
- **Column resize handle:** 3px ink line on drag, no ghost.
- **Sort indicator:** a solid ink triangle in the header, plus the column header
  goes 900 weight. Not an outline chevron.
- **Frozen columns** (Score, Name on Results) get a `3px solid ink` right edge so
  the freeze boundary is visible rather than implied by a shadow.
- **Bulk action bar** appears docked to the bottom of the table region as a full
  ink-black block with accent text, `hard-lg` shadow, when ≥1 row is selected.

### Forms

- Field label: `label` type, 6px below-gap, always above the input (never inline,
  never floating).
- Input: 40px tall, `--white` fill, `3px solid ink`, 12px padding-x, `body` type.
- Focus: `3px` yellow outline offset `2px`; the input itself does not change fill.
- Placeholder: `--ink-60`, sentence case, describes the format (`plumber, roofer`)
  rather than repeating the label.
- Help text: `micro` type in `--ink-60`, directly under the field.
- Error: field border becomes `3px solid --pink`, and the help slot is replaced by
  the error in `--pink` 700 with a `!` glyph. The field never turns pink-filled.
- Required is marked on the label with a pink `*`; optional fields are marked
  `(optional)` in the label when a form is mostly required.
- **Select / combobox:** same box, plus a 3px ink chevron. Menu is a `hard-lg`
  panel, max-height 320px, items 36px, hover `--sand`, selected `--yellow`.
- **Checkbox:** 18px square, `3px solid ink`, checked fill `--blue` with a white
  2.5px stroke tick. **Radio:** same square with an inset 8px ink square — this
  system has no circles.
- **Switch:** 44×24 track, `3px solid ink`, off fill `--sand`, on fill `--green`,
  knob is an 16px ink square that slides. Square knob, not round.
- **Slider:** 6px ink track, filled portion `--blue`, thumb a 20px square with
  `3px solid ink` and a `hard-sm` shadow. Value shown in a yellow pill above the
  thumb while dragging.
- **Chip input:** chips are `--white` with `2px solid ink` and a `✕`; the
  add-affordance is the bare text cursor at the end of the row, not a button.

### Overlays

- **Modal:** `--white` panel, `3px solid ink`, `hard-lg`, over a `--ink` scrim at
  70% — a flat dark scrim, never a blur. Header is an ink-black bar with white
  `h3` text and a white `✕`. Actions bottom-right, primary last.
- **Drawer:** slides from the right, `3px solid ink` on the left edge only,
  `hard-lg` toward the content. Same ink header bar.
- **Popover / dropdown:** `hard-lg`, no arrow/tail — the offset shadow already
  anchors it.
- **Toast:** stacks bottom-right, `--white` fill with a `6px` left bar in the
  semantic accent, `3px solid ink`, `hard-sm`. Auto-dismiss 6s, pauses on hover,
  carries an action link when one exists.
- **Tooltip:** solid `--ink` block, white `micro` text, no border, no shadow, no
  arrow. 200ms delay.

### Progress & loading

- **Determinate bar:** 16px tall, `3px solid ink`, `--sand` track, `--blue` fill,
  square end. Percentage in `label` type sits outside the bar, right-aligned.
- **Indeterminate:** three 12px ink squares marching left to right, 400ms apart.
  No spinners anywhere in this system.
- **Skeleton:** `--sand` blocks with a `3px solid --rule` border at the exact
  dimensions of the content they replace. They do not shimmer — a static block is
  honest; a shimmer is decoration pretending to be progress.
- **Meter** (quota, seats): same bar, fill color follows thresholds — `--green`
  under 75%, `--yellow` 75–90%, `--pink` above 90%.

### Empty, error and confirm states

- **Empty state:** a `--yellow` square icon block rotated -6°, a `display`-size
  headline stating what is missing in plain words, one `body` line explaining
  why, and exactly one primary action. Never two competing calls to action.
- **Error state:** same layout, `--pink` block, the error class as `h2`, the
  human cause as `body`, the error id in `mono` for the bug report, and a Retry.
- **Confirm (destructive):** modal with a `--pink` header bar, the count of what
  will be affected stated numerically ("This removes 1,284 stored rows"), and a
  typed confirmation for anything irreversible. The destructive button is the
  primary; Cancel is secondary.

### Map / data panels

- Grid background using a 2px pattern line (`#EFE6CF`) at 36px spacing to suggest a map without needing real tile imagery.
- Location markers: flat-color squares rotated 45° (diamonds), `3px solid ink` border — no drop shadow, no gradient pin shape.
- Marker color carries meaning (score band or status), and a cluster is a larger
  diamond with the count in `micro` white on ink.
- Live/status callouts: solid `--ink` background chip with accent-colored text (e.g. yellow text on black), not a translucent overlay.

### Charts

There is one chart in the app (the delta series on Schedule Detail); this section
exists so a second one cannot be invented in a different language.

- Bars are flat accent fills with `3px solid ink`, no rounding, no gradient.
- Series order and color: `--teal` (new) → `--yellow` (changed) → `--ink-60`
  (gone). Meaning first, aesthetics second.
- Axes are `3px solid ink` on the left and bottom only. Gridlines are `2px solid
  --rule`, horizontal only.
- Labels in `micro`, values in tabular numerals.
- No legend swatch without a text label beside it.
- Tooltip on hover is the standard ink tooltip.

---

## 7. Motion

Motion in this system is **mechanical, not organic**. Things snap, land, and
slide on straight lines. Nothing eases in a curve you would call "smooth."

| Interaction | Duration | Easing | Change |
|---|---|---|---|
| Button hover | 120ms | ease-out | translate -1/-1, shadow 4→5 |
| Button press | 80ms | linear | translate +3/+3, shadow → 0 |
| Nav active change | 0ms | — | instant; the yellow block does not animate |
| Modal / drawer enter | 180ms | ease-out | slide 24px + opacity 0→1 |
| Modal / drawer exit | 120ms | ease-in | reverse |
| Toast enter | 160ms | ease-out | slide up 16px |
| Row expand | 160ms | ease-out | height only |
| Skeleton → content | 0ms | — | instant swap, no crossfade |
| Live feed row insert | 200ms | ease-out | slide down from 0 height, yellow flash that decays over 600ms |
| Progress bar fill | 300ms | linear | width |

Rules: nothing animates longer than 300ms. Nothing scales. Nothing rotates except
the -6° brand marks, which are static. `prefers-reduced-motion: reduce` drops every
translate and slide to an instant state change and keeps only the opacity fades.

---

## 8. Iconography

- Outline-only SVG icons, `2–2.5px` stroke, no fills except for filled brand marks (e.g. the logo pin).
- Icon size: 15–17px in nav/buttons, 20px in empty states, matched to the adjacent text's cap-height.
- Square caps and square joins — round caps read as a different system.
- Small intentional rotation (±6°) is reserved for brand/logo marks only — don't rotate functional icons.
- An icon never appears alone as the sole label of a destructive action.

---

## 9. Content & voice

The UI copy is part of the design system; the visual language is blunt and the
words match.

- **Say the number.** "1,284 rows" not "many rows". "Next run in 4h 12m" not
  "soon".
- **Name the actor.** "Google Maps stopped returning results" not "Something went
  wrong".
- **Buttons are verbs.** `START JOB`, `GENERATE`, `REVOKE KEY`. Never `OK`,
  `Submit`, or `Yes`.
- **Errors state the fix.** "No active license — run `npm run license -- extend`"
  beats "Unauthorized".
- **No exclamation marks.** No "Oops". No "Whoops". No emoji in product chrome.
- **Sentence case for prose, uppercase for labels.** Title Case never appears.

---

## 10. Accessibility Notes

- Text-on-color contrast is generally strong (near-black ink on light accent fills), but verify pink (`#FF5C8A`) with white text meets WCAG AA at your chosen font sizes — bump to bold/700 weight if used below 14px. `--pink` with `--ink` text passes comfortably and is the safer default; reserve white-on-pink for ≥14px 700.
- `--ink-60` on `--bg` is the lowest-contrast pair in the system. It passes AA for
  body text but not for anything below 12px — do not use it for `micro`.
- Don't rely on color alone for status — pair every status color with an explicit label (`Verified`, `Pending`) and the glyph prefix from §6.
- Keep the 3px border on all interactive elements — it doubles as a visible focus/hit-target indicator, which flat borderless brutalist knockoffs often lose.
- **Focus order** follows visual order. The sidebar is one tab stop with arrow-key
  navigation inside it, not fourteen stops.
- **Skip to content** link, visible on focus as a yellow `hard-sm` block top-left.
- Minimum hit target 32×32 including the border; table row actions get 36×36.
- Live regions: the activity feed is `aria-live="polite"`, toasts are `polite`,
  a job failure toast is `assertive`.
- Every table has a caption or `aria-label` naming what it lists; sortable headers
  expose `aria-sort`.
- Modals trap focus, restore it on close, and close on `Esc` unless they are a
  typed-confirm.

---

## 11. Quick Reference — CSS Tokens

```css
:root{
  /* ground */
  --ink:#111111;
  --ink-60:#6B6B63;
  --bg:#FFF9EC;
  --white:#FFFFFF;
  --sand:#F2EEDD;
  --rule:#E4DCC4;

  /* accents */
  --yellow:#FFD23F;
  --green:#3DDC84;
  --pink:#FF5C8A;
  --blue:#4D7FFF;
  --purple:#B18CFF;
  --orange:#FF8A3D;
  --teal:#2FD6C4;

  /* type */
  --font-display:'Archivo Black', sans-serif;
  --font-body:'Space Grotesk', sans-serif;
  --font-mono:'JetBrains Mono', monospace;

  /* structure */
  --border:3px solid var(--ink);
  --border-thin:2px solid var(--ink);
  --shadow-xl:10px 10px 0 var(--ink);
  --shadow-lg:6px 6px 0 var(--ink);
  --shadow-md:4px 4px 0 var(--ink);
  --shadow-sm:3px 3px 0 var(--ink);

  /* rhythm */
  --sp-1:4px;  --sp-2:8px;  --sp-3:12px; --sp-4:16px;
  --sp-5:20px; --sp-6:24px; --sp-8:32px; --sp-10:40px; --sp-12:48px;

  --row-compact:36px;
  --row-comfortable:44px;
  --sidebar:250px;
  --sidebar-rail:64px;
  --topbar:64px;
}

:root[data-theme="dark"]{
  --ink:#F5F0E3;
  --ink-60:#9A9A8C;
  --bg:#14140F;
  --white:#1E1E18;
  --sand:#2A2A22;
  --rule:#3A3A30;
}
```

---

## 12. Do / Don't

| Do | Don't |
|---|---|
| Flat colors, hard offset shadows | Gradients, blurred box-shadows |
| Square corners everywhere | Rounded corners / pill shapes |
| Uppercase labels & buttons | Mixed-case UI chrome |
| One accent color per meaning | Reusing yellow for four unrelated things |
| Ink-black borders on every block | Borderless "floating" cards |
| Marching squares for indeterminate load | Spinners |
| Static skeleton blocks | Shimmer sweeps |
| Tabular numerals in every number column | Proportional digits in a live counter |
| Disabled = sand fill + rule border | Disabled = 40% opacity |
| Say the count | "Several", "many", "a few" |
| Square switch knobs and radio marks | Circles anywhere |
| Flat 70% ink scrim behind modals | Backdrop blur |

---

*Reference mockup: `5-neobrutalist.png` (dashboard screen — search/filters, live map, stat tiles, results table).*
