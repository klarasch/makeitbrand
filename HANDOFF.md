# makeitbrand — POC handoff

Read this whole file before touching anything. It records decisions already made with the
user; do not reopen them. Where it says "lift from slaydy", copy the approach or the code from
`~/Code/slidecraft` (the slaydy upstream, github.com/klarasch/slaydy) and adapt names.

## What this is

A Claude skill that is trained once on a brand and then produces any on-brand visual:
social posts, Slack/Confluence graphics, diagrams and charts for slides, dashboards,
nametags from a CSV, or any custom WxH. Output is always one editable HTML file ("sheet")
that previews inline in Claude Chat / Cowork, where the user makes last text edits and
downloads a PNG per artboard (native SVG for diagrams follows in Phase 5). Slaydy does this for slide decks; this does it for
everything else.

The core competence is not a layout library. It is three separable kinds of knowledge:

1. **Brand** — tokens, type, logo rules, chart palette, voice, and how the brand degrades at
   small sizes or on dark grounds.
2. **Medium** — dimensions, safe areas, ground, viewing context. One short profile per medium.
3. **Composition** — a small set of primitives (text, containers, diagram, chart, table, logo)
   and rules for combining them so everything reads as one system.

A new medium costs one profile file, not a new skill.

## Decisions (do not reopen)

- **No artifacts required.** The sheet is a single self-contained HTML file. It renders in the
  chat file preview and in Chrome. Artifacts are an optional later path for shareable
  dashboards only.
- **Self-contained by construction, written once.** Content-first like slaydy's export:
  markup at the top, hand-readable; minified runtime CSS + JS appended at the end of body;
  fonts and images inlined as data URIs. Claude edits only the markup part. No save-back
  machinery, no File System Access, no standalone.py.
- **Export is client-side.** Each artboard serializes to SVG `<foreignObject>` and rasterizes
  to a canvas at 2x, then downloads. Therefore every primitive must stay inside the CSS subset
  that rasterizes faithfully: no `backdrop-filter`, no external `url()`, no blend modes, no
  `filter: blur` on print-critical elements. This is a contract rule in PRIMITIVES.md.
- **Headless Chrome export is a Claude-side extra** for batch jobs (200 nametags), not the
  primary path.
- **Edits flow back to Claude via clipboard.** A "Copy changes" button copies the edited
  markup (artboards only, no runtime) so the user can paste it into chat. Edits also live in
  the DOM if the user downloads the HTML.
- **One sheet, many artboards.** One artboard per target medium. `data-bind="id"` on a text
  element propagates its edit to same-id elements on sibling artboards.
- **Diagram editing** = edit text, drag nodes, connectors follow. Not a freeform canvas.
- **Dashboards are static** with inline data in the POC.
- **Upstream/fork model is slaydy's, verbatim in spirit.** Upstream files are replaced
  byte-for-byte on update; fork files are never touched. Lift `take-update.sh`, `build.sh`,
  and the `SKILL.fork.md` composition from slaydy; rename the stamp file to
  `.makeitbrand-upstream`.
- **Brand file is a superset of a slaydy theme**: it must contain slaydy's nine tokens under
  the same names so a trained brand can emit `themes/<brand>.css` for slaydy later.

## Repo layout

```
UPSTREAM (replaced on update)                 FORK (never touched by an update)
runtime.js  runtime.css  runtime.min.*        SKILL.fork.md          name, description, standing orders
SKILL.md                                      brand/<name>.css       tokens + @font-face
PRIMITIVES.md   markup contract               brand/<name>.md        voice + adaptation rules
MEDIA.md        stock medium profiles         brand/assets/          logo variants, fonts, imagery
BRANDING.md  CUSTOMIZING.md  UPDATING.md      brand/default          one line: which brand
build.sh  take-update.sh  export.py           media/<own>.md         fork's own medium profiles
demo/           demo brand + demo sheets      custom.css custom.js   extensions, loaded after runtime
```

`build.sh` composes `dist/<name>/` from `SKILL.fork.md` + upstream `SKILL.md` body, minifies
the runtime (esbuild via npx, fallback: copy), and inlines nothing — inlining happens per
sheet at generation time (a small `sheet.py` or a documented shell recipe: concat markup +
`<style>` + `<script>`, base64 fonts/images).

## Brand model (`brand/<name>.css`)

