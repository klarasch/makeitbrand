# NOTES

## Phase 0 — sandbox test (`phase0/sandbox.html`)

Test file: one 540×540 board, Geist (OFL) inlined as a woff2 data URI, a button that
serializes the board into SVG `<foreignObject>`, draws it to a 2x canvas, fires an
`<a download>` click, and also renders the PNG inline as the right-click fallback.
The page logs each check.

Key technique finding: an SVG loaded as an `<img>` cannot see document fonts, so the
`@font-face` (with its data URI) must be copied *into* the foreignObject's `<style>`.
The runtime must do this per export.

| surface | JS runs | font in page | font in PNG | canvas tainted | download fires | inline fallback |
|---|---|---|---|---|---|---|
| Local Chromium (Claude desktop browser pane, file://) | yes | yes | yes | no | click dispatched, arrival unverified | yes |
| Claude Chat, file returned by Claude, opened in preview | yes | yes | yes (Geist) | no | yes | not needed |
| Cowork file preview | ? | ? | ? | ? | ? | ? |
| Safari (file://) | yes | ? | ? | no | yes, file lands in Downloads | ? |

**Result: pass.** Export via foreignObject works in the surfaces that matter (Chat preview of a
Claude-returned file, Safari, Chromium). Inline-PNG fallback kept in the runtime but not the primary
path. Cowork untested.

## Phase 1 — contract review (Fable, 2026-09-13)

Applied to PRIMITIVES.md, MEDIA.md, BRANDING.md, the demo brand and the hand-written sheet:

- Medium profiles gained a CSS rule each (the runtime can't read MEDIA.md); defaults for ground
  and `data-v` moved into profiles. New stock profile `nametag`. `custom` requires `data-like`.
- Type factor k re-derived (social 2.25, chat-header 1.5); budgets tightened to match. The 10%
  auto-shrink is gone; overflow is only marked.
- `data-fill` scoped to board children; charts and diagrams fill cards implicitly.
- Grounds table incl. `transparent` via new `--inset-ground` token; logo `auto` rules explicit.
- Diagram: `data-span="c,r"`, only box/pill, deterministic single-bend routing and label placement,
  edge label = element text.
- Charts: `stat` removed (tile gets `.tile__spark`), `data-highlight` given one meaning per chart
  shape, label/legend drawing rules fixed, `data-stack`/`data-min`/`data-max` cut.
- `data-bind` propagates `<strong>`/`<b>`, forbids `<br>`, obeys the tightest budget.
- Batch: `sheet.py` materialises; template shown but not exported; `{column}` in titles.
- "Copy changes" keeps `data-overflow`/`data-invalid` so Claude sees them. Dev form needs http.
- Cut for the POC: `.bleed`/scrim, empty image slots, table row editing, cylinder/circle shapes.
- Demo brand: accent darkened to #c8441d (white on it 4.9:1), `--good`/`--bad` pass 4.5:1 on surface.

Decided with the user: no hard runtime line budget. POC exports diagrams as transparent PNG; real
SVG export (for slaydy decks and slide tools) is planned as Phase 5 in HANDOFF.md.

## Phase 1 — blind authoring test (fresh session, 2026-09-13)

A session with no context wrote `demo/sheets/hiring-onboarding.html` from the docs alone and listed
19 ambiguities. Fixed in PRIMITIVES.md/MEDIA.md: separator rule vs URLs and CTAs; pinned logo reserves
its band; `data-note` also flags Claude's assumptions; `data-alt`; chat-header one-line character
budget and eyebrow+lead wording; leftward/upward edge routing; ports allowed for direction; label
segment measured in px; edge crossings; group label position; node caption not counted and may hold a
step number; branches without diamonds; faint outline on transparent-ground nodes.
Left for SKILL.md (Phase 4): make mode must ask for missing content (role, how to apply, which
flow) instead of inventing it, and the brief format (`tone=`, audience).
Expected, not a gap: no runtime/sheet.py yet, so the sheet can't render or be inlined.

## Phase 2 — runtime (2026-09-13)

`runtime.css` (~345 lines), `runtime.js` (~800 lines), `sheet.py` (inliner, pulled forward from
Phase 4 so the delivered form can be tested). Verified in the Claude desktop browser pane:

- Both hand-written sheets render: profiles, grounds (incl. transparent + checkerboard), type scale,
  containers, tiles, table, logo variants, diagram node placement (edges/charts are Phase 3).
- Edit mode: plain-text editing, ⌘B wraps/unwraps `<strong>`, Enter adds list items or a `<br>` in
  unbound headings, Tab cycles fields, ⌘Z/⇧⌘Z, `data-bind` propagates live, notes via the Note button
  render as chips and land as `data-note`.
- Save HTML round-trips: an unedited sheet serialises identical to the source (whitespace aside).
  Copy changes gives the same board markup, derived attributes stripped.
- Export: all boards to 2x PNG with Geist and data-URI logos; the transparent inset keeps alpha.
  The inlined sheet makes zero network requests.
- Overflow marking works: the blind-test onboarding diagram (7 columns, `.h3` labels) is flagged.
  → PRIMITIVES §7 now says `.h3` node text only up to 5 columns.

Findings:
- A relative `url()` inside a custom property resolves against the page, not the brand stylesheet;
  the runtime finds the declaring sheet via CSSOM. (Only matters in dev form.)
- Chrome's `CSSStyleRule.cssRules` exists (nesting) — walk style first, then children.
- Export stalls while the tab is in the background (image decode is throttled). Fine for a user
  clicking a button; matters for headless batch export (Phase 4 `export.py` must keep the page active).
- CSS `pow()` is used for the type scale (Chrome 120+, Safari 15.4+, Firefox 118+).

To test in Claude Chat: `python3 sheet.py demo/sheets/phase1-handwritten.html -o dist-sheets/phase1-handwritten.html`.
- Claude Chat preview (user, 2026-09-13): edit + bind, ⌘B, PNG export, Copy changes (clipboard),
  Save HTML all work. **Phase 2 accepted.** Feedback: diagram looks random and the dashboard poor
  (no edges/charts yet, and the look needs design care) → Phase 3 includes a visual pass on both.

## Phase 3 — diagram + chart (2026-09-13)

Added to runtime.js (~1150 lines now): deterministic edge routing per PRIMITIVES §7 (facing sides,
one bend, rounded corners, arrowheads, dashed/both), edge labels as the editable `.edge` element on
the longest segment, node heights equalised per diagram, cell-snapped node drag in edit mode with
undo; bar (v/h, grouped, direct labels ≤ 8 bars else gridlines, legend ≥ 2 series), line (nice
ticks, end labels with collision push), donut (gapped arcs, outside labels), tile sparklines;
`data-highlight` and limits enforced with `data-invalid`.

Design pass after user feedback ("diagram random, dashboard poor"): diagram rows size to content and
centre (they used to stretch to the board), visible group outline, bigger arrowheads, a cleaner demo
flow; dashboard rebuilt as a tile row with sparklines plus two titled chart cards; tick labels carry
only the precision their step needs.

Dev aid: `tools/shoot.sh URL out.png [W H]` screenshots a sheet with headless Chrome (Chrome writes
the file then hangs; the script kills it). Used because the in-app browser pane freezes when hidden.
Not yet verified by hand: node drag and PNG export of the new diagram in Claude Chat.

## Rich composition pass (2026-09-13) — benchmark: user's reference infographic

The user's reference (a dark, art-directed joint-research infographic) set the bar. It needed things
the contract didn't have, all added as primitives (no sheet CSS):

- ground `art` (brand `--art` layered gradients + `--art-ink`), `--bg-tone` for logo variants
- card/tile tone `glass`; `.eyebrow[data-rule]` section headers; `.row[data-justify=between]`,
  `.row[data-divide]`; `hr.rule`; `.stat` hero figures; `.icon[data-icon]` (brand iconset, inlined
  as SVG so it exports crisply and survives Phase 5); `.lockup` co-brand with `img.partner`;
  `figure.quote` with avatar or initials; `footer.band`
- chart `range` (spans on one axis, step labels with drawn arrows, bracketed `data-gap` callout) and
  `dots` (share-of-100 field, fill or deterministic scatter); `--chart-accent` for single-emphasis
  marks so a neon brand colour can be used without failing the categorical validator
- profile `infographic` (1080×1350, k 1.25): the k rule gave 1.5, but research posts are meant to be
  zoomed; measured against the reference, body ≈ 20 px at 1080
- `?mib-board=N` solo mode: one board at true size on a transparent page, for headless export

Second demo brand `halcyon` (dark, fictional; icons lifted from slaydy's set) and
`demo/sheets/halcyon-research.html` recreate the reference's structure with fictional content.
Iterated with headless screenshots: fixed wrapping rows that collapsed the chart card, range label
collisions, reference rows in ink instead of a second chart colour. Inlined output is pixel-identical
to the dev form.

Phase 4 in parallel: build.sh / take-update.sh / CUSTOMIZING.md / UPDATING.md written by a Sonnet
agent from slaydy's, reviewed (syntax, refuses without SKILL.md, profile sync check verified against
the real MEDIA.md: in sync). SKILL.md written (modes make/revise/batch/setup/update; "never invent
the user's content" from the blind test; composition guidance aimed at designed-looking output).

## Phase 4 acceptance — blind runs with Sonnet (2026-09-14)

Three fresh Sonnet agents, each given only `dist/makeitbrand` and a user-style brief: Kestrel API
announcement (square, portrait, Slack header, Confluence header); architecture diagram + Q3 dashboard;
a new Halcyon research infographic. All three produced sheets and PNGs from SKILL.md alone. Quality:
infographic strong, dashboard good, diagram decent, announcement clean but plain (Kestrel has no art).

Findings and fixes:
- export.py couldn't size boards in minified sheets (esbuild drops attribute-selector quotes) →
  regex accepts both forms. Both diagram and infographic runs hit it and worked around with --no-min.
- An agent handed off an overflowing LinkedIn square: nothing checked. export.py now loads the sheet
  once more and reports every `data-overflow` / `data-invalid`, exiting 1; SKILL.md §3 says a flagged
  board is not done.
- `<strong>` vanished on an accent ground (accent = ground) → underline there, or brand `--accent-strong`.
- Fan-out edges from one node shared a line and stacked labels → the runtime spreads connections that
  share a node side along it, ordered by the other end; PRIMITIVES §7 gained a fan-out note.
- Tiles without sparklines left a void → the figure sits at the tile bottom.
- `range` couldn't show mixed units (11 min vs 9 days) → optional per-row `label`.
- Contract gaps: `glass` on tiles, where icons may sit.
Not changed: Kestrel stays the default brand; Kestrel boards stay flat (no `--art`) by brand choice.

## Phase 7 — sheet chrome design pass, and brand polish (2026-09-14)

- Toolbar rebuilt: sheet title with board count, board tabs, a zoom segmented control, 16px stroke
  icon buttons (edit/done, undo, note, save) with custom tooltips showing shortcuts, "Copy changes", and
  one primary "Export all". Frames: title, medium and size as quiet metadata, a warning pill, and a PNG
  button that appears on hover. Toast, dialogs and note chips restyled to match.
- Chrome tone follows the surround: the runtime reads `--app-bg` luminance and switches to dark chrome
  (Halcyon's dark surround made the old black labels invisible). Chrome tokens `--c-*` in runtime.css.
- Kestrel gained an `--art` ground (warm paper, a soft accent glow, a cool counterweight); its voice
  file puts social, infographic and nametag boards on it.
- Nametag template redesigned: logo, ruled event eyebrow, name, role, team chip, footer band.
- Found: the dev server was gone after the night, so screenshots now come from the inlined sheets
  over file://, which is also what users open.
