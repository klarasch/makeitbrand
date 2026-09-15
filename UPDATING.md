<!-- Upstream-owned: every update replaces this file whole (UPDATING.md §1). -->

# Taking an update from makeitbrand

Upstream is the makeitbrand repo. This page is for whoever runs a copy of it — a company fork
with its own brand, or a plain install someone dropped into `.claude/skills/`.

The short version: **updates are a file copy, never a merge.** `CUSTOMIZING.md` explains why —
everything makeitbrand ships is replaceable and everything yours lives in files a release never
touches. What follows is the mechanics, and the places a copy hides.

---

## 1. What a release owns

```
runtime.js  runtime.css  runtime.min.js  runtime.min.css     replaced
SKILL.md  PRIMITIVES.md  MEDIA.md  PAGES.md  BRANDING.md      replaced
CUSTOMIZING.md  UPDATING.md  build.sh  take-update.sh          replaced
sheet.py  export.py  kit.py                                    replaced
tools/  demo/                                                  added to, never pruned
```

Everything else in a fork — `SKILL.fork.md`, `.skillignore`, `brand/<name>.css`,
`brand/<name>.md`, `brand/assets/`, `brand/default`, your own `media/<id>.md` +
`media/<id>.css`, `custom.css`, `custom.js` — is yours, and no update touches it, and all of it
ships.

**`SKILL.md` is replaced, and that is fine, because the shipped one is composed.** The repo's
`SKILL.md` is upstream's generic instruction set and stays that way. Your skill's *identity* —
its `name:`, the `description:` that makes it trigger, and the brand's standing orders — lives
in `SKILL.fork.md`, which no update touches. `./build.sh` puts the two together: your head on
upstream's body (`CUSTOMIZING.md`, Layer 0). An install that instead edits `SKILL.md`, or
patches its frontmatter from `build.sh`, ships as "makeitbrand" the first time upstream rewords
a line.

If you have edited anything on a **replaced** line, that edit is the thing that will hurt. Move
it into the extension layer (`CUSTOMIZING.md`) before updating, not after. §2 stops and tells
you when you haven't.

## 2. Update the fork

Keep an upstream checkout as a **sibling** of your fork:

```bash
cd ~/Code && git clone <upstream-url> makeitbrand
```

Your fork keeps its own history, its own remote, its own branches — nothing about it changes.
What the sibling adds is *history*: a folder of files tells you what upstream has, a git
checkout tells you what upstream **changed**, which is the difference between copying an update
and understanding one.

Then, from inside the fork:

```bash
cd ~/Code/my-fork && git -C ~/Code/makeitbrand pull && ~/Code/makeitbrand/take-update.sh
```

The script lives upstream on purpose — it carries the §1 manifest, so it can never be out of
date with the files it is copying. It copies; it never merges. What it adds over `cp`:

- **It prints the log** since your last update, and says which commits let you *delete* code
  from the fork. An update that only adds is an update half-taken.
- **It skips a file you edited, and takes everything else** — comparing against the version
  you last took, not against upstream's HEAD, so an upstream change never looks like your edit.
  This is the signal `git merge` gave you as a conflict, without the merge. Skipped files are
  named at the end with where the edit belongs instead, and the exit code is 1. One local
  patch no longer freezes the whole fork; `--force` overwrites it if you meant to drop it.
- **`--check` reports drift and nothing else** — exit 1 if any upstream-owned file is edited.
  Cheap enough for a pre-commit hook or a fork's `CLAUDE.md`: drift found the day it happens is
  a five-minute move, drift found at update time is an archaeology session.
- **`--dry-run` reports what would change and copies nothing** — exit 0 if nothing conflicts,
  exit 1 if any upstream-owned file is edited in the fork (same edited/skipped report as a real
  run, just without writing anything). Run it before a real update when you want to see the
  blast radius first.
- **It refuses to copy from a dirty upstream.** There is no commit to record, so the *next*
  update would have nothing to diff against. (`--allow-dirty` if you must; the stamp then says
  so.)
- **It records what you took**, in `.makeitbrand-upstream`. Commit that file with the update —
  it is what makes every bullet above work next time.

First run has no stamp, so it can't tell your edits from upstream's changes: it lists what
differs, you review, and `--first-run` records the baseline. Exact from then on.

**Why not `git merge upstream/master`?** It works only for a fork that was born as a clone. A
fork that started as a folder someone handed you has no shared ancestor — the merge needs
`--allow-unrelated-histories` and conflicts on essentially every file. And even where it works,
a merge is the wrong verb for a system in which nothing is merged: every file is either wholly
upstream's or wholly yours. Submodules and subtrees fail the same test.

## 3. Update the install

The skill in `.claude/skills/` is a **copy of a build**, not a link to the fork. Pulling the
repo changes nothing until you rebuild and re-install:

```bash
./build.sh && rm -rf ~/.claude/skills/makeitbrand && cp -R dist/makeitbrand ~/.claude/skills/makeitbrand
```

A fork builds under its own name — `./build.sh` reads it from `SKILL.fork.md`, so
`dist/<name>/` and `dist/<name>-skill.zip` come out branded with no arguments. Pass a name to
build under a different one (`./build.sh acme-brand-beta` for a trial install beside the real
one); the folder, the zip and the `name:` frontmatter always agree. Never install the repo
folder itself as the skill: its `SKILL.md` is upstream's generic one, and it registers as
"makeitbrand".

New sheets now generate with the new runtime. Sheets already handed to a user do not — see §4.

## 4. Refresh a sheet already in progress

Unlike the sibling slide skill, a makeitbrand sheet is not a live folder Claude keeps writing
into between sessions — it is inlined once, at the end, by `sheet.py`, into a single
self-contained HTML file with no external references left. So there is nothing to "refresh in
place" for a delivered sheet; the runtime it carries is frozen the moment it was inlined, same
as any other exported artifact.

What *can* need a refresh is a **dev-form sheet still being worked on** — one that links
`runtime.css`/`runtime.js` (and a `brand/*.css`, `media/*.css`) rather than having them inlined
yet. If that dev-form sheet's linked files are a stale copy from before the update, point it at
the updated ones (or re-run `sheet.py` against the freshly-updated skill folder) before the
final inline:

```bash
python3 sheet.py path/to/in-progress-sheet.html -o out/sheet.html
```

`sheet.py` always pulls in whatever `runtime.min.*` (or `runtime.*`, per `--no-min`) and
`brand/*.css` / `media/*.css` sit next to it at run time, so re-running it after `./build.sh`
is what "refreshing" means here. A sheet already delivered as a single file is not revisited —
regenerate it from the brief instead if it needs the new runtime's fixes.

## 5. Check it landed

1. Rebuild (`./build.sh`) and reinstall; confirm the skill's `SKILL.md` still opens with your
   `SKILL.fork.md` head (name, description, standing orders).
2. Generate one sheet through `make` mode and confirm it exports at 2x with correct fonts and
   the right brand tokens.
3. Confirm your `media/<id>.css` profiles (if any) still take effect — a board on that medium
   should render at the profile's `--board-w`/`--board-h`, not a stock fallback.
4. The new thing from the changelog actually shows up. If it doesn't, you are looking at a
   sheet or a build assembled before the update — rebuild and regenerate.
