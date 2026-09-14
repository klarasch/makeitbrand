#!/usr/bin/env python3
"""makeitbrand sheet.py — upstream-owned, replaced whole on update.

Turn a dev-form sheet (linked stylesheets and scripts) into the inlined form a user receives:
one self-contained HTML file, markup first, runtime last, every font and image a data: URI.

    python3 sheet.py demo/sheets/phase1-handwritten.html -o out/sheet.html
    python3 sheet.py sheet.html --brand brand/acme.css -o out/sheet.html   # (re)attach a brand

Only the part after the `makeitbrand:runtime` marker is rewritten; the markup above it is copied
byte for byte, except relative <img src> which are inlined.

Batch (PRIMITIVES.md §10): materialise a `data-template` board against rows of data, one ordinary
board per row. Works on the dev form or the inlined form, and can run together with inlining:

    python3 sheet.py sheet.html --rows data.csv -o out.html          # materialise only
    python3 sheet.py in.html --rows people.csv -o out.html           # materialise, then inline

Re-running --rows on an already-materialised sheet replaces the previous `data-row` boards rather
than duplicating them.

Scope guard (SKILL.md §5): snapshot a sheet before revising it, diff after, to catch drift beyond
what was asked.

    python3 sheet.py work/sheet.html --snapshot                     # before editing
    python3 sheet.py work/sheet.html --diff --allow "Carousel 3 pricing"   # after

--diff exits non-zero if a board outside --allow changed or was removed, a new board isn't in
--allow, or a protected board-level attribute (look/layout: data-ground, data-medium, data-tone,
data-v, data-h-align, data-w, data-h, data-like) changed without --allow-attr naming it.

Promote (SKILL.md, "Promote"): move an authored figure.illo the user approved into the brand's
illustration library, so future boards can reach it by name instead of drawing it again.

    python3 sheet.py work/sheet.html --promote-illo "Carousel 3 layered defence" --name rings
    python3 sheet.py work/sheet.html --promote-illo "Carousel 3 layered defence" --name rings --relink

Refuses a data-free illustration and anything that fails the same checks runtime.js makes at
render time (viewBox, no text/image/foreignObject, no external reference, brand-token colours
only, var(--stroke)-scaled stroke-width). Writes brand/assets/illustrations/<name>.svg, appends
--illo-<name> to the brand's css and the name to the brand .md's Illustration library, in the
skill/fork root sheet.py itself lives in (not the sheet's own folder, and not --brand's path).
--relink also rewrites the sheet's figure to data-illo="<name>" in place.
"""
import argparse
import base64
import csv
import hashlib
import html
import json
import mimetypes
import re
import sys
from pathlib import Path

MARKER = "<!-- makeitbrand:runtime"
SNAPSHOT_NAME = ".makeitbrand-snapshot.json"
PROTECTED_ATTRS = ["data-ground", "data-medium", "data-tone", "data-v", "data-h-align", "data-w", "data-h", "data-like"]
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("image/svg+xml", ".svg")

BOARD_RE = re.compile(r'<section\b(?=[^>]*\bclass="board")[^>]*>.*?</section>', re.S)
MAIN_RE = re.compile(r'(<main\b[^>]*\bclass="sheet"[^>]*>)(.*)(</main>)', re.S)
FIELD_RE = re.compile(r'(<([a-zA-Z0-9]+)\b[^>]*\bdata-field="([^"]+)"[^>]*>)(.*?)(</\2>)', re.S)
TITLE_ATTR_RE = re.compile(r'\bdata-title="([^"]*)"')
ATTR_RE = re.compile(r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*"([^"]*)"')
GEN_TAG_RE = re.compile(r'<([a-zA-Z0-9]+)\b[^>]*\bdata-gen\b[^>]*>.*?</\1>', re.S)
NOTE_ATTR_RE = re.compile(r'\s+data-note="[^"]*"')
FIGURE_ILLO_RE = re.compile(r'<figure\b(?=[^>]*\bclass="illo")[^>]*>.*?</figure>', re.S)
SVG_RE = re.compile(r'<svg\b.*?</svg>', re.S)
TAG_RE = re.compile(r'<([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>')

