<!-- Upstream-owned: every update replaces this file whole. A brand's page rules go in the
     `## Surfaces` section of brand/<name>.md (BRANDING.md §5). -->

# Pages — the brand beyond boards

Boards are fixed-size images: the markup contract in PRIMITIVES.md, no CSS of your own. **Pages** are
everything else that carries the brand: a dashboard published as an artifact, an internal site or
tool, a report or one-pager read in a browser, a landing page, a document with no template. A page
is free in layout and bound in style: you write its HTML and CSS, but every colour, font, size, gap
and radius comes from the brand kit.

```
kit.py css    the brand as one stylesheet: fonts, logos, tokens, page roles, type scale, components
kit.py guide  a visual brand guide page (colour, type, data, logo, icons, illustration, rules)
kit.py lint   exits non-zero on colours, fonts or font links that aren't the brand's
kit.py shot   desktop, phone and dark screenshots of a page
```

---

## 1. Board or page?

| the user wants | build |
|---|---|
| an image, a PNG, a post, a header, a slide graphic, a print PDF | a **board** (SKILL.md §3) |
| an artifact, a web page, a site, an internal tool, something interactive, live or scrollable | a **page** |
| a document or report to read on screen, with no fixed size | a **page** |
| a dashboard **image** for slides or chat | a `dashboard` board |
| a dashboard **as an artifact**, "interactive", "with filters", "that I can share as a link" | a **page** |
| slides, a deck, a presentation | the slide skill (SKILL.md §1b) |
| "what are our colours / fonts", "brand guidelines", "how do I use the logo" | **guide** (§7) |

When a request names an artifact, a site or a page, never answer with a board, a PNG or a PDF, and
never turn a page back into one without being asked.

---

## 2. Start from the kit

```bash
python3 <skill>/kit.py css -o work/brand-kit.css
```

Put the whole file as the **first** `<style>` of the page, unedited (it carries `/* brand kit:start`
and `/* brand kit:end */`; lint skips that span). Your own `<style>` comes after it. Never retype
tokens, never link the brand's `.css`, never add a Google Fonts link: the fonts are inside the kit.
For an artifact, write the kit into the artifact's HTML file with a shell step (`cat`), never
by reading base64 into your context.

A light brand's kit is already theme-aware (light, dark under `prefers-color-scheme`, and both
`data-theme` stamps), because its dark scheme is the brand's own inverse ground. A dark brand's kit
commits to its one look. `--scheme light|dark` forces one look when the page must not follow the
viewer (a printed report, a page that mirrors a board).

## 3. Tokens you write with

