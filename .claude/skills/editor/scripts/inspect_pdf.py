#!/usr/bin/env python3
"""Look inside a PDF before changing it.

  python inspect_pdf.py file.pdf                 overview: pages, text vs scanned, fonts, annotations, forms, signatures
  python inspect_pdf.py file.pdf --find "Total"  where a phrase is (page + coordinates) and the font it uses
  python inspect_pdf.py file.pdf --text 2        the text of page 2, in reading order
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import AUTHOR, find_text, out_json, pages_of, pymupdf, text_in  # noqa: E402


def overview(doc, path):
    pages = []
    for p in doc:
        text_chars = len(p.get_text("text").strip())
        images = len(p.get_images())
        kind = "text" if text_chars > 20 else ("scanned image (no text layer)" if images else "blank or vector-only")
        annots = [{"type": a.type[1], "author": a.info.get("title", ""), "content": a.info.get("content", "")[:60]}
                  for a in p.annots()]
        pages.append({
            "page": p.number + 1,
            "size_pt": [round(p.rect.width), round(p.rect.height)],
            "rotation": p.rotation,
            "kind": kind,
            "text_chars": text_chars,
            "images": images,
            "annotations": annots,
            "form_fields": len(list(p.widgets())),
        })
    fonts = sorted({f[3] for p in doc for f in p.get_fonts()})
    sig_fields = [w.field_name for p in doc for w in p.widgets() if w.field_type == pymupdf.PDF_WIDGET_TYPE_SIGNATURE]
    signed = bool(doc.get_sigflags() and doc.get_sigflags() > 0)
    scanned = [p["page"] for p in pages if p["kind"].startswith("scanned")]
    advice = []
    if scanned:
        advice.append(f"Pages {scanned} are images without text: text search, highlighting-by-phrase and text edits "
                      "won't find anything there. Run OCR first (ocrmypdf, or the pdf skill), or mark them by coordinates.")
    if signed:
        advice.append("This PDF is digitally signed. Any change, even a highlight, invalidates the signature. "
                      "Ask before editing, and keep the original.")
    if doc.is_encrypted:
        advice.append("The PDF is encrypted. Open it with its password first (doc.authenticate).")
    mine = sum(1 for p in pages for a in p["annotations"] if a["author"] == AUTHOR)
    if mine:
        advice.append(f"{mine} annotations were added earlier by {AUTHOR}; annotate.py can remove them with op 'remove'.")
    out_json({
        "file": str(path),
        "pages": doc.page_count,
        "encrypted": doc.is_encrypted,
        "digitally_signed": signed,
        "signature_fields": sig_fields,
        "has_form": doc.is_form_pdf,
        "fonts": fonts[:40],
        "page_details": pages,
        "advice": advice,
    })


def find(doc, phrase, page_spec):
    hits = []
    for i in pages_of(doc, page_spec):
        page = doc[i]
        spans = [s for b in page.get_text("dict")["blocks"] if b.get("type") == 0
                 for ln in b["lines"] for s in ln["spans"]]
        for n, rect in enumerate(find_text(page, phrase), 1):
            span = next((s for s in spans if pymupdf.Rect(s["bbox"]).intersects(rect)), None)
            hits.append({
                "page": i + 1,
                "occurrence_on_page": n,
                "rect": [round(v, 1) for v in rect],
                "font": span and span["font"],
                "size": span and round(span["size"], 1),
                "color": span and f"#{span['color']:06x}",
                "line_text": text_in(page, pymupdf.Rect(0, rect.y0, page.rect.width, rect.y1)).strip()[:120],
            })
    out_json({"phrase": phrase, "hits": hits, "count": len(hits)} if hits else
             {"phrase": phrase, "count": 0, "hint": "Not found. Check spelling, try a shorter piece of the phrase, "
              "or the page may be a scan without text (see the overview)."})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--find", help="phrase to locate")
    ap.add_argument("--pages", default=None, help="limit --find to pages, e.g. 2 or 1-3")
    ap.add_argument("--text", type=int, help="print the text of this page (1-based)")
    a = ap.parse_args()
    doc = pymupdf.open(a.pdf)
    if a.find:
        find(doc, a.find, a.pages)
    elif a.text:
        print(doc[a.text - 1].get_text("text", sort=True))
    else:
        overview(doc, a.pdf)


if __name__ == "__main__":
    main()