# ---- figure.illo validation (PRIMITIVES.md §6b) ---------------------------
# Duplicated, not shared: runtime.js checks these against the live DOM in the browser;
# sheet.py checks them against sheet markup before a promote. COUPLING: if you change the rule
# set here, change illoSvgReason() (and ILLO_COLOR_TOKEN / ILLO_STROKE_W) in runtime.js to match,
# and vice versa — this comment lives in both files so a change to one is a prompt to check the other.
ILLO_COLOR_TOKEN = re.compile(r'^var\(\s*--(illo-[1-4]|chart-accent|accent|accent-2|fg|bg|muted|faint|surface)\s*(,[^)]*)?\)$')
ILLO_STROKE_W = re.compile(r'^(var\(\s*--stroke\s*\)|calc\(\s*var\(\s*--stroke\s*\)\s*\*\s*[\d.]+\s*\))$')


def illo_color_ok(v) -> bool:
    if v is None:
        return True
    v = v.strip()
    return v in ("", "none", "currentColor") or bool(ILLO_COLOR_TOKEN.match(v))


def style_props(style: str) -> dict:
    out = {}
    for decl in style.split(";"):
        if ":" not in decl:
            continue
        k, v = decl.split(":", 1)
        out[k.strip().lower()] = v.strip()
    return out


def illo_svg_reason(svg_text: str):
    """Mirrors runtime.js illoSvgReason() (PRIMITIVES.md §6b). data-free is never accepted here —
    promote always validates as if data-free were absent, since promote refuses data-free outright."""
    open_m = re.match(r'<svg\b[^>]*>', svg_text)
    if not open_m:
        return "not a valid svg element"
    root_attrs = parse_attrs(open_m.group(0))
    if not root_attrs.get("viewBox"):
        return "illustration needs a viewBox"
    if re.search(r'<(text|image|foreignObject)\b', svg_text, re.I):
        return "illustration may not contain text, image or foreignObject"
    for tm in TAG_RE.finditer(svg_text):
        attrs = parse_attrs(tm.group(0))
        for attr in ("href", "xlink:href"):
            v = attrs.get(attr)
            if v and not v.startswith("#"):
                return "illustration may not reference anything outside the board"
        style = style_props(attrs.get("style", ""))
        sw = attrs.get("stroke-width") or style.get("stroke-width")
        if sw and not ILLO_STROKE_W.match(sw.strip()):
            return "stroke-width must be var(--stroke), scaled with calc()"
        for prop in ("fill", "stroke", "stop-color"):
            v = attrs.get(prop) or style.get(prop)
            if v and not illo_color_ok(v):
                return f"illustration uses a hard-coded {prop} colour"
    return None


def check_hard_rules(head: str, src: Path):
    """SKILL.md §9: never write CSS or JS into a sheet. Above the runtime marker only."""
    if re.search(r'<style\b', head, re.I):
        sys.exit(f"sheet.py: {src} has a <style> above the runtime marker (SKILL §9)")
    if re.search(r'<script\b', head, re.I):
        sys.exit(f"sheet.py: {src} has a <script> above the runtime marker (SKILL §9)")
    if re.search(r'(?<![\w-])style\s*=\s*["\']', head):
        sys.exit(f"sheet.py: {src} has a style= attribute above the runtime marker (SKILL §9)")


def parse_attrs(open_tag: str) -> dict:
    return {m.group(1): html.unescape(m.group(2)) for m in ATTR_RE.finditer(open_tag)}


def normalize_inner(inner: str) -> str:
    """Content used for the diff hash: drop notes and runtime-generated markup, collapse whitespace."""
    inner = GEN_TAG_RE.sub("", inner)
    inner = NOTE_ATTR_RE.sub("", inner)
    inner = re.sub(r'>\s+<', '><', inner.strip())
    inner = re.sub(r'\s+', ' ', inner)
    return inner


