"""Shared helpers for the editor skill scripts (PyMuPDF)."""
from __future__ import annotations

import json
import math
import os
import platform
import random
import re
import sys
import urllib.request
from pathlib import Path

try:
    import pymupdf
except ImportError:  # older installs only have the legacy name
    try:
        import fitz as pymupdf  # type: ignore
    except ImportError:
        sys.exit("PyMuPDF is missing. Install it with: pip install pymupdf")

AUTHOR = "Claude"  # every annotation we add carries this, so they can be listed/removed later

COLORS = {
    "yellow": (1.0, 0.92, 0.23), "green": (0.55, 0.88, 0.45), "blue": (0.12, 0.38, 0.86),
    "lightblue": (0.62, 0.82, 1.0), "pink": (1.0, 0.55, 0.78), "orange": (1.0, 0.62, 0.12),
    "red": (0.86, 0.1, 0.1), "purple": (0.5, 0.22, 0.72), "black": (0, 0, 0),
    "gray": (0.45, 0.45, 0.45), "grey": (0.45, 0.45, 0.45), "white": (1, 1, 1),
    "ink": (0.08, 0.2, 0.55),          # ballpoint-pen blue
    "pencil": (0.3, 0.3, 0.32),
    "note": (1.0, 0.97, 0.72),         # sticky-note yellow, for text box fills
}


# Highlights multiply with the page, so dark colors would bury the words: named colors map to
# light highlighter shades when used for highlighting.
HIGHLIGHT = {"yellow": (1.0, 0.93, 0.35), "blue": (0.62, 0.8, 1.0), "lightblue": (0.62, 0.8, 1.0),
             "green": (0.62, 0.92, 0.55), "pink": (1.0, 0.68, 0.85), "orange": (1.0, 0.78, 0.45),
             "purple": (0.82, 0.72, 1.0), "red": (1.0, 0.6, 0.6), "gray": (0.82, 0.82, 0.82), "grey": (0.82, 0.82, 0.82)}


def highlight_color(value):
    if isinstance(value, str) and value.strip().lower() in HIGHLIGHT:
        return HIGHLIGHT[value.strip().lower()]
    return color(value, "yellow")


def color(value, default="red"):
    """'red' | '#ff0000' | [1,0,0] | [255,0,0] -> (r, g, b) floats, or None for 'none'."""
    if value is None:
        value = default
    if value in ("none", "transparent", ""):
        return None
    if isinstance(value, (list, tuple)):
        vals = [float(v) for v in value[:3]]
        return tuple(v / 255 for v in vals) if max(vals) > 1 else tuple(vals)
    v = str(value).strip().lower()
    if v in COLORS:
        return COLORS[v]
    if v.startswith("#") and len(v) in (4, 7):
        h = v[1:] if len(v) == 7 else "".join(c * 2 for c in v[1:])
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    raise ValueError(f"Unknown color {value!r}. Use a name ({', '.join(COLORS)}) or #rrggbb.")


def pages_of(doc, spec):
    """1-based page spec (None/'all' | 3 | [1,3] | '2-5') -> list of 0-based indexes."""
    n = doc.page_count
    if spec in (None, "all", "*"):
        return list(range(n))
    if isinstance(spec, int):
        spec = [spec]
    if isinstance(spec, str):
        out = []
        for part in spec.split(","):
            if "-" in part:
                a, b = part.split("-")
                out += range(int(a), int(b) + 1)
            else:
                out.append(int(part))
        spec = out
    idx = [p - 1 for p in spec]
    bad = [p + 1 for p in idx if not 0 <= p < n]
    if bad:
        raise ValueError(f"Page(s) {bad} don't exist; the document has {n} pages.")
    return idx


