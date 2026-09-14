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
    args = ap.parse_args()

    src = Path(args.sheet).resolve()

    if args.snapshot:
        cmd_snapshot(src)
        return
    if args.diff:
        cmd_diff(src, args.allow, args.allow_attr)
        return
    if not args.out:
        ap.error("-o/--out is required unless --snapshot or --diff is given")

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
