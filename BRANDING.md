<!-- Upstream-owned: every update replaces this file whole. Brand rules live in brand/<name>.md;
     install rules in SKILL.fork.md. -->

# Branding makeitbrand

A brand is these files on disk, all fork-owned:

```
brand/<name>.css      tokens, @font-face, logo variants            ← required
brand/<name>.md       voice rules + adaptation rules               ← required
brand/assets/         font files, logo sources, approved imagery   ← as needed
brand/default         one line: <name>                             ← the install's own; upstream never ships one
```

The runtime never changes for a brand. A brand that needs a runtime change is a runtime bug.
Every CSS rule a brand file adds is bound by PRIMITIVES.md §12 (rasterization-safe CSS).

---

## 1. Tokens — `brand/<name>.css`

The first nine are slaydy's, with the same names and meanings, so a trained brand can emit
`themes/<name>.css` for slaydy unchanged (§6).

```css
:root {
  /* slaydy's nine */
  --app-bg:   /* sheet surround behind the boards */
  --bg:       /* default board ground */
  --fg:       /* primary text */
  --muted:    /* secondary text — rgba() of --fg at ~0.58, never a separate hex */
  --faint:    /* hairlines and outlines — rgba() of --fg at ~0.14 */
  --surface:  /* card, node and tile fill, one step off --bg */
  --accent:   /* the one vivid brand colour: eyebrows, highlights, accent tiles/nodes */
  --accent-2: /* secondary; decorative only, never data */
  --accent-fg:/* text on --accent — check contrast, a mid-tone usually needs white */
  --accent-strong: /* optional: the highlight colour on an accent ground (default: an underline) */
  --wash-opacity: 0;   /* kept for slaydy compatibility; unused here */

  /* type */
  --font-display: "Brand Display", system-ui, sans-serif;
  --font-body:    "Brand Sans", system-ui, sans-serif;
  --font-mono:    "Brand Mono", ui-monospace, monospace;
  --base:  16px;    /* body size at type factor k = 1 (MEDIA.md) */
  --scale: 1.25;    /* ratio between steps (PRIMITIVES.md §3); 1.2–1.333 */
  --font-eyebrow: /* optional: eyebrows; default --font-caption */
  --font-caption: /* optional: captions, chips, chart and edge labels; default --font-mono. A brand
                     with no mono face sets its sans here */
  --weight-display: 650;  /* optional: .display .h1 .h2 and tile values */
  --weight-heading: 600;  /* optional: .h3 and .stat */
  --tracking: 1;          /* optional: multiplier on the runtime's negative display tracking; 0 = none */
  --tracking-eyebrow: .08em;

  /* shape */
  --space:  8px;    /* spacing unit at k = 1; every gap is a multiple */
  --radius: 12px;   /* cards, tiles, nodes at k = 1; 0 for square brands */
  --stroke: 1.5px;  /* outlines, edges, chart axes at k = 1 */

  /* data */
  --chart-1 … --chart-6: /* categorical, fixed order, validated (§3) */
  --chart-accent: /* optional: single-emphasis marks (dots, sparklines, a highlighted series). May be
                     the vivid brand colour even when it can't join the validated set; ≥ 3:1 on the ground */
  --chart-seq-0: /* light end of the sequential ramp */
  --chart-seq-1: /* dark end, same hue */
  --good: /* status: better — ≥ 4.5:1 on --surface, where tiles sit */
  --bad:  /* status: worse — same */

  /* illustration */
  --illo-1 … --illo-4: /* optional: the palette figure.illo may paint with (§4c). Falls back to
                          --accent, --accent-2, --chart-1, --fg — every brand gets a usable set */

  /* grounds */
  --bg-tone: light;       /* light | dark: whether --bg itself is light; picks logo variants */
  --inverse-bg: …;        /* optional: the dark ground's colour when it isn't the text ink (default --fg) */
  --inset-ground: light;  /* light | dark: the slide ground transparent boards expect */
  --art: …;               /* optional: the art-directed ground for data-ground="art", a background
                             shorthand (layered gradients, glow). Falls back to --bg */
  --art-ink: bg;          /* bg | inverse: which text tokens read on --art */
  --band: …;              /* optional: footer.band fill; default a faint tint of the text colour */

  /* logo */
  --logo-light: url("data:image/svg+xml,…");  /* for dark grounds */
  --logo-dark:  url("data:image/svg+xml,…");  /* for light grounds */
  --logo-mono:  url("data:image/svg+xml,…");  /* single colour, for accent or busy grounds */
  --logo-min:   20px;  /* never rendered shorter than this */
}
```