def board_records(head: str) -> dict:
    """Per-board (by data-title) snapshot: board-level attributes and a hash of normalized content."""
    m = MAIN_RE.search(head)
    inner = m.group(2) if m else head
    records = {}
    for bm in BOARD_RE.finditer(inner):
        board_html = bm.group(0)
        open_tag = board_html[: board_html.index(">") + 1]
        body = board_html[len(open_tag): -len("</section>")]
        attrs = parse_attrs(open_tag)
        title = attrs.pop("data-title", None)
        if not title:
            sys.exit(f"sheet.py: a board has no data-title: {open_tag[:80]}")
        if title in records:
            print(f"sheet.py: WARNING duplicate data-title {title!r}; only the last is snapshotted", file=sys.stderr)
        records[title] = {
            "attrs": attrs,
            "hash": hashlib.sha256(normalize_inner(body).encode()).hexdigest()[:16],
        }
    return records


def read_head(src: Path) -> str:
    doc = src.read_text(encoding="utf-8")
    at = doc.find(MARKER)
    if at < 0:
        sys.exit(f"sheet.py: no '{MARKER}' marker in {src}")
    return doc[:at]


def cmd_snapshot(src: Path):
    records = board_records(read_head(src))
    dest = src.parent / SNAPSHOT_NAME
    dest.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{dest}  {len(records)} board(s)")


def cmd_diff(src: Path, allow: str, allow_attr: str):
    snap_path = src.parent / SNAPSHOT_NAME
    if not snap_path.exists():
        sys.exit(f"sheet.py: no snapshot at {snap_path}; run --snapshot first")
    before = json.loads(snap_path.read_text(encoding="utf-8"))
    current = board_records(read_head(src))
    allow_set = {t.strip() for t in (allow or "").split(",") if t.strip()}
    allow_attr_set = {a.strip() for a in (allow_attr or "").split(",") if a.strip()}

    bad = False
    for title in sorted(set(before) | set(current)):
        b, c = before.get(title), current.get(title)
        if b is None:
            ok = title in allow_set
            bad = bad or not ok
            print(f"+ {title}: added" + ("" if ok else "  [SCOPE: not in --allow]"))
            continue
        if c is None:
            ok = title in allow_set
            bad = bad or not ok
            print(f"- {title}: removed" + ("" if ok else "  [SCOPE: not in --allow]"))
            continue

        attr_changes = [
            (k, b["attrs"].get(k), c["attrs"].get(k))
            for k in sorted(set(b["attrs"]) | set(c["attrs"]))
            if b["attrs"].get(k) != c["attrs"].get(k)
        ]
        content_changed = b["hash"] != c["hash"]
        if not content_changed and not attr_changes:
            print(f"= {title}: unchanged")
            continue

        parts = []
        if content_changed:
            ok = title in allow_set
            bad = bad or not ok
            parts.append("content changed" + ("" if ok else "  [SCOPE: not in --allow]"))
        for k, ov, nv in attr_changes:
            protected = k in PROTECTED_ATTRS
            ok = not protected or k in allow_attr_set
            bad = bad or not ok
            parts.append(f'{k} {ov!r}→{nv!r}' + ("" if ok else "  [SCOPE: protected, not in --allow-attr]"))
        print(f"~ {title}: " + "; ".join(parts))

    sys.exit(1 if bad else 0)


# ---- promote-illo (SKILL.md, "Promote") ------------------------------------

def ensure_svg_xmlns(svg_text: str) -> str:
    """An authored figure.illo's <svg> has no xmlns — the HTML parser puts it in the SVG namespace
    for free because it sits inline in the document. A promoted illustration becomes a standalone
    file the runtime fetches and parses with DOMParser(..., "image/svg+xml") (PRIMITIVES.md §6b,
    fillIllo in runtime.js): without an explicit xmlns that parse yields elements in no namespace,
    which the DOM accepts and even serialises back looking right, but Chrome never paints as SVG —
    invisible, not invalid. Add it if the root tag doesn't already carry one."""
    if re.search(r'<svg\b[^>]*\bxmlns=', svg_text):
        return svg_text
    return re.sub(r'^<svg\b', '<svg xmlns="http://www.w3.org/2000/svg"', svg_text, count=1)