| use | tokens |
|---|---|
| page ground, text, secondary text, hairlines | `--page-bg` `--page-fg` `--page-muted` `--page-faint` |
| cards, panels, tiles (translucent over the ground) · opaque panel | `--page-fill` · `--page-surface` |
| the one vivid colour, text on it | `--page-accent` `--page-accent-fg` |
| type | `--font-display` `--font-body` `--font-caption` `--font-mono`, `--weight-display` `--weight-heading` |
| sizes (the brand's scale at screen size) | `--text-caption` `--text-body` `--text-lead` `--text-h3` `--text-h2` `--text-h1` `--text-display` |
| space and shape | `--gap-xs` `--gap-sm` `--gap-md` `--gap-lg` `--gap-xl` `--gap-2xl`, `--r`, `--line` |
| data | `--chart-1` … `--chart-6` in order, `--chart-accent`, `--chart-seq-0`/`-1`, `--good` `--bad` |
| hero ground | `var(--art)` on `.mb-hero` only |
| logo | `--page-logo` (follows the scheme) via `.mb-logo` |

Always the `--page-*` roles for painting, not the raw `--bg`/`--fg`: the roles are what flip in the
dark scheme and inside `.mb-inverse`. `color-mix(in srgb, var(--page-fg) N%, transparent)` is fine
for a tint; a colour that isn't a token is not.

## 4. Components

The kit styles plain elements (`body`, `h1`–`h4`, `p`, `a`, `table`, `th`, `td`, `hr`, `code`,
focus and selection) at zero specificity, and ships the board primitives as `mb-` classes:

```
.mb-eyebrow[data-rule]   .mb-display   .mb-lead   .mb-muted   .mb-caption
.mb-card[data-tone="outline|accent|glass"]      .mb-chip      ul.mb-list
.mb-tile > .mb-tile__label + .mb-tile__value + .mb-tile__delta[data-trend="up|down"][data-good="up|down"]
.mb-stat   .mb-band   .mb-icon > svg   .mb-logo (role="img" aria-label="…")
.mb-inverse   a section on the brand's dark ground, all roles flipped
.mb-hero      a section on var(--art), with the ink --art-ink asks for
```

Use them before writing your own. Layout (grid, flex, columns, nav, sticky header, responsive
breakpoints) is yours to write, from `--gap-*`, `--r` and `--line`.

Icons: copy the SVG from `<skill>/brand/assets/icons/<name>.svg` into `<span class="mb-icon">`;
only names the brand file lists. Illustrations: the library SVGs in `brand/assets/illustrations/`
inline as they are (they paint with `currentColor` and `--illo-*`), under the brand's
`## Illustration` rules.

## 5. Composing a page that looks like the brand

Pages go wrong in the same few ways. Check each before you publish:

- **Read `brand/<name>.md` first**: voice, `## Surfaces` (page rules win over this file) and
  adaptation. The voice applies to every word on the page, headings and labels included.
- **Ground.** Pages sit on `--page-bg`. `--art` is a hero moment: at most one `.mb-hero` per page,
  at the top, never behind data. A brand whose social boards live on `art` still keeps its
  dashboards and documents on the plain ground, as its boards do.
- **One accent per view.** Accent is for the eyebrow, the one highlighted word, the key figure, the
  primary action, the current series. Never accent-filled cards in a row, never accent body text.
- **Type from the scale only.** One `h1` per page. Headings in the display face at the brand
  weights; UI labels and chart text in `--font-caption`. Never a size between steps.
- **Density like the boards.** A number that matters is a `.mb-tile` or `.mb-stat`, not a
  sentence. Cards on `--page-fill` with `--r`; hairlines `--page-faint` at `--line`. Leave space:
  section gaps are `--gap-xl` or `--gap-2xl`.
- **Charts** (load the dataviz skill when present): series take `--chart-1…6` in order, never
  `--accent-2`; label directly; a caption with the source. To highlight one series, it takes
  `--chart-accent` and every other series recedes to
  `color-mix(in srgb, var(--page-fg) 22%, transparent)` — never accent beside `--chart-n`, which
  can be the same hue (on some brands `--chart-accent` is `--chart-1`). Hand-drawn SVG charts keep
  their aspect ratio (never `preserveAspectRatio="none"` on an SVG with text) and read at 400 px.
- **Tables** wider than a phone sit in a wrapper with `overflow-x: auto`; numeric columns align
  right. Chart libraries read colours from CSS at runtime:
  `getComputedStyle(document.documentElement).getPropertyValue("--chart-1").trim()`, re-read when the
  theme changes — never a hex in a script.
- **Logo** once, in the header, `.mb-logo`; never recoloured, never redrawn as text, never below
  `--logo-min`.
- **No new looks**: no gradients except `var(--art)`, no drop-shadow decoration, no emoji, no
  stock-UI palettes (Tailwind grays, default blues), no fonts outside the kit.
- Responsive to 400 px, as the artifact rules require.

Don't invent content the user owns (SKILL.md §2): numbers, names and quotes they didn't give are
placeholders, marked visibly on the page and named in the handoff.

## 6. Check it

```bash
python3 <skill>/kit.py lint page.html                  # must print "on brand"
python3 <skill>/kit.py shot page.html -o work/png/     # look at desktop, phone and dark
```

Fix every lint error. Warnings (a literal px font size, a gradient) need a reason or a fix. Then
read the three PNGs and compare them with the guide (`kit.py guide`) and a board of the same brand:
same type, same accent use, same density. A page that passes lint but reads as a generic app is
not done.

## 7. Guide mode: brand questions

"What are our brand colours", "which font", "show me the brand guidelines", "how should I use the
logo", "make me a brand cheat sheet":

```bash
python3 <skill>/kit.py guide -o "<Brand> brand guide.html"
```

It renders logo variants on their grounds, colour roles with values and contrast, the type scale
with families, the chart palette light and dark, shape and components, icons, illustrations, and the
brand file's rules. Publish it as an artifact or hand over the file. For a narrow question
("what's the accent hex"), answer in text from `brand/<name>.css` and the guide's values; offer
the guide in one line. Never state a value that isn't in the brand files.