Rules that save a round trip:

- `--muted` and `--faint` are `rgba()` of `--fg`. The runtime derives the muted and faint colours
  of `inverse` and `accent` grounds itself with `color-mix()` from `--bg` and `--accent-fg`; a brand
  never sets per-ground text tokens unless it overrides a ground (§4, Ground overrides).
- `--space`, `--radius` and `--stroke` scale with `k`, exactly like type. Write them for a 1440 px
  dashboard; the social boards will look right.
- `--good`/`--bad` are for tile deltas only. They never double as chart colours, and a delta always
  carries words.
- Show the user every resolved value before writing the file.

---

## 2. Fonts

Fonts must travel inside the sheet, so they are always files, never a Google Fonts `<link>`
(an external stylesheet also breaks export, PRIMITIVES.md §12).

```css
@font-face {
  font-family: "Brand Sans";
  src: url("assets/fonts/BrandSans-var.woff2") format("woff2");
  font-weight: 100 900;
}
```

Write relative `url()`s in `brand/<name>.css`; `sheet.py` inlines them as `data:` URIs when
building a sheet. Prefer one variable woff2 per family, subset to the scripts the brand writes in —
every byte ends up in every sheet. If a family is only licensed for desktop use, stop and tell the
user; don't embed it.

A condensed or serif display face runs longer or shorter than the grotesk the budgets assume.
Tighten budgets in the voice file; don't change `--scale` to compensate.

---

## 3. Chart palette

Six categorical slots, assigned in order and never cycled, plus a sequential pair. The palette is
validated, not eyeballed:

```bash
node <dataviz skill>/scripts/validate_palette.js "#c1,#c2,#c3,#c4,#c5,#c6" --mode light --surface "<--bg>"
```

Hard gates must pass (lightness band, chroma floor, adjacent CVD separation, normal-vision floor).
A contrast WARN is expected for yellows and pinks on light grounds and is covered by the runtime
always direct-labelling charts. If the brand has a dark ground in use, validate again with
`--mode dark` against it, and put the dark steps under the brand's dark ground selector (§4).

Start from the brand's own hues, snap each to the nearest passing step, and put the brand's
signature hue in slot 1 only if it passes. `--accent-2` is never a chart colour.

---

## 4. Logo

Three variants in the tokens: `--logo-dark` (for light grounds), `--logo-light` (for dark grounds),
`--logo-mono` (one colour, for accent and image grounds). Like fonts, write relative `url()`s to
`assets/`; `sheet.py` inlines them, so in a sheet they are always `data:` URIs. SVG wherever
possible, with text **outlined to paths** (an SVG used as an image can't see web fonts), and a
viewBox tight to the mark, since the runtime sizes the logo by height.

`--logo-min` is the smallest height the brand guidelines allow. The runtime never goes below it,
and a medium whose logo height is smaller simply renders at the minimum.

**Ground overrides.** A brand whose `--bg` is light but that also ships dark boards adds selector
blocks, not a second file. Only tokens go in them:

```css
.board[data-ground="inverse"]     { --chart-1: …; … }   /* dark-validated chart steps */
.board[data-ground="transparent"] { --surface: …; }     /* node fill that reads on the slides it lands on */
```

`--inset-ground: dark` makes transparent boards resolve like `inverse` (light text, light logo);
set it when the brand's slides are dark.

---

## 4b. Icons

A brand may ship an iconset: one SVG per icon in `assets/icons/`, drawn on a 24×24 viewBox for
`stroke: currentColor`, and one token per icon in a stylesheet next to the brand file:

```css
:root { --icon-shield: url("assets/icons/shield.svg"); /* … */ }
```

Markup uses `<i class="icon" data-icon="shield">`; the runtime inlines the SVG, so icons export
crisply and will survive native SVG export. List the available names in the voice file. The demo
set (`brand/icons.css`, shipped with the stock brands) is a good starting point.

---

## 4c. Illustrations

A brand may ship a small library for `figure.illo` (PRIMITIVES.md §6b): one SVG per illustration in
`assets/illustrations/`, and one `--illo-<name>` token per file, in the brand's own stylesheet (not
`icons.css` — illustrations are bigger, slower-changing, and brand-specific):

```css
:root { --illo-network-nodes: url("assets/illustrations/network-nodes.svg"); /* … */ }
```

Colours inside the SVG are `none`, `currentColor`, or `var(--illo-1)` … `var(--illo-4)` only — the
runtime rejects anything else (PRIMITIVES.md §6b). `currentColor` inherits the board's ink, so most
of an illustration should use it; reserve `--illo-1`…`--illo-4` for the one or two marks meant to pop
regardless of ground, the way `--chart-accent` does for a chart. Write `stroke-width` as
`var(--stroke)` or `calc(var(--stroke) * N)` so line weight scales with the board like everything
else, and give the root `<svg>` a `viewBox`.

