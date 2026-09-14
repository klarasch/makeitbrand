#!/bin/bash
# Assemble the distributable Claude skill into dist/<name>/ (+ a zip).
#
#     ./build.sh              → dist/makeitbrand/, dist/makeitbrand-skill.zip
#     ./build.sh acme-brand    → dist/acme-brand/, dist/acme-brand-skill.zip
#     ./build.sh --sync-profiles
#
# The repo is the dev source, and the skill is the repo minus the dev files:
# demo/, dist*, dot-files and dot-folders, the top-level .sh scripts, and the
# repo docs (top-level .md other than the contract docs) never ship. A fork's
# own layers — brand/, media/, SKILL.fork.md, custom.css, custom.js — ship
# whatever they are called, with nothing to add here.
#
# A fork never edits this file, and never edits SKILL.md. Its identity lives
# in SKILL.fork.md (CUSTOMIZING.md "Layer 0"): the frontmatter there — name,
# description — replaces upstream's, and whatever it says below the
# frontmatter is inserted under the title as the install's standing orders.
# The shipped SKILL.md is composed from that plus upstream's generic body, so
# an update to the body lands without touching a word that is yours.
set -euo pipefail
cd "$(dirname "$0")"

# --sync-profiles is the one case where this script edits an upstream file
# (runtime.css), and only when run inside the upstream repo itself — see the
# profiles check below. Handle it before anything else needs SKILL.md etc.
SYNC=0
ARGS=()
for a in "$@"; do
  case "$a" in
    --sync-profiles) SYNC=1 ;;
    *) ARGS+=("$a") ;;
  esac
done

# ---- MEDIA.md <-> runtime.css profile block --------------------------------
# MEDIA.md is the prose+CSS source of truth for stock media profiles; the one
# CSS rule per profile is duplicated, unavoidably, into runtime.css's
# `@profiles` block because the runtime can't read markdown. The two drift
# the moment someone edits one and forgets the other, so build.sh refuses to
# ship a stale block instead of shipping a runtime that disagrees with the
# docs a fork author is reading.
extract_media_profiles() {
  # One-line `.board[data-medium="…"]{…}` rules from MEDIA.md's fenced css
  # blocks, in the order they appear.
  awk '
    /^```css$/ { incss=1; next }
    /^```$/    { incss=0; next }
    incss && /^\.board\[data-medium="[^"]+"\]\{.*\}$/ { print }
  ' MEDIA.md
}

extract_runtime_profiles() {
  awk '
    /\/\* @profiles:start \*\// { on=1; next }
    /\/\* @profiles:end \*\// { on=0 }
    on && /^\.board\[data-medium="[^"]+"\]\{.*\}$/ { print }
  ' runtime.css
}

if [ "$SYNC" -eq 1 ]; then
  # A fork also carries MEDIA.md and runtime.css (both are files a release
  # replaces), so their mere presence doesn't mean this is upstream. The
  # signal that does: SKILL.fork.md exists in every fork and in no upstream
  # checkout (CUSTOMIZING.md, Layer 0) — refuse rather than rewrite a file
  # the fork's next `take-update.sh` run will just overwrite anyway.
  if [ -f SKILL.fork.md ]; then
    echo "build.sh: --sync-profiles edits runtime.css, an upstream-owned file — refusing to" >&2
    echo "          run it here because SKILL.fork.md marks this as a fork. Fix MEDIA.md/" >&2
    echo "          runtime.css in the upstream repo and take the update instead." >&2
    exit 2
  fi
  [ -f MEDIA.md ] || { echo "build.sh: --sync-profiles needs MEDIA.md — run this inside the upstream repo" >&2; exit 2; }
  [ -f runtime.css ] || { echo "build.sh: --sync-profiles needs runtime.css — run this inside the upstream repo" >&2; exit 2; }
  NEW="$(extract_media_profiles)"
  if [ -z "$NEW" ]; then
    echo "build.sh: found no .board[data-medium=…] rules in MEDIA.md's css blocks — nothing to sync" >&2
    exit 1
  fi
  python3 - "$NEW" <<'SYNCPY'
import re, sys
from pathlib import Path
new_block = sys.argv[1]
p = Path("runtime.css")
css = p.read_text()
m = re.search(r"(/\* @profiles:start \*/\n).*?(\n/\* @profiles:end \*/)", css, re.S)
if not m:
    sys.exit("build.sh: runtime.css has no /* @profiles:start */ ... /* @profiles:end */ block")
