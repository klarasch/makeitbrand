#!/usr/bin/env python3
"""makeitbrand kit.py — upstream-owned, replaced whole on update. Stdlib only.

The brand beyond boards (PAGES.md): everything that isn't a fixed-size graphic — a dashboard
artifact, an internal site, a report page, a one-off document — built from the same tokens the
sheets use, so a page and a graphic read as one brand.

    python3 kit.py css   -o brand-kit.css                # the brand as a self-contained stylesheet
    python3 kit.py guide -o "Acme brand guide.html"      # a visual brand guide page, built on the kit
    python3 kit.py lint  page.html                       # off-brand colours, fonts, gradients
    python3 kit.py shot  page.html -o work/png/          # screenshots: desktop, phone, dark

css — one stylesheet: the brand's @font-face rules and logos as data: URIs, every token from
brand/<name>.css (library illustrations and icons left out: they are big and pages pick a few),
derived page roles (--page-bg, --page-fg, … — what a page paints with), a screen type scale
(--text-caption … --text-display at k = 1), spacing and shape (--gap-xs … --gap-xl, --r, --line),
a zero-specificity base layer for plain elements, and a small set of `mb-` components that mirror
the board primitives (eyebrow, card, tile, stat, chip, band, logo, inverse and hero sections).

A light brand (--bg-tone: light) also gets a dark scheme: the brand's own inverse ground (the
same one the runtime paints `data-ground="inverse"` boards with, and the brand's
`.board[data-g="inverse"]` overrides), under `prefers-color-scheme: dark` guarded by
`:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`. A dark brand
commits to its one look. `--scheme light` or `--scheme dark` forces a single look.

The kit is wrapped in `/* brand kit:start … */` … `/* brand kit:end */`; lint skips that span.

guide — a standalone HTML page that shows the brand: logo on its grounds, colour roles with
contrast ratios, type scale, chart palette (light and dark), shape, components, icons,
illustrations, and the brand file's voice, surfaces and adaptation rules.

lint — reads a page (or artifact source) and exits non-zero on: no kit; a colour literal (hex,
rgb/hsl/oklch…, named colours) in CSS, style=, SVG paint attributes or scripts; a font-family that
isn't a --font-* token; an @font-face, @import or font <link> of its own. Warns on literal px font
sizes and gradients other than var(--art).

shot — headless Chrome screenshots of a page at 1440 px and 400 px wide, plus 1440 px in the dark
scheme (a temporary copy with data-theme="dark" on <html>). Reuses export.py's capture.
"""
import argparse
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from sheet import data_uri, inline_css_urls, resolve_brand  # noqa: E402

KIT_START = "/* brand kit:start"
KIT_END = "/* brand kit:end */"

# screen type scale, same steps as PRIMITIVES.md §3 at k = 1
STEPS = [("caption", -1), ("body", 0), ("lead", 1), ("h3", 2), ("h2", 3), ("h1", 4), ("display", 6)]
GAPS = [("xs", .5), ("sm", 1), ("md", 2), ("lg", 3), ("xl", 5), ("2xl", 8)]


# ---------------------------------------------------------------- brand css parsing
def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def rules(css: str):
    """Top-level (selector, body) pairs; @font-face comes through with its selector."""
    out, i, n = [], 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        sel = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        out.append((sel, css[j + 1:k - 1]))
        i = k
    return out


def declarations(body: str):
    """[(prop, value)] split on ; outside parentheses and quotes."""
    out, buf, depth, quote = [], [], 0, None
    for ch in body:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == ";" and depth == 0:
            out.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    out.append("".join(buf))
    decls = []
    for d in out:
        if ":" in d and d.strip():
            p, v = d.split(":", 1)
            decls.append((p.strip(), " ".join(v.split())))
    return decls


class Brand:
    def __init__(self, brand_arg):
        if brand_arg and brand_arg.endswith(".css") and Path(brand_arg).exists():
            self.css_path = Path(brand_arg).resolve()
            self.name, self.md_path = self.css_path.stem, self.css_path.with_suffix(".md")
            if not self.md_path.exists():
                sys.exit(f"kit.py: no {self.md_path}")
        else:
            self.name, self.css_path, self.md_path = resolve_brand(ROOT, brand_arg)
        raw = strip_comments(self.css_path.read_text(encoding="utf-8"))
        self.font_faces, self.root, self.dark = [], {}, {}
        for sel, body in rules(raw):
            if sel.startswith("@font-face"):
                self.font_faces.append(body)
            elif re.fullmatch(r":root", sel):
                self.root.update(declarations(body))
            elif any(re.search(r'\[data-g(?:round)?="inverse"\]', s) for s in sel.split(",")):
                self.dark.update(declarations(body))
        self.md = self.md_path.read_text(encoding="utf-8")
        self.tone = self.root.get("--bg-tone", "light").strip()
        self.art_ink = self.root.get("--art-ink", "bg").strip()

    def px(self, prop, default):
        m = re.match(r"([\d.]+)px", self.root.get(prop, ""))
        return float(m.group(1)) if m else default

    def num(self, prop, default):
        try:
            return float(self.root.get(prop, default))
        except ValueError:
            return default

    def logo_ratio(self, token="--logo-dark"):
        m = re.search(r'url\(\s*["\']?([^"\')]+)', self.root.get(token, ""))
        if not m or m.group(1).startswith("data:"):
            return 4.0
        p = (self.css_path.parent / m.group(1)).resolve()
        if not p.exists() or p.suffix != ".svg":
            return 4.0
        vb = re.search(r'viewBox="\s*[\d.-]+[\s,]+[\d.-]+[\s,]+([\d.]+)[\s,]+([\d.]+)', p.read_text(encoding="utf-8"))
        return round(float(vb.group(1)) / float(vb.group(2)), 4) if vb else 4.0

    def asset_svgs(self, folder, only=None):
        d = self.css_path.parent / "assets" / folder
        if not d.is_dir():
            return []
        out = []
        for p in sorted(d.glob("*.svg")):
            if only is not None and p.stem not in only:
                continue
            svg = p.read_text(encoding="utf-8")
            svg = re.sub(r"<\?xml.*?\?>", "", svg).strip()
            out.append((p.stem, svg))
        return out

    def library_illos(self):
        return [k[len("--illo-"):] for k in self.root if re.match(r"--illo-(?!\d$)", k)]

    def icons(self):
        icons_css = self.css_path.parent / "icons.css"
        if not icons_css.exists():
            return []
        names = re.findall(r"--icon-([\w-]+)\s*:", icons_css.read_text(encoding="utf-8"))
        return self.asset_svgs("icons", set(names))


