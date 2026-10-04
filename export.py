#!/usr/bin/env python3
"""makeitbrand export.py — headless batch PNG or PDF export of a sheet's boards. Stdlib only.

    python3 export.py sheet.html -o outdir/
    python3 export.py sheet.html -o outdir/ --boards 1,3-5 --scale 2
    python3 export.py sheet.html -o outdir/ --pdf                 # one page per board
    python3 export.py sheet.html -o outdir/ --pdf --paper a4      # imposed on A4 with cut marks
    python3 export.py sheet.html -o outdir/ --pdf --flat          # one raster page per board, safe everywhere

## PDF

--pdf writes one vector PDF, `<slug of <title>>.pdf` (`-a4`/`-letter` appended with --paper), by
opening the sheet at `?mib-print` (runtime.js's print layout) and printing it with Chrome's
--print-to-pdf. Text stays text and fonts are embedded. Each board's page size is its px × 72 /
the profile's `--dpi` (default 96), so a nametag at 300 dpi is a 3.5 × 5 in page. --paper a4|letter
imposes boards on that paper instead, in a centred grid with cut marks; a board bigger than the
paper keeps its own page. --bleed grows every board by 1/8 in on each side (the board's ground and
full-width bands run into it, the content stays where it was relative to the trim): a trim-size
page becomes the bleed size, and on paper the bleed boxes touch with the cut marks in the margin. The page count is checked against the same arithmetic the runtime uses
(expected_pages), which also catches a print that fired before the layout was ready.

The default vector PDF is slow and blend-dependent when a board's ground has a scrim or gradient:
Chrome writes the blended layers as soft-masked image tiles (big, slow to open, and some viewers
render the blend wrong), and the fonts it embeds are Type3. For carousels, for any gradient or
scrim ground, and for viewers that mishandle the vector PDF, use --pdf --flat.

--flat (implies --pdf) renders each board to PNG through the normal PNG path (--scale, default 2),
then writes the PDF by hand, stdlib only: one page per board at the board's true size (px × 72 /
`--dpi`), each page a single image, so every viewer shows what the PNG shows. Text is no longer
selectable and the file is bigger than a flat-colour vector PDF, but never blend-dependent. Use
--scale 3 for print-sharp pages. --paper and --bleed are vector-only and are refused with --flat.

For each board (skipping any `data-template` board), this opens the sheet in headless Chrome at
`?mib-board=<0-based index>` (runtime.js's solo-render mode: one board at true size, no chrome,
transparent page) and takes a `--screenshot`. The sheet is served over a throwaway local HTTP
server rooted at "/" so relative links in a dev-form sheet (`<link href="../../runtime.css">`)
resolve the same way they would from a real URL, whether the sheet itself is the dev form or the
fully inlined form.

Board pixel size comes from the medium's CSS rule (`.board[data-medium="id"]{--board-w:…}`),
read out of the sheet's own <style> blocks and any linked stylesheets — not by rendering anything.
A `data-medium="custom"` board uses its `data-w`/`data-h` attributes instead.

--boards takes a 1-based selector (e.g. "1,3-5") into the list of *exportable* boards, i.e. after
template boards are already excluded — board 1 is the first non-template board in the sheet, not
raw DOM position 1.

Filenames are `<slug of data-title>@<scale>x.png`, using the same slug() rule as runtime.js.

## Font-loading finding

Headless Chrome's `--screenshot` flag blocks on the page's `load` event before it captures, and
Chrome resolves `@font-face` (whether a `data:` URI in an inlined sheet, or fetched from this
script's own localhost server for a dev-form sheet) well within that — in testing against
demo/sheets/nametags.html (both forms, Chrome headless=new on macOS), a screenshot taken with
`--virtual-time-budget=1` was byte-identical to one taken with `--virtual-time-budget=4000`, for
every board tried. No font-swap race was observed here.

That said, `--screenshot` has no way to wait on an arbitrary JS condition (e.g. runtime.js's own
`document.fonts.ready` gate, used by the on-screen sheet view but not by this flag), so a race is
still plausible with a slow disk, a large custom font, or a slower machine. This script does not
rely on the finding above holding everywhere: `capture()` below takes up to three screenshots per
board with a growing `--virtual-time-budget` (800ms, 2500ms, 6000ms) and stops as soon as two
consecutive captures are byte-identical, otherwise settling on the most patient (last) one. This
costs nothing extra in the common case (the first two captures already match) and self-heals in
the rare one.

Headless Chrome can also hang after writing the screenshot file instead of exiting; this script
polls for the file to appear and then kills the process, same trick as tools/shoot.sh.
"""
import argparse
import html
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

