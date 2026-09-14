<!-- Upstream-owned: every update replaces this file whole (UPDATING.md §1). Don't edit it in a
     fork — what you want to write here goes in brand/<name>.md, media/<id>.md/.css, or
     SKILL.fork.md. -->

# Customizing makeitbrand — and still getting updates

The rule that makes updates painless: **everything makeitbrand ships is replaceable; everything
yours lives in files an update never touches.**

```
UPDATED (replace byte-for-byte, never edit)     YOURS (an update never touches these)
─────────────────────────────────────────       ─────────────────────────────────────
runtime.js  runtime.css  runtime.min.*          SKILL.fork.md        your skill's name, description, standing orders
SKILL.md · PRIMITIVES.md · MEDIA.md             brand/<name>.css     your brand: tokens + @font-face
BRANDING.md · CUSTOMIZING.md · UPDATING.md      brand/<name>.md      your brand's voice AND its adaptation rules
build.sh · take-update.sh                       brand/assets/        logo variants, fonts, imagery
sheet.py · export.py                            brand/default        which brand to use without asking
tools/  (additive)                              media/<id>.md        your own medium profiles (prose)
demo/   (additive)                              media/<id>.css       your own medium profiles (the CSS rule)
                                                 custom.css           bespoke, rasterization-safe CSS
                                                 custom.js            bespoke sheet behaviour (optional)
```

Taking an update = overwriting the left column with the new release. `take-update.sh` does it
file by file (below). Nothing on the right is ever part of a release, so nothing merges.

`UPDATING.md` has the mechanics: syncing a fork from upstream, re-installing the skill, and
refreshing a sheet that is already in progress.

## What the runtime promises you

The primitives, `data-*` attributes, and medium ids documented in `PRIMITIVES.md` and
`MEDIA.md` are a **stable contract**. Releases add primitives and profiles; they don't rename
or remove them, and they don't change what existing markup means. That is why a sheet generated
last month and your customizations both survive a runtime update.

## Layer 0 — the skill's identity: `SKILL.fork.md`

Claude picks a skill by its `description:`; two installs with the same one compete, and the
loser is whichever you happen to want. So a branded install needs its own name and its own
description — and `SKILL.md`, where those live, is upstream's and gets replaced. Editing it
loses the edit on the next update; patching it from `build.sh` with a regex breaks the first
time upstream rewords the line. Both have happened, in the sibling project this one borrows
the mechanism from.

`SKILL.fork.md` is the file that is yours. It has the shape of a `SKILL.md` head — frontmatter,
then markdown — and `./build.sh` composes the shipped `SKILL.md` from it and upstream's body:

```markdown
---
name: acme-brand
description: Produce on-brand visuals for Acme as single-file HTML sheets — social posts, Slack/Confluence graphics, diagrams, dashboards, nametags from a CSV, or any custom size. Use whenever the user wants a branded graphic, a social image, a header, a diagram, a dashboard, or a batch of nametags/badges. Also use to revise an existing Acme sheet.html this skill generated. Not for slide decks (see acme-decks) or .pptx/Google Slides.
---

**This install is brand-locked to Acme.** Always use `brand/acme.css`; never ask which brand.
Read `brand/acme.md` before writing a board — it overrides the defaults below.
```

What happens at build:

- **Frontmatter merges by key.** Every key you write replaces upstream's; keys you leave out
  come through from upstream. Keep each value on one line, as upstream does — skill loaders
  are not all full YAML parsers. `description:` is required — leaving it out ships upstream's,
  which says "makeitbrand", which is the bug this file exists to fix. Say the brand in the
  first clause, keep the trigger phrases (they are what makes "make me a social post" land
  here), and keep the "Not for slide decks / .pptx" tail so it doesn't compete with a sibling
  slide skill.
- **`name:` is the build's name** — `./build.sh` uses it for `dist/<name>/`, the zip, and the
  frontmatter, all the same. They have to agree: Claude Code keys a local skill on its folder,
  Claude Desktop's upload reads `name:` out of `SKILL.md` — a zip whose frontmatter still says
  `makeitbrand` installs and matches as makeitbrand there, whatever the folder was called. An
  argument overrides it (`./build.sh acme-brand-beta`) so a trial build can sit beside the real
  install; nothing else changes.
- **The body lands right under the title,** before upstream's generic instructions — the first
  thing read after the frontmatter. Two to ten lines: which brand to assume, whether to ask
  before generating, anything about *which files this install ships* that isn't already
  obvious from the folder. Anything about *how a board reads* belongs in `brand/<name>.md`,
  not here.

**What ships is the repo minus the dev files.** Everything in the folder goes into
`dist/<name>/` except `demo/` and its sheets, the repo docs (top-level `.md` other than the
five contract docs), the `.sh` scripts, dot-files and dot-folders, `dist*/`, and whatever a
fork-owned `.skillignore` lists (gitignore-style, one pattern per line). So a brand layer ships
whatever it is called — `brand/`, `media/`, `custom.css`, `custom.js` — and the build prints
what it shipped so you can see a stray file before it leaves. Name anything non-standard in the
standing orders so the model copies it.