def figure_is_authored(fig_html: str) -> bool:
    open_tag = fig_html[: fig_html.index(">") + 1]
    if re.search(r'(?<![\w-])data-illo\s*=', open_tag):
        return False
    return bool(re.search(r'<svg\b', fig_html))


def resolve_brand(skill_root: Path, brand_arg: str):
    if brand_arg:
        name = Path(brand_arg).name
        if name.endswith(".css"):
            name = name[:-4]
    else:
        default_file = skill_root / "brand" / "default"
        name = None
        if default_file.exists():
            first = default_file.read_text(encoding="utf-8").strip()
            name = first.splitlines()[0].strip() if first else None
        if not name:
            candidates = sorted(p.stem for p in (skill_root / "brand").glob("*.css") if p.stem != "icons")
            if len(candidates) == 1:
                name = candidates[0]
            else:
                sys.exit(
                    f"sheet.py: several brands ({', '.join(candidates) or 'none'}) and no "
                    f"brand/default; pass --brand <name>"
                )
    css_path = skill_root / "brand" / f"{name}.css"
    md_path = skill_root / "brand" / f"{name}.md"
    if not css_path.exists():
        sys.exit(f"sheet.py: no {css_path}")
    if not md_path.exists():
        sys.exit(f"sheet.py: no {md_path}")
    return name, css_path, md_path


def insert_illo_token(css_text: str, name: str, force: bool) -> str:
    """Appends --illo-<name> to a brand css, in the same form halcyon.css uses (BRANDING.md §4c)."""
    existing_re = re.compile(rf'^([ \t]*)--illo-{re.escape(name)}\s*:.*$\n?', re.M)
    line = f'  --illo-{name}: url("assets/illustrations/{name}.svg");\n'
    if existing_re.search(css_text):
        if not force:
            sys.exit(f"sheet.py: --illo-{name} is already defined; pass --force to overwrite")
        return existing_re.sub(line, css_text, count=1)
    prior = list(re.finditer(r'^[ \t]*--illo-[\w-]+\s*:\s*url\([^\n]*\n', css_text, re.M))
    if prior:
        pos = prior[-1].end()
        return css_text[:pos] + line + css_text[pos:]
    root_m = re.search(r':root\s*\{.*?\n(\})', css_text, re.S)
    if not root_m:
        sys.exit(f"sheet.py: no :root block found to add --illo-{name} to")
    pos = root_m.start(1)
    return css_text[:pos] + line + css_text[pos:]


LIBRARY_LINE_RE = re.compile(
    r'(Library \(`figure\.illo\[data-illo\]`\):\s*)(.*?)(\.)'
    r'(\s*Reach for one of these before drawing an authored illustration\.)?',
    re.S,
)


def insert_illo_library_entry(md_text: str, name: str, title: str, force: bool) -> str:
    """Appends <name> to the brand .md's ## Illustration library list (BRANDING.md §5)."""
    section_m = re.search(r'^## Illustration\b.*?(?=^## |\Z)', md_text, re.M | re.S)
    if not section_m:
        sys.exit("sheet.py: brand .md has no '## Illustration' section (BRANDING.md §5)")
    section = section_m.group(0)
    if re.search(rf'`{re.escape(name)}`', section):
        if not force:
            sys.exit(f"sheet.py: '{name}' is already listed in the Illustration library; pass --force")
        return md_text
    entry = f', `{name}` (promoted from "{title}")'
    lm = LIBRARY_LINE_RE.search(section)
    if lm:
        prefix, body, dot, tail = lm.group(1), lm.group(2), lm.group(3), lm.group(4) or ""
        new_section = section[: lm.start()] + prefix + body + entry + dot + tail + section[lm.end():]
    else:
        new_section = section.rstrip("\n") + (
            f'\n\nLibrary (`figure.illo[data-illo]`): `{name}` (promoted from "{title}").\n'
        )
    return md_text[: section_m.start()] + new_section + md_text[section_m.end():]


