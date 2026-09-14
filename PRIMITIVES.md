<!-- Upstream-owned: every update replaces this file whole. Brand-specific preferences live in
     brand/<name>.md; fork-specific medium profiles in media/<id>.md + media/<id>.css. -->

# Markup contract

This is the model-facing reference. A sheet is written **only** from the markup below. Never
write CSS or JS into a sheet — the runtime, the medium profiles and the brand stylesheet are fixed
assets appended at generation time. If something can't be expressed here, say so; don't style
around it.

Contents: 1 Sheet · 2 Board · 3 Type scale · 4 Text · 5 Containers · 6 Media and logo ·
7 Diagram · 8 Chart · 9 Table · 10 Bind, notes, batch · 11 Density budgets ·
12 Rasterization-safe CSS · 13 Derived attributes

**Never type a separator character.** No `·`, `•`, `|`, `—` or `/` joining two phrases in an
eyebrow, chip, caption or anywhere else. Write two elements, use `<b>` for a neutral division
(`<b>03</b> Launch`), or let whitespace do the work.
The rule is about joining phrases; a URL, a date, a ratio or a unit (`kestrel.io/jobs`, `24/7`)
keeps its own characters. A call to action is plain text in a `.lead` or `.caption`
(`Apply at kestrel.io/jobs`); there are no links, since the output is an image.

**No emoji and no decorative Unicode symbols** (★ ✓ ➜ …) in any text. Arrows between numbers
(`3.2 h → 40 min`) only where the brand's voice file allows them.

---

## 1. Sheet

A sheet is one self-contained HTML file. Content first, runtime last. Claude writes and edits
**only** the part between `<body>` and the runtime marker.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spring launch</title>
<meta name="makeitbrand-brief" content="what=launch announcement; media=social-square social-portrait chat-header; tone=plain">
</head>
<body>
<main class="sheet" data-brand="kestrel">

  <section class="board" data-medium="social-square" data-title="Launch square">…</section>
  <section class="board" data-medium="chat-header" data-title="Launch header">…</section>

</main>
<!-- makeitbrand:runtime — generated below this line, never edit by hand -->
<style data-runtime>…runtime.min.css, including the stock medium profiles…</style>
<style data-media>…the fork's media/*.css, if any…</style>
<style data-brand>…brand/<name>.css with fonts and logos as data: URIs…</style>
<style data-custom>…custom.css, if the fork has one…</style>
<script data-runtime>…runtime.min.js…</script>
<script data-custom>…custom.js, if the fork has one…</script>
</body>
</html>
```

- One `<main class="sheet">`, boards as its direct children, in the order they should appear.
- `data-brand` names the brand the sheet was generated with. Informational; the `<style
  data-brand>` block is what actually applies.
- `makeitbrand-brief` records the brief. Read it on a revise pass; keep it current.
- **Dev form.** While developing upstream, a sheet may `<link>` the stylesheets and `<script src>`
  the runtime in the same positions. The dev form must be served over http (a `file://` page can't
  read linked stylesheets back, so export loses fonts). `sheet.py` turns it into the inlined form.
  A sheet handed to a user is always the inlined form.
- JSON inside single-quoted attributes (`data-series`, `data-labels`, `data-spark`) writes an
  apostrophe as `&#39;`.

---

## 2. Board

One board is one exported image, or one page of a PDF. Every board is a `<section class="board">`
directly inside `.sheet`; for a multi-page document the sheet order is the page order.

```html
<section class="board" data-medium="social-square" data-title="Launch square">
  <p class="eyebrow">New in Kestrel</p>
  <h1 class="display">Reports that <strong>write themselves</strong></h1>
  <div class="logo" data-corner="br"></div>
</section>
```

