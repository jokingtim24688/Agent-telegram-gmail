#!/usr/bin/env python3
"""Compare two PDFs: did the layout survive, and what text changed?

  python compare.py original.pdf new.pdf --out diff/

Reports page counts and sizes, per-page visual change (% of pixels that differ), where on
each page the change is, and a word-level text diff. For pages that changed visually, it
writes a side-by-side PNG (before | after) with the changed regions boxed in red, so you can
look instead of trusting a number.

Verdict:
  "identical layout"     no text changes and every page within 0.5% of pixels
  "changed where edited" text changed, and any visual change is on pages whose text changed
  "layout drift"        pages moved or broke without matching text edits, or page count/size changed
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import out_json, pymupdf  # noqa: E402

DPI = 60
PIXEL_DELTA = 48  # grey-level difference that counts as "changed"


def gray(page):
    return page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY, annots=True)


def _regions(changed, width, height, cell=6):
    """Group changed pixels into separate boxes: mark coarse grid cells that contain a change,
    then flood-fill neighbouring cells together. `changed` is a set of (x, y) pixels."""
    cells = {(x // cell, y // cell) for x, y in changed}
    boxes, seen = [], set()
    for start in cells:
        if start in seen:
            continue
        stack, members = [start], []
        seen.add(start)
        while stack:
            cx, cy = stack.pop()
            members.append((cx, cy))
            for nx in (cx - 1, cx, cx + 1):
                for ny in (cy - 1, cy, cy + 1):
                    if (nx, ny) in cells and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        stack.append((nx, ny))
        xs = [m[0] for m in members]
        ys = [m[1] for m in members]
        boxes.append([min(xs) * cell, min(ys) * cell, min((max(xs) + 1) * cell, width), min((max(ys) + 1) * cell, height)])
    return sorted(boxes, key=lambda r: (r[1], r[0]))


def diff_pages(pa, pb):
    """(fraction of pixels changed, [changed regions as Rects in PDF points])."""
    a, b = gray(pa), gray(pb)
    if (a.width, a.height) != (b.width, b.height):
        return 1.0, []
    try:
        import numpy as np
        da = np.frombuffer(a.samples, dtype=np.uint8).reshape(a.height, a.stride)[:, :a.width]
        db = np.frombuffer(b.samples, dtype=np.uint8).reshape(b.height, b.stride)[:, :b.width]
        mask = np.abs(da.astype(int) - db.astype(int)) > PIXEL_DELTA
        frac = float(mask.mean())
        ys, xs = np.nonzero(mask)
        changed = set(zip(xs.tolist(), ys.tolist()))
    except ImportError:  # pure Python fallback (slower)
        sa, sb, st = a.samples, b.samples, a.stride
        changed = {(i % st, i // st) for i in range(len(sa)) if abs(sa[i] - sb[i]) > PIXEL_DELTA and i % st < a.width}
        frac = len(changed) / (a.width * a.height)
    scale = 72 / DPI
    return frac, [pymupdf.Rect(*(v * scale for v in r)) for r in _regions(changed, a.width, a.height)]


def words(page):
    return [w[4] for w in page.get_text("words", sort=True)]


def text_changes(wa, wb, limit=12):
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=wa, b=wb, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        out.append({"change": tag, "before": " ".join(wa[i1:i2])[:120], "after": " ".join(wb[j1:j2])[:120]})
        if len(out) >= limit:
            out.append({"change": "...", "before": "more changes not shown", "after": ""})
            break
    return out


def side_by_side(pa, pb, boxes, path):
    w, h = pa.rect.width, pa.rect.height
    tmp = pymupdf.open()
    sheet = tmp.new_page(width=w * 2 + 20, height=h + 24)
    sheet.insert_text((6, 14), "BEFORE", fontsize=10, color=(0.4, 0.4, 0.4))
    sheet.insert_text((w + 26, 14), "AFTER", fontsize=10, color=(0.4, 0.4, 0.4))
    sheet.insert_image(pymupdf.Rect(0, 20, w, 20 + h), pixmap=pa.get_pixmap(dpi=100, annots=True))
    sheet.insert_image(pymupdf.Rect(w + 20, 20, w * 2 + 20, 20 + h), pixmap=pb.get_pixmap(dpi=100, annots=True))
    for box in boxes:
        for dx in (0, w + 20):
            r = pymupdf.Rect(box.x0 + dx - 3, box.y0 + 20 - 3, box.x1 + dx + 3, box.y1 + 20 + 3)
            sheet.draw_rect(r, color=(0.9, 0.1, 0.1), width=1.2)
    sheet.get_pixmap(dpi=90).save(path)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out", help="folder for side-by-side PNGs of changed pages")
    ap.add_argument("--threshold", type=float, default=0.005, help="fraction of pixels (default 0.005 = 0.5%%)")
    a = ap.parse_args()

    A, B = pymupdf.open(a.before), pymupdf.open(a.after)
    out_dir = Path(a.out) if a.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    pages, drift, images = [], [], []
    for i in range(min(A.page_count, B.page_count)):
        pa, pb = A[i], B[i]
        same_size = abs(pa.rect.width - pb.rect.width) < 1 and abs(pa.rect.height - pb.rect.height) < 1
        frac, boxes = diff_pages(pa, pb) if same_size else (1.0, [])
        tchanges = text_changes(words(pa), words(pb))
        row = {"page": i + 1, "visual_change_percent": round(frac * 100, 2),
               "changed_regions_pt": [[round(v) for v in r] for r in boxes[:20]],
               "text_changes": tchanges}
        if not same_size:
            row["note"] = f"page size changed: {pa.rect} -> {pb.rect}"
        if frac > a.threshold and (not tchanges or not same_size):
            drift.append(i + 1)
        if (frac > 0 or tchanges) and out_dir:
                images.append(side_by_side(pa, pb, boxes, str(out_dir / f"compare-p{i + 1}.png")))
        pages.append(row)

    count_changed = A.page_count != B.page_count
    if count_changed or drift:
        verdict = "layout drift"
    elif any(p["text_changes"] or p["visual_change_percent"] > a.threshold * 100 for p in pages):
        verdict = "changed where edited"
    else:
        verdict = "identical layout"
    summary = {
        "verdict": verdict,
        "page_count": [A.page_count, B.page_count],
        "pages_with_unexplained_changes": drift,
        "pages": [p for p in pages if p["visual_change_percent"] > 0 or p["text_changes"] or p.get("note")],
        "side_by_side": images,
    }
    if count_changed:
        summary["warning"] = f"page count changed from {A.page_count} to {B.page_count}: text reflowed onto other pages"
    out_json(summary)


if __name__ == "__main__":
    main()
