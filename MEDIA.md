<!-- Upstream-owned: every update replaces this file whole. A fork adds its own profiles as
     media/<id>.md + media/<id>.css in the same shape; a fork profile with a stock id overrides it. -->

# Medium profiles

A medium is where a board ends up. Its profile fixes everything about the board that is not content
or brand. Picking the medium is picking the profile; nothing else is tuned per board.

Every profile exists twice, and the two must agree:

- **prose** (this file) — for the model: why the numbers are what they are, what to avoid.
- **a CSS rule** — for the runtime, which can't read this file. Stock rules ship inside
  `runtime.css`; a fork's go in `media/<id>.css`, which `sheet.py` inlines as `<style data-media>`.
  The rule sets only these custom properties, and is bound by PRIMITIVES.md §12:

```css
.board[data-medium="<id>"] {
  --board-w: 1080px;  --board-h: 1080px;
  --safe-t:96px; --safe-r:135px; --safe-b:96px; --safe-l:135px;
  --k: 2.25;                        /* type factor, PRIMITIVES.md §3 */
  --floor: 28px;                    /* min body size; the runtime raises k to meet it */
  --logo-h: 56px;                   /* 0 = this medium carries no logo */
  --ground-default: bg;             /* bg | surface | accent | inverse | transparent */
  --v-default: spread;              /* top | center | bottom | spread */
  --dpi: 300;                       /* print profiles only: px per inch, which sets the PDF page size */
}
```

`--dpi` is left out on screen profiles (it defaults to 96, so a 1080 px board is a 810 pt page, 11.25
in). A print profile sets the resolution its pixels were designed at: a 1050 px nametag at 300 is a
3.5 in page. Only PDF export reads it.

A `custom` board takes `--board-w`/`--board-h` from its `data-w`/`data-h` and every other property
from its `data-like` profile (the runtime reads them off a hidden probe board with that medium).