| attribute | values | does |
|---|---|---|
| `data-medium` | a profile id (MEDIA.md, or the fork's `media/`) or `custom` | size, safe area, type factor, defaults, budgets. **Required** |
| `data-title` | short label | tab name and download filename. **Required**, unique within the sheet |
| `data-w` `data-h` | integers, px | only with `data-medium="custom"` |
| `data-like` | a profile id | `custom` only, **required** there: borrow that profile's type factor, safe area, defaults and budgets |
| `data-ground` | `bg` `surface` `accent` `inverse` `art` `transparent` | what the board is painted on. Default from the profile |
| `data-v` | `top` `center` `bottom` `spread` | vertical distribution of the board's in-flow children inside the safe area. `spread` = first child at top, last at bottom, the rest between. Default from the profile |
| `data-h-align` | `start` `center` | horizontal alignment of text and children. Default `start` |
| `data-alt` | a sentence | optional description of the image for people who can't see it; kept with the markup and offered next to the download |

A board's content box is its safe area (from the profile). In-flow children stack in a single
column with the brand's spacing rhythm between them. Pinned elements (`.logo[data-corner]`) leave
the flow and don't count for `data-v`, but they reserve their band: content on that side of the
board stops above (or below) the logo's height plus one `md` gap, so nothing ever sits under it.

**Grounds.** Text, charts, nodes and the logo re-resolve against the ground; never compensate by hand.

| ground | paint | text | cards, tiles, nodes |
|---|---|---|---|
| `bg` | `--bg` | `--fg`, `--muted` | `--surface` |
| `surface` | `--surface` | `--fg`, `--muted` | `--bg` |
| `accent` | `--accent` | `--accent-fg`, and a muted mix of it | `--accent-fg` at low alpha |
| `inverse` | `--fg` | `--bg`, and a muted mix of it | `--bg` at low alpha |
| `art` | the brand's `--art` composition (gradients, glow, texture), falling back to `--bg` | as the brand's `--art-ink` says: `bg` (default) uses the `bg` text tokens, `inverse` the `inverse` ones | a translucent tint of the text colour |
| `transparent` | nothing (exports with alpha; the sheet shows a checkerboard) | as the brand's `--inset-ground` says: `light` → like `bg`, `dark` → like `inverse` | as that ground, plus a `--faint` outline, because the slide colour is unknown |

---

## 3. Type scale

Sizes are derived, never chosen: `size(step) = --base × k × --scale^step`. `--base` and `--scale`
come from the brand, `k` (the type factor) from the medium profile. If `--base × k` is below the
profile's floor, the runtime raises `k` until it isn't. With the demo brand (16px, 1.25):

| class | step | dashboard k=1 | slide-inset, chat-header k=1.5 | social k=2.25 | nametag k=2.5 |
|---|---|---|---|---|---|
| `.caption` `.eyebrow` `.chip` | −1 | 13 | 19 | 29 | 32 |
| `.body` | 0 | 16 | 24 | 36 | 40 |
| `.lead` | 1 | 20 | 30 | 45 | 50 |
| `.h3` | 2 | 25 | 38 | 56 | 63 |
| `.h2` | 3 | 31 | 47 | 70 | 78 |
| `.h1` | 4 | 39 | 59 | 88 | 98 |
| `.display` | 6 | 61 | 92 | 137 | 153 |

You cannot resize type. If it doesn't fit, cut words (§11). Content that overflows its board is
marked `data-overflow`; nothing shrinks automatically.

---

## 4. Text primitives

| markup | use |
|---|---|
| `<p class="eyebrow">` | small uppercase mono kicker, accent-coloured. `<b>` inside for a neutral division |
| `<h1 class="display">` | the one hero line of a board. At most one per board |
| `<h1 class="h1">` `<h2 class="h2">` `<h3 class="h3">` | headings. Pick by hierarchy on this board, not by desired size |
| `<p class="lead">` | one supporting sentence, muted |
| `<p class="body">` | paragraph, muted |
| `<p class="caption">` | mono footnote, source line, credit |
| `<span class="chip">` | pill tag. Several chips sit in a `.row` |
| `<p class="stat">` | a hero figure: `display` size, accent colour, tabular digits. ≤ 5 characters (`82%`, `7.8k`, `~143`). Anywhere a number is the point |
| `<p class="eyebrow" data-rule>` | an eyebrow followed by a hairline running to the end of its container: the section header of a dense board |
| `<i class="icon" data-icon="shield"></i>` | a brand icon at the size of the surrounding text (`data-size="lg"`: 2em, `"xl"`: 3em). Names are listed in the brand voice file. Never decorative filler: an icon labels something next to it. It may sit inside an `.eyebrow`, `.caption`, `.chip`, a tile's caption, a node's or group's caption, or beside a `.stat` or `.h2` in a `.row` |
| `<ul class="list">` `<ol class="list">` | short items; markers come from the brand |
| `<strong>` | the highlight. Accent-coloured inside `.display` and headings (underlined instead on an `accent` ground or card, where the accent is the ground), semibold in body text. ⌘B toggles it in edit mode. At most one per heading |
| `<b>` | neutral division inside an eyebrow or chip, never coloured |
| `<br>` | a deliberate line break in a display line or heading. Never inside a `data-bind` element |

No other inline markup: no `<em>`, `<span style>`, `<a>`, `<font>`. Every text element above is
editable in edit mode as plain text plus `<strong>`/`<b>`/`<br>`.

---

## 5. Containers

| markup | does |
|---|---|
| `<div class="stack" data-gap="xs\|sm\|md\|lg\|xl">` | vertical flow; gap = 0.5, 1, 2, 3, 5 × `--space` × k. Default `md` |
| `<div class="row" data-gap="…" data-align="start\|center\|baseline\|end">` | horizontal flow, wraps. Default gap `sm`. `data-justify="between"` pushes the first and last child apart; `data-divide` draws a hairline between children and makes them share the width equally |
| `<hr class="rule">` | a full-width hairline between sections |
| `<div class="grid" data-cols="2…6" data-gap="…">` | equal columns. A child with `data-span="2"` spans columns |
| `<article class="card" data-tone="surface\|accent\|outline\|glass">` | a bounded group: an optional `.eyebrow`, then `.h3` + `.body`, **or** an optional `.h3` then one `figure.chart` / `table.table` / `figure.media`, **or** (for a badge) a `.row` of an `.icon` and a small `.stack`. Default tone `surface`. `glass` is a translucent panel with a hairline edge, for `art` grounds. At most one `accent` card or tile per board. A card may also hold an `.eyebrow[data-rule]` above its content |
| `<div class="bento" data-cols="2…6" data-rows="1…4">` | a grid that fills its height; children are `.card` or `.tile` with `data-span="c,r"` (default `1,1`) |
| `<article class="tile" data-tone="surface\|accent\|glass">` | KPI, see below. `glass` on `art` grounds, like cards |

**`data-fill`** makes an element take the remaining height of its container. It is valid on a
direct child of `.board`. Inside a `.card` or `.tile`, a `figure.chart`, `.diagram` or
`figure.media` always fills the leftover height and needs no attribute.

**Tile.**

```html
<article class="tile">
  <p class="caption">Active teams</p>
  <p class="tile__value">1,240</p>
  <p class="tile__delta" data-trend="up" data-good="up">+48% vs Q2</p>
  <i class="tile__spark" data-spark='[810,870,905,990,1120,1240]'></i>
</article>
```

`.tile__value` is the `h1` step, ≤ 7 characters including unit. `.tile__delta` is optional;
`data-trend="up|down|flat"` with `data-good="up|down"` colours it `--good` when trend matches good,
`--bad` when it opposes, `--muted` when flat. It always carries its words — never colour alone.
`.tile__spark` is optional: a sparkline of ≤ 24 values, no axes, the last point marked.

---

## 6. Media and logo

```html
<figure class="media" data-crop="cover|contain"><img src="data:image/…" alt=""></figure>
<div class="logo" data-variant="auto|light|dark|mono" data-corner="tl|tr|bl|br"></div>
<div class="lockup"><div class="logo"></div><img class="partner" src="data:image/svg+xml;…" alt="Meridian"></div>
<figure class="quote">
  <img class="avatar" src="data:image/…" alt="">          <!-- or <span class="avatar" data-initials="AR"></span> -->
  <blockquote class="h3">Quotation, ≤ 20 words.</blockquote>
  <figcaption class="caption">Name, role, company</figcaption>
</figure>
<footer class="band"><p class="caption">Short footer line</p></footer>
```

- Images are always `data:` URIs in a delivered sheet. Never invent a path; if the user hasn't
  supplied an image, leave it out and say so.
- `.logo` is an empty element; the runtime fills it from the brand's `--logo-*` tokens. `auto`
  (default) picks `dark` on `bg`/`surface` grounds, `light` on `inverse`, `mono` on `accent`, and on
  `transparent` follows `--inset-ground`. Its height is the profile's logo height, never below
  `--logo-min`. Without `data-corner` it sits in flow; with it, it pins to that safe-area corner.
- `.lockup` is a co-brand: the brand logo, then partner marks as `img.partner` (supplied by the user,
  already in a colour that works on the ground — the runtime can't recolour them). The runtime draws
  the joining `+`; never type it. Partner marks render at the logo's height.
- `.quote` is a pull quote with an optional round avatar (an `img`, or initials when there is no
  photo). The figcaption carries attribution; wrap the person's name in `<strong>` and it takes the
  accent.
- `footer.band` must be the last child of the board: a full-width strip along the bottom edge (it
  ignores the side safe area) on a darker tint of the ground. One line of `.caption`, ≤ 12 words.
- A profile with logo `none` ignores `.logo`. The brand's adaptation rules (brand/<name>.md) can
  forbid corners and variants; they win.

---

## 7. Diagram

Boxes and connectors on a grid. The runtime places nodes, draws edges as SVG, and in edit mode lets
nodes be dragged by whole cells (edges follow). The model is deliberately geometric — cells, two
shapes, text-only nodes — so that a diagram maps one-to-one onto native SVG (HANDOFF, Phase 5).
Don't expect it to hold anything that isn't listed here.

```html
<div class="diagram" data-cols="5" data-rows="3" data-fill>
  <div class="group" data-at="3,1" data-span="3,3"><p class="caption">Cloud</p></div>
  <div class="node" data-id="app" data-at="1,2"><p class="h3">App</p></div>
  <div class="node" data-id="api" data-at="3,2" data-tone="accent">
    <p class="caption">edge</p><p class="h3">API gateway</p></div>
  <div class="node" data-id="db" data-at="5,2"><p class="h3">Postgres</p></div>
  <div class="note" data-at="4,3"><p class="caption">Read replicas in two regions</p></div>
  <i class="edge" data-from="app" data-to="api">HTTPS</i>
  <i class="edge" data-from="api" data-to="db"></i>
</div>
```

| element | attributes |
|---|---|
| `.diagram` | `data-cols` `data-rows` (1–8 each); the grid divides the diagram's box evenly |
| `.node` | `data-id` (unique within the diagram), `data-at="col,row"` (1-based), `data-span="c,r"` (default `1,1`), `data-tone="surface\|accent\|outline"` (default `surface`), `data-shape="box\|pill"` (default `box`). Content: an optional `.caption` (≤ 2 words or a step number as `<b>03</b>`, not counted in the label budget) then one `.h3` or `.body` |
| `.group` | `data-at`, `data-span`; a labelled outline drawn behind nodes, label inside its top-left corner. Content: one `.caption`. Groups don't partially overlap each other |
| `.note` | `data-at`, optional `data-span`; unboxed text, one `.caption` or `.body` |
| `.edge` | `data-from` `data-to` (node ids), `data-style="arrow\|line\|dashed\|both"` (default `arrow`), `data-ports="r-l"` to force exit and entry sides (`t r b l`). Text content is the label, editable |

**Routing, so the result is predictable.** Nodes in the same row connect by their facing sides
(right to left when the target is to the right, left to right when it is to the left); same column,
likewise bottom to top or top to bottom. Otherwise the edge leaves horizontally from the side facing
the target, bends once at the target's column centre, and enters vertically. `data-ports` overrides
the sides — use it for direction or to separate two edges, never to route around an obstacle; the
single-bend rule stays. The label sits beside the segment that is longer **in pixels** — above a
horizontal one, right of a vertical one — never on the line.

**Fan-outs.** When one node connects to three or more others, stack those targets in one column
beside it (or one row below it). The runtime spreads connections that share a side of a node along
that side, ordered by where the other end sits, so they neither overlap nor stack their labels. Use
`data-ports` only to force a direction, never to untangle a fan-out.

**Authoring rules.** Node text is `.h3` in diagrams of up to 5 columns and `.body` in wider ones (the
cells get too narrow for a heading to fit three words). Nodes don't overlap. A labelled edge's labelled segment must cross at least one
empty cell. No edge may pass through a node, note or group label — if it would, move a node. Edges
may cross each other at right angles but never run along the same line. At most one accent node
per diagram, for the thing the diagram is about.

Not in the POC: decision diamonds and loops-back as shapes. Draw a branch as an `outline` node with
labelled edges (`yes`, `no`), and a retry as a `dashed` edge.

---

## 8. Chart

```html
<figure class="chart" data-type="bar"
        data-labels='["Q1","Q2","Q3","Q4"]'
        data-series='[{"name":"2026","values":[12,19,23,31]},{"name":"2025","values":[10,14,15,22]}]'
        data-unit="%" data-highlight="2026">
  <figcaption class="caption">Accounts on annual plans. Source: billing, Oct 2026</figcaption>
</figure>
```

| attribute | values |
|---|---|
| `data-type` | `bar` `line` `donut` `range` `dots` |
| `data-labels` | JSON array of category or x labels |
| `data-series` | JSON: an array of numbers (one series) or an array of `{"name","values"}` |
| `data-unit` / `data-prefix` | appended / prepended to every printed value exactly as written — include a space if you want one (`" h"`) |
| `data-decimals` | printed precision, default 0 |
| `data-orient` | bar only: `v` (default) or `h` (use `h` when labels are longer than ~8 characters) |
| `data-highlight` | multi-series charts: a series name. Single-series bar or donut: a label. That series or mark takes `--chart-1`; everything else recedes to a neutral tint of the text colour. Anything else is `data-invalid` |

Forms and limits (outside them the runtime renders nothing and marks `data-invalid`):

- **bar** — magnitude comparison, axis from 0. ≤ 12 categories, ≤ 3 series.
- **line** — change over time, one y-axis. ≤ 24 points, ≤ 4 series.
- **donut** — part of a meaningful whole. ≤ 5 slices; fold the rest into "Other" yourself.

- **range** — durations or spans compared on one axis ("7 days vs 150 days"). One row per series:
  `{"name", "from", "to", "steps": ["…", "…"]}` (steps optional, ≤ 4, each ≤ 3 words — the runtime
  draws the arrows between them). ≤ 4 rows. `data-gap="…"` (≤ 5 words) names the difference between
  the shortest and the longest row and is drawn as a bracketed callout between them; `data-max` sets
  the axis end. A row may carry `"label"`, printed instead of its value: for spans in mixed units,
  give `from`/`to` in one unit (minutes) and label each row in its own ("11 min", "9 days"). The first row is the subject and takes `--chart-1`; the other rows are
  reference rows drawn in the text colour. `data-highlight` instead names the row that stands out.
- **dots** — one share of a whole shown as a field of dots. `data-series='[18]'` means 18 of 100.
  `data-pattern="fill"` (default, reads fastest) or `"scatter"` (evenly spread, deterministic).
  Pair it with a `.stat` beside it; the chart itself prints no number.

For a single headline number, use a `.tile` or a `.stat`, not a chart.

**What the runtime draws.** Colours from `--chart-1…6` in series order, never cycled, unless
`data-highlight` is set. Bars: value labels on every bar when there are ≤ 8 bars in total,
otherwise light gridlines; a legend row when there are ≥ 2 series. Lines: each series labelled by
name at its end, no legend. Donut: slice labels with values outside the ring. Values and labels wear
text colours, never series colours. No 3D, no gradients, no dual axes.

The `<figcaption>` is the only author-written text in a chart: what it shows, then `Source: …`.
Chart data is changed by Claude on a revise pass, not in edit mode.

---

## 9. Table

```html
<table class="table" data-key="3">
  <thead><tr><th>Plan</th><th>Starter</th><th>Team</th><th>Scale</th></tr></thead>
  <tbody><tr><td>Seats</td><td>3</td><td>25</td><td>Unlimited</td></tr></tbody>
</table>
```

Hairline rows, no vertical rules, first column reads as the row label. Numeric columns right-align
automatically. `data-key="N"` tints column N, at most one. Cells are a few words or a figure, never
paragraphs. Cell text is editable; rows are added or removed by Claude, not in edit mode.

---

## 10. Bind, notes, batch

**`data-bind="id"`** on any text primitive: editing it copies its content (text, `<strong>`, `<b>`)
to every element with the same `data-bind` on other boards. Use it for the headline, the date, the
CTA of a multi-medium set. Bound elements may have different classes (a `.display` on the square, an
`.h1` on the header). A bound text must fit the **tightest** budget among the boards it appears on,
and never contains `<br>`.

**`data-note="…"`** on any board or element: a note shown as a chip in edit mode. It runs both ways.
From the user, it is a change request: on a revise pass, apply it and remove the attribute. From
Claude, it flags something assumed that the user should confirm (`data-note="placeholder: real
apply link?"`): keep it until the user answers or deletes it. A placeholder board is
`<section class="board" data-medium="…" data-title="TBD" data-note="what goes here">` with no children.

**Batch.** One template board plus rows of data make one board per row.

```html
<section class="board" data-medium="nametag" data-title="Nametag {name}" data-template>
  <div class="logo" data-corner="tl"></div>
  <h1 class="h1" data-field="name">Name Surname</h1>
  <p class="lead" data-field="role">Role</p>
  <p class="caption" data-field="team">Team</p>
</section>
```

- Write the template board only. `data-field="column"` marks each element whose text comes from the
  data; the name matches the CSV header or JSON key. `{column}` in `data-title` is substituted.
- `sheet.py --rows data.csv` materialises it: the template stays first in the sheet, followed by one
  ordinary board per row with `data-row="n"`. The runtime shows the template as a tab but skips it
  in export and Download all. Materialised boards are editable and revisable one by one.
- `data-field` and `data-bind` never sit on the same element.
- Before writing the template, find the **longest** value in each column and check it against the
  profile's field budgets (§11).

---

## 11. Density budgets — hard limits

Type size is fixed (§3), so words are the only lever. These are ceilings, not targets. Counted per
board. "—" means the primitive doesn't belong on that medium.

| medium | eyebrow | display | h1 | lead | body | list | cards / tiles | chart | diagram |
|---|---|---|---|---|---|---|---|---|---|
| `social-square` | ≤ 4 words | ≤ 6 words | ≤ 8 (if no display) | ≤ 12 | ≤ 20 | ≤ 3 × ≤ 5 words | ≤ 2 | 1 (bar ≤ 5 bars, donut ≤ 3) | ≤ 4 nodes |
| `social-portrait` | ≤ 4 | ≤ 8 | ≤ 10 | ≤ 16 | ≤ 30 | ≤ 4 × ≤ 5 | ≤ 3 | 1 (bar ≤ 6, donut ≤ 4) | ≤ 5 nodes |
| `carousel` (per page) | ≤ 4 | ≤ 8, cover and last page only | ≤ 10 | ≤ 16 | ≤ 30 | ≤ 4 × ≤ 6 | ≤ 3 | 1 (bar ≤ 6, donut ≤ 4) | ≤ 5 nodes |
| `infographic` | ≤ 4 per section | — | ≤ 16 | ≤ 12 each, ≤ 2 | ≤ 30 | ≤ 4 × ≤ 8 | ≤ 4 | ≤ 2 (range, dots, bar ≤ 6) | ≤ 6 nodes |
| `social-landscape` | ≤ 4 | — | ≤ 6 | ≤ 10 | — | — | — | — | — |
| `chat-header` | ≤ 4 | — | ≤ 7 words and ≤ 36 characters (one line) | ≤ 12 | — | — | — | — | — |
| `slide-inset` | ≤ 5 | — | ≤ 8 | ≤ 20 | ≤ 40 | ≤ 5 × ≤ 10 | ≤ 4 | 1, full limits | ≤ 12 nodes, ≤ 14 edges |
| `dashboard` | ≤ 5 | — | ≤ 8 | ≤ 20 | ≤ 30 | — | ≤ 6 tiles + 3 cards | ≤ 3, full limits | — |
| `nametag` | — | — | name ≤ 24 characters | role ≤ 32 characters | — | — | — | — | — |

Everywhere: node label ≤ 3 words, edge label ≤ 3 words, card `.h3` ≤ 4 words, card `.body` ≤ 16
words, tile caption ≤ 3 words, tile delta ≤ 4 words, chip ≤ 3 words, caption ≤ 16 words, table
≤ 5 columns × ≤ 6 body rows.

A `custom` board uses its `data-like` row. The brand file may tighten these (a wide or serif display
face runs longer); it may not loosen them.

---

## 12. Rasterization-safe CSS

Export draws each board through SVG `<foreignObject>` into a canvas. Anything the browser can't paint
in that path silently disappears from the PNG. This is a contract for **everyone who writes CSS for
this system**: upstream runtime and stock profiles, `media/*.css`, `brand/<name>.css`, and a fork's
`custom.css`. Sheets contain no CSS at all.

Allowed: flex and grid layout, borders, border-radius, solid and gradient backgrounds, uniform-alpha
colours and `color-mix()`, `box-shadow`, static `transform`, `object-fit`, inline `<svg>` whose
references (`<use href>`, gradients, markers) resolve **inside the same board**, `@font-face` with
`data:` sources, custom properties.

Forbidden:

- any `url()` that isn't `data:` — fonts, images, cursors, masks; and `@import`
- `backdrop-filter`, `mix-blend-mode`, `background-blend-mode`
- `filter` of any kind on exported content (fine on edit-mode chrome)
- `background-clip: text` and other text-fill tricks
- `<canvas>`, `<video>`, `<iframe>`, `<object>` inside a board (their pixels don't serialise)
- looks that depend on interaction or time on board content: `:hover`/`:focus` styles, animations,
  transitions
- `position: fixed`, and scroll containers inside a board
- fonts not declared in the sheet's own `<style>` blocks (a system font is acceptable only as the
  last entry of a stack)
- `@media print` rules that reach board content: the vector PDF prints the boards, the PNG doesn't,
  and the two must match

The runtime copies every `<style>` block into each exported SVG, so rules in all of them apply to
exports automatically.

**PDF.** The sheet's own PDF button builds its pages from these same rasters, so nothing more is
needed. `export.py --pdf` instead prints the live boards through Chrome for vector text, which paints
everything allowed above; the one extra rule is the `@media print` line.

---

## 13. Derived attributes — never write these

The runtime writes these itself.

Kept by "Copy changes", so they reach Claude — act on them, then drop them:

- `data-overflow` — content overflows its board or its cell. Cut words (§11).
- `data-invalid="reason"` — a chart or diagram outside its limits (§7, §8), or a broken reference
  (unknown `data-from`, unknown `data-medium`).

Stripped by "Copy changes"; remove them if you see them anyway:

- `data-gen` — on elements the runtime generated (edge and chart SVGs, logo images, legends, sparklines)
- `data-empty`, `contenteditable`, `data-edited` — edit-mode state
- `data-g`, `data-ink`, `data-va`, `data-off` on boards, `data-num` on table cells, and inline `style` on
  boards — the runtime's resolved defaults and sizes
- inline `style` on `.node`, `.group`, `.note` — the runtime's placement. After a drag the runtime
  rewrites `data-at`, so copied markup carries the new cell.
