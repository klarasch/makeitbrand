---
name: makeitbrand
description: Make on-brand visuals as one editable HTML sheet with PNG and PDF export — social posts (square, portrait, landscape), multi-page LinkedIn carousels as a PDF document post, infographics, Slack and Confluence headers, diagrams and charts for slides, KPI dashboards, print-ready nametags and other graphics from a CSV, or any custom size. Use whenever the user wants a graphic, visual, social post, carousel or document post, banner, header image, infographic, architecture diagram, chart image, dashboard image, badge or nametags "on brand", a printable PDF of them, or wants one message turned into several formats. Also use to revise a sheet this skill made (applying pasted "Copy changes" markup or data-note requests) and to train a brand from a website URL, brand guidelines PDF or logo. Not for slide decks, .pptx, or photo editing.
---

# makeitbrand

<!-- Upstream-owned: every update replaces this file whole (UPDATING.md). An install's own rules go
     in SKILL.fork.md (composed in above this line); a brand's rules in brand/<name>.md. -->

A sheet is one HTML file of fixed-size boards, one board per image or per PDF page. The runtime,
the medium profiles and the brand stylesheet are fixed assets; you write board markup and nothing
else.

```
runtime.js · runtime.css     sheet view, edit mode, export, charts, diagrams   ← never edit
brand/<name>.css · .md       tokens, fonts, logo; voice and adaptation rules    ← never edit per sheet
sheet.py                     inliner + batch rows                               ← run it
export.py                    headless PNG and PDF export                        ← run it
PRIMITIVES.md · MEDIA.md     the markup contract and the media                  ← read them
```

Read `PRIMITIVES.md` and `MEDIA.md` in this skill's folder before writing any markup, every time.
They are the complete list of what exists. If a primitive is not in them, it does not exist: never
solve a layout problem with a `<style>`, a `style=` or a class you made up.

---

## 1. Pick the mode

| mode | trigger |
|---|---|
| **make** | default: a new visual, or one message in several formats |
| **revise** | the user pastes board markup ("Copy changes"), sends back a sheet this skill made, or asks to change one ("apply my notes", "shorter headline on the square") |
| **batch** | many boards from data: nametags, badges, a card per person or product, "from this CSV" |
| **setup** | the user wants a brand trained: "set up our brand", a website URL, brand PDF or logo |
| **update** | the user wants the latest makeitbrand in their fork |

Pasted markup that starts with `<section class="board"` is always a revise.

---

## 2. The brief (make mode)

| field | what you need |
|---|---|
| **what** | the message or the data. Headline, supporting line, numbers, names, steps — the actual words |
| **media** | profile ids from `MEDIA.md` (`social-square`, `infographic`, `chat-header`, `slide-inset`, `dashboard`, …) or a custom W×H and where it will be seen |
| **audience** | who sees it and where (LinkedIn feed, a Confluence page, a slide) |
| **tone** | a few words; the brand voice file has the rest |
| **deliver** | images (PNG, the default) or a document (PDF). Follows from the media: a profile's **delivery** line in `MEDIA.md` says when it is a PDF |

Map the request to media yourself: "a LinkedIn post" → `social-square` (or `infographic` when it
carries research, several numbers or a chart); "a carousel", "a document post", "a multi-page
LinkedIn post", "swipeable" → `carousel`, one board per page, delivered as a PDF; "for Confluence" →
`chat-header`; "a diagram for my slides" → `slide-inset`; "nametags to print" → `nametag` as a PDF;
"a banner 3000×600" → `custom` with the `data-like` of how it is seen.

**Gathering it.**

1. State your assumptions in one line ("Assuming: social-square + chat-header, plain tone").
2. **Never invent content the user owns**: a job title, a URL, a quote and its speaker, numbers,
   the steps of their process, names. If any is missing, ask for it in one message, together with
   any open brief field, each with a default so "go" works. If they say go without it, write a
   clearly placeholder value and flag it with `data-note="placeholder: …"` (PRIMITIVES §10).
3. Anything printed needs one answer in that same message: office printer (A4 or Letter sheets with
   cut marks; default A4, Letter for a US user) or a print shop or badge printer (one page per piece
   at its trim size). Bleed follows from that: a print shop gets it, office sheets get it when the
   pieces will be cut, a badge printer that prints the exact size doesn't.