# ---------------------------------------------------------------- css kit
def is_library_token(prop):
    return re.match(r"--illo-(?!\d$)", prop) or prop.startswith("--icon-")


def decl_block(pairs, indent="  "):
    return "\n".join(f"{indent}{p}: {v};" for p, v in pairs)


def dark_roles(tone="light"):
    """The brand's inverse ground as page roles. For a dark brand that ground is light."""
    return [
        ("color-scheme", "dark"),
        ("--page-bg", "var(--inverse-bg, var(--fg))"),
        ("--page-fg", "var(--bg)"),
        ("--page-muted", "color-mix(in srgb, var(--bg) 64%, transparent)"),
        ("--page-faint", "color-mix(in srgb, var(--bg) 18%, transparent)"),
        ("--page-surface", "color-mix(in srgb, var(--bg) 7%, var(--inverse-bg, var(--fg)))"),
        ("--page-fill", "color-mix(in srgb, var(--bg) 9%, transparent)"),
        ("--page-accent", "var(--accent)"),
        ("--page-accent-fg", "var(--accent-fg)"),
        ("--page-logo", "var(--logo-dark)" if tone == "dark" else "var(--logo-light)"),
    ]


def light_roles(tone):
    if tone == "dark":
        return [
            ("color-scheme", "dark"),
            ("--page-bg", "var(--bg)"), ("--page-fg", "var(--fg)"), ("--page-muted", "var(--muted)"),
            ("--page-faint", "var(--faint)"), ("--page-surface", "var(--surface)"),
            ("--page-fill", "var(--surface)"), ("--page-accent", "var(--accent)"),
            ("--page-accent-fg", "var(--accent-fg)"), ("--page-logo", "var(--logo-light)"),
        ]
    return [
        ("color-scheme", "light"),
        ("--page-bg", "var(--bg)"), ("--page-fg", "var(--fg)"), ("--page-muted", "var(--muted)"),
        ("--page-faint", "var(--faint)"), ("--page-surface", "var(--surface)"),
        ("--page-fill", "var(--surface)"), ("--page-accent", "var(--accent)"),
        ("--page-accent-fg", "var(--accent-fg)"), ("--page-logo", "var(--logo-dark)"),
    ]


def build_css(b: Brand, scheme: str) -> str:
    base, scale, space = b.px("--base", 16), b.num("--scale", 1.25), b.px("--space", 8)
    root = [(p, v) for p, v in b.root.items() if not is_library_token(p)]
    # tokens that point at other tokens resolve where declared (BRANDING.md §4c): re-declare them
    # wherever the dark overrides land, so --illo-1: var(--accent) follows the dark accent
    relative = [(p, v) for p, v in root if "var(" in v and p not in b.dark]
    derived = [(f"--text-{n}", f"{round(base * scale ** s, 2)}px") for n, s in STEPS]
    derived += [(f"--gap-{n}", f"{round(space * f, 2)}px") for n, f in GAPS]
    derived += [("--r", "var(--radius)"), ("--line", "var(--stroke)"),
                ("--logo-ratio", str(b.logo_ratio()))]

    look = scheme if scheme != "auto" else ("dark" if b.tone == "dark" else "both")
    head = light_roles("dark" if look == "dark" else "light")
    dark_decls = list(b.dark.items()) + relative + dark_roles(b.tone)
    if look == "dark" and b.tone != "dark":
        head = dark_decls  # a light brand forced dark: the inverse ground everywhere

    out = [f"{KIT_START}: {b.name} — generated by makeitbrand kit.py from brand/{b.name}.css. Regenerate, never edit. */"]
    for face in b.font_faces:
        out.append("@font-face {\n" + decl_block(declarations(face)) + "\n}")
    out.append(":root {\n" + decl_block(root) + "\n\n" + decl_block(derived) + "\n\n" + decl_block(head) + "\n}")
    if look == "both":
        blk = decl_block(dark_decls, "    ")
        out.append('@media (prefers-color-scheme: dark) {\n  :root:not([data-theme="light"]) {\n' + blk + "\n  }\n}")
        out.append(':root[data-theme="dark"] {\n' + decl_block(dark_decls) + "\n}")
    inverse_sel = ".mb-inverse" + (", .mb-hero" if b.art_ink == "inverse" else "")
    out.append(inverse_sel + " {\n" + decl_block([d for d in dark_decls if d[0] != "color-scheme"]) + "\n}")
    if b.art_ink != "inverse" and b.tone != "dark":
        out.append(".mb-hero {\n" + decl_block(light_roles("light")[1:]) + "\n}")
    out.append(BASE_CSS)
    out.append(KIT_END)
    return inline_css_urls("\n\n".join(out), b.css_path.parent) + "\n"