def cmd_promote_illo(src: Path, title: str, name: str, brand_arg: str, index, force: bool, relink: bool):
    if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', name):
        sys.exit(f"sheet.py: --name {name!r} must be kebab-case (lowercase letters, digits, hyphens)")

    doc = src.read_text(encoding="utf-8")
    at = doc.find(MARKER)
    if at < 0:
        sys.exit(f"sheet.py: no '{MARKER}' marker in {src}")
    head, tail = doc[:at], doc[at:]
    m = MAIN_RE.search(head)
    if not m:
        sys.exit('sheet.py: no <main class="sheet"> found')
    inner = m.group(2)

    board_m = None
    for bm in BOARD_RE.finditer(inner):
        open_tag = bm.group(0)[: bm.group(0).index(">") + 1]
        tm = TITLE_ATTR_RE.search(open_tag)
        if tm and html.unescape(tm.group(1)) == title:
            board_m = bm
            break
    if board_m is None:
        sys.exit(f"sheet.py: no board with data-title={title!r}")
    board_html = board_m.group(0)

    figs = list(FIGURE_ILLO_RE.finditer(board_html))
    if not figs:
        sys.exit(f"sheet.py: board {title!r} has no figure.illo")
    authored_positions = [i for i, fm in enumerate(figs) if figure_is_authored(fm.group(0))]

    if index is not None:
        if index < 1 or index > len(figs):
            sys.exit(f"sheet.py: --index {index} out of range; board {title!r} has {len(figs)} figure.illo")
        chosen_i = index - 1
        if chosen_i not in authored_positions:
            sys.exit(f"sheet.py: figure.illo #{index} on {title!r} is a library reference (data-illo), not authored")
    else:
        if not authored_positions:
            sys.exit(f"sheet.py: board {title!r} has no authored figure.illo (inline svg) to promote")
        if len(authored_positions) > 1:
            sys.exit(
                f"sheet.py: board {title!r} has {len(authored_positions)} authored figure.illo elements; "
                f"pass --index (1-based, counting all figure.illo on the board)"
            )
        chosen_i = authored_positions[0]

    chosen = figs[chosen_i]
    fig_html = chosen.group(0)
    open_tag = fig_html[: fig_html.index(">") + 1]
    if re.search(r'(?<![\w-])data-free\b', open_tag):
        sys.exit(f"sheet.py: won't promote a data-free illustration (board {title!r})")

    svg_m = SVG_RE.search(fig_html)
    if not svg_m:
        sys.exit(f"sheet.py: figure.illo on {title!r} has no inline svg")
    reason = illo_svg_reason(svg_m.group(0))
    if reason:
        sys.exit(f"sheet.py: won't promote — {reason} (board {title!r})")

    skill_root = Path(__file__).resolve().parent
    brand_name, css_path, md_path = resolve_brand(skill_root, brand_arg)

    illo_dir = skill_root / "brand" / "assets" / "illustrations"
    illo_dir.mkdir(parents=True, exist_ok=True)
    svg_path = illo_dir / f"{name}.svg"
    if svg_path.exists() and not force:
        sys.exit(f"sheet.py: {svg_path} already exists; pass --force to overwrite")
    svg_path.write_text(ensure_svg_xmlns(svg_m.group(0).strip()) + "\n", encoding="utf-8")
    print(f"wrote {svg_path}")

    css_text = insert_illo_token(css_path.read_text(encoding="utf-8"), name, force)
    css_path.write_text(css_text, encoding="utf-8")
    print(f"wrote --illo-{name} to {css_path}")

    md_text = insert_illo_library_entry(md_path.read_text(encoding="utf-8"), name, title, force)
    md_path.write_text(md_text, encoding="utf-8")
    print(f"added '{name}' to the Illustration library in {md_path}")
    print(f"brand: {brand_name}")

    if relink:
        new_open = open_tag[:-1] + f' data-illo="{name}">'
        new_fig = new_open + "</figure>"
        abs_start = board_m.start() + chosen.start()
        abs_end = board_m.start() + chosen.end()
        new_inner = inner[:abs_start] + new_fig + inner[abs_end:]
        new_head = head[: m.start()] + m.group(1) + new_inner + m.group(3) + head[m.end():]
        src.write_text(new_head + tail, encoding="utf-8")
        print(f'relinked {title!r} to data-illo="{name}" in {src}')


