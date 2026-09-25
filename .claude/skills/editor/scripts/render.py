#!/usr/bin/env python3
"""Render PDF pages to PNG so you can look at them (annotations included).

  python render.py file.pdf                      every page -> file-p1.png, file-p2.png ... next to the PDF
  python render.py file.pdf --pages 2 --grid     page 2 with a coordinate grid, for placing marks by eye
  python render.py file.pdf --pages 1 --clip 50,300,560,420 --dpi 200    zoom into a region
  python render.py file.pdf --out previews/

--grid labels are PDF points (1/72 inch, origin top-left, as the page is displayed). Pass those
numbers straight to annotate.py's "rect", "at", "from" and "to".
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import out_json, pages_of, pymupdf  # noqa: E402


def grid_render(page, dpi, step=50):
    """Render the page as displayed, then draw the grid in display coordinates on a scratch page."""
    pix = page.get_pixmap(dpi=dpi, annots=True)
    w, h = page.rect.width, page.rect.height          # page.rect already reflects rotation
    tmp = pymupdf.open()
    sheet = tmp.new_page(width=w, height=h)
    sheet.insert_image(sheet.rect, pixmap=pix)
    shape = sheet.new_shape()
    x = 0
    while x <= w:
        shape.draw_line((x, 0), (x, h))
        x += step
    y = 0
    while y <= h:
        shape.draw_line((0, y), (w, y))
        y += step
    shape.finish(color=(0.9, 0.2, 0.2), width=0.3, stroke_opacity=0.45)
    shape.commit()
    for x in range(0, int(w) + 1, step * 2):
        sheet.insert_text((x + 1.5, 7), str(x), fontsize=6, color=(0.85, 0.1, 0.1))
    for y in range(step * 2, int(h) + 1, step * 2):
        sheet.insert_text((1.5, y - 1.5), str(y), fontsize=6, color=(0.85, 0.1, 0.1))
    return sheet.get_pixmap(dpi=dpi)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--pages", default=None, help="e.g. 1 or 2-4 or 1,3 (default: all)")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--grid", action="store_true", help="overlay a coordinate grid (PDF points)")
    ap.add_argument("--clip", help="x0,y0,x1,y1 in PDF points (as displayed) to zoom into")
    ap.add_argument("--out", help="output folder (default: next to the PDF)")
    a = ap.parse_args()

    src = Path(a.pdf)
    out_dir = Path(a.out) if a.out else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(src)
    files = []
    for i in pages_of(doc, a.pages):
        page = doc[i]
        if a.grid:
            pix = grid_render(page, a.dpi)
        else:
            clip = None
            if a.clip:
                clip = pymupdf.Rect(*[float(v) for v in a.clip.split(",")])
                if page.rotation:
                    clip = (clip * page.derotation_matrix).normalize()
            pix = page.get_pixmap(dpi=a.dpi, clip=clip, annots=True)
        suffix = "-grid" if a.grid else "-clip" if a.clip else ""
        path = out_dir / f"{src.stem}-p{i + 1}{suffix}.png"
        pix.save(path)
        files.append(str(path))
    out_json({"rendered": files, "note": "Open the PNGs to look at the pages."})


if __name__ == "__main__":
    main()