BOARD_OPEN_RE = re.compile(r'<section\b(?=[^>]*\bclass="board")[^>]*>', re.S)
# quotes optional: esbuild's minifier drops them from attribute selectors
RULE_RE = re.compile(r'\.board\[data-medium=(?:"([^"]+)"|([\w-]+))\]\s*\{([^}]*)\}')

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "chrome", "chrome-browser",
]


class ExportError(Exception):
    pass


def find_chrome(explicit):
    if explicit:
        if not Path(explicit).exists() and not shutil.which(explicit):
            sys.exit(f"export.py: --chrome {explicit} not found")
        return explicit
    for c in CHROME_CANDIDATES:
        if os.path.sep in c:
            if Path(c).exists():
                return c
        else:
            p = shutil.which(c)
            if p:
                return p
    sys.exit("export.py: could not find a Chrome/Chromium binary; pass --chrome PATH")


def slug(s):
    """Mirrors runtime.js's slug(): lowercase, strip diacritics, drop non-word/space/hyphen
    characters (ASCII \\w, matching JS's un-flagged \\w), collapse whitespace/underscore to '-'."""
    s = (s or "board").lower()
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^\w\s-]", "", s, flags=re.ASCII)
    s = s.strip()
    s = re.sub(r"[\s_]+", "-", s, flags=re.ASCII)
    return s or "board"


def unescape_attr(s):
    return (s.replace("&quot;", '"').replace("&#39;", "'")
             .replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))


def fmt_scale(scale):
    return str(int(scale)) if float(scale).is_integer() else str(scale)


def parse_boards(doc):
    """All top-level boards in DOM order; list index == 0-based ?mib-board=N (runtime.js's
    `boards` array includes template boards, so they must stay in this list too, just flagged)."""
    boards = []
    for m in BOARD_OPEN_RE.finditer(doc):
        tag = m.group(0)

        def attr(name):
            am = re.search(rf'\b{name}="([^"]*)"', tag)
            return unescape_attr(am.group(1)) if am else None

        boards.append({
            "template": bool(re.search(r"\bdata-template\b", tag)),
            "medium": attr("data-medium"),
            "like": attr("data-like"),
            "title": attr("data-title"),
            "w": attr("data-w"),
            "h": attr("data-h"),
        })
    return boards


def parse_medium_sizes(css_text):
    sizes = {}
    for m in RULE_RE.finditer(css_text):
        medium, body = m.group(1) or m.group(2), m.group(3)
        w = re.search(r"--board-w:\s*(\d+)px", body)
        h = re.search(r"--board-h:\s*(\d+)px", body)
        if w and h:
            sizes[medium] = (int(w.group(1)), int(h.group(1)))
    return sizes


def parse_medium_dpis(css_text):
    dpis = {}
    for m in RULE_RE.finditer(css_text):
        d = re.search(r"--dpi:\s*([\d.]+)", m.group(3))
        if d:
            dpis[m.group(1) or m.group(2)] = float(d.group(1))
    return dpis


def board_dpi(board, dpis):
    medium = board["like"] if board["medium"] == "custom" else board["medium"]
    return dpis.get(medium, 96.0)


