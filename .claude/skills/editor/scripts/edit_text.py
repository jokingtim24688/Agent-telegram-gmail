#!/usr/bin/env python3
"""Change words in place: cover the old text, write the new text in a matching font at the same spot.

  python edit_text.py in.pdf edits.json -o out.pdf --preview previews/

edits.json: [{"find": "March 3, 2026", "replace": "April 10, 2026"},
             {"find": "$1,240.00", "replace": "$1,315.00", "page": 2, "occurrence": 1}]

Good for short, same-line changes: names, dates, amounts, typos. The new text keeps the
old text's position, size and color, and reuses the document's embedded font when that
font contains every needed character. Otherwise it uses the closest standard font
(sans/serif/mono, bold/italic). If the replacement is wider than the space available, it
is shrunk by up to 15%; beyond that the edit is refused. Use the Word round trip for
anything that needs text to reflow.

The old text is really removed (redacted), not just covered, so it can't be copied back out.
Images and drawings under it are left alone.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import find_text, out_json, pages_of, pymupdf, render  # noqa: E402

BASE14 = {  # (serif, mono, bold, italic) -> built-in font
    (False, False, False, False): "helv", (False, False, True, False): "hebo",
    (False, False, False, True): "heit", (False, False, True, True): "hebi",
    (True, False, False, False): "tiro", (True, False, True, False): "tibo",
    (True, False, False, True): "tiit", (True, False, True, True): "tibi",
    (False, True, False, False): "cour", (False, True, True, False): "cobo",
    (False, True, False, True): "coit", (False, True, True, True): "cobi",
}
MAX_SHRINK = 0.85


def spans_in(page, rect):
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            for sp in ln["spans"]:
                # a char belongs to the match if its centre is inside it (line boxes overlap
                # the lines above and below, so plain intersection picks those up)
                chars = [c for c in sp["chars"]
                         if rect.contains(pymupdf.Point((c["bbox"][0] + c["bbox"][2]) / 2,
                                                        (c["bbox"][1] + c["bbox"][3]) / 2))]
                if chars:
                    out.append((ln, sp, chars))
    return out


def background(page, rect):
    """Most common color around the text box, so the cover patch matches tinted backgrounds."""
    clip = pymupdf.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2) & page.rect
    pix = page.get_pixmap(clip=clip, dpi=144, annots=False)
    border = [(x, y) for x in range(pix.width) for y in (0, pix.height - 1)] + \
             [(x, y) for y in range(pix.height) for x in (0, pix.width - 1)]
    rgb = Counter(pix.pixel(x, y)[:3] for x, y in border).most_common(1)[0][0]
    return tuple(v / 255 for v in rgb)


def choose_font(doc, page, span, new_text, cache):
    """(fontname registered on the page, pymupdf.Font, description)."""
    flags = span["flags"]
    name = span["font"]
    lower = name.lower()
    bold = bool(flags & 16) or "bold" in lower or "black" in lower or "heavy" in lower
    italic = bool(flags & 2) or "italic" in lower or "oblique" in lower
    serif = bool(flags & 4) or any(k in lower for k in ("times", "serif", "georgia", "garamond", "cambria", "roman"))
    serif = serif and "sans" not in lower
    mono = bool(flags & 8) or any(k in lower for k in ("mono", "courier", "consol"))
    # 1. the embedded font, if it's extractable and covers every character we need
    for xref, ext, _typ, basefont, _n, _enc in page.get_fonts(full=False):
        if basefont.split("+")[-1] == name.split("+")[-1] and ext not in ("n/a", ""):
            key = f"emb{xref}"
            if key not in cache:
                try:
                    buf = doc.extract_font(xref)[3]
                    cache[key] = pymupdf.Font(fontbuffer=buf) if buf else None
                except Exception:
                    cache[key] = None
            f = cache[key]
            if f and all(f.has_glyph(ord(c)) for c in new_text if not c.isspace()):
                page.insert_font(fontname=key, fontbuffer=f.buffer)
                return key, f, f"embedded {name}"
            break
    # 2. nearest built-in font
    b14 = BASE14[(serif, mono, bold, italic)]
    return b14, pymupdf.Font(b14), f"standard {b14} (closest match to {name})"


def right_limit(page, line, hit, bnd):
    """How far the new text may extend: to the next text on the same line, or the page margin."""
    limit = bnd.x1 - 36
    for b in page.get_text("rawdict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            if abs(ln["bbox"][1] - line["bbox"][1]) > 2 and not pymupdf.Rect(ln["bbox"]).intersects(hit):
                continue
            for sp in ln["spans"]:
                for c in sp["chars"]:
                    x0 = c["bbox"][0]
                    if x0 >= hit.x1 - 0.5 and c["c"].strip() and abs(c["bbox"][1] - hit.y0) < hit.height:
                        limit = min(limit, x0 - 1.5)
    return limit


def apply_edit(doc, page, hit, new_text, cache):
    found = spans_in(page, hit)
    if not found:
        return {"status": "skipped", "reason": "no text under the match"}
    line, span, chars = found[0]
    if line["dir"] != (1.0, 0.0) and tuple(round(v, 3) for v in line["dir"]) != (1.0, 0.0):
        return {"status": "skipped", "reason": "text isn't horizontal; use the Word round trip"}
    if len({round(s["origin"][1]) for _, s, _ in found}) > 1:
        return {"status": "skipped", "reason": "the match spans several lines; use the Word round trip"}

    size, rgb = span["size"], span["color"]
    rgb = ((rgb >> 16) & 255) / 255, ((rgb >> 8) & 255) / 255, (rgb & 255) / 255
    origin = pymupdf.Point(chars[0]["origin"])
    fontname, font, fontdesc = choose_font(doc, page, span, new_text, cache)

    bnd = page.rect
    avail = right_limit(page, line, hit, bnd) - origin.x
    width = font.text_length(new_text, size)
    new_size = size
    if width > avail:
        new_size = size * avail / width
        if new_size < size * MAX_SHRINK:
            return {"status": "skipped",
                    "reason": f"'{new_text}' needs {width:.0f}pt but only {avail:.0f}pt is free on that line "
                              "(would need shrinking below 85%). Use a shorter wording or the Word round trip."}

    # Cover exactly the matched characters: shrink the box slightly so neighbours aren't caught.
    cover = pymupdf.Rect(chars[0]["bbox"][0] + 0.3, hit.y0 + 0.5, chars[-1]["bbox"][2] - 0.3, hit.y1 - 0.5)
    for _, _, cs in found[1:]:
        cover |= pymupdf.Rect(cs[-1]["bbox"][0] + 0.3, hit.y0 + 0.5, cs[-1]["bbox"][2] - 0.3, hit.y1 - 0.5)
    fill = background(page, hit)
    page.add_redact_annot(cover, fill=fill)
    kw = dict(images=pymupdf.PDF_REDACT_IMAGE_NONE)
    try:
        page.apply_redactions(graphics=pymupdf.PDF_REDACT_LINE_ART_NONE, **kw)
    except (TypeError, AttributeError):
        page.apply_redactions(**kw)
    page.insert_text(origin, new_text, fontsize=new_size, fontname=fontname, color=rgb)
    return {"status": "done", "font": fontdesc, "size": round(new_size, 2),
            "shrunk": round(new_size / size, 3) if new_size != size else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("edits", help="JSON file, or '-' for stdin")
    ap.add_argument("-o", "--out")
    ap.add_argument("--preview")
    ap.add_argument("--dpi", type=int, default=130)
    a = ap.parse_args()

    src = Path(a.pdf)
    out = Path(a.out) if a.out else src.with_name(f"{src.stem}-edited.pdf")
    if out.resolve() == src.resolve():
        sys.exit("Refusing to overwrite the input; pass a different -o.")
    edits = json.loads(sys.stdin.read() if a.edits == "-" else Path(a.edits).read_text("utf-8"))
    doc = pymupdf.open(src)
    report, changed, cache = [], set(), {}
    for e in edits:
        results = []
        for i in pages_of(doc, e.get("page")):
            page = doc[i]
            # search again after each edit on this page: redactions change the page
            hits = find_text(page, e["find"], e.get("occurrence", "all"), e.get("match_case", True))
            for hit in hits:
                r = apply_edit(doc, page, hit, e["replace"], cache)
                r["page"] = i + 1
                results.append(r)
                if r["status"] == "done":
                    changed.add(i)
        if not results:
            results = [{"status": "skipped", "reason": f"'{e['find']}' not found (exact case). "
                        "Check with inspect_pdf.py --find, or set \"match_case\": false."}]
        report.append({"find": e["find"], "replace": e["replace"], "results": results})

    doc.save(out, garbage=3, deflate=True)
    previews = []
    if a.preview and changed:
        Path(a.preview).mkdir(parents=True, exist_ok=True)
        done = pymupdf.open(out)
        previews = [render(done[i], str(Path(a.preview) / f"{out.stem}-p{i + 1}.png"), a.dpi) for i in sorted(changed)]
    done_n = sum(1 for r in report for x in r["results"] if x["status"] == "done")
    skipped = sum(1 for r in report for x in r["results"] if x["status"] != "done")
    out_json({"output": str(out), "edits": report, "replaced": done_n, "skipped": skipped, "previews": previews})


if __name__ == "__main__":
    main()