css = css[:m.start()] + m.group(1) + new_block + m.group(2) + css[m.end():]
p.write_text(css)
SYNCPY
  echo "build.sh: runtime.css's @profiles block rewritten from MEDIA.md"
  echo "$NEW"
  exit 0
fi

# Fail loudly, not silently, if the two have drifted — this is a data
# integrity check, not a style nit, so it runs on every normal build too.
if [ -f MEDIA.md ] && [ -f runtime.css ]; then
  MEDIA_PROFILES="$(extract_media_profiles)"
  RUNTIME_PROFILES="$(extract_runtime_profiles)"
  if [ "$MEDIA_PROFILES" != "$RUNTIME_PROFILES" ]; then
    echo "build.sh: runtime.css's @profiles block is out of sync with MEDIA.md's css blocks." >&2
    echo "          run ./build.sh --sync-profiles (upstream repo only) to fix it, then re-run." >&2
    diff <(echo "$MEDIA_PROFILES") <(echo "$RUNTIME_PROFILES") >&2 || true
    exit 1
  fi
fi

set -- "${ARGS[@]+"${ARGS[@]}"}"

FORK=""; [ -f SKILL.fork.md ] && FORK=SKILL.fork.md

if [ ! -f SKILL.md ]; then
  echo "build.sh: SKILL.md is missing. It is upstream's file (the generic instruction set" >&2
  echo "          that SKILL.fork.md's head is composed onto) and build.sh cannot invent" >&2
  echo "          one — someone still needs to write it. Nothing was built." >&2
  exit 2
fi

# Skill name: argument > SKILL.fork.md `name:` > makeitbrand. It names the
# dist folder, the zip, and the `name:` frontmatter, all three the same —
# Claude Code keys the skill on the folder, the frontmatter says what it
# should be.
NAME="${1:-}"
if [ -z "$NAME" ] && [ -n "$FORK" ]; then
  NAME="$(sed -n 's/^name:[[:space:]]*//p' "$FORK" | head -1)"
fi
NAME="${NAME:-makeitbrand}"
case "$NAME" in
  *[!a-zA-Z0-9._-]*|"") echo "build.sh: skill name '$NAME' — letters, digits, . _ - only" >&2; exit 2 ;;
esac

# Real minification for sheet.py's inliner, which prefers runtime.min.*
# when present and fresh; without esbuild it falls back to inlining the
# unminified files, so the fallback here just needs to not be stale.
if command -v esbuild >/dev/null 2>&1; then ESBUILD=esbuild
elif command -v npx >/dev/null 2>&1; then ESBUILD="npx --yes esbuild"
else ESBUILD=""; fi
if [ -n "$ESBUILD" ]; then
  $ESBUILD runtime.js  --minify --outfile=runtime.min.js  --log-level=warning
  $ESBUILD runtime.css --minify --outfile=runtime.min.css --log-level=warning
  echo "minified: runtime.min.js ($(du -k runtime.min.js | cut -f1)K) runtime.min.css ($(du -k runtime.min.css | cut -f1)K)"
else
  echo "warning: esbuild unavailable — copying runtime.js/.css as runtime.min.*; sheet.py will inline the unminified files"
  cp runtime.js runtime.min.js
  cp runtime.css runtime.min.css
fi

OUT="dist/$NAME"
rm -rf "$OUT"
mkdir -p "$OUT"

# ---- SKILL.md: upstream's body under the install's own head ---------------
python3 - "$NAME" SKILL.md "$OUT/SKILL.md" $FORK <<'COMPOSE'
import re, sys
from pathlib import Path

name, src, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
fork = Path(sys.argv[4]) if len(sys.argv) > 4 else None

def split(path):
    """(frontmatter lines, body) — the frontmatter is the block between the
    opening '---' line and the next one; nothing is parsed inside it."""
    text = path.read_text()
    if not text.startswith("---\n"):
        sys.exit(f"build.sh: {path} does not start with a frontmatter block")
    end = text.find("\n---\n", 4)
    if end < 0:
        sys.exit(f"build.sh: {path}: frontmatter never closes")
    return text[4:end].split("\n"), text[end + 5:]

def keyed(lines):
    """Group frontmatter lines by top-level key so a fork can replace one
    key at a time. An indented (or blank) line continues the previous key."""
    groups = []
    for ln in lines:
        if groups and (ln[:1] in (" ", "\t") or not ln.strip()):
            groups[-1][1].append(ln); continue
        m = re.match(r"([A-Za-z_][\w-]*)\s*:", ln)
        groups.append((m.group(1) if m else ln, [ln]))
    return groups