# Mirrors runtime.js printLayout(); change both together.
PAPER = {"a4": (595.28, 841.89), "letter": (612.0, 792.0)}
PAPER_MARGIN, PAPER_GUTTER = 24, 18
BLEED_IN = 0.125                       # 1/8 in, which also covers the 3 mm most shops ask for
BLEED_MARGIN = 18                      # with bleed, bleed boxes touch and marks sit in the margin only


def expected_pages(items, paper, bleed=False):
    """items: (w_pt, h_pt) trim sizes per board in sheet order -> the page count printLayout() produces."""
    if not paper:
        return len(items)
    pw, ph = PAPER[paper]
    b = BLEED_IN * 72 if bleed else 0
    margin, gutter = (BLEED_MARGIN, 0) if bleed else (PAPER_MARGIN, PAPER_GUTTER)
    pages = i = 0
    while i < len(items):
        w, h = items[i]
        cols = math.floor((pw - 2 * margin + gutter) / (w + 2 * b + gutter))
        rows = math.floor((ph - 2 * margin + gutter) / (h + 2 * b + gutter))
        pages += 1
        if cols < 1 or rows < 1:
            i += 1
            continue
        n = 0
        while n < cols * rows and i < len(items) and items[i] == (w, h):
            n += 1
            i += 1
    return pages


def pdf_summary(data):
    """(page count, distinct page sizes as text) read from the uncompressed page dicts Chrome writes."""
    pages = len(re.findall(rb"/Type\s*/Page(?![A-Za-z])", data))
    sizes = []
    for box in re.findall(rb"/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)\s*\]", data):
        w, h = (float(v) / 72 for v in box)
        label = f"{w:.2f} × {h:.2f} in".replace(".00", "")
        if label not in sizes:
            sizes.append(label)
    return pages, sizes


def print_pdf(chrome, url, out_path, budget, timeout):
    profile = tempfile.mkdtemp(prefix="mib-pdf-")
    part = out_path.with_name(f".{out_path.name}.part")
    part.unlink(missing_ok=True)
    args = [
        chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
        f"--user-data-dir={profile}", "--no-pdf-header-footer", f"--virtual-time-budget={budget}",
        f"--print-to-pdf={part}", url,
    ]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline, last = time.time() + timeout, -1
        while time.time() < deadline:
            if part.exists():
                size = part.stat().st_size
                if size and size == last and part.read_bytes()[-32:].rstrip().endswith(b"%%EOF"):
                    break
                last = size
            elif proc.poll() is not None:
                raise ExportError(f"chrome exited without writing a PDF ({url})")
            time.sleep(0.3)
        else:
            raise ExportError(f"chrome did not write a PDF within {timeout}s ({url})")
    finally:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        shutil.rmtree(profile, ignore_errors=True)
    data = part.read_bytes()
    shutil.move(str(part), str(out_path))
    return data


def export_pdf(chrome, base_url, jobs, paper, bleed, out_path, timeout):
    expected = expected_pages([(j["w_pt"], j["h_pt"]) for j in jobs], paper, bleed)
    query = "mib-print=" + (paper or "1") + ("&mib-bleed=1" if bleed else "")
    if jobs and any(j.get("picked") for j in jobs):
        query += "&mib-boards=" + ",".join(str(j["idx"]) for j in jobs)
    for budget in (5000, 15000):
        data = print_pdf(chrome, f"{base_url}?{query}", out_path, budget, timeout)
        pages, sizes = pdf_summary(data)
        if pages == expected:
            return pages, sizes
    raise ExportError(f"{out_path.name}: {pages} pages, expected {expected} (the print layout was not ready)")