Upstream's own build is the degenerate case: no `SKILL.fork.md`, so the repo's `SKILL.md`
ships as is, and the stock brands in `brand/` (`kestrel`, `halcyon`, and the demo iconset) are what a
hand-written sheet points at. A fork adds its own brand beside them, never edits a stock one, and
names its own in `brand/default`. Install from `dist/<name>/`, never from the repo folder — the folder's `SKILL.md` is
upstream's generic one and registers as "makeitbrand".

## Layer 1 — brand tokens (covers most needs)

`brand/<name>.css` restyles every primitive at once through the token set in `BRANDING.md` §1
— the same nine core tokens as the sibling slide skill, plus type scale, chart palette, and
logo variants as `data:` URIs. This is the right tool for "make it look like us".

`brand/<name>.md` is the other half: **voice** (5–10 concrete, checkable rules — tone, banned
words, number formatting) and **adaptation** (how the brand degrades across media and grounds:
"below 1200px board width, drop the eyebrow"; "on `inverse` grounds, the logo is `mono`, not
`light`"). See `BRANDING.md` §5. Rules for the *install* rather than the brand (which files to
copy, what the skill is called) go in `SKILL.fork.md`. If neither file can express what you
need, that is a gap in `PRIMITIVES.md` or `MEDIA.md`: report it upstream rather than editing
the vendored copy, which loses the edit on the next update.

`brand/default` is one line naming the brand to use once more than one exists (`BRANDING.md`
§7) — with it present, make mode never asks which brand.

`brand/assets/` carries fonts, logo variants, and imagery the brand's CSS references by
relative `url()`; `sheet.py` inlines them as `data:` URIs when a sheet is assembled, so nothing
in `brand/assets/` needs to travel any further than the fork.

## Layer 2 — your own medium profiles

A medium a fork needs that isn't in the stock set (`MEDIA.md`'s table) is two files, not a
theme override: `media/<id>.md` (prose, ≤ 20 lines, same shape as a stock profile) and
`media/<id>.css` (the one `.board[data-medium="<id>"]{…}` rule — see `MEDIA.md`, "Writing a
profile for a fork"). A fork profile that reuses a stock id overrides it; `sheet.py` inlines
`media/*.css` as `<style data-media>` right after the runtime, so a fork's rule wins the
cascade the same way a browser resolves any later rule. Add a budget row for the new medium to
`brand/<name>.md`, since `PRIMITIVES.md`'s density budgets are upstream's and won't know about
an id it never shipped.

## Layer 3 — custom.css / custom.js (bespoke graphics and behaviour)

For things that aren't a "brand" or a "medium" — an extra utility class, a small behaviour
tweak to the sheet's edit mode. Ship `custom.css` and/or `custom.js` in the skill folder;
`sheet.py` inlines them into every sheet after the brand and after the runtime respectively.

**Every rule in `custom.css` is bound by `PRIMITIVES.md` §12, Rasterization-safe CSS**, exactly
like the runtime, the stock profiles, and a brand's own CSS: export draws a board through SVG
`<foreignObject>` into a canvas, and anything the browser can't paint in that path silently
disappears from the PNG. No `backdrop-filter`, no non-`data:` `url()`, no blend modes, no
`filter`, nothing that depends on `:hover`/animation. That rule applies to every author of CSS
in this system, `custom.css` included — there is no exception for the fork layer.

`custom.js` runs in the sheet's edit/export runtime, not inside a board's exported pixels — a
board is a static markup+CSS snapshot at export time, so script-driven visuals belong in
`custom.css` (drawn once, before export) rather than `custom.js` (which can only affect the
live editing session).

## What not to do

- Don't edit `runtime.js` / `runtime.css` — your change dies on the next update, or worse,
  keeps you from ever taking one.
- Don't edit `MEDIA.md` or `PRIMITIVES.md` to describe a fork-only medium or primitive — a
  fork's own medium is `media/<id>.md` + `media/<id>.css`; a fork can't add primitives at all
  (report a gap upstream instead).
- Don't put per-sheet `<style>`/`<script>` beyond what `sheet.py` generates — a sheet's markup
  is meant to stay Claude-editable, plain HTML above the `makeitbrand:runtime` marker.

## Sharing your customized install

`./build.sh` writes the installable skill to `dist/<name>/` (and a zip) under the name in
`SKILL.fork.md`: commit the folder and distribute as a Claude Code plugin, or drop the build
into a repo's `.claude/skills/`. Everyone who installs it gets your brand and your media
profiles — and you can still pull runtime updates into it from upstream (`UPDATING.md`).