BASE_CSS = r"""/* base: zero specificity, any page style wins */
:where(html) { background: var(--page-bg); }
:where(body) {
  margin: 0; background: var(--page-bg); color: var(--page-fg);
  font-family: var(--font-body); font-size: var(--text-body); line-height: 1.5;
  -webkit-font-smoothing: antialiased; font-kerning: normal;
}
:where(h1, h2, h3, h4) {
  margin: 0; font-family: var(--font-display); color: var(--page-fg);
  font-weight: var(--weight-display, 650); text-wrap: balance;
}
:where(h1) { font-size: var(--text-h1); line-height: 1.04; letter-spacing: calc(-.025em * var(--tracking, 1)); }
:where(h2) { font-size: var(--text-h2); line-height: 1.1; letter-spacing: calc(-.02em * var(--tracking, 1)); }
:where(h3) { font-size: var(--text-h3); line-height: 1.15; letter-spacing: calc(-.01em * var(--tracking, 1)); font-weight: var(--weight-heading, 600); }
:where(h4) { font-size: var(--text-lead); line-height: 1.3; font-weight: var(--weight-heading, 600); }
:where(h1, h2, h3) :where(strong) { color: var(--page-accent); font-weight: inherit; }
:where(p, ul, ol, figure, blockquote) { margin: 0; }
:where(p) { text-wrap: pretty; }
:where(a) { color: var(--page-accent); text-decoration-thickness: max(1px, var(--line)); text-underline-offset: .2em; }
:where(small) { font-size: var(--text-caption); }
:where(code, kbd, pre, samp) { font-family: var(--font-mono); font-size: .9em; }
:where(hr) { border: 0; border-top: max(1px, calc(var(--line) * .7)) solid var(--page-faint); margin: 0; }
:where(table) { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
:where(th) {
  text-align: left; font-family: var(--font-caption, var(--font-mono)); font-size: var(--text-caption);
  font-weight: 500; color: var(--page-muted); padding: 0 var(--gap-md) var(--gap-sm) 0;
  border-bottom: max(1px, calc(var(--line) * .7)) solid var(--page-faint);
}
:where(td) { padding: var(--gap-sm) var(--gap-md) var(--gap-sm) 0; border-bottom: max(1px, calc(var(--line) * .7)) solid var(--page-faint); }
:where(button, input, select, textarea) { font: inherit; color: inherit; }
:where(:focus-visible) { outline: calc(var(--line) * 1.5) solid var(--page-accent); outline-offset: 2px; }
:where(::selection) { background: color-mix(in srgb, var(--page-accent) 24%, transparent); }

/* components — the board primitives, at page size (PAGES.md §4) */
.mb-eyebrow {
  font-family: var(--font-eyebrow, var(--font-caption, var(--font-mono))); font-size: var(--text-caption);
  line-height: 1.3; font-weight: 500; text-transform: uppercase;
  letter-spacing: var(--tracking-eyebrow, .08em); color: var(--page-accent);
}
.mb-eyebrow[data-rule] { display: flex; align-items: center; gap: var(--gap-md); }
.mb-eyebrow[data-rule]::after { content: ""; flex: 1 1 0; height: max(1px, calc(var(--line) * .7)); background: var(--page-faint); }
.mb-display {
  font-family: var(--font-display); font-weight: var(--weight-display, 650); font-size: var(--text-display);
  line-height: 1; letter-spacing: calc(-.03em * var(--tracking, 1)); text-wrap: balance; color: var(--page-fg);
}
.mb-lead { font-size: var(--text-lead); line-height: 1.35; color: var(--page-muted); text-wrap: pretty; }
.mb-muted { color: var(--page-muted); }
.mb-caption { font-family: var(--font-caption, var(--font-mono)); font-size: var(--text-caption); line-height: 1.3; color: var(--page-muted); }
.mb-card, .mb-tile {
  display: flex; flex-direction: column; gap: var(--gap-sm); min-width: 0;
  padding: var(--gap-lg); background: var(--page-fill); color: var(--page-fg);
  border: var(--line) solid transparent; border-radius: var(--r);
}
.mb-card[data-tone="outline"] { background: transparent; border-color: var(--page-faint); }
.mb-card[data-tone="accent"], .mb-tile[data-tone="accent"] {
  background: var(--page-accent); color: var(--page-accent-fg); --page-fg: var(--page-accent-fg);
  --page-muted: color-mix(in srgb, var(--page-accent-fg) 78%, transparent);
  --page-faint: color-mix(in srgb, var(--page-accent-fg) 28%, transparent);
}
.mb-card[data-tone="glass"], .mb-tile[data-tone="glass"] {
  background: color-mix(in srgb, var(--page-fg) 6%, transparent);
  border-color: color-mix(in srgb, var(--page-fg) 16%, transparent);
}
.mb-tile { gap: var(--gap-xs); }
.mb-tile__label { font-family: var(--font-caption, var(--font-mono)); font-size: var(--text-caption); color: var(--page-muted); margin-bottom: var(--gap-sm); }
.mb-tile__value {
  font-family: var(--font-display); font-weight: var(--weight-display, 650); font-size: var(--text-h1);
  line-height: 1; letter-spacing: -.025em; font-variant-numeric: tabular-nums; white-space: nowrap; margin-top: auto;
}
.mb-tile__delta { font-size: var(--text-caption); font-weight: 550; color: var(--page-muted); }
.mb-tile__delta:is([data-trend="up"][data-good="up"], [data-trend="down"][data-good="down"]) { color: var(--good); }
.mb-tile__delta:is([data-trend="up"][data-good="down"], [data-trend="down"][data-good="up"]) { color: var(--bad); }
.mb-tile__delta[data-trend="up"]::before { content: "\2191\00a0"; }
.mb-tile__delta[data-trend="down"]::before { content: "\2193\00a0"; }
.mb-stat {
  font-family: var(--font-display); font-weight: var(--weight-heading, 600); color: var(--page-accent);
  font-size: var(--text-display); line-height: .95; letter-spacing: calc(-.035em * var(--tracking, 1));
  font-variant-numeric: tabular-nums; white-space: nowrap;
}
.mb-chip {
  display: inline-flex; align-items: center; padding: .32em .85em; white-space: nowrap;
  font-family: var(--font-caption, var(--font-mono)); font-size: var(--text-caption); line-height: 1.3;
  border: var(--line) solid var(--page-faint); border-radius: 999px; color: var(--page-fg);
}
.mb-list { list-style: none; padding: 0; display: flex; flex-direction: column; gap: var(--gap-sm); color: var(--page-muted); }
.mb-list > li { position: relative; padding-left: 1.3em; }
.mb-list > li::before { content: ""; position: absolute; left: .1em; top: .72em; width: .55em; height: var(--line); background: var(--page-accent); }
.mb-logo {
  display: block; flex: 0 0 auto; height: max(var(--logo-h, 28px), var(--logo-min, 20px));
  aspect-ratio: var(--logo-ratio); background: var(--page-logo) left center / contain no-repeat;
}
.mb-icon { display: inline-flex; width: 1em; height: 1em; vertical-align: -.14em; flex: 0 0 auto; }
.mb-icon > svg { width: 100%; height: 100%; display: block; overflow: visible; }
.mb-band { background: var(--band, color-mix(in srgb, var(--page-fg) 6%, transparent)); color: var(--page-fg); }
.mb-inverse, .mb-hero { background: var(--page-bg); color: var(--page-fg); }
.mb-hero { background: var(--art, var(--page-bg)); }
"""