def read_png(path):
    """Decode an 8-bit non-interlaced PNG (what headless Chrome writes) to (w, h, rgb, alpha-or-None).
    alpha is None when every pixel is opaque. Stdlib only."""
    import zlib
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ExportError(f"{path}: not a PNG")
    pos, idat, plte = 8, [], None
    while pos < len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif typ == b"PLTE":
            plte = body
        elif typ == b"IDAT":
            idat.append(body)
    if depth != 8 or interlace or ctype not in (0, 2, 3, 4, 6):
        raise ExportError(f"{path}: unsupported PNG (depth {depth}, type {ctype}, interlace {interlace})")
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    stride = w * bpp
    raw = zlib.decompress(b"".join(idat))
    out = bytearray(h * stride)
    prev = bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]
        row = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if f == 1:
            for i in range(bpp, stride):
                row[i] = (row[i] + row[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                row[i] = (row[i] + (((row[i - bpp] if i >= bpp else 0) + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = row[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        elif f != 0:
            raise ExportError(f"{path}: bad PNG filter {f}")
        out[y * stride:(y + 1) * stride] = row
        prev = row
    alpha = None
    if ctype == 6:
        rgb = bytearray(w * h * 3)
        for k in range(3):
            rgb[k::3] = out[k::4]
        alpha = bytes(out[3::4])
    elif ctype == 4:
        rgb = bytearray(w * h * 3)
        for k in range(3):
            rgb[k::3] = out[0::2]
        alpha = bytes(out[1::2])
    elif ctype == 0:
        rgb = bytearray(w * h * 3)
        for k in range(3):
            rgb[k::3] = out
    elif ctype == 3:
        rgb = bytearray()
        for v in out:
            rgb += plte[v * 3:v * 3 + 3]
    else:
        rgb = out
    if alpha is not None and alpha.count(255) == len(alpha):
        alpha = None
    return w, h, bytes(rgb), alpha


def write_flat_pdf(pages, out_path):
    """pages: [(png_path, w_pt, h_pt)] -> a PDF with one image page each, written by hand (stdlib).
    The image is Flate-compressed RGB; transparent pixels go in an SMask, so a board with no ground
    stays transparent rather than turning black."""
    import zlib
    objs = []  # index n-1 holds object n's bytes

    def add(b):
        objs.append(b)
        return len(objs)

    def stream(d, body):
        return b"<< " + d.encode() + b" /Length %d >>\nstream\n" % len(body) + body + b"\nendstream"

    add(b"")  # 1: catalog, filled in below
    add(b"")  # 2: page tree
    kids = []
    for png, w_pt, h_pt in pages:
        w, h, rgb, alpha = read_png(png)
        smask = ""
        if alpha is not None:
            n = add(stream(f"/Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceGray "
                           f"/BitsPerComponent 8 /Filter /FlateDecode", zlib.compress(alpha, 6)))
            smask = f" /SMask {n} 0 R"
        img = add(stream(f"/Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB "
                         f"/BitsPerComponent 8 /Filter /FlateDecode{smask}", zlib.compress(rgb, 6)))
        content = add(stream("", f"q {w_pt:.3f} 0 0 {h_pt:.3f} 0 0 cm /Im0 Do Q".encode()))
        kids.append(add(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w_pt:.3f} {h_pt:.3f}] "
                        f"/Resources << /XObject << /Im0 {img} 0 R >> >> /Contents {content} 0 R >>".encode()))
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = f"<< /Type /Pages /Count {len(kids)} /Kids [{' '.join(f'{k} 0 R' for k in kids)}] >>".encode()
    out = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    Path(out_path).write_bytes(bytes(out))


def collect_css(doc, sheet_path):
    """Inline <style> blocks plus the text of any linked stylesheets (dev form), so board sizes
    can be read without ever rendering the page."""
    css = []
    for m in re.finditer(r"<style\b[^>]*>(.*?)</style>", doc, re.S):
        css.append(m.group(1))
    for m in re.finditer(r'<link\b[^>]*\brel="stylesheet"[^>]*>', doc):
        href_m = re.search(r'\bhref="([^"]+)"', m.group(0))
        if not href_m:
            continue
        href = href_m.group(1)
        if href.startswith(("http:", "https:", "data:")):
            continue
        path = (sheet_path.parent / href).resolve()
        if path.exists():
            css.append(path.read_text(encoding="utf-8"))
    return "\n".join(css)


def board_size(board, sizes):
    if board["medium"] == "custom":
        try:
            return (int(board["w"]), int(board["h"]))
        except (TypeError, ValueError):
            return None
    return sizes.get(board["medium"])


def parse_board_selector(spec, n):
    """'1,3-5' (1-based, over the n exportable boards) -> a sorted list of 0-based positions."""
    if not spec:
        return list(range(n))
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a) - 1, int(b)))
        else:
            out.add(int(part) - 1)
    bad = [i for i in out if i < 0 or i >= n]
    if bad:
        sys.exit(f"export.py: --boards selects an out-of-range board; there are {n} exportable boards")
    return sorted(out)


def start_server():
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory="/", **kw)

        def log_message(self, *a):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port


