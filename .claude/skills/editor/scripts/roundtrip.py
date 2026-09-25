#!/usr/bin/env python3
"""PDF -> Word -> PDF, for rewrites that need text to reflow.

  python roundtrip.py probe  in.pdf --work tmp/     convert there and back WITHOUT edits and compare:
                                                    tells you whether this PDF survives the trip
  python roundtrip.py to-docx in.pdf out.docx       convert for editing (then edit the .docx with python-docx
                                                    or the docx skill)
  python roundtrip.py to-pdf  in.docx out.pdf       convert back (LibreOffice, or Microsoft Word if installed)

Always probe first. If the probe says "layout drift", the round trip would damage the
document even before your edits, so use edit_text.py (in-place) instead, or warn the user.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import out_json  # noqa: E402


def to_docx(pdf, docx):
    try:
        from pdf2docx import Converter
    except ImportError:
        sys.exit("pdf2docx is missing. Install it with: pip install pdf2docx")
    import logging
    logging.getLogger().setLevel(logging.ERROR)   # pdf2docx logs every page at INFO
    cv = Converter(str(pdf))
    try:
        cv.convert(str(docx))
    finally:
        cv.close()
    return str(docx)


def find_soffice():
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    for p in (r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
              "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if Path(p).exists():
            return p
    return None


def word_available():
    if platform.system() == "Windows":
        try:
            import win32com.client  # noqa: F401
            return "com"
        except ImportError:
            pass
    try:
        import docx2pdf  # noqa: F401
        return "docx2pdf"
    except ImportError:
        return None


def to_pdf(docx, pdf, engine="auto"):
    docx, pdf = Path(docx).resolve(), Path(pdf).resolve()
    soffice = find_soffice()
    word = word_available()
    if engine == "auto":
        engine = "word" if word and platform.system() == "Windows" else "libreoffice" if soffice else "word" if word else None
    if engine == "libreoffice":
        if not soffice:
            sys.exit("LibreOffice not found. Install it (winget install TheDocumentFoundation.LibreOffice / brew install --cask libreoffice), or use --engine word.")
        with tempfile.TemporaryDirectory() as tmp:
            # a private profile avoids clashing with a LibreOffice window the user has open
            profile = Path(tmp, "profile").as_uri()
            subprocess.run([soffice, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf",
                            "--outdir", tmp, str(docx)], check=True, capture_output=True, timeout=300)
            shutil.move(str(Path(tmp, docx.stem + ".pdf")), pdf)
        return str(pdf), "LibreOffice"
    if engine == "word":
        if word == "com":
            import win32com.client
            app = win32com.client.DispatchEx("Word.Application")
            app.Visible = False
            try:
                d = app.Documents.Open(str(docx), ReadOnly=True)
                d.ExportAsFixedFormat(str(pdf), 17)  # wdExportFormatPDF
                d.Close(False)
            finally:
                app.Quit()
            return str(pdf), "Microsoft Word"
        if word == "docx2pdf":
            from docx2pdf import convert
            convert(str(docx), str(pdf))
            return str(pdf), "Microsoft Word (docx2pdf)"
        sys.exit("Microsoft Word automation isn't available (pip install pywin32 on Windows, or docx2pdf on macOS).")
    sys.exit("No converter found. Install LibreOffice, or Microsoft Word plus pywin32/docx2pdf.")


def probe(pdf, work, engine):
    work = Path(work or tempfile.mkdtemp(prefix="pdf-roundtrip-"))
    work.mkdir(parents=True, exist_ok=True)
    stem = Path(pdf).stem
    docx = to_docx(pdf, work / f"{stem}.docx")
    back, used = to_pdf(docx, work / f"{stem}-roundtrip.pdf", engine)
    res = subprocess.run([sys.executable, str(Path(__file__).parent / "compare.py"), str(pdf), back,
                          "--out", str(work / "probe-diff")], capture_output=True, text=True)
    report = json.loads(res.stdout)
    worst = max((p["visual_change_percent"] for p in report["pages"]), default=0)
    ok = report["page_count"][0] == report["page_count"][1] and worst < 3
    out_json({
        "survives_round_trip": ok,
        "converter": used,
        "page_count": report["page_count"],
        "worst_page_change_percent": worst,
        "docx": docx,
        "roundtrip_pdf": back,
        "side_by_side": report["side_by_side"],
        "advice": ("Round trip is safe: edit the .docx, convert back, then compare against the original."
                   if ok else
                   "The document changes just from converting (see the side-by-side images). Prefer edit_text.py "
                   "for in-place edits, or tell the user the layout will shift before going ahead."),
    })


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe"); p.add_argument("pdf"); p.add_argument("--work"); p.add_argument("--engine", default="auto")
    d = sub.add_parser("to-docx"); d.add_argument("pdf"); d.add_argument("docx")
    f = sub.add_parser("to-pdf"); f.add_argument("docx"); f.add_argument("pdf"); f.add_argument("--engine", default="auto")
    a = ap.parse_args()
    if a.cmd == "probe":
        probe(a.pdf, a.work, a.engine)
    elif a.cmd == "to-docx":
        out_json({"docx": to_docx(a.pdf, a.docx)})
    else:
        path, used = to_pdf(a.docx, a.pdf, a.engine)
        out_json({"pdf": path, "converter": used})


if __name__ == "__main__":
    main()