# ---------------------------------------------------------------- colour maths (guide)
def parse_color(v):
    v = (v or "").strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (1.0,)
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+%?))?\s*\)", v)
    if m:
        a = m.group(4)
        a = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
        return (float(m.group(1)), float(m.group(2)), float(m.group(3)), a)
    return None


def over(c, ground):
    a = c[3]
    return tuple(c[i] * a + ground[i] * (1 - a) for i in range(3)) + (1.0,)


def lum(c):
    def ch(x):
        x /= 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def contrast(fg, bg):
    if not fg or not bg:
        return None
    fg = over(fg, bg)
    hi, lo = sorted((lum(fg), lum(bg)), reverse=True)
    return round((hi + 0.05) / (lo + 0.05), 1)


# ---------------------------------------------------------------- tiny markdown (guide)
def md_inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s


def md_sections(md):
    """{heading: body} for every ## section."""
    out, cur = {}, None
    for line in md.splitlines():
        m = re.match(r"##\s+(.*)", line)
        if m:
            cur = m.group(1).strip()
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def md_blocks(text):
    items, paras, buf, mode = [], [], [], None
    html_out = []

    def flush():
        nonlocal buf, mode
        if buf:
            joined = " ".join(x.strip() for x in buf)
            html_out.append(("li" if mode == "li" else "p", md_inline(joined)))
        buf, mode = [], None

    for line in text.splitlines():
        if not line.strip():
            flush()
        elif re.match(r"\s*[-*]\s+", line) and not line.startswith("  "):
            flush()
            mode = "li"
            buf = [re.sub(r"^\s*[-*]\s+", "", line)]
        else:
            if mode is None:
                mode = "p"
            buf.append(line)
    flush()
    res, in_list = [], False
    for tag, body in html_out:
        if tag == "li" and not in_list:
            res.append('<ul class="mb-list">')
            in_list = True
        if tag != "li" and in_list:
            res.append("</ul>")
            in_list = False
        res.append(f"<{tag}>{body}</{tag}>")
    if in_list:
        res.append("</ul>")
    return "\n".join(res)


# ---------------------------------------------------------------- guide page
GUIDE_CSS = r"""
.g { max-width: 1200px; margin: 0 auto; padding-inline: var(--gap-lg); padding-block: var(--gap-xl) calc(var(--gap-2xl) * 2); display: flex; flex-direction: column; gap: calc(var(--gap-2xl) * 1.25); }
.g-top { display: flex; justify-content: space-between; align-items: center; gap: var(--gap-md); padding-block-end: var(--gap-lg); border-bottom: max(1px, calc(var(--line) * .7)) solid var(--page-faint); }
.g-hero { border-radius: calc(var(--r) * 1.5); padding: calc(var(--gap-xl) * 1.4) var(--gap-xl); display: flex; flex-direction: column; gap: var(--gap-md); min-height: 320px; justify-content: flex-end; }
.g-hero .mb-logo { --logo-h: 32px; margin-bottom: auto; }
.g-hero .mb-lead { max-width: 46ch; }
.g-sec { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 3fr); gap: var(--gap-lg) var(--gap-xl); }
.g-sec > header { display: flex; flex-direction: column; gap: var(--gap-sm); }
.g-sec > header p { color: var(--page-muted); font-size: var(--text-caption); line-height: 1.5; max-width: 32ch; }
.g-body { display: flex; flex-direction: column; gap: var(--gap-lg); min-width: 0; }
.g-grid { display: grid; gap: var(--gap-md); grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); }
.g-sw { display: flex; flex-direction: column; gap: var(--gap-sm); min-width: 0; }
.g-sw__chip { height: 96px; border-radius: var(--r); border: max(1px, calc(var(--line) * .7)) solid var(--page-faint); display: flex; align-items: flex-end; justify-content: space-between; padding: var(--gap-sm) var(--gap-sm); font-size: var(--text-caption); font-weight: 550; }
.g-sw__name { font-weight: 600; font-size: var(--text-caption); }
.g-sw__meta { font-family: var(--font-caption, var(--font-mono)); font-size: var(--text-caption); color: var(--page-muted); line-height: 1.4; overflow-wrap: anywhere; }
.g-type { display: flex; flex-direction: column; }
.g-type__row { display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: var(--gap-md); align-items: baseline; padding-block: var(--gap-md); border-bottom: max(1px, calc(var(--line) * .7)) solid var(--page-faint); }
.g-type__row > :last-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.g-fam { display: grid; gap: var(--gap-md); grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.g-fam .mb-card { gap: var(--gap-xs); }
.g-fam__glyph { font-size: var(--text-h1); line-height: 1.1; }
.g-bars { display: flex; height: 64px; border-radius: var(--r); overflow: hidden; }
.g-bars > div { flex: 1 1 0; display: flex; align-items: flex-end; padding: var(--gap-xs) var(--gap-sm); font-family: var(--font-caption, var(--font-mono)); font-size: var(--text-caption); color: var(--page-bg); font-weight: 600; }
.g-ramp { height: 28px; border-radius: var(--r); }
.g-duo { display: grid; gap: var(--gap-md); grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
.g-duo > * { padding: var(--gap-lg); border-radius: var(--r); display: flex; flex-direction: column; gap: var(--gap-md); }
.g-shape { display: flex; flex-wrap: wrap; gap: var(--gap-lg); align-items: flex-end; }
.g-space { display: flex; flex-direction: column; align-items: flex-start; gap: var(--gap-xs); }
.g-space > div { background: var(--page-accent); height: 16px; border-radius: 2px; }
.g-comp { display: grid; gap: var(--gap-md); grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
.g-logos { display: grid; gap: var(--gap-md); grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
.g-logos > div { height: 150px; border-radius: var(--r); display: flex; flex-direction: column; justify-content: space-between; padding: var(--gap-md); border: max(1px, calc(var(--line) * .7)) solid var(--page-faint); }
.g-logos .mb-logo { --logo-h: 36px; align-self: center; margin-block: auto; }
.g-icons { display: grid; gap: var(--gap-xs); grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); }
.g-icons > div { display: flex; flex-direction: column; align-items: center; gap: var(--gap-sm); padding: var(--gap-md) var(--gap-xs); border-radius: var(--r); background: var(--page-fill); }
.g-icons .mb-icon { font-size: 24px; color: var(--page-fg); }
.g-icons span { font-family: var(--font-caption, var(--font-mono)); font-size: 11px; color: var(--page-muted); text-align: center; overflow-wrap: anywhere; }
.g-illos { display: grid; gap: var(--gap-md); grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); }
.g-illos .mb-card { align-items: center; }
.g-illos svg { width: 100%; height: 150px; color: var(--page-fg); overflow: visible; }
.g-rules { display: grid; gap: var(--gap-md); grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
.g-rules .mb-card { gap: var(--gap-md); }
.g-rules .mb-list { font-size: 15px; line-height: 1.5; }
.g-rules p { color: var(--page-muted); font-size: 15px; line-height: 1.55; }
.g-rules code, .g-prose code { font-size: .86em; padding: .05em .3em; border-radius: 4px; background: color-mix(in srgb, var(--page-fg) 7%, transparent); color: var(--page-fg); }
.g-prose { display: flex; flex-direction: column; gap: var(--gap-sm); color: var(--page-muted); max-width: 72ch; }
.g-foot { color: var(--page-muted); font-size: var(--text-caption); }
@media (max-width: 760px) {
  .g-sec { grid-template-columns: minmax(0, 1fr); }
  .g-hero { padding: var(--gap-lg); min-height: 260px; }
  .g-type__row { grid-template-columns: minmax(0, 1fr); gap: var(--gap-xs); }
}
"""