Because `currentColor` carries the ground's text colour automatically, an illustration usually needs
no ground override. A brand whose `--illo-1`…`--illo-4` don't read on `art` or `inverse` (the way a
brand's own `--accent` sometimes doesn't) overrides them the same way as chart steps (§4, Ground
overrides): `.board[data-g="inverse"] { --illo-1: …; }`. A token that points at another token
(`--illo-1: var(--accent)`) resolves where it is declared: set on `:root`, it keeps the root
`--accent` even on a ground that overrides `--accent`, so re-declare it inside that ground's block.

List the available names and the illustration style spec in the voice file's `## Illustration`
section (§5).

---

## 5. The voice and adaptation file — `brand/<name>.md`

Two sections, both concrete and checkable. A fork's own medium profiles also need their budget
row here (MEDIA.md, Writing a profile). "No exclamation marks" is a rule; "be confident" is not.

**Voice** — 5–10 rules: tone, banned words, how headlines are written, number formatting,
naming. Same style as slaydy's `themes/<name>.md`.

**Illustration** (§4c) — its own `## Illustration` section, concrete and checkable like the other
two, so both a person and an authored `figure.illo` can be checked against it. Required fields, in
this order:

- **Style** — line vs fill (are shapes `currentColor` outlines or flat fills?), corner style
  (sharp or round joins), what carries the emphasis (which `--illo-<n>` slot, and how many marks
  may use it — usually one, the same "one accent" rule as a chart's `data-highlight`).
- **Palette use** — what each of `--illo-1`…`--illo-4` is for (emphasis vs structure vs echo), and
  when `currentColor` is preferred over a token.
- **Density** — a shape-count ceiling ("at most 5–7 shapes") so an illustration reads at a glance.
- **Never** — a short list of what must not appear (gradients, photographic or textured fills,
  drop shadows, more than one filled shape, decorative clutter around the subject — trim to what
  the brand actually needs to rule out).
- **Library** — one line, `Library (`figure.illo[data-illo]`): `<name>` (one-clause description of
  what it depicts or is used for), `<name>` (…), …` for every SVG in `brand/assets/illustrations/`,
  ending "Reach for one of these before drawing an authored illustration." `sheet.py
  --promote-illo` appends to this exact line, so keep the sentence shape when hand-editing it.

A brand with no illustration style writes `## Illustration` as one line, `none: use icons and
charts`, skips `--illo-1`…`--illo-4` and the Library line, and Compose (SKILL.md §3) then never
adds a `figure.illo` unless the user explicitly asks for one.

**Surfaces** — optional, its own `## Surfaces` section: rules for pages (PAGES.md), which are built
from `kit.py css` rather than boards. Same style as adaptation rules, each a checkable condition and
an action: "Pages stay on the light ground; `.mb-hero` only on landing pages", "Internal tools carry
no hero", "Tables use `--font-caption` headers, never uppercase". A brand without the section gets
PAGES.md's defaults. The kit needs no new tokens: it derives page roles, the screen type scale and
the dark scheme from the tokens above.

**Adaptation** — how the brand degrades across media and grounds. Each rule names a condition and an
action, and the condition is something the generator can check: a medium id, a board width, a ground,
a primitive.

- "Below 1200 px board width, drop the eyebrow."
- "On `inverse` grounds, the logo is `mono`, not `light`."
- "On social media, the logo never goes top-left (platform avatar sits there)."
- "Charts never use `--accent-2`; accent nodes only in diagrams, never accent cards."
- "`slide-inset` boards carry no heading; the slide title does that job."
- "Budgets: `.display` on social is ≤ 6 words (the display face is wide)."

These rules win over PRIMITIVES.md defaults and MEDIA.md, but may only tighten budgets, never
loosen them. Behaviour rules for the install ("always make the square and the portrait together")
go here too.

---

## 6. Emitting a slaydy theme

`brand/<name>.css` → `themes/<name>.css` for slaydy: copy the nine slaydy tokens, `--font-display`,
`--font-body`, `--font-mono` and the `@font-face` rules (with `url()`s repointed to slaydy's
`fonts/`). Nothing else carries over. The voice section of `brand/<name>.md` can be copied to
`themes/<name>.md`; the adaptation section can't.

---

## 7. `brand/default`

Once more than one brand exists, one line naming the brand to use without asking. With it present,
make mode never asks about branding.
