#!/usr/bin/env python3
"""Mark up a PDF: highlights, pen drawings, text boxes, notes, stamps.

  python annotate.py in.pdf ops.json -o out.pdf --preview previews/

ops.json is a list of operations (or {"ops": [...]}). Every operation accepts:
  "page"   1-based page, list, "2-4" or "all" (default: every page where the target text appears)
  "color"  name (yellow, green, blue, pink, orange, red, ink, pencil, black ...) or "#rrggbb"
  "note"   optional pop-up comment attached to the mark

Targets: either "text" (a phrase to find; "occurrence": "all" | "first" | "last" | N;
"match_case": true) or explicit coordinates in PDF points as displayed (see render.py --grid).

  Text marks (real annotations; editable/removable in any PDF viewer)
    {"op": "highlight", "text": "net 30 days", "color": "yellow"}
    {"op": "underline" | "strikeout" | "squiggly", "text": "...", "color": "red"}
    {"op": "highlight", "text": "To readers", "to_text": "went through.", "color": "green"}
       -> range: from the start of "text" through the end of "to_text"; best for whole sentences

  Shapes (clean lines)
    {"op": "box", "text": "Total" | "rect": [x0,y0,x1,y1], "color": "red", "width": 1.5, "fill": "none", "pad": 3}
    {"op": "ellipse", "text": "..." | "rect": [...]}
    {"op": "line" | "arrow", "from": [x,y], "to": [x,y] | "to_text": "Total"}

  Hand-drawn pen marks (ink annotations with natural wobble; "width" default 1.6, color default "ink")
    {"op": "circle", "text": "$1,240.00"}                   loop drawn around the words
    {"op": "pen_underline", "text": "...", "double": true}
    {"op": "pen_arrow", "from": [x,y], "to": [x,y] | "to_text": "...", "from_text": "..."}
    {"op": "check", "at": [x,y] | "text": "...", "size": 14}    check mark (placed left of the text)
    {"op": "cross", "text": "..." | "rect": [...]}             X through something
    {"op": "star", "at": [x,y] | "rect": [...] | "text": "...", "size": 16}   hand-drawn star (left of text)
    {"op": "bracket", "text": "first words of a block", "to_text": "last words", "side": "left"}
    {"op": "ink", "strokes": [[[x,y],[x,y],...], ...]}          any freehand drawing

  Text you add
    {"op": "textbox", "text": "Please confirm this date", "rect": [...] | "near_text": "Deadline",
       "fontsize": 10, "color": "black", "fill": "note", "border": "none"}   typed comment box
       (the thin border takes the text color; "border": "none" removes it)
    {"op": "sticky", "at": [x,y] | "near_text": "...", "content": "Longer comment"}  note icon
    {"op": "handwrite", "text": "Looks good! -T", "at": [x,y] | "near_text": "...", "size": 16,
       "color": "ink", "font": "optional .ttf", "width": 200}
       -> written into the page in a handwriting font with slight jitter. Not an annotation: it becomes
          part of the page and can't be moved in a viewer afterwards.

  Other
    {"op": "image", "file": "my_signature.png", "rect": [...] | "at": [x,y], "width": 140}   stamp/signature
    {"op": "remove", "author": "Claude" | "*", "types": ["Highlight", "Ink", ...]}          delete earlier marks

Output: a JSON report (what was applied where, and warnings) plus preview PNGs of changed pages.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (AUTHOR, color, find_text, hand_arrow, hand_bracket, hand_check, hand_cross,  # noqa: E402
                     hand_ellipse, hand_star, hand_underline, highlight_color, handwrite_lines, handwriting_font, out_json, pages_of, pymupdf,
                     render, tag, to_unrotated, union_rect, wrap)

TEXT_MARKUP = {"highlight": "add_highlight_annot", "underline": "add_underline_annot",
               "strikeout": "add_strikeout_annot", "squiggly": "add_squiggly_annot"}
DEFAULT_COLOR = {"highlight": "yellow", "underline": "red", "strikeout": "red", "squiggly": "red",
                 "box": "red", "ellipse": "red", "line": "red", "arrow": "red",
                 "circle": "ink", "pen_underline": "ink", "pen_arrow": "ink", "check": "green",
                 "cross": "red", "bracket": "ink", "star": "orange", "ink": "ink", "handwrite": "ink",
                 "textbox": "black", "sticky": "yellow"}


class Skip(Exception):
    pass


def targets(doc, op, key="text"):
    """Yield (page, rect_or_quads) for a text target, or for explicit coordinates."""
    phrase = op.get(key)
    if phrase:
        pages = pages_of(doc, op.get("page"))
        found = False
        for i in pages:
            page = doc[i]
            for quads in find_text(page, phrase, op.get("occurrence", "all"), op.get("match_case", False), quads=True):
                found = True
                yield page, quads
        if not found:
            raise Skip(f"text {phrase!r} not found" + (f" on page(s) {op['page']}" if op.get("page") else "")
                       + ". Check the spelling or use a shorter piece; scanned pages have no text (see inspect_pdf.py).")
        return
    if "rect" in op or "at" in op or "from" in op:
        page_spec = op.get("page", 1)
        for i in pages_of(doc, page_spec):
            yield doc[i], None
        return
    raise Skip(f"needs \"{key}\" or coordinates")


def range_quads(page, start_rect, end_rect):
    """Line-by-line boxes covering every word from the one at start_rect to the one at end_rect,
    in reading order. (PyMuPDF's own start/stop selection returns nothing when both ends are on
    the same line, so the range is built from words.)"""
    words = sorted(page.get_text("words"), key=lambda w: (w[5], w[6], w[7]))

    def centre_in(w, r):
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        return r.x0 - 1 <= cx <= r.x1 + 1 and r.y0 - 1 <= cy <= r.y1 + 1

    first = next((i for i, w in enumerate(words) if centre_in(w, start_rect)), None)
    last = next((i for i in range(len(words) - 1, -1, -1) if centre_in(words[i], end_rect)), None)
    if first is None or last is None or last < first:
        return []
    lines = {}
    for w in words[first:last + 1]:
        r = pymupdf.Rect(w[:4])
        key = (w[5], w[6])
        lines[key] = lines[key] | r if key in lines else r
    return [r.quad for r in lines.values()]


def bounds(page):
    """The page rectangle in native (unrotated) coordinates."""
    return page.rect if not page.rotation else (page.rect * page.derotation_matrix).normalize()


def occupied(page):
    """Rects that a new box must not cover: every word, images, and existing annotations.
    Word-level (not block-level) so a note can sit in the empty end of a line, but never on text."""
    rects = [pymupdf.Rect(x[:4]) for x in page.get_text("words")]
    rects += [pymupdf.Rect(img["bbox"]) for img in page.get_image_info()]
    # pen strokes and lines are thin: their bounding box is mostly empty, so don't block it
    rects += [a.rect for a in page.annots() if a.type[1] not in ("Ink", "Line", "PolyLine")]
    return [pymupdf.Rect(r.x0 - 2, r.y0 - 2, r.x1 + 2, r.y1 + 2) for r in rects]


def is_free(rect, taken, b):
    return rect in b and not any(rect.intersects(t) for t in taken)


def near_rect(page, anchor, w, measure, gap=6, min_w=90):
    """Put a w-wide box near an anchor without covering anything. Candidates, in order:
    beside the anchor on its own line, the right margin, the left margin, then the nearest
    empty band below or above. Widths shrink to fit (not below min_w); the height comes from
    measure(width). Returns (rect, where)."""
    b = bounds(page)
    b = pymupdf.Rect(b.x0 + 8, b.y0 + 8, b.x1 - 8, b.y1 - 8)
    taken = occupied(page)
    others = taken

    def fit(x0, x1, y0):
        ww = min(w, x1 - x0)
        if ww < min_w:
            return None
        r = pymupdf.Rect(x0, y0, x0 + ww, y0 + measure(ww))
        return r if is_free(r, others, b) else None

    # beside the anchor, same line (e.g. the empty space right of a table cell)
    r = fit(anchor.x1 + gap, b.x1, anchor.y0 - 2)
    if r:
        return r, "beside the text"
    text_blocks = [pymupdf.Rect(x[:4]) for x in page.get_text("blocks") if x[4].strip()]
    col_right = max((t.x1 for t in text_blocks), default=anchor.x1)
    col_left = min((t.x0 for t in text_blocks), default=anchor.x0)
    r = fit(col_right + gap, b.x1, anchor.y0 - 2)
    if r:
        return r, "right margin"
    ww = min(w, col_left - gap - b.x0)
    if ww >= min_w:
        r = pymupdf.Rect(col_left - gap - ww, anchor.y0 - 2, col_left - gap, anchor.y0 - 2 + measure(ww))
        if is_free(r, others, b):
            return r, "left margin"
    # nearest empty band, searching outward from the anchor
    h = measure(w)
    x0 = min(max(anchor.x0, b.x0), b.x1 - w)
    for step in range(0, int(b.height), 3):
        for y0 in (anchor.y1 + 3 + step, anchor.y0 - 3 - h - step):
            r = pymupdf.Rect(x0, y0, x0 + w, y0 + h)
            if is_free(r, others, b):
                return r, "nearest empty space " + ("below" if y0 > anchor.y0 else "above")
    x0 = min(max(anchor.x0, b.x0), b.x1 - w)
    return pymupdf.Rect(x0, anchor.y1 + 3, x0 + w, anchor.y1 + 3 + h), "below the line (no free space found; covers text, check the preview)"


def ink(page, strokes, op, default_color):
    a = page.add_ink_annot([[tuple(map(float, p)) for p in s] for s in strokes])
    a.set_colors(stroke=color(op.get("color"), default_color))
    a.set_border(width=float(op.get("width", 1.6)))
    return tag(a, op.get("note"), op.get("opacity"))


def apply(doc, op, n, font_cache):
    kind = op.get("op")
    dc = DEFAULT_COLOR.get(kind, "red")
    seed = op.get("seed", n * 17 + 3)
    touched, notes = [], []

    if kind in TEXT_MARKUP and op.get("to_text"):
        # a range: from the start of "text" through the end of "to_text" (reading order)
        found = False
        for i in pages_of(doc, op.get("page")):
            page = doc[i]
            for start in find_text(page, op["text"], op.get("occurrence", "first"), quads=True):
                s0 = start[0].rect
                ends = [g for g in find_text(page, op["to_text"], "all", quads=True)
                        if g[-1].rect.y0 > s0.y0 + 1 or (abs(g[-1].rect.y0 - s0.y0) <= 1 and g[-1].rect.x0 >= s0.x0)]
                if not ends:
                    continue
                quads = range_quads(page, s0, ends[0][-1].rect)
                if not quads:
                    continue
                a = getattr(page, TEXT_MARKUP[kind])(quads)
                if a.rect.is_infinite or a.rect.is_empty:
                    page.delete_annot(a)
                    continue
                a.set_colors(stroke=highlight_color(op.get("color", dc)) if kind == "highlight" else color(op.get("color"), dc))
                tag(a, op.get("note"), op.get("opacity"))
                touched.append(page.number)
                found = True
        if not found:
            raise Skip(f"range {op['text']!r} ... {op['to_text']!r} not found" +
                       (f" on page(s) {op['page']}" if op.get("page") else "") + " (the end must come after the start)")

    elif kind in TEXT_MARKUP:
        for page, quads in targets(doc, op):
            a = getattr(page, TEXT_MARKUP[kind])(quads)
            if a.rect.is_infinite or a.rect.is_empty:
                page.delete_annot(a)
                continue
            a.set_colors(stroke=highlight_color(op.get("color", dc)) if kind == "highlight" else color(op.get("color"), dc))
            tag(a, op.get("note"), op.get("opacity"))
            touched.append(page.number)

    elif kind in ("box", "ellipse"):
        for page, quads in targets(doc, op):
            r = union_rect(quads) if quads else to_unrotated(page, op["rect"])
            pad = float(op.get("pad", 3 if quads else 0))
            r = pymupdf.Rect(r.x0 - pad, r.y0 - pad, r.x1 + pad, r.y1 + pad)
            a = page.add_rect_annot(r) if kind == "box" else page.add_circle_annot(r)
            a.set_colors(stroke=color(op.get("color"), dc), fill=color(op.get("fill", "none")))
            a.set_border(width=float(op.get("width", 1.5)), dashes=op.get("dashes"))
            tag(a, op.get("note"), op.get("opacity"))
            touched.append(page.number)

    elif kind in ("line", "arrow", "pen_arrow"):
        page = doc[pages_of(doc, op.get("page", 1))[0]]
        if op.get("to_text") or op.get("from_text"):
            # resolve on the page given, or the first page where the text is
            anchor_text = op.get("to_text") or op.get("from_text")
            spec = op.get("page")
            page = next((doc[i] for i in pages_of(doc, spec) if find_text(doc[i], anchor_text, "first")), None)
            if page is None:
                raise Skip(f"text {anchor_text!r} not found")
        p_from = _point(page, op, "from")
        p_to = _point(page, op, "to")
        if kind == "pen_arrow":
            ink(page, hand_arrow(p_from, p_to, seed, head=float(op.get("head", 10))), op, dc)
        else:
            a = page.add_line_annot(p_from, p_to)
            a.set_colors(stroke=color(op.get("color"), dc))
            a.set_border(width=float(op.get("width", 1.5)))
            if kind == "arrow":
                a.set_line_ends(pymupdf.PDF_ANNOT_LE_NONE, pymupdf.PDF_ANNOT_LE_CLOSED_ARROW)
                a.set_colors(stroke=color(op.get("color"), dc), fill=color(op.get("color"), dc))
            tag(a, op.get("note"), op.get("opacity"))
        touched.append(page.number)

    elif kind in ("circle", "pen_underline", "cross", "check"):
        for page, quads in targets(doc, op):
            if kind == "check" and not quads:
                at = to_unrotated(page, op["at"])
                strokes = hand_check(at.x, at.y, float(op.get("size", 14)), seed)
            elif not quads:
                r = to_unrotated(page, op["rect"])
                strokes = hand_ellipse(r, 2, seed) if kind == "circle" else hand_cross(r, seed)
            else:
                r = union_rect(quads)
                if kind == "circle":
                    strokes = hand_ellipse(r, float(op.get("pad", 4)), seed)
                elif kind == "cross":
                    strokes = hand_cross(r, seed)
                elif kind == "check":
                    s = float(op.get("size", r.height * 1.1))
                    strokes = hand_check(r.x0 - s * 1.3, r.y0 - s * 0.15, s, seed)
                else:
                    strokes = [st for q in quads for st in hand_underline(q.rect, seed, op.get("double", False))]
            ink(page, strokes, op, dc)
            seed += 11
            touched.append(page.number)

    elif kind == "star":
        size = float(op.get("size", 16))
        if "at" in op or "rect" in op:
            page = doc[pages_of(doc, op.get("page", 1))[0]]
            c = to_unrotated(page, op["at"]) if "at" in op else to_unrotated(page, op["rect"])
            cx, cy = (c.x, c.y) if "at" in op else ((c.x0 + c.x1) / 2, (c.y0 + c.y1) / 2)
            ink(page, hand_star(cx, cy, size, seed), op, dc)
            touched.append(page.number)
        else:
            for page, quads in targets(doc, op):
                r = union_rect(quads)
                ink(page, hand_star(r.x0 - size * 0.8, (r.y0 + r.y1) / 2, size, seed), op, dc)
                touched.append(page.number)

    elif kind == "bracket":
        page_idx = pages_of(doc, op.get("page"))
        for i in page_idx:
            page = doc[i]
            first = find_text(page, op["text"], "first")
            last = find_text(page, op.get("to_text", op["text"]), "first")
            if first and last:
                block = first[0] | last[0]
                block.x0 = min(first[0].x0, last[0].x0)
                ink(page, hand_bracket(block, seed, op.get("side", "left")), op, dc)
                touched.append(page.number)
                break
        else:
            raise Skip("bracket: start or end text not found on the same page")

    elif kind == "ink":
        page = doc[pages_of(doc, op.get("page", 1))[0]]
        strokes = [[tuple(to_unrotated(page, p)) for p in s] for s in op["strokes"]]
        ink(page, strokes, op, dc)
        touched.append(page.number)

    elif kind == "textbox":
        helv = font_cache.setdefault("helv", pymupdf.Font("helv"))
        size = float(op.get("fontsize", 10))
        width = float(op.get("width", 170))

        def measure(wd):
            return len(wrap(op["text"], helv, size, wd - 8)) * size * 1.25 + 8

        for page, rect, where in _placements(doc, op, width, measure):
            notes.append(f"placed: {where}")
            bw = 0 if op.get("border") in ("none", False) else float(op.get("border_width", 0.8))
            kwargs = dict(fontsize=size, fontname="helv", text_color=color(op.get("color"), dc),
                          fill_color=color(op.get("fill", "note")), align=0)
            try:  # the border is drawn in the text color (PyMuPDF only colors borders of rich-text boxes)
                a = page.add_freetext_annot(rect, op["text"], border_width=bw, **kwargs)
            except TypeError:  # older PyMuPDF
                a = page.add_freetext_annot(rect, op["text"], **kwargs)
                a.set_border(width=bw)
            tag(a, op.get("note"), op.get("opacity"))
            touched.append(page.number)

    elif kind == "sticky":
        for page, rect, where in _placements(doc, op, 20, lambda wd: 20, min_w=20):
            a = page.add_text_annot(rect.tl, op.get("content", op.get("note", "")), icon=op.get("icon", "Comment"))
            a.set_colors(stroke=color(op.get("color"), dc))
            a.set_info(title=AUTHOR, content=op.get("content", op.get("note", "")))
            a.update()
            touched.append(page.number)

    elif kind == "handwrite":
        path, fname = font_cache.get("hand") or handwriting_font(op.get("font"))
        font_cache["hand"] = (path, fname)
        font = pymupdf.Font(fontfile=path) if path else pymupdf.Font("heit")
        size = float(op.get("size", 16))
        width = float(op.get("width", 220))

        def measure(wd):
            return len(wrap(op["text"], font, size, wd)) * size * 1.15 + 4

        for page, rect, where in _placements(doc, op, width, measure):
            if page.rotation:
                raise Skip("handwrite on rotated pages isn't supported; use a textbox")
            handwrite_lines(page, rect, wrap(op["text"], font, size, rect.width), font, path, size,
                       color(op.get("color"), dc), seed)
            notes.append(f"placed: {where}; font: {fname if path else 'Helvetica italic'}")
            touched.append(page.number)
        if not path:
            notes.append(fname)

    elif kind == "image":
        page = doc[pages_of(doc, op.get("page", 1))[0]]
        src = Path(op["file"]).expanduser()
        if not src.exists():
            raise Skip(f"image {src} not found")
        if "rect" in op:
            r = to_unrotated(page, op["rect"])
        else:
            pix = pymupdf.Pixmap(str(src))
            w = float(op.get("width", 140))
            at = to_unrotated(page, op["at"])
            r = pymupdf.Rect(at.x, at.y, at.x + w, at.y + w * pix.height / pix.width)
        page.insert_image(r, filename=str(src), keep_proportion=True, overlay=True)
        touched.append(page.number)

    elif kind == "remove":
        who = op.get("author", AUTHOR)
        types = {t.lower() for t in op.get("types", [])}
        removed = 0
        for i in pages_of(doc, op.get("page")):
            page = doc[i]
            for a in list(page.annots()):
                if (who == "*" or a.info.get("title") == who) and (not types or a.type[1].lower() in types):
                    page.delete_annot(a)
                    removed += 1
                    touched.append(i)
        return sorted(set(touched)), [f"removed {removed} annotation(s)"]

    else:
        raise Skip(f"unknown op {kind!r}")
    return sorted(set(touched)), notes


def _point(page, op, which):
    t = op.get(f"{which}_text")
    if t:
        hits = find_text(page, t, op.get("occurrence", "first"))
        if not hits:
            raise Skip(f"{which}_text {t!r} not found on page {page.number + 1}")
        r = hits[0]
        other = op.get("from" if which == "to" else "to")
        toward = to_unrotated(page, other) if other else pymupdf.Point(r.x1 + 50, r.y0 - 50)
        return edge_point(r, toward, pad=float(op.get("gap", 7)))
    if which not in op:
        raise Skip(f"needs \"{which}\" or \"{which}_text\"")
    return to_unrotated(page, op[which])


def edge_point(rect, toward, pad=7):
    """Where a line from `toward` to the rect's centre crosses the rect's border (grown by pad),
    so arrows stop just short of the words (and of a circle drawn round them) instead of crossing them."""
    r = pymupdf.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad)
    c = pymupdf.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
    dx, dy = toward.x - c.x, toward.y - c.y
    if dx == 0 and dy == 0:
        return c
    t = min(abs(r.width / 2 / dx) if dx else float("inf"), abs(r.height / 2 / dy) if dy else float("inf"))
    return pymupdf.Point(c.x + dx * t, c.y + dy * t)


def _placements(doc, op, w, measure, min_w=90):
    """Yield (page, rect, where) for text boxes, notes and handwriting."""
    if "rect" in op:
        page = doc[pages_of(doc, op.get("page", 1))[0]]
        yield page, to_unrotated(page, op["rect"]), "given rect"
    elif "at" in op:
        page = doc[pages_of(doc, op.get("page", 1))[0]]
        at = to_unrotated(page, op["at"])
        yield page, pymupdf.Rect(at.x, at.y, at.x + w, at.y + measure(w)), "given point"
    elif "near_text" in op:
        hits = [(doc[i], r) for i in pages_of(doc, op.get("page"))
                for r in find_text(doc[i], op["near_text"], op.get("occurrence", "first"))]
        if not hits:
            raise Skip(f"near_text {op['near_text']!r} not found")
        page, anchor = hits[0]
        rect, where = near_rect(page, anchor, w, measure, min_w=min_w)
        yield page, rect, where
    else:
        raise Skip("needs \"rect\", \"at\" or \"near_text\"")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("ops", help="JSON file with the operations, or '-' for stdin")
    ap.add_argument("-o", "--out", help="output PDF (default: <name>-marked.pdf; never overwrites the input)")
    ap.add_argument("--preview", help="folder for PNG previews of changed pages")
    ap.add_argument("--dpi", type=int, default=110)
    a = ap.parse_args()

    src = Path(a.pdf)
    out = Path(a.out) if a.out else src.with_name(f"{src.stem}-marked.pdf")
    if out.resolve() == src.resolve():
        sys.exit("Refusing to overwrite the input. Pass a different -o path, then replace the file if you want.")
    raw = sys.stdin.read() if a.ops == "-" else Path(a.ops).read_text("utf-8")
    ops = json.loads(raw)
    ops = ops.get("ops", ops) if isinstance(ops, dict) else ops

    doc = pymupdf.open(src)
    if doc.is_encrypted:
        sys.exit("The PDF is encrypted; decrypt it first.")
    report, changed, font_cache = [], set(), {}
    for n, op in enumerate(ops, 1):
        entry = {"n": n, "op": op.get("op"), "target": op.get("text") or op.get("near_text") or op.get("to_text")}
        try:
            pages, notes = apply(doc, op, n, font_cache)
            entry.update(pages=[p + 1 for p in pages], count=len(pages))
            if notes:
                entry["notes"] = notes
            changed.update(pages)
        except Skip as e:
            entry.update(count=0, warning=str(e))
        except KeyError as e:
            entry.update(count=0, warning=f"missing field {e} for op {op.get('op')!r}")
        except Exception as e:  # one bad operation must not lose the others
            entry.update(count=0, warning=f"failed: {e.__class__.__name__}: {e}")
        report.append(entry)

    doc.save(out, garbage=3, deflate=True)
    previews = []
    if a.preview and changed:
        pdir = Path(a.preview)
        pdir.mkdir(parents=True, exist_ok=True)
        done = pymupdf.open(out)
        for i in sorted(changed):
            previews.append(render(done[i], str(pdir / f"{out.stem}-p{i + 1}.png"), a.dpi))
    out_json({"output": str(out), "operations": report, "pages_changed": sorted(p + 1 for p in changed),
              "previews": previews,
              "warnings": sum(1 for r in report if r.get("warning"))})


if __name__ == "__main__":
    main()