def build_guide(b: Brand) -> str:
    # a reference document commits to the light look and shows the dark grounds explicitly, so a
    # swatch never changes colour under the viewer's theme
    kit = build_css(b, "light" if b.tone == "light" else "auto")
    r = b.root
    h1 = re.match(r"#\s+(.+)", b.md)
    title = re.split(r"\s+[—-]\s+", h1.group(1))[0].strip() if h1 else b.name.capitalize()
    intro = ""
    secs = md_sections(b.md)

    bg = parse_color(r.get("--bg"))
    inv = parse_color(r.get("--inverse-bg")) or parse_color(r.get("--fg"))

    def swatch(name, token, value, ground, text_token=None, note=""):
        col = parse_color(value)
        ratio = contrast(col, ground) if col and ground else None
        fg_css = f"var({text_token})" if text_token else "transparent"
        label = "Aa" if text_token else ""
        meta = html.escape(value)
        if ratio:
            meta += f"<br>{ratio}:1 {note}"
        return (f'<div class="g-sw"><div class="g-sw__chip" style="background:var({token});color:{fg_css}">'
                f'<span>{label}</span></div><div class="g-sw__name">{html.escape(name)} '
                f'<span class="mb-caption">{token}</span></div><div class="g-sw__meta">{meta}</div></div>')

    colour = [
        swatch("Ground", "--bg", r.get("--bg", ""), None, "--fg"),
        swatch("Surface", "--surface", r.get("--surface", ""), None, "--fg"),
        swatch("Ink", "--fg", r.get("--fg", ""), bg, None, "on ground"),
        swatch("Muted ink", "--muted", r.get("--muted", ""), bg, None, "on ground"),
        swatch("Hairline", "--faint", r.get("--faint", ""), None),
        swatch("Accent", "--accent", r.get("--accent", ""), bg, "--accent-fg", "on ground"),
        swatch("Accent 2", "--accent-2", r.get("--accent-2", ""), None, None),
    ]
    acc, accfg = parse_color(r.get("--accent")), parse_color(r.get("--accent-fg"))
    if acc and accfg:
        colour[5] = colour[5].replace("on ground", f"on ground · text on it {contrast(accfg, acc)}:1")
    if b.tone == "light":
        colour.append(swatch("Inverse ground", "--inverse-bg" if "--inverse-bg" in r else "--fg",
                             r.get("--inverse-bg", r.get("--fg", "")), None, "--bg"))

    # dark overrides shown on the inverse ground
    dark_accent = b.dark.get("--accent")
    dark_note = ""
    if dark_accent:
        ratio = contrast(parse_color(dark_accent), inv)
        dark_note = (f'<p class="mb-caption">On dark grounds the accent becomes <code>{html.escape(dark_accent)}</code>'
                     + (f", {ratio}:1 on the inverse ground" if ratio else "") + ".</p>")

    type_rows = []
    base, scale = b.px("--base", 16), b.num("--scale", 1.25)
    samples = {"display": "Brand at a glance", "h1": "Headlines are claims", "h2": "Section heading",
               "h3": "Card heading", "lead": "A lead sentence sets up the page in plain words.",
               "body": "Body copy carries the detail. It stays short, in the brand's voice, and never shrinks to fit.",
               "caption": "Caption, source, chart label"}
    for n, s in reversed(STEPS):
        px = round(base * scale ** s)
        if n == "display":
            sample = f'<div class="mb-display">{samples[n]}</div>'
        elif n in ("h1", "h2", "h3"):
            sample = f"<{n}>{samples[n]}</{n}>"
        elif n == "lead":
            sample = f'<div class="mb-lead">{samples[n]}</div>'
        elif n == "caption":
            sample = f'<div class="mb-caption">{samples[n]}</div>'
        else:
            sample = f"<p>{samples[n]}</p>"
        type_rows.append(f'<div class="g-type__row"><div class="mb-caption">--text-{n}<br>{px} px</div>{sample}</div>')
    fams = []
    seen = set()
    for label, tok in [("Display", "--font-display"), ("Body", "--font-body"), ("Captions", "--font-caption"), ("Mono", "--font-mono")]:
        v = r.get(tok)
        if not v or v in seen:
            continue
        seen.add(v)
        fam = v.split(",")[0].strip().strip("\"'")
        weight = r.get("--weight-display", "650") if label == "Display" else "400"
        fams.append(f'<div class="mb-card"><div class="mb-caption">{label} <code>{tok}</code></div>'
                    f'<div class="g-fam__glyph" style="font-family:var({tok});font-weight:{weight}">Aa Gg 0123</div>'
                    f'<div class="g-sw__meta">{html.escape(fam)}</div></div>')

    charts_light = "".join(f'<div style="background:var(--chart-{i})">{i}</div>' for i in range(1, 7))
    chart_section = f'''<div class="g-duo">
  <div class="mb-card" style="background:var(--bg)"><div class="mb-caption">On light · in this order, never cycled</div>
    <div class="g-bars">{charts_light}</div>
    <div class="g-ramp" style="background:linear-gradient(90deg,var(--chart-seq-0),var(--chart-seq-1))"></div>
    <div class="mb-caption">Sequential <code>--chart-seq-0</code> → <code>--chart-seq-1</code> · highlight <code>--chart-accent</code></div>
  </div>'''
    if any(k.startswith("--chart-") for k in b.dark) and b.tone == "light":
        chart_section += f'''
  <div class="mb-inverse"><div class="mb-caption">On dark grounds</div>
    <div class="g-bars">{charts_light}</div>
    <div class="row"><span class="mb-chip" style="color:var(--good)">Better <code>--good</code></span> <span class="mb-chip" style="color:var(--bad)">Worse <code>--bad</code></span></div>
  </div>'''
    else:
        chart_section += '''
  <div class="mb-card"><div class="mb-caption">Status, for deltas only, always with words</div>
    <div class="row"><span class="mb-chip" style="color:var(--good)">Better <code>--good</code></span> <span class="mb-chip" style="color:var(--bad)">Worse <code>--bad</code></span></div>
  </div>'''
    chart_section += "\n</div>"

    spaces = "".join(f'<div style="width:var(--gap-{n})" title="--gap-{n}"></div>' for n, _ in GAPS)
    space_labels = " · ".join(f"--gap-{n} {round(b.px('--space', 8) * f)}" for n, f in GAPS)

    inverse_muted = 'color-mix(in srgb, var(--bg) 64%, transparent)'
    if b.tone == "dark":
        logos = [('var(--bg)', 'var(--logo-light)', 'Brand ground', '--logo-light', 'var(--muted)'),
                 ('var(--inverse-bg, var(--fg))', 'var(--logo-dark)', 'Light ground', '--logo-dark', inverse_muted)]
    else:
        logos = [('var(--bg)', 'var(--logo-dark)', 'Light ground', '--logo-dark', 'var(--muted)'),
                 ('var(--inverse-bg, var(--fg))', 'var(--logo-light)', 'Dark ground', '--logo-light', inverse_muted)]
    if "--art" in r:
        logos.append(('var(--art)', 'var(--logo-light)' if b.art_ink == "inverse" or b.tone == "dark" else 'var(--logo-dark)',
                      'Art ground', '--art', 'color-mix(in srgb, var(--bg) 64%, transparent)' if b.art_ink == "inverse" else 'var(--muted)'))
    logo_html = "".join(
        f'<div style="background:{g}"><span class="mb-logo" style="--page-logo:{l}" role="img" aria-label="{html.escape(title)} logo"></span>'
        f'<span class="mb-caption" style="color:{c}">{lab} · <code style="background:transparent;color:inherit">{tok}</code></span></div>'
        for g, l, lab, tok, c in logos)

    icons = b.icons()
    icon_html = "".join(f'<div><span class="mb-icon">{svg}</span><span>{html.escape(n)}</span></div>' for n, svg in icons)
    illos = b.asset_svgs("illustrations", set(b.library_illos()))
    illo_html = "".join(f'<figure class="mb-card">{svg}<span class="mb-caption">{html.escape(n)}</span></figure>' for n, svg in illos)

    rule_cards = []
    for heading in ("Voice", "Surfaces", "Adaptation"):
        body = secs.get(heading)
        if not body:
            continue
        rule_cards.append(f'<div class="mb-card" data-tone="outline"><div class="mb-eyebrow">{heading}</div>{md_blocks(body)}</div>')
    illo_rules = secs.get("Illustration", "")

    hero_ink = "mb-hero"
    sections = []

    def sec(eyebrow, heading, blurb, body):
        sections.append(f'''<section class="g-sec">
  <header><div class="mb-eyebrow">{eyebrow}</div><h3>{heading}</h3><p>{blurb}</p></header>
  <div class="g-body">{body}</div>
</section>''')

    sec("01", "Logo", f"Three variants, one per ground. Never below {html.escape(r.get('--logo-min', '20px'))} tall, never recoloured or redrawn.",
        f'<div class="g-logos">{logo_html}</div>')
    sec("02", "Colour", "Roles, not a palette to pick from. One accent per view; ink and hairlines carry the rest.",
        f'<div class="g-grid">{"".join(colour)}</div>{dark_note}')
    sec("03", "Type", f"One scale, {base:g} px × {scale:g}<sup>step</sup>. Type never shrinks to fit; words get cut.",
        f'<div class="g-fam">{"".join(fams)}</div><div class="g-type">{"".join(type_rows)}</div>')
    sec("04", "Data", "Six categorical colours, a sequential ramp, and status colours for deltas. Label directly; cite a source.",
        chart_section)
    sec("05", "Shape and components", f"Every gap is a multiple of {html.escape(r.get('--space', '8px'))}. Radius {html.escape(r.get('--radius', ''))}, stroke {html.escape(r.get('--stroke', ''))}.",
        f'''<div class="g-shape"><div class="g-space">{spaces}</div><span class="mb-caption">{space_labels}</span></div>
<div class="g-comp">
  <div class="mb-tile"><div class="mb-tile__label">Tile label</div><div class="mb-tile__value">4h → 12m</div><div class="mb-tile__delta" data-trend="down" data-good="down">Faster than last quarter</div></div>
  <div class="mb-card"><div class="mb-eyebrow">Eyebrow</div><h3>Card heading</h3><p class="mb-muted">Cards sit on the surface colour with the brand radius.</p></div>
  <div class="mb-card" data-tone="outline"><div class="mb-stat">98%</div><p class="mb-muted">A number that matters becomes a stat.</p><div class="row"><span class="mb-chip">Chip</span></div></div>
</div>''')
    if icons:
        sec("06", "Icons", "24 px line icons drawn for currentColor. Use them at text size beside a label, never as decoration.",
            f'<div class="g-icons">{icon_html}</div>')
    if illos:
        sec("07", "Illustration", "Reach for the library before drawing anything new.",
            f'<div class="g-illos">{illo_html}</div><div class="g-prose">{md_blocks(illo_rules)}</div>')
    elif illo_rules:
        sec("07", "Illustration", "", f'<div class="g-prose">{md_blocks(illo_rules)}</div>')
    if rule_cards:
        sec("08", "Rules", f"From <code>brand/{b.name}.md</code>. They win over any default.",
            f'<div class="g-rules">{"".join(rule_cards)}</div>')

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} brand guide</title>
<style>
{kit}
.row {{ display: flex; flex-wrap: wrap; gap: var(--gap-sm); align-items: center; }}
{GUIDE_CSS}
</style>
</head>
<body>
<main class="g">
  <div class="g-top"><span class="mb-logo" role="img" aria-label="{html.escape(title)} logo"></span><span class="mb-caption">Brand guide · generated from brand/{b.name}.css</span></div>
  <section class="g-hero {hero_ink}">
    <span class="mb-logo" role="img" aria-label="{html.escape(title)} logo"></span>
    <div class="mb-eyebrow">Brand guide</div>
    <h1>{html.escape(title)}, <strong>on every surface</strong></h1>
    <p class="mb-lead">{intro or "Logo, colour, type, data and rules for anything that carries the brand."}</p>
  </section>
  {"".join(sections)}
  <p class="g-foot">Everything on this page is drawn from the brand tokens. Pages, dashboards and documents use the same kit: <code>kit.py css</code>.</p>