4. Never ask about colours, fonts or layout. The brand and the profiles decide those.
5. One round of questions, never a second.

Record the settled brief, `deliver=` included, in `<meta name="makeitbrand-brief">`.

---

## 3. Make

**Workspace.** Build in a work folder: next to the user's files in Claude Code or Cowork
(`<slug>-work/`), in `/tmp/makeitbrand/<slug>/` on a chat surface. The user receives exactly one
file: the inlined sheet, named after its `<title>`.

**Write the dev-form sheet** `work/sheet.html` with the skeleton in PRIMITIVES §1, linking this
skill's files by absolute path after the runtime marker, in this order:

```html
<!-- makeitbrand:runtime — generated below this line, never edit by hand -->
<link rel="stylesheet" href="<skill>/runtime.css">
<link rel="stylesheet" href="<skill>/media/<id>.css">          <!-- each fork profile used, if any -->
<link rel="stylesheet" href="<skill>/brand/<name>.css">
<link rel="stylesheet" href="<skill>/brand/icons.css">          <!-- if the brand ships icons -->
<link rel="stylesheet" href="<skill>/custom.css">               <!-- if present -->
<script src="<skill>/runtime.js"></script>
<script src="<skill>/custom.js"></script>                       <!-- if present -->
```

**Compose.** For each medium, one board. Before writing a board, settle its structure out loud to
yourself in one line (e.g. "eyebrow, h1, divided lead, glass card with range chart, stat row,
quote, band"), then write it.

- Follow the profile's constraints and the brand's adaptation rules (`brand/<name>.md`), which win.
- One message across media: put the shared headline, date and CTA on every board with the same
  `data-bind`, and write the bound text to fit the tightest board.
- A carousel is a sequence, not a set of posts: settle the page list first (cover, one point per
  page, the last page's takeaway), write the boards in page order, title them with the page number
  first (`Carousel 3 pricing`), keep one structure across the middle pages, and follow the profile's
  constraints in `MEDIA.md`. Budgets count per page.
- Make it look designed, not filled in. A number that matters becomes a `.stat` or a chart, never a
  sentence. Group dense boards into sections with `.eyebrow[data-rule]`. On brands with an `--art`
  ground, use it for social and infographic boards with `glass` cards. Leave space: a board that
  hits every budget is too full.
- Charts: pick the form by the job (PRIMITIVES §8). Always a figcaption with a source.
- Diagrams: lay the grid out on paper first (columns × rows, who sits where), keep the main flow on
  one row, apply the routing rules, and at most one accent node.
- Illustrations: use the brand's `figure.illo` library first (PRIMITIVES §6b); draw one by hand only
  when nothing in the library fits, following the brand's `## Illustration` spec exactly. `data-free`
  only when the user explicitly asked for custom colours or style. An illustration request adds
  `figure.illo` to the boards named and changes nothing else — no grounds, no tones, no copy.
- Count words against PRIMITIVES §11 for every text element. Over budget → cut, never shrink.

**Build the file.**

```bash
python3 <skill>/sheet.py work/sheet.html -o "<Title>.html"
```

Never inline anything yourself; base64 must never enter your context.

**Check it** (always for `infographic`, `dashboard` and diagrams; otherwise when unsure):

```bash
python3 <skill>/export.py "<Title>.html" -o work/png/
```

Look at the PNGs (read the image files). export.py also lists every board the runtime marked
`data-overflow` or `data-invalid` and exits non-zero when there is one: that board is not done, however
it looks in the PNG. Fix overflows by cutting words, collisions and imbalance by changing the markup,
then rebuild and export again until export.py reports clean.

**A PDF delivery** (a carousel, anything printed): always check the PNGs as above first, then make
the PDF from the clean sheet:

```bash
python3 <skill>/export.py "<Title>.html" -o <folder>/ --pdf                # one page per board
python3 <skill>/export.py "<Title>.html" -o <folder>/ --pdf --paper a4     # office sheets, cut marks
python3 <skill>/export.py "<Title>.html" -o <folder>/ --pdf --bleed        # print shop: 1/8 in bleed
```

It prints the boards as vector pages at their real size (a nametag is 3.5 × 5 in; 3.75 × 5.25 with
bleed) and checks the page count. `--bleed` combines with `--paper`. Hand over the PDF with the sheet. The PNGs stay the visual check; don't reread the PDF.

**Hand off in three lines, no more:** what you made (boards and media), the file (and the PDF when
there is one), and how to use it — it opens in a browser; E edits text (⌘B highlights, linked text
updates everywhere); Export saves PNGs, or a PDF of each medium's boards; "Copy changes" copies the
edited markup to paste back here for another round. Never mention the work folder, the runtime or
internal paths.

---

## 4. Brand selection

List `brand/*.css` in this skill's folder (ignore `icons.css`).

- **One** → use it, say nothing.
- **Several** → the name in `brand/default` if present; otherwise ask in the same message as the brief.

Read `brand/<name>.md` before writing a board, every time: voice, adaptation rules, icon names,
budget tightening. It overrides this file. Standing orders in `SKILL.fork.md` (composed above) win
over both.

---

## 5. Revise

The sheet's markup is the source of truth. **Never regenerate a sheet** that the user has edited or
annotated. Edit in place.

**Pasted "Copy changes" markup.** It is the complete, current set of boards. Replace the boards in
`work/sheet.html` with it (match by `data-title`; new titles are new boards), then apply the request.

**A sheet file sent back.** The markup is at the top, the runtime below the marker. Read only the
top part (`sed -n '1,/makeitbrand:runtime/p' file.html`), write it to `work/sheet.html`, add the dev
links from §3 below the marker, and revise that. Never read or edit below the marker.

Then:

1. Read `<meta name="makeitbrand-brief">`; stay consistent with it.
2. `python3 <skill>/sheet.py work/sheet.html --snapshot` before touching anything.
3. `grep -o 'data-note="[^"]*"'` — apply each user note, then remove the attribute. Notes that start
   with `placeholder:` are yours: keep them until the user supplies the value.
4. Fix every `data-overflow` (cut words) and `data-invalid` (read the reason) you find.
5. Change only what was asked. The user's wording is theirs. A request's scope is its boards **and**
   its kind of change: "add illustrations" never permits ground, tone or copy changes; "shorter
   headline on the square" never permits touching another board.
6. Re-check budgets on every board you touched, rebuild with `sheet.py`, check as in §3.
7. `python3 <skill>/sheet.py work/sheet.html --diff --allow "<boards the request named>"` (all
   boards' titles, comma-separated, when the request was sheet-wide). It fails on any board outside
   `--allow` that changed or was removed, on a new board not in `--allow`, or on a protected
   board-level attribute (`data-ground`, `data-medium`, `data-tone`, `data-v`, `data-h-align`,
   `data-w`, `data-h`, `data-like`) that changed without `--allow-attr` naming it. When it fails,
   **fix the drift, never widen `--allow`/`--allow-attr`** to make it pass — the diff caught scope
   creep, not a false positive.

---

## 6. Batch

1. Read the data first (header row and the longest value per column).
2. Write one template board with `data-template` and `data-field` (PRIMITIVES §10), sized for the
   longest values. `data-title` with a `{column}` for useful filenames.
3. `python3 <skill>/sheet.py work/sheet.html --rows data.csv -o "<Title>.html"` — it materialises one
   board per row and warns about values over budget; shorten the template's type choice or ask the
   user about outliers, never truncate their data silently.
4. Check the look on the first few boards only: `python3 <skill>/export.py "<Title>.html" -o work/png/
   --boards 1-3` (the overflow check still covers every board).
5. Deliver by where it goes. Printed (nametags, badges, place cards): the PDF from §3, with `--paper`
   from the brief for office printing. On screen with more than 20 rows, or the user wants files:
   `python3 <skill>/export.py "<Title>.html" -o <folder>/` and hand over the folder of PNGs. Either
   way, with the sheet.

---

## 7. Setup — training a brand

Inputs: a website URL, brand guidelines PDF and/or logo. Any one is enough.

**Where it goes.** A brand lives in a fork repo beside an upstream makeitbrand checkout, so
`take-update.sh` can update it (`UPDATING.md`). Never write brand files into upstream or into an
installed skill folder. Already in a fork (`SKILL.fork.md` or `.makeitbrand-upstream` present) →
write there. In upstream → make the fork beside it (`make-it-<brand>` unless the user names it):

```bash
git clone <upstream> <parent>/<name>
git -C <parent>/<name> remote rename origin upstream-makeitbrand
cd <parent>/<name> && <upstream>/take-update.sh --first-run
```

No shell or git (Cowork, chat) → write the files into `makeitbrand-brand/` and tell the user to
finish the setup in Claude Code next to an upstream checkout.

**Extract**: colours, type, logo, and the look — is there an art-directed ground (gradients,
glow)? Iconography? How dense are their real social posts? From a URL read the rendered page and
its CSS custom properties; from a PDF the palette, type and application pages.

**Show before writing**, in one message: every resolved token (BRANDING.md §1), the chart palette
with the validator's result, the draft voice and adaptation rules. Say plainly:

- `--accent-fg` must contrast with `--accent`; `--good`/`--bad` must pass on `--surface`.
- Fonts must be files the brand may embed. If only desktop-licensed, stop and ask.
- Logos must be SVG with outlined text, one per variant (dark, light, mono).

**Then write**, following `BRANDING.md`: `brand/<name>.css`, `brand/<name>.md`, `brand/assets/`
(fonts, logo variants, icons), `brand/icons.css` if they have an iconset, `brand/default`, any
`media/<id>.md` + `media/<id>.css` they need, and `SKILL.fork.md` — frontmatter with a
`description:` that names the brand first and keeps the trigger phrases, then two to five lines of
standing orders (the brand to use, never ask which). Leave `name:` out: the skill is then called
`make-it-<brand>` after `brand/default` (`/make-it-acme`). Add `name:` only when the user wants
another name.

**Build and check.** `./build.sh` → `dist/<name>/`. Make a check sheet from `dist/<name>/` with
three boards (a social-square, a chat-header, a slide-inset diagram), export it, and look at the
PNGs: fonts, colours, logo. Fix the brand files, never the runtime. Commit the brand with
`.makeitbrand-upstream` as one commit, ask before installing (`cp -R dist/<name>
~/.claude/skills/<name>`), and mention that a generic `makeitbrand` install would compete with it.

---

## 8. Update — taking a new makeitbrand into a fork

Needs a shell and git. Mechanics in `UPDATING.md`; order:

1. Fork = working directory with `SKILL.fork.md` or `.makeitbrand-upstream`; upstream = sibling
   checkout (ask otherwise). Running inside upstream is a mistake; say so.
2. Uncommitted fork changes → show them, ask to commit first. Never stash or discard.
3. `git -C <upstream> pull --ff-only`; stop and show why if it fails.
4. `<upstream>/take-update.sh --dry-run`, show the result, then run it for real. Never `--force`
   on your own.
5. Summarise the upstream log in plain words. Skipped files are fork edits to upstream-owned files:
   say where each belongs instead and offer to move it.
6. `./build.sh`, the three-board check sheet, commit ("Take makeitbrand <sha>"), ask before
   reinstalling.

---

## 9. Hard rules

- Never write CSS or JavaScript into a sheet. No `<style>`, `<script>` or `style=` above the marker.
  `sheet.py` refuses to build a sheet that has one.
- Never edit `runtime.*`, a brand file or a profile to make one sheet work. Missing primitive → say
  so; that is an upstream request, not a workaround.
- Never invent a class, a data attribute value, an icon name, an illustration name, a medium id or
  an image path.
- Never write an inline `<svg>` outside `figure.illo` (PRIMITIVES §6b, §9).
- Never invent the user's content (§2). Placeholders are flagged with `data-note`.
- Never exceed the density budgets. Cut words instead.
- Never type a separator character (`·`, `•`, `|`, `—`, `/`) to join phrases, and no emoji.
- Never inline assets yourself or read below the runtime marker.
- Never regenerate a sheet that carries user edits or notes.
- Never ask more than one round of questions.
- On chat surfaces, hand over only the inlined sheet (and the PNGs or the PDF when exported).
- Never mix media in a PDF delivery: a carousel's pages are all `carousel`, a print batch is one medium.
- Never change more than the revise request's own boards and kind of change (§5). `sheet.py --diff`
  enforces this; a failing diff means fix the drift, not widen `--allow`.