def load_rows(path: Path):
    """Load rows from a CSV or JSON file, values coerced to strings."""
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            sys.exit(f"sheet.py: {path} must contain a JSON array of objects")
        rows = []
        for i, row in enumerate(data, 1):
            if not isinstance(row, dict):
                sys.exit(f"sheet.py: {path} row {i} is not a JSON object")
            rows.append({str(k): ("" if v is None else str(v)) for k, v in row.items()})
        return rows
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def materialize_template(open_tag: str, body: str, medium: str, rows: list, seen_titles: dict) -> str:
    """Build the materialised `data-row` boards for one template board."""
    fields = sorted({fm.group(3) for fm in FIELD_RE.finditer(body)})
    for fm in FIELD_RE.finditer(body):
        if "data-bind=" in fm.group(1):
            sys.exit(f"sheet.py: element has both data-field and data-bind: {fm.group(1)}")

    columns = set()
    for row in rows:
        columns |= set(row.keys())
    unknown = [f for f in fields if f not in columns]
    if unknown:
        sys.exit(
            f"sheet.py: template references unknown column(s) {', '.join(unknown)}; "
            f"available columns: {', '.join(sorted(columns)) or '(none)'}"
        )

    budgets = {"name": 24, "role": 32} if medium == "nametag" else {}
    for field in fields:
        longest_row = max(rows, key=lambda r: len(r.get(field, "")), default=None)
        if longest_row is None:
            continue
        val = longest_row.get(field, "")
        print(f"sheet.py: field {field!r}: longest value {val!r} ({len(val)} chars)")
        if field in budgets and len(val) > budgets[field]:
            print(
                f"sheet.py: WARNING field {field!r} exceeds the nametag budget of "
                f"{budgets[field]} characters (longest is {len(val)})"
            )

    def field_repl(row):
        def repl(fm):
            return fm.group(1) + html.escape(row.get(fm.group(3), "")) + fm.group(5)
        return repl

    def title_repl(row):
        def sub_col(cm):
            col = cm.group(1)
            if col not in columns:
                sys.exit(f"sheet.py: data-title references unknown column {{{col}}}")
            return row.get(col, "")
        def repl(tm):
            title = re.sub(r"\{([^{}]+)\}", sub_col, tm.group(1))
            n = seen_titles.get(title, 0) + 1
            seen_titles[title] = n
            if n > 1:
                title = f"{title} ({n})"
            return 'data-title="' + html.escape(title, quote=True) + '"'
        return repl

    out = []
    for n, row in enumerate(rows, 1):
        tag = re.sub(r'\s+data-template(="[^"]*")?', "", open_tag, count=1)
        tag = TITLE_ATTR_RE.sub(title_repl(row), tag, count=1)
        tag = tag[:-1] + f' data-row="{n}">'
        body_n = FIELD_RE.sub(field_repl(row), body)
        out.append(tag + body_n + "</section>")
    return "".join(out)