Slaydy's nine, same names: `--app-bg --bg --fg --muted --faint --surface --accent --accent-2
--accent-fg` (+ `--wash-opacity`, may be unused). Plus:

```
--font-display --font-body --font-mono
--scale          type scale ratio (e.g. 1.25); runtime derives sizes from --base and --scale
--base           base font size at 1x artboard (e.g. 16px)
--space          spacing unit (e.g. 8px)
--radius --stroke
--chart-1 … --chart-6   categorical palette, validated for contrast on --bg
--chart-seq-0 --chart-seq-1   ends of the sequential ramp
--logo-light --logo-dark --logo-mono    url(data:…) of each variant
--logo-min       minimum logo height in px
--good --bad     status colours for KPI deltas (added after the Phase 1 review)
--inset-ground   light|dark: the slide ground transparent boards expect (same)
```

`brand/<name>.md` = voice rules (slaydy BRANDING.md §4 style: 5–10 concrete, checkable) plus
**adaptation rules**, e.g. "below 600px wide drop the eyebrow", "on dark ground use
--logo-mono", "never place the logo in the top-left on social", "charts never use --accent-2".

## Medium profiles (`MEDIA.md`, one section each, ≤20 lines)

Each profile is prose for the model **plus one CSS rule** (`.board[data-medium=id]{--board-w …
--k …}`) for the runtime, which can't read markdown. Stock rules ship in `runtime.css`; a fork's
in `media/<id>.css`.

Fields: id, dimensions (px), safe area, ground (brand bg / transparent / white-or-dark
unknown), expected viewing width, type floor (min body px), constraints, what to avoid.

Stock set for the POC:

| id | px | notes |
|---|---|---|
| `social-square` | 1080×1080 | phone viewing; type floor 28px |
| `social-portrait` | 1080×1350 | same |
| `social-landscape` | 1200×628 | link previews; logo required |
| `chat-header` | 1600×400 | Slack/Confluence; ground unknown → brand bg, never transparent |
| `slide-inset` | 1600×900 | transparent ground; goes into a slide; no logo |
| `dashboard` | 1440×900 | dense; tiles + 2 charts |
| `nametag` | 1050×1500 | print, 3.5×5 in @300dpi; batch template |
| `custom` | WxH from brief | `data-like` names the profile it borrows from |
| data-driven | any profile | template artboard × rows (CSV/JSON) |

## Primitives (`PRIMITIVES.md`, the model-facing contract)

- Text: `.eyebrow .display .h1 .h2 .h3 .lead .body .caption .chip`, `<strong>` = the highlight
  (accent in titles, 600 in body; ⌘B in edit mode). Lift table from slaydy LAYOUTS.md.
- Containers: `.stack`, `.row`, `.grid` (`data-cols`), `.card`, `.bento`, `.tile` (KPI, with optional
  `.tile__spark` sparkline).
- Media: `<figure class="media">`, `.logo` slot (`data-variant="auto|light|dark|mono"`).
- Diagram: `<div class="diagram" data-cols data-rows>` with `.node` (`data-at="c,r"`,
  `data-span="c,r"`), `.group`, `.note`, and `<i class="edge" data-from data-to
  data-style="arrow|line|dashed|both">label</i>` (label is the element's text, so it is editable).
  Deterministic single-bend routing. Geometric on purpose, so it maps 1:1 onto native SVG (Phase 5). Runtime positions nodes on the grid and draws edges as
  SVG connectors. In edit mode nodes drag by grid cell.
- Chart: `<figure class="chart" data-type="bar|line|donut" data-series='[…]'
  data-labels='[…]'>`. Runtime renders SVG from `--chart-*`. Follow the dataviz skill's form
  heuristics (no 3D, no gradients, direct labels over legends where possible).
- Table: plain `<table>` with `.table` class; runtime styles.
- Every artboard: `<section class="board" data-medium="social-square" data-title="…">`.
  Custom size: `data-w data-h`.
- `data-bind="id"` propagation; `data-note` change requests (lift from slaydy).
- Rasterization-safe CSS rule, stated explicitly.
- Density budgets per medium (a table, like slaydy's), because type cannot be resized by hand.

## Runtime (`runtime.js` / `runtime.css`)

Soft size target: stay lean and justify big additions; there is no hard line budget. Claude never
reads the runtime and fonts dominate sheet size, so line count only matters as scope discipline.

Sheet view: boards laid out at true px size, scaled to fit width, zoom control, board tabs
when >3. Edit mode (lift from slaydy: contenteditable plaintext-only on text primitives, ⌘B
toggles `<strong>`, undo stack, `data-note` chip). Connector layer + node drag. Chart
renderer. Export: per-board PNG at 2x (foreignObject → canvas; transparent boards keep alpha),
"Download all" (zip via JSZip from cdnjs is acceptable; fallback: sequential downloads).
"Copy changes" (serialize `.board` elements, strip contenteditable/data-gen). No presenter
view, no print CSS, no save-to-folder.

## SKILL.md modes

- **setup** — train a brand from URL / PDF / logo. Lift slaydy §8. Writes `brand/*`,
  `SKILL.fork.md`. Show resolved tokens before writing.
- **make** — brief (what, for which media, tone) → one sheet with one board per medium.
  One round of questions max, defaults offered, "go" accepts.
- **revise** — edit the sheet's markup in place, apply `data-note`s, or apply pasted markup
  from "Copy changes".
- **batch** — template board + CSV/JSON → one board per row; offer `export.py` for >20.
- Hard rules: never write CSS/JS into a sheet; only PRIMITIVES.md markup; budgets are
  ceilings; on chat surfaces build in scratch and hand over only `sheet.html`.

## Phases and acceptance

**Phase 0 — sandbox test (do first, half a day).** A 60-line HTML file with an inlined font,
one board, a button that rasterizes it via foreignObject and triggers a download. Open it as
a file preview in Claude Chat and in Cowork. Record: does JS run, does the inlined font
render, does the download fire, does the canvas taint. If download is blocked, the fallback is
rendering the PNG inline for right-click-save. Write the result into `NOTES.md`. Everything
after depends on this.

**Phase 1 — contracts.** `PRIMITIVES.md`, `MEDIA.md`, `BRANDING.md`, demo brand
(stock brands in `brand/`: kestrel, halcyon). Accept: a human can hand-write a valid sheet from the docs alone.
Gate: a Fable review of the contract before Phase 2 (done 2026-09-13; findings applied, see NOTES.md).

**Phase 2 — runtime.** Sheet view, edit mode, export, bind propagation, copy changes.
Accept: hand-written sheet from phase 1 previews, edits, exports at 2x with correct fonts.
(Passed 2026-09-13 in the in-app browser and in a Claude Chat file preview.)

**Phase 3 — diagram + chart.** Connectors, node drag, bar/line/donut, tile sparklines.
Accept: an architecture diagram on `slide-inset` exports as a clean transparent PNG at 2x.

**Phase 4 — skill.** `SKILL.md`, `SKILL.fork.md` composition, `build.sh`, `take-update.sh`,
`sheet.py` (inliner), `export.py` (headless Chrome batch). Install as a local skill and run
the demo set through it.

**Phase 5 — native SVG export (after the POC, wanted).** A foreignObject SVG only renders in
browsers, so diagram boards (and later charts) get a second, real-SVG serializer: nodes as
`<rect>`, text as `<text>` lines read from the live layout, edges as the paths the runtime already
draws. Two flavours: **for slaydy**, inline SVG that uses `var(--accent)` etc. and the deck's fonts
(pastes into a `data-custom` figure and follows the deck theme); **for slides** (PowerPoint,
Keynote, Google Slides, Figma), baked colours, text as `<text>` with a system fallback, with text
outlined to paths as a later option (needs a font parser, ~170 KB). Accept: the pipeline inset
pastes into a slaydy deck and follows a theme switch, and opens editable in Figma.

**Phase 6 — rich dashboards (after the POC, wanted).** When a dashboard is published as an artifact
it is a rich HTML document, not a static board: hover tooltips, a table view, crisp at any width,
and made to be pasted into a slide deck. Same markup contract and brand tokens; the static
`dashboard` board stays the image export of it.

**Phase 7 — sheet chrome design pass (after the POC, wanted; first pass done 2026-09-14).** The sheet UI (toolbar, frames,
edit mode, notes, dialogs) should look like a seasoned UI designer made it: quiet, typographic,
precise, not a generic assistant UI and not text-heavy. Icons where they read faster than words,
tight spacing, one restrained accent, keyboard hints on hover.

**Phase 8 — a real brand fork (after the POC, wanted).** Create a fork repo of makeitbrand the way
`~/Code/acme-slaydy` forks slaydy: its own `SKILL.fork.md`, `brand/`, `media/`, the upstream files
taken with `take-update.sh`, and a dry-run update that reports clean.

**Visual ambition.** The Phase 3 look is a floor, not the target: diagrams and charts should be able
to go further (richer illustration-grade compositions) within the rasterization-safe rules.

**Demo set (the POC is done when all five pass):** an announcement as social-square +
social-portrait + chat-header on one sheet; a Confluence header; an architecture diagram on
a transparent slide inset; a 4-tile KPI dashboard with two charts; 12 nametags from a CSV.
Pass = they read as one brand, survive edit → export, and the fork can take an upstream
update with `take-update.sh --dry-run` reporting clean.

## What to lift from slaydy, where

| need | slaydy file | notes |
|---|---|---|
| edit mode, undo, ⌘B, data-note | `runtime.js` ~L520–L700, L1090, L1400–L1760 | strip slide nav/presenter |
| text primitives, budgets style | `LAYOUTS.md` top | rename to PRIMITIVES.md |
| brand tokens + voice file | `BRANDING.md` §1, §4 | drop §1b print section entirely |
| fork/upstream mechanics | `take-update.sh`, `build.sh`, `CUSTOMIZING.md`, `UPDATING.md` | rename stamp |
| SKILL.fork.md composition | `CUSTOMIZING.md` Layer 0 | as is |
| setup mode | `SKILL.md` §8 | as is, minus skeleton.html |
| content-first single file | `standalone.py` | only the ordering idea; reimplement small |

## Not in the POC

Live data, freeform drawing, artifact publishing, animation, PDF export, image generation,
multi-brand switching inside one sheet.