def png_size(path):
    with open(path, "rb") as f:
        header = f.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", header[16:24])


def shoot(chrome, url, w, h, scale, out_path, budget, timeout):
    profile = tempfile.mkdtemp(prefix="mib-export-")
    args = [
        chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
        f"--window-size={w},{h}", f"--force-device-scale-factor={scale}",
        "--default-background-color=00000000", f"--user-data-dir={profile}",
        f"--screenshot={out_path}", f"--virtual-time-budget={budget}", url,
    ]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if out_path.exists() and out_path.stat().st_size > 0:
                time.sleep(0.2)  # headless Chrome may still be flushing
                break
            time.sleep(0.1)
        else:
            raise ExportError(f"chrome did not write a screenshot within {timeout}s ({url})")
    finally:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        shutil.rmtree(profile, ignore_errors=True)


def capture(chrome, url, w, h, scale, out_path, timeout):
    """Screenshot url at (w,h) CSS px and `scale`x device-scale-factor into out_path. See the
    file header: retries with a growing --virtual-time-budget until two consecutive captures
    match, to guard against a screenshot landing before web fonts finish swapping in."""
    budgets = (800, 2500, 6000)
    prev_bytes = None
    final = None
    try:
        for i, budget in enumerate(budgets):
            cand = out_path.with_name(f".{out_path.name}.try{i}.png")
            shoot(chrome, url, w, h, scale, cand, budget, timeout)
            data = cand.read_bytes()
            final = cand
            if prev_bytes is not None and data == prev_bytes:
                break
            prev_bytes = data
        shutil.move(str(final), str(out_path))
    finally:
        for p in out_path.parent.glob(f".{out_path.name}.try*.png"):
            p.unlink(missing_ok=True)


def export_board(chrome, base_url, idx, w, h, scale, out_path, timeout):
    url = f"{base_url}?mib-board={idx}"
    capture(chrome, url, w, h, scale, out_path, timeout)
    size = png_size(out_path)
    expected = (round(w * scale), round(h * scale))
    if size != expected:
        raise ExportError(f"{out_path.name}: PNG is {size}px, expected {expected}px (board index {idx}, {w}x{h} @{scale}x)")


