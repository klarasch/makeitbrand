#!/usr/bin/env python3
"""makeitbrand export.py — headless batch PNG export of a sheet's boards. Stdlib only.

    python3 export.py sheet.html -o outdir/
    python3 export.py sheet.html -o outdir/ --boards 1,3-5 --scale 2

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
    ap.add_argument("--scale", type=float, default=2)
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
        jobs.append({"pos": pos, "idx": idx, "title": b["title"], "w": w, "h": h, "out": outdir / fname})

    httpd, port = start_server()
    base_url = f"http://127.0.0.1:{port}{quote(str(sheet_path), safe='/')}"
    failures = []
    try:
        with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as ex:
            futs = {
                ex.submit(export_board, chrome, base_url, j["idx"], j["w"], j["h"], args.scale, j["out"], args.timeout): j
                for j in jobs
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
        sys.exit(f"export.py: {len(failures)} of {len(jobs)} board(s) failed")

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