</main>
</body>
</html>
'''


# ---------------------------------------------------------------- lint
NAMED = ("white black red green blue yellow orange purple pink gray grey silver navy teal maroon olive "
         "lime aqua fuchsia cyan magenta indigo violet gold brown beige tan coral salmon crimson "
         "lightgray lightgrey darkgray darkgrey whitesmoke gainsboro slategray slategrey").split()
COLOR_FN = re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(\s*[\d.][^)]*\)", re.I)
HEX = re.compile(r"(?<![\w&#-])#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
NAMED_RE = re.compile(r"(?<![\w-])(" + "|".join(NAMED) + r")(?![\w-])", re.I)
PAINT_ATTR = re.compile(r'\b(fill|stroke|stop-color|flood-color|color)\s*=\s*["\']([^"\']*)["\']', re.I)


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def lint_value(value):
    v = re.sub(r'url\((?:[^()"\']|"[^"]*"|\'[^\']*\')*\)', "", value)
    v = re.sub(r'"[^"]*"|\'[^\']*\'', "", v)
    hits = HEX.findall(v) + [m.group(0) for m in COLOR_FN.finditer(v)] + NAMED_RE.findall(v)
    return hits


def cmd_lint(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    errors, warns = [], []
    ks, ke = text.find(KIT_START), text.find(KIT_END)
    if ks < 0 or ke < 0:
        errors.append((1, "no brand kit: paste the output of `kit.py css` into the page's first <style>"))
        skip = (0, 0)
    else:
        skip = (ks, ke + len(KIT_END))

    def in_kit(i):
        return skip[0] <= i < skip[1]

    # css declarations: the innermost {…} bodies of <style> blocks, and style="" attributes
    decls = []
    for m in re.finditer(r"<style\b[^>]*>(.*?)</style>", text, re.S | re.I):
        css, start = m.group(1), m.start(1)
        for a in re.finditer(r"@import|@font-face", css):
            if not in_kit(start + a.start()):
                errors.append((line_of(text, start + a.start()), f"{a.group(0)}: fonts come from the kit only"))
        blanked = re.sub(r"/\*.*?\*/", lambda c: " " * len(c.group(0)), css, flags=re.S)
        for body in re.finditer(r"\{([^{}]*)\}", blanked):
            decls.append((start + body.start(1), body.group(1)))
    decls += [(m.start(2), m.group(2)) for m in re.finditer(r'\sstyle=(["\'])(.*?)\1', text, re.S)]
    for start, body in decls:
        for m in re.finditer(r"(?:^|;)\s*([a-zA-Z-]+)\s*:\s*((?:[^;(]|\([^)]*\))+)", body):
            at = start + m.start(1)
            if in_kit(at):
                continue
            prop, value = m.group(1).lower(), m.group(2).strip()
            for hit in lint_value(value):
                errors.append((line_of(text, at), f"{prop}: {hit} — use a brand token (var(--page-*), var(--accent), var(--chart-n))"))
            if prop in ("font-family", "font"):
                fam = value
                while re.search(r"var\(--font-[\w-]+(?:,\s*[^()]*)?\)", fam):
                    fam = re.sub(r"var\(--font-[\w-]+(?:,\s*[^()]*)?\)", "", fam)
                fam = re.sub(r"\b(inherit|initial|unset)\b", "", fam)
                fam = re.sub(r"[\d.]+(px|em|rem|%)?(/[\d.]+(px|em|rem|%)?)?|\b(bold|normal|italic|[1-9]00)\b|var\(--[\w-]+\)|calc\([^)]*\)", "", fam)
                if prop == "font-family" and fam.strip(" ,"):
                    errors.append((line_of(text, at), f"font-family: {value} — use var(--font-display|body|caption|mono)"))
                elif prop == "font" and re.search(r"['\"]|\b(sans-serif|serif|monospace|system-ui|arial|helvetica|inter)\b", value, re.I):
                    errors.append((line_of(text, at), f"font: {value} — use var(--font-*) for the family"))
            if prop == "font-size" and re.fullmatch(r"[\d.]+px", value):
                warns.append((line_of(text, at), f"font-size: {value} — prefer var(--text-caption…display)"))
            if "gradient(" in value and "var(--art" not in value:
                warns.append((line_of(text, at), f"{prop}: a gradient — the brand's only gradient is var(--art)"))

    for m in re.finditer(r"<link\b[^>]*>", text, re.I):
        if re.search(r"fonts\.(googleapis|gstatic)|typekit|fonts\.bunny", m.group(0)):
            errors.append((line_of(text, m.start()), "font <link>: fonts come from the kit only"))

    for m in PAINT_ATTR.finditer(text):
        v = m.group(2).strip()
        if v.lower() in ("none", "currentcolor", "transparent", "inherit") or v.startswith(("var(", "url(#")):
            continue
        if lint_value(v):
            errors.append((line_of(text, m.start()), f'{m.group(1)}="{v}" — use currentColor or var(--token)'))

    for m in re.finditer(r"<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script>", text, re.S | re.I):
        body = m.group(1)
        for h in re.finditer(r"""["'`]\s*(#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})|(?:rgba?|hsla?)\([^)]*\))\s*["'`]""", body):
            errors.append((line_of(text, m.start(1) + h.start()),
                           f"script colour {h.group(1)} — read tokens: getComputedStyle(document.documentElement).getPropertyValue('--chart-1')"))

    for ln, msg in sorted(set(errors)):
        print(f"{path.name}:{ln}: error: {msg}")
    for ln, msg in sorted(set(warns)):
        print(f"{path.name}:{ln}: warning: {msg}")
    if not errors:
        print(f"{path.name}: on brand" + (f" ({len(set(warns))} warnings)" if warns else ""))
    return 1 if errors else 0


# ---------------------------------------------------------------- shot
def cmd_shot(path: Path, outdir: Path, height: int, chrome_arg, timeout: float) -> int:
    from urllib.parse import quote
    import export
    chrome = export.find_chrome(chrome_arg)
    outdir.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8")
    if re.search(r"<html\b", text, re.I):
        dark_text = re.sub(r"<html\b", '<html data-theme="dark"', text, count=1, flags=re.I)
    else:
        dark_text = '<!doctype html><html data-theme="dark"><meta charset="utf-8">' + text
    dark = path.with_name(f".{path.stem}.dark.html")
    dark.write_text(dark_text, encoding="utf-8")
    httpd, port = export.start_server()
    # headless Chrome won't lay a window out narrower than ~500 px, so the phone view is a 400 px iframe
    phone = path.with_name(f".{path.stem}.phone.html")
    ph = int(height * 1.6)
    phone.write_text(f'<!doctype html><body style="margin:0"><iframe src="{quote(path.name)}" width="400" height="{ph}" '
                     f'style="border:0;display:block"></iframe>', encoding="utf-8")
    shots = [(path, 1440, height, "desktop"), (phone, 400, ph, "phone"), (dark, 1440, height, "dark")]
    try:
        for src, w, h, label in shots:
            out = outdir / f"{path.stem}-{label}.png"
            url = f"http://127.0.0.1:{port}{quote(str(src), safe='/')}"
            export.capture(chrome, url, w, h, 1, out, timeout)
            print(out)
    finally:
        dark.unlink(missing_ok=True)
        phone.unlink(missing_ok=True)
        httpd.shutdown()
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("css", help="write the brand kit stylesheet")
    c.add_argument("-o", "--out", required=True)
    c.add_argument("--brand", help="brand name or brand/<name>.css (default: brand/default, or the only brand)")
    c.add_argument("--scheme", choices=["auto", "light", "dark"], default="auto")
    g = sub.add_parser("guide", help="write a visual brand guide page")
    g.add_argument("-o", "--out", required=True)
    g.add_argument("--brand")
    li = sub.add_parser("lint", help="check a page for off-brand colours and fonts")
    li.add_argument("page")
    s = sub.add_parser("shot", help="screenshot a page at desktop, phone and dark")
    s.add_argument("page")
    s.add_argument("-o", "--outdir", required=True)
    s.add_argument("--height", type=int, default=1400, help="desktop capture height in CSS px (phone gets 1.6x)")
    s.add_argument("--chrome")
    s.add_argument("--timeout", type=float, default=30)
    args = ap.parse_args()

    if args.cmd == "css":
        b = Brand(args.brand)
        out = Path(args.out)
        out.write_text(build_css(b, args.scheme), encoding="utf-8")
        print(f"{out}  {out.stat().st_size / 1024:.0f} KB  (brand {b.name}, scheme {args.scheme})")
    elif args.cmd == "guide":
        b = Brand(args.brand)
        out = Path(args.out)
        out.write_text(build_guide(b), encoding="utf-8")
        print(f"{out}  {out.stat().st_size / 1024:.0f} KB  (brand {b.name})")
    elif args.cmd == "lint":
        sys.exit(cmd_lint(Path(args.page)))
    elif args.cmd == "shot":
        sys.exit(cmd_shot(Path(args.page).resolve(), Path(args.outdir), args.height, args.chrome, args.timeout))


if __name__ == "__main__":
    main()