def materialize(head: str, rows: list) -> str:
    m = MAIN_RE.search(head)
    if not m:
        sys.exit('sheet.py: no <main class="sheet"> found')
    open_main, inner, close_main = m.group(1), m.group(2), m.group(3)

    # seed title de-duplication with titles already present (static boards, other templates)
    seen_titles = {}
    for bm in BOARD_RE.finditer(inner):
        tag = bm.group(0).split(">", 1)[0]
        tm = TITLE_ATTR_RE.search(tag)
        if tm and not re.search(r"\bdata-template\b", tag) and not re.search(r'\bdata-row="\d+"', tag):
            seen_titles[tm.group(1)] = seen_titles.get(tm.group(1), 0) + 1

    result = []
    cursor = 0
    found_template = False
    for bm in BOARD_RE.finditer(inner):
        result.append(inner[cursor:bm.start()])
        cursor = bm.end()
        board_html = bm.group(0)
        open_tag = board_html[: board_html.index(">") + 1]
        if re.search(r"\bdata-template\b", open_tag):
            found_template = True
            body = board_html[len(open_tag): -len("</section>")]
            medium_m = re.search(r'\bdata-medium="([^"]*)"', open_tag)
            medium = medium_m.group(1) if medium_m else ""
            result.append(board_html)
            result.append(materialize_template(open_tag, body, medium, rows, seen_titles))
        elif re.search(r'\bdata-row="\d+"', open_tag):
            continue  # drop a stale materialised row board; it is regenerated above
        else:
            result.append(board_html)
    result.append(inner[cursor:])
    if not found_template:
        sys.exit('sheet.py: --rows given but no board has data-template')

    return head[: m.start()] + open_main + "".join(result) + close_main + head[m.end():]


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def inline_css_urls(css: str, base: Path) -> str:
    def repl(m):
        url = m.group(2)
        if url.startswith(("data:", "#", "http:", "https:")):
            return m.group(0)
        target = (base / url).resolve()
        if not target.exists():
            sys.exit(f"sheet.py: {url} (from {base}) does not exist")
        return f'url("{data_uri(target)}")'
    return re.sub(r"url\(\s*(['\"]?)(.*?)\1\s*\)", repl, css)


def role_for(href: str) -> str:
    name = Path(href).name
    if name.startswith("runtime"):
        return "runtime"
    if "/brand/" in "/" + href or href.startswith("brand/"):
        return "brand"
    if "/media/" in "/" + href or href.startswith("media/"):
        return "media"
    return "custom"