def to_unrotated(page, obj):
    """Coordinates as seen in a render (view space) -> the page's native space.
    Text search results are already native; only hand-given coordinates need this."""
    is_rect = isinstance(obj, pymupdf.Rect) or (isinstance(obj, (list, tuple)) and len(obj) == 4)
    obj = pymupdf.Rect(obj) if is_rect else pymupdf.Point(obj)
    if not page.rotation:
        return obj
    return (obj * page.derotation_matrix).normalize() if is_rect else obj * page.derotation_matrix


def _norm(s):
    return re.sub(r"[\s\-\u00ad]+", "", s).lower()


def text_in(page, rect):
    """Text inside a rect, reading only its vertical middle band. Line boxes overlap the
    lines above and below by a point or two, and a full-height read picks those up."""
    r = pymupdf.Rect(rect)
    inset = r.height * 0.3
    return page.get_textbox(pymupdf.Rect(r.x0, r.y0 + inset, r.x1, r.y1 - inset))


def find_text(page, text, occurrence="all", match_case=False, quads=False):
    """Hits of `text` on a page, as rects (or lists of quads with quads=True).

    PyMuPDF's search is case-insensitive and returns one quad per line fragment, so a
    phrase that wraps onto the next line arrives as two quads. Consecutive fragments
    are joined back into one hit while the text collected so far is still shorter
    than what we searched for.
    """
    target = _norm(text)
    groups, got = [], 0
    hits = page.search_for(text, quads=True)
    if not hits:  # typographic quotes: try ' <-> ’ and " <-> “”
        for variant in (text.replace("'", "\u2019"), text.replace("\u2019", "'"),
                        re.sub(r'"(.*?)"', "\u201c\\1\u201d", text), text.replace("\u201c", '"').replace("\u201d", '"')):
            if variant != text:
                hits = page.search_for(variant, quads=True)
                if hits:
                    break
    for q in hits:
        frag = len(_norm(text_in(page, q.rect)))
        if groups and got < len(target) - 1 and q.rect.y0 >= groups[-1][-1].rect.y1 - 2:
            groups[-1].append(q)
            got += frag
        else:
            groups.append([q])
            got = frag
    if match_case:
        groups = [g for g in groups if text.replace(" ", "") in
                  "".join(text_in(page, q.rect) for q in g).replace(" ", "").replace("\n", "")]
    if occurrence not in (None, "all"):
        k = 1 if occurrence == "first" else len(groups) if occurrence == "last" else int(occurrence)
        groups = groups[k - 1:k] if 0 < k <= len(groups) else []
    return groups if quads else [union_rect(g) for g in groups]


def union_rect(quads):
    r = pymupdf.Rect(quads[0].rect)
    for q in quads[1:]:
        r |= q.rect
    return r


def tag(annot, note=None, opacity=None):
    annot.set_info(title=AUTHOR, content=note or "")
    if opacity is not None:
        annot.set_opacity(opacity)
    annot.update()
    return annot


# ------------------------------------------------------------------ hand-drawn geometry
# Everything returns lists of strokes (lists of (x, y)) for ink annotations.
# A seeded RNG keeps a re-run identical, so re-applying a spec gives the same marks.

def _rng(seed):
    return random.Random(seed)