def check_sheet(chrome, url, timeout):
    """Load the whole sheet once and report what the runtime marked: boards or elements carrying
    data-overflow or data-invalid. Returns a list of human-readable problems ([] when clean)."""
    import subprocess, tempfile, shutil, time
    prof = tempfile.mkdtemp(prefix="mib-check-")
    dom = Path(prof) / "dom.html"
    try:
        with open(dom, "wb") as out:
            proc = subprocess.Popen(
                [chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                 f"--user-data-dir={prof}", "--window-size=1600,1200", "--virtual-time-budget=5000",
                 "--dump-dom", url],
                stdout=out, stderr=subprocess.DEVNULL)
            deadline = time.time() + timeout
            while time.time() < deadline:
                if proc.poll() is not None:
                    break
                if dom.exists() and b"</html>" in dom.read_bytes()[-4000:]:
                    break
                time.sleep(0.25)
            proc.kill()
        html_text = dom.read_text(encoding="utf-8", errors="replace")
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    if "</html>" not in html_text:
        return ["could not load the sheet to check it for overflow (Chrome timed out)"]
    problems = []
    for chunk in re.split(r'(?=<section\b[^>]*\bclass="board")', html_text)[1:]:
        tag = chunk[: chunk.find(">") + 1]
        title = re.search(r'data-title="([^"]*)"', tag)
        title = html.unescape(title.group(1)) if title else "(untitled)"
        body = chunk[: chunk.find("</section>")] if "</section>" in chunk else chunk
        if "data-template" in tag:
            continue
        if "data-overflow" in tag:
            problems.append(f"{title}: overflows its board, cut words (PRIMITIVES §11)")
        for m in re.finditer(r'<([a-z0-9]+)\b([^>]*\bdata-invalid="([^"]*)"[^>]*)>', body):
            cls = re.search(r'class="([^"]*)"', m.group(2))
            problems.append(f"{title}: {cls.group(1) if cls else m.group(1)} invalid: {html.unescape(m.group(3))}")
        inner_over = len(re.findall(r'<[a-z0-9]+\b(?![^>]*class="board")[^>]*\bdata-overflow\b', body))
        if inner_over:
            problems.append(f"{title}: {inner_over} element(s) run outside the board or their card, tile or node")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheet")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--boards", help='1-based selector into the exportable boards, e.g. "1,3-5" (default: all)')
    ap.add_argument("--scale", type=float, default=2, help="PNG only")
    ap.add_argument("--pdf", action="store_true", help="write one vector PDF instead of PNGs")
    ap.add_argument("--paper", choices=sorted(PAPER), help="with --pdf: impose boards on this paper with cut marks")
    ap.add_argument("--bleed", action="store_true", help="with --pdf: extend each board's ground 1/8 in past the trim (print profiles)")
    ap.add_argument("--flat", action="store_true", help="with --pdf: one raster page per board (PNG inside a PDF) instead of vector; the safe choice for gradient or scrim grounds, carousels, and viewers that mishandle the vector PDF, which is slow and blend-dependent there")
    ap.add_argument("--chrome", help="path to a Chrome/Chromium binary")
    ap.add_argument("--parallel", type=int, default=4, help="boards to export concurrently")
    ap.add_argument("--timeout", type=float, default=30, help="seconds to wait for each Chrome screenshot")
    args = ap.parse_args()

    sheet_path = Path(args.sheet).resolve()
    if not sheet_path.exists():
        sys.exit(f"export.py: {sheet_path} does not exist")
    doc = sheet_path.read_text(encoding="utf-8")
    chrome = find_chrome(args.chrome)

    boards = parse_boards(doc)
    if not boards:
        sys.exit("export.py: no boards found in the sheet")
    css = collect_css(doc, sheet_path)
    sizes = parse_medium_sizes(css)
    dpis = parse_medium_dpis(css)
    if args.flat:
        args.pdf = True
        if args.paper or args.bleed:
            sys.exit("export.py: --flat writes one page per board at true size; --paper and --bleed need the vector PDF")
    if args.paper or args.bleed:
        args.pdf = True

    exportable = [(i, b) for i, b in enumerate(boards) if not b["template"]]
    if not exportable:
        sys.exit("export.py: no exportable boards (every board is data-template)")

    positions = parse_board_selector(args.boards, len(exportable))

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    jobs = []
    seen_names = {}
    for pos in positions:
        idx, b = exportable[pos]
        size = board_size(b, sizes)
        if not size:
            sys.exit(
                f"export.py: board {pos + 1} (sheet index {idx}, data-medium={b['medium']!r}) has no "
                f"known size; custom boards need data-w/data-h, others need a matching "
                f".board[data-medium=\"...\"] CSS rule"
            )
        w, h = size
        name = slug(b["title"])
        seen_names[name] = seen_names.get(name, 0) + 1
        n = seen_names[name]
        fname = f"{name}@{fmt_scale(args.scale)}x.png" if n == 1 else f"{name}-{n}@{fmt_scale(args.scale)}x.png"
        dpi = board_dpi(b, dpis)
        jobs.append({"pos": pos, "idx": idx, "title": b["title"], "w": w, "h": h, "out": outdir / fname,
                     "w_pt": w * 72 / dpi, "h_pt": h * 72 / dpi, "picked": bool(args.boards)})

    httpd, port = start_server()
    base_url = f"http://127.0.0.1:{port}{quote(str(sheet_path), safe='/')}"
    failures = []
    if args.flat:
        title = re.search(r"<title>(.*?)</title>", doc, re.S)
        name = slug(html.unescape(title.group(1)) if title else sheet_path.stem)
        out = outdir / f"{name}.pdf"
        tmp = Path(tempfile.mkdtemp(prefix="mib-flat-"))
        try:
            for n, j in enumerate(jobs):
                j["png"] = tmp / f"{n}.png"
            with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as ex:
                futs = [ex.submit(export_board, chrome, base_url, j["idx"], j["w"], j["h"], args.scale, j["png"], args.timeout)
                        for j in jobs]
                for f in futs:
                    f.result()
            write_flat_pdf([(j["png"], j["w_pt"], j["h_pt"]) for j in jobs], out)
            print(f"{out}  {len(jobs)} {'page' if len(jobs) == 1 else 'pages'}  (flat, {fmt_scale(args.scale)}x PNG per page)")
        except ExportError as e:
            failures.append(str(e))
            print(f"export.py: FAILED {out.name}: {e}", file=sys.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            httpd.shutdown()
    elif args.pdf:
        title = re.search(r"<title>(.*?)</title>", doc, re.S)
        name = slug(html.unescape(title.group(1)) if title else sheet_path.stem)
        out = outdir / f"{name}{'-' + args.paper if args.paper else ''}{'-bleed' if args.bleed else ''}.pdf"
        try:
            pages, page_sizes = export_pdf(chrome, base_url, jobs, args.paper, args.bleed, out, max(args.timeout, 60))
            print(f"{out}  {pages} {'page' if pages == 1 else 'pages'}  ({', '.join(page_sizes)}; {len(jobs)} boards)")
        except ExportError as e:
            failures.append(str(e))
            print(f"export.py: FAILED {out.name}: {e}", file=sys.stderr)
        finally:
            httpd.shutdown()
    try:
        with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as ex:
            futs = {
                ex.submit(export_board, chrome, base_url, j["idx"], j["w"], j["h"], args.scale, j["out"], args.timeout): j
                for j in ([] if args.pdf else jobs)
            }
            for fut in as_completed(futs):
                j = futs[fut]
                try:
                    fut.result()
                    print(f"{j['out']}  {round(j['w'] * args.scale)}x{round(j['h'] * args.scale)}  ({j['title']})")
                except ExportError as e:
                    failures.append(str(e))
                    print(f"export.py: FAILED {j['out'].name}: {e}", file=sys.stderr)
    finally:
        httpd.shutdown()

    if failures:
        sys.exit("export.py: the PDF failed" if args.pdf else f"export.py: {len(failures)} of {len(jobs)} board(s) failed")

    httpd, port = start_server()
    try:
        problems = check_sheet(chrome, f"http://127.0.0.1:{port}{quote(str(sheet_path), safe='/')}", args.timeout)
    finally:
        httpd.shutdown()
    if problems:
        print("export.py: the runtime flagged problems; these boards are not done:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)
    print("export.py: check clean (no overflow, nothing invalid)")


if __name__ == "__main__":
    main()