def prefer_min(path: Path) -> Path:
    if ".min." in path.name:
        return path
    m = path.with_name(path.stem + ".min" + path.suffix)
    return m if m.exists() and m.stat().st_mtime >= path.stat().st_mtime else path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheet")
    ap.add_argument("-o", "--out", help="required unless --snapshot or --diff")
    ap.add_argument("--brand", help="brand stylesheet to use instead of the one the sheet links")
    ap.add_argument("--no-min", action="store_true", help="inline runtime.css/js even if .min files exist")
    ap.add_argument("--rows", help="CSV or JSON file of rows to materialise a data-template board against")
    ap.add_argument("--snapshot", action="store_true", help="write a per-board content/attribute snapshot next to the sheet")
    ap.add_argument("--diff", action="store_true", help="compare the sheet to its last --snapshot; non-zero on out-of-scope drift")
    ap.add_argument("--allow", help="--diff: comma-separated data-title list allowed to change or be added")
    ap.add_argument("--allow-attr", help="--diff: comma-separated protected attribute names allowed to change")
    ap.add_argument("--promote-illo", metavar="TITLE", help="data-title of the board carrying the authored figure.illo to promote into the brand library")
    ap.add_argument("--name", help="--promote-illo: kebab-case name for the promoted illustration")
    ap.add_argument("--index", type=int, help="--promote-illo: 1-based figure.illo position on the board, when it has several")
    ap.add_argument("--force", action="store_true", help="--promote-illo: overwrite an existing illustration/token/library entry of the same name")
    ap.add_argument("--relink", action="store_true", help="--promote-illo: also replace the board's inline svg with data-illo=\"<name>\"")
    args = ap.parse_args()

    src = Path(args.sheet).resolve()

    if args.snapshot:
        cmd_snapshot(src)
        return
    if args.diff:
        cmd_diff(src, args.allow, args.allow_attr)
        return
    if args.promote_illo:
        if not args.name:
            ap.error("--name is required with --promote-illo")
        cmd_promote_illo(src, args.promote_illo, args.name, args.brand, args.index, args.force, args.relink)
        return
    if not args.out:
        ap.error("-o/--out is required unless --snapshot, --diff or --promote-illo is given")

    doc = src.read_text(encoding="utf-8")
    at = doc.find(MARKER)
    if at < 0:
        sys.exit(f"sheet.py: no '{MARKER}' marker in {src}")
    head, tail = doc[:at], doc[at:]
    check_hard_rules(head, src)

    if args.rows:
        rows = load_rows(Path(args.rows))
        head = materialize(head, rows)

    # relative images in the markup
    def img(m):
        url = m.group(2)
        if url.startswith(("data:", "http:", "https:")):
            return m.group(0)
        return f'{m.group(1)}"{data_uri((src.parent / url).resolve())}"'
    head = re.sub(r'(<img\b[^>]*?\bsrc=)["\']([^"\']+)["\']', img, head)

    parts = {"runtime": [], "media": [], "brand": [], "custom": []}
    scripts = {"runtime": [], "custom": []}

    for m in re.finditer(r'<link\b[^>]*\brel=["\']stylesheet["\'][^>]*>', tail):
        href = re.search(r'\bhref=["\']([^"\']+)["\']', m.group(0)).group(1)
        role = role_for(href)
        path = (src.parent / href).resolve()
        if role == "brand" and args.brand:
            path = Path(args.brand).resolve()
        if role == "runtime" and not args.no_min:
            path = prefer_min(path)
        parts[role].append(inline_css_urls(path.read_text(encoding="utf-8"), path.parent))
    for m in re.finditer(r'<style\b([^>]*)>(.*?)</style>', tail, re.S):
        role = re.search(r'data-(runtime|media|brand|custom)', m.group(1))
        parts[role.group(1) if role else "custom"].append(inline_css_urls(m.group(2), src.parent))

    for m in re.finditer(r'<script\b([^>]*)>(.*?)</script>', tail, re.S):
        s = re.search(r'\bsrc=["\']([^"\']+)["\']', m.group(1))
        if s:
            path = (src.parent / s.group(1)).resolve()
            role = "runtime" if path.name.startswith("runtime") else "custom"
            if role == "runtime" and not args.no_min:
                path = prefer_min(path)
            code = path.read_text(encoding="utf-8")
        else:
            role = "runtime" if "data-runtime" in m.group(1) else "custom"
            code = m.group(2)
        scripts[role].append(code)

    if not parts["runtime"] or not scripts["runtime"]:
        sys.exit("sheet.py: the sheet links no runtime.css / runtime.js after the marker")
    if not parts["brand"]:
        if not args.brand:
            sys.exit("sheet.py: no brand stylesheet; pass --brand brand/<name>.css")
        b = Path(args.brand).resolve()
        parts["brand"].append(inline_css_urls(b.read_text(encoding="utf-8"), b.parent))

    out = [head.rstrip() + "\n", "<!-- makeitbrand:runtime — generated below this line, never edit by hand -->\n"]
    for role in ("runtime", "media", "brand", "custom"):
        if parts[role]:
            css = "\n".join(parts[role])
            if "</style" in css:
                sys.exit(f"sheet.py: {role} CSS contains '</style'")
            out.append(f"<style data-{role}>{css}</style>\n")
    for role in ("runtime", "custom"):
        if scripts[role]:
            js = "\n".join(scripts[role])
            if "</script" in js:
                sys.exit(f"sheet.py: {role} JS contains '</script'")
            out.append(f"<script data-{role}>{js}</script>\n")
    out.append("</body>\n</html>\n")

    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(out), encoding="utf-8")
    print(f"{dest}  {dest.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