def hand_ellipse(rect, pad=4, seed=1, loops=1.0):
    r = _rng(seed)
    rect = pymupdf.Rect(rect)
    cx, cy = (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
    rx, ry = rect.width / 2 + pad + 2, rect.height / 2 + pad
    start = r.uniform(-2.6, -1.9)                  # start near top-left like a right-handed pen
    sweep = 2 * math.pi * loops + r.uniform(0.25, 0.5)  # overshoot the start point
    wob_a, wob_f, wob_p = r.uniform(0.02, 0.05), r.uniform(2, 3.5), r.uniform(0, 6.28)
    pts, steps = [], max(40, int(sweep / 0.12))
    for i in range(steps + 1):
        t = start + sweep * i / steps
        grow = 1 + 0.06 * (i / steps)              # spiral out slightly so the ends don't meet exactly
        k = grow * (1 + wob_a * math.sin(wob_f * t + wob_p))
        pts.append((cx + rx * k * math.cos(t), cy + ry * k * math.sin(t)))
    return [pts]


def hand_line(p1, p2, seed=1, amp=0.45, bow=None):
    """A pen stroke: a gentle overall bow plus a small tremor (a few waves per stroke, not per inch)."""
    r = _rng(seed)
    (x1, y1), (x2, y2) = p1, p2
    length = math.hypot(x2 - x1, y2 - y1) or 1
    nx, ny = -(y2 - y1) / length, (x2 - x1) / length
    bow = r.uniform(0.012, 0.025) * length * r.choice((-1, 1)) if bow is None else bow
    steps = max(8, int(length / 4))
    ph = r.uniform(0, 6.28)
    waves = min(3.0, 0.8 + length / 150)
    pts = []
    for i in range(steps + 1):
        t = i / steps
        off = bow * math.sin(math.pi * t) + amp * math.sin(ph + 2 * math.pi * waves * t)
        pts.append((x1 + (x2 - x1) * t + nx * off, y1 + (y2 - y1) * t + ny * off))
    return pts


def hand_arrow(p1, p2, seed=1, head=10):
    shaft = hand_line(p1, p2, seed)
    (x1, y1), (x2, y2) = shaft[-2], shaft[-1]
    ang = math.atan2(y2 - y1, x2 - x1)
    r = _rng(seed + 7)
    strokes = [shaft]
    for side in (-1, 1):
        a = ang + math.pi + side * math.radians(r.uniform(24, 32))
        tip = (x2 + head * math.cos(a), y2 + head * math.sin(a))
        strokes.append(hand_line((x2, y2), tip, seed + side, amp=0.3, bow=0))
    return strokes


def hand_check(x, y, size=14, seed=1):
    a = (x, y + size * 0.55)
    b = (x + size * 0.35, y + size)
    c = (x + size * 1.05, y - size * 0.05)
    return [hand_line(a, b, seed, amp=0.25, bow=0.5) + hand_line(b, c, seed + 1, amp=0.35)[1:]]


def hand_cross(rect, seed=1):
    rect = pymupdf.Rect(rect)
    return [hand_line(rect.tl, rect.br, seed, amp=0.4), hand_line(rect.tr, rect.bl, seed + 1, amp=0.4)]


def hand_underline(rect, seed=1, double=False):
    rect = pymupdf.Rect(rect)
    y = rect.y1 + 1.5
    strokes = [hand_line((rect.x0 - 1.5, y), (rect.x1 + 2, y - 0.6), seed, amp=0.5)]
    if double:
        strokes.append(hand_line((rect.x0, y + 2.6), (rect.x1 + 1, y + 2.2), seed + 3, amp=0.5))
    return strokes


def hand_star(cx, cy, size=16, seed=1):
    """A five-pointed star drawn in one stroke, the way people draw one by hand."""
    r = _rng(seed)
    outer = size / 2
    start = -math.pi / 2 + r.uniform(-0.12, 0.12)
    pts = []
    for k in range(6):                       # visit every second point: 0, 2, 4, 1, 3, back to 0
        a = start + k * 4 * math.pi / 5
        pts.append((cx + outer * math.cos(a) * r.uniform(0.94, 1.05), cy + outer * math.sin(a) * r.uniform(0.94, 1.05)))
    stroke = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        seg = hand_line((x1, y1), (x2, y2), seed + len(stroke), amp=0.25, bow=r.uniform(-0.4, 0.4))
        stroke += seg if not stroke else seg[1:]
    return [stroke]


def hand_bracket(rect, seed=1, side="left"):
    """A margin bracket spanning a block of lines."""
    rect = pymupdf.Rect(rect)
    x = rect.x0 - 8 if side == "left" else rect.x1 + 8
    d = 4 if side == "left" else -4
    return [hand_line((x + d, rect.y0), (x, rect.y0 + 2), seed, amp=0.2, bow=0)
            + hand_line((x, rect.y0 + 2), (x, rect.y1 - 2), seed + 1, amp=0.4)[1:]
            + hand_line((x, rect.y1 - 2), (x + d, rect.y1), seed + 2, amp=0.2, bow=0)[1:]]


# ------------------------------------------------------------------ handwriting font

def _cache_dir():
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    d = Path(base) / "editor-skill"
    d.mkdir(parents=True, exist_ok=True)
    return d


SYSTEM_HAND_FONTS = [
    # Windows
    r"C:\Windows\Fonts\Inkfree.ttf", r"C:\Windows\Fonts\segoepr.ttf", r"C:\Windows\Fonts\comic.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf", "/System/Library/Fonts/Noteworthy.ttc",
    "/System/Library/Fonts/Supplemental/Chalkboard.ttc",
    # Linux (fonts-comic-neue etc.)
    "/usr/share/fonts/truetype/comic-neue/ComicNeue-Regular.ttf",
]
# Caveat (SIL Open Font License). The Google Fonts CSS API hands out a direct .ttf link to
# clients it doesn't recognise as a modern browser; GitHub is the fallback.
CAVEAT_CSS = "https://fonts.googleapis.com/css2?family=Caveat:wght@500"
CAVEAT_URL = "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf"


def _download_caveat(dest):
    ua = {"User-Agent": "Mozilla/5.0"}
    try:
        css = urllib.request.urlopen(urllib.request.Request(CAVEAT_CSS, headers=ua), timeout=15).read().decode()
        url = re.search(r"url\((https://[^)]+\.ttf)\)", css).group(1)
    except Exception:
        url = CAVEAT_URL
    data = urllib.request.urlopen(urllib.request.Request(url, headers=ua), timeout=30).read()
    if not data.startswith((b"\x00\x01\x00\x00", b"OTTO", b"true")):
        raise ValueError("download was not a font file")
    dest.write_bytes(data)


def handwriting_font(explicit=None):
    """Path to a handwriting-style font: explicit > cached Caveat > system font > download Caveat.
    Returns (path, name) or (None, reason) when only the built-in italic fallback is possible."""
    if explicit:
        p = Path(explicit).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"Font file not found: {p}")
        return str(p), p.stem
    cached = _cache_dir() / "Caveat.ttf"
    if cached.exists():
        return str(cached), "Caveat"
    for f in SYSTEM_HAND_FONTS:
        if Path(f).exists():
            return f, Path(f).stem
    try:
        _download_caveat(cached)
        return str(cached), "Caveat"
    except Exception as e:  # offline or blocked
        return None, f"no handwriting font available ({e.__class__.__name__}); used italic Helvetica"