Prose fields, in this order: **px**, **safe**, **ground**, **viewing** (the width the image is
typically seen at, which is why `k` is what it is), **k** and **floor**, **logo**, **delivery** (only
when it isn't one PNG per board), **constraints**, **avoid**. Density budgets per medium are in PRIMITIVES.md §11.

---

## social-square

- **px** 1080 × 1080
- **safe** 96 135 96 135 — the side margins also cover a 3:4 profile-grid crop
- **ground** brand
- **viewing** ~375 px wide on a phone (≈ 0.35×)
- **k** 2.25 · **floor** 28 px
- **logo** optional, 56 px
- **constraints** one idea per board; the headline must survive at thumbnail size
- **avoid** paragraphs, charts with axes, tables, small print

```css
.board[data-medium="social-square"]{--board-w:1080px;--board-h:1080px;--safe-t:96px;--safe-r:135px;--safe-b:96px;--safe-l:135px;--k:2.25;--floor:28px;--logo-h:56px;--ground-default:bg;--v-default:spread}
```

## social-portrait

- **px** 1080 × 1350
- **safe** 96 96 140 96 — the bottom sits under caption and like UI on some feeds
- **ground** brand
- **viewing** ~375 px wide on a phone
- **k** 2.25 · **floor** 28 px
- **logo** optional, 56 px
- **constraints** as social-square; the extra height is for one more element, not smaller type
- **avoid** as social-square

```css
.board[data-medium="social-portrait"]{--board-w:1080px;--board-h:1350px;--safe-t:96px;--safe-r:96px;--safe-b:140px;--safe-l:96px;--k:2.25;--floor:28px;--logo-h:56px;--ground-default:bg;--v-default:spread}
```

## carousel

- **px** 1080 × 1350 (4:5), every page the same
- **safe** 110 120 110 120 — LinkedIn's document viewer lays its title bar over the top and its page
  arrows over the side edges
- **ground** brand; the cover and the last page may take `art` or `accent`, the pages between share
  one quieter ground. The runtime marks a middle page `data-invalid` when its ground differs from
  the others' — fix the ground, don't widen the check
- **viewing** in the feed without opening it: ~375 px wide on a phone, ~555 px on a desktop
- **k** 2.25 · **floor** 28 px
- **logo** optional, 48 px: on the cover and the last page, not in between
- **delivery** a PDF (LinkedIn document post), one board per page in sheet order. PNGs only when the
  user asks for an image carousel on another network
- **constraints** 4–10 pages. The cover is the hook: a display line and a one-line lead, nothing
  else. Each page between makes one point, and they share a structure (the same eyebrow form,
  "Step 2", "Myth 3", and the same element order), so paging feels like a rhythm, not a new layout.
  The last page is the takeaway or call to action. A running `footer.band` or eyebrow with one
  `data-bind` on every page ties the set together
- **avoid** mixing media in one carousel, a new ground on every page, a page that needs zooming
  (that is an `infographic`), a slide deck's worth of text

```css
.board[data-medium="carousel"]{--board-w:1080px;--board-h:1350px;--safe-t:110px;--safe-r:120px;--safe-b:110px;--safe-l:120px;--k:2.25;--floor:28px;--logo-h:48px;--ground-default:bg;--v-default:spread}
```

## infographic

- **px** 1080 × 1350 (4:5)
- **safe** 72 72 72 72
- **ground** brand; `art` is its natural ground when the brand has one
- **viewing** a desktop feed at ~555 px wide (≈ 0.5×), and opened full-screen on a phone to read.
  Deliberately denser than the k rule gives: readers expect to zoom a research post
- **k** 1.25 · **floor** 20 px
- **logo** required, 48 px, usually in a header `.row` with a `.lockup` or a badge
- **constraints** a dense, sectioned research or results post: header row, a `.h1`, a divided lead,
  then 2–3 sections each introduced by `.eyebrow[data-rule]` (a `glass` card with a chart, a stat
  row, a quote), and an optional `footer.band`. Every section makes one point
- **avoid** a display line, more than one chart per section, sections without an eyebrow

```css
.board[data-medium="infographic"]{--board-w:1080px;--board-h:1350px;--safe-t:72px;--safe-r:72px;--safe-b:72px;--safe-l:72px;--k:1.25;--floor:20px;--logo-h:48px;--ground-default:bg;--v-default:top}
```

## social-landscape

- **px** 1200 × 628
- **safe** 64 72 80 72 — some platforms overlay the page title along the bottom
- **ground** brand
- **viewing** ~500 px wide in a feed (≈ 0.4×)
- **k** 2.25 · **floor** 28 px
- **logo** required, 48 px
- **constraints** a link preview: heading, logo, at most one lead. No display step
- **avoid** body text, charts

```css
.board[data-medium="social-landscape"]{--board-w:1200px;--board-h:628px;--safe-t:64px;--safe-r:72px;--safe-b:80px;--safe-l:72px;--k:2.25;--floor:28px;--logo-h:48px;--ground-default:bg;--v-default:spread}
```

## chat-header

- **px** 1600 × 400
- **safe** 48 200 48 200 — Confluence covers crop to the page width on narrow windows
- **ground** unknown host (light or dark) → always a painted ground, never `transparent`
- **viewing** ~900 px wide in a Confluence page or Slack post (≈ 0.55×)
- **k** 1.5 · **floor** 22 px
- **logo** optional, 48 px
- **constraints** one line of heading, plus at most an eyebrow above it and a lead below it
- **avoid** multi-line headings, body text, charts

```css
.board[data-medium="chat-header"]{--board-w:1600px;--board-h:400px;--safe-t:48px;--safe-r:200px;--safe-b:48px;--safe-l:200px;--k:1.5;--floor:22px;--logo-h:48px;--ground-default:bg;--v-default:center}
```

## slide-inset

- **px** 1600 × 900
- **safe** 40 40 40 40 — the slide around it provides the margin
- **ground** transparent; text and fills follow the brand's `--inset-ground` (PRIMITIVES.md §2)
- **viewing** placed at 60–80 % of a 1280 px slide (≈ 0.5–0.65×)
- **k** 1.5 · **floor** 22 px
- **logo** none — the slide carries it
- **constraints** a diagram, a chart, a table or a card group; a heading only if the slide has none
- **avoid** a display line, backgrounds that fight the slide

```css
.board[data-medium="slide-inset"]{--board-w:1600px;--board-h:900px;--safe-t:40px;--safe-r:40px;--safe-b:40px;--safe-l:40px;--k:1.5;--floor:22px;--logo-h:0px;--ground-default:transparent;--v-default:top}
```

## dashboard

- **px** 1440 × 900
- **safe** 32 32 32 32
- **ground** brand
- **viewing** 1:1 on a laptop screen
- **k** 1 · **floor** 14 px
- **logo** optional, 24 px
- **constraints** a heading, then a `.bento` of tiles and up to three chart cards. Static numbers
  written into the markup
- **avoid** display type, prose, decorative imagery, an `accent` ground

```css
.board[data-medium="dashboard"]{--board-w:1440px;--board-h:900px;--safe-t:32px;--safe-r:32px;--safe-b:32px;--safe-l:32px;--k:1;--floor:14px;--logo-h:24px;--ground-default:bg;--v-default:top}
```

## nametag

- **px** 1050 × 1500 (3.5 × 5 in at 300 dpi)
- **safe** 210 90 90 90 — about 0.3 in at the sides, and a top band clear of the clip or lanyard hole
- **ground** brand
- **viewing** printed, read at arm's length
- **k** 2.5 · **floor** 36 px
- **logo** required, 80 px
- **delivery** a print PDF from `export.py --pdf`: `--paper a4` or `letter` for office printing
  (four tags a sheet, cut marks), or one 3.5 × 5 in page per tag for a print shop or badge printer.
  `--bleed` runs the ground 1/8 in past the trim so a slightly off cut shows no paper edge: use it
  for a print shop, and for office sheets cut on a trimmer. Without it the page is the trim size
- **constraints** a batch template: name, role, optionally a team line. Names are the only large
  text. Budgets are in characters (PRIMITIVES.md §11), checked against the longest row
- **avoid** a display line, charts

```css
.board[data-medium="nametag"]{--board-w:1050px;--board-h:1500px;--safe-t:210px;--safe-r:90px;--safe-b:90px;--safe-l:90px;--k:2.5;--floor:36px;--logo-h:80px;--ground-default:bg;--v-default:spread;--dpi:300}
```

## custom

- **px** `data-w` × `data-h` from the brief
- `data-like` is required and supplies everything else. Pick it by how the image is **seen**, not how
  big it is: a 3000 px banner shown at 600 px wide is `data-like="social-landscape"`, not `dashboard`

---

## Illustration fit

`figure.illo` (PRIMITIVES.md §6b) suits a `social-square`, `social-portrait` or `carousel` board
that needs a visual anchor beyond type, and an `infographic` section that isn't carrying a chart. It
crowds a `dashboard` (data only), a `nametag` (no room, no reason) and `chat-header` (one line, no
figure); a `slide-inset` stays to the slide's own visuals, so bring one only if the slide has none.
At most one illustration per board — it is the visual anchor, not decoration alongside a chart.

## Writing a profile for a fork

Two files: `media/<id>.md` (one prose section in the shape above, ≤ 20 lines) and `media/<id>.css`
(the one rule). Add a budget row for it in the brand voice file, since PRIMITIVES.md is upstream's.

Derive `k` from viewing: take the smallest comfortable apparent body size (≈ 12.5 px on a screen), divide by
the viewing scale, divide by the brand's `--base`, round **up** to 0.25. Set `--floor` to what that gives with a
16 px base, rounded down, so a brand with a small `--base` still gets readable type.

A printed medium (a postcard, a table tent, a badge of another size) sets `--dpi` to the resolution
its px are drawn at, normally 300, and gives px = inches × dpi. Its viewing is the reading distance,
not a screen width.