up_fm, up_body = split(src)
body = up_body.lstrip("\n")
title, nl, body = body.partition("\n")
if not title.startswith("# "):
    sys.exit(f"build.sh: {src}: expected the title line right after the frontmatter, got {title!r}")
body = body.lstrip("\n")

fm = keyed(up_fm)
brand = ""
if fork:
    fk_fm, fk_body = split(fork)
    fk = keyed(fk_fm)
    if "description" not in {k for k, _ in fk}:
        sys.exit(f"build.sh: {fork} has no description: — the description is what "
                 "makes the skill trigger, and upstream's says 'makeitbrand'. Write your own.")
    for k, lines in fk:
        fm = [(gk, gl) for gk, gl in fm if gk != k]
        fm.append((k, lines))
    brand = fk_body.strip("\n")
fm = [(k, l) for k, l in fm if k != "name"]
fm.insert(0, ("name", [f"name: {name}"]))

parts = ["---\n", "\n".join(l for _, ls in fm for l in ls), "\n---\n\n", f"# {name}\n\n"]
if brand:
    parts += [brand, "\n\n"]
parts.append(body)
out.write_text("".join(parts))
print(f"SKILL.md: name={name}" + (f", head + brand section from {fork}" if fork else ", generic"))
COMPOSE

# ---- everything else: the repo minus the dev files -------------------------
python3 - "$OUT" <<'SHIP'
import fnmatch, shutil, sys
from pathlib import Path

out = Path(sys.argv[1]); root = Path(".")
CONTRACT_DOCS = {"PRIMITIVES.md", "MEDIA.md", "BRANDING.md", "CUSTOMIZING.md", "UPDATING.md"}
NEVER = {"dist", "node_modules", "__pycache__", "SKILL.md", "SKILL.fork.md", "demo",
         "phase0"}                     # POC sandbox scratch dir, not part of the repo layout

def dev_only(rel: Path) -> bool:
    top = rel.parts[0]
    if top in NEVER or top.startswith("."):
        return True
    if top.startswith("dist"):                       # dist/, dist-sheets/, ...
        return True
    if rel.name == ".DS_Store" or rel.suffix in (".pdf", ".log", ".zip"):
        return True
    if len(rel.parts) == 1:                      # top-level files only
        if rel.suffix == ".html":
            return True                          # nothing top-level ships as html
        if rel.suffix == ".sh":
            return True
        if rel.suffix == ".md" and rel.name not in CONTRACT_DOCS:
            return True
    return False

# .skillignore — gitignore-flavoured, fork-owned: one pattern per line,
# '/' anchors at the repo root, a trailing '/' means a folder, '#' comments.
ignore = []
if Path(".skillignore").exists():
    for line in Path(".skillignore").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            ignore.append(line.rstrip("/"))

def ignored(rel: Path) -> bool:
    s = rel.as_posix()
    for pat in ignore:
        if pat.startswith("/"):
            p = pat[1:]
            if s == p or s.startswith(p + "/") or fnmatch.fnmatch(s, p):
                return True
        elif any(fnmatch.fnmatch(part, pat) for part in rel.parts) or fnmatch.fnmatch(s, pat):
            return True
    return False

shipped = []
for path in sorted(root.rglob("*")):
    rel = path.relative_to(root)
    if any(dev_only(Path(*rel.parts[:i + 1])) for i in range(len(rel.parts))):
        continue
    if ignored(rel):
        continue
    if path.is_file():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out / rel)
        shipped.append(rel)

for name in ("runtime.js", "runtime.css", "sheet.py", "PRIMITIVES.md", "MEDIA.md"):
    if not (out / name).exists():
        sys.exit(f"build.sh: {name} did not ship — is this a makeitbrand checkout?")
if not (out / "export.py").exists():
    print("build.sh: note — export.py did not ship (not written yet); batch export via headless Chrome is unavailable in this build")
tops = {}
for rel in shipped:
    tops.setdefault(rel.parts[0], 0)
    tops[rel.parts[0]] += 1
print("shipping: " + "  ".join(f"{k}/ ({n})" if n > 1 or (root / k).is_dir() else k
                               for k, n in sorted(tops.items())))
SHIP

(cd dist && rm -f "$NAME-skill.zip" && zip -qr "$NAME-skill.zip" "$NAME")

echo "$OUT/:"
ls "$OUT"
echo
echo "→ install by dropping $OUT into .claude/skills/, or share dist/$NAME-skill.zip"