# ------------------------------------------------------------------ text layout

def wrap(text, font, size, width):
    lines = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split(" "):
            trial = f"{line} {word}".strip()
            if font.text_length(trial, size) <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def handwrite_lines(page, rect, lines, font, path, size, rgb, seed):
    r = random.Random(seed)
    name = "HandF"
    if path:
        page.insert_font(fontname=name, fontfile=path)
    else:
        name = "heit"
    y = rect.y0 + size
    for line in lines:
        x = rect.x0
        drift = r.uniform(-0.6, 0.6)                      # the whole line slopes a little
        for k, ch in enumerate(line):
            s = size * r.uniform(0.96, 1.04)
            dy = drift * k / 10 + r.uniform(-0.35, 0.35)
            ang = r.uniform(-2.5, 2.5)
            p = pymupdf.Point(x, y + dy)
            page.insert_text(p, ch, fontsize=s, fontname=name, color=rgb,
                             morph=(p, pymupdf.Matrix(1, 1).prerotate(ang)))
            x += font.text_length(ch, s) * r.uniform(0.97, 1.02)
        y += size * 1.15


def render(page, path, dpi=110, clip=None):
    pix = page.get_pixmap(dpi=dpi, clip=clip, annots=True)
    pix.save(path)
    return path


def out_json(obj):
    print(json.dumps(obj, indent=2, default=str))
