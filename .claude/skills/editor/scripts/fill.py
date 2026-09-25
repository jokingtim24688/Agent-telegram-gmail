#!/usr/bin/env python3
"""Answer the questions on a worksheet, quiz, questionnaire or printed form (a PDF without
real form fields). For PDFs WITH fillable form fields, use the pdf skill's FORMS.md instead.

  python fill.py scan in.pdf                      find questions, answer spaces and choices (JSON)
  python fill.py apply in.pdf answers.json -o out.pdf --style typed|handwriting --preview prev/

scan finds, per page:
  questions  numbered lines ("1.", "2)", "Q3") or lines ending in "?"; text may run over 2-3 lines
  spaces     where an answer goes: underscore blanks "____", drawn answer lines, empty boxes, or
             empty space below a question with nothing else to write in
  choices    bubbles, checkboxes, lettered options "a) ...", and "True / False" / "Yes / No"
  fields     blanks that aren't under a question, e.g. "Name: ____", "Date: ____"
Every item has an id like "p1-q3-s1" (space), "p1-q2-c2" (choice) or "p1-f1" (field).

answers.json:
  [{"space": "p1-q1-s1", "text": "Paris"},
   {"space": "p1-q3-s1", "text": "Sunlight scatters off air molecules ... (long answers continue onto the next lines of the same question)"},
   {"choose": "p1-q2-c2"},                                  bubble filled / box ticked / option circled
   {"choose": "p1-q5-c3", "mark": "x"},                     mark: auto | check | x | fill | circle
   {"space": "p1-f1", "text": "Tim Jokinen"},
   {"space": "p1-para3-s1", "star": true, "text": "Strong: ..."},   hand-drawn star, then the text beside it
   {"after_text": "Signature:", "text": "..."}  or  {"at": [x, y], "text": "..."}   (y = baseline)
   ... any answer may also set "style", "size", "color"]

Nothing is guessed about fit: if an answer can't fit its space even at the minimum size, it is
NOT written, and the report says how much room there is so the answer can be shortened.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (AUTHOR, color, find_text, hand_check, hand_cross, hand_ellipse, hand_star, handwrite_lines,  # noqa: E402
                     handwriting_font, out_json, pymupdf, render, tag, to_unrotated, wrap)

Q_START = re.compile(r"^\s*(?:Q(?:uestion)?\s*)?(\d{1,3})\s*[.)]\s+\S", re.I)
LETTER_OPT = re.compile(r"^\(?([a-hA-H])[).]$")
HEADING = re.compile(r"^\s*(Paragraph|Passage|Part|Section|Problem|Exercise|Question|Prompt|Excerpt|Text|Source|Activity|Task)"
                     r"\s+([0-9]{1,3}|[A-Z])\s*[:.)]?\s*$", re.I)
PAIRS = [("true", "false"), ("yes", "no"), ("agree", "disagree"), ("t", "f"), ("y", "n")]
STYLE_SIZE = {"typed": (11, 7), "handwriting": (15, 10)}   # default, minimum


# ------------------------------------------------------------------ scanning

def _lines(page):
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            chars = [c for s in ln["spans"] for c in s["chars"]]
            text = "".join(c["c"] for c in chars)
            if text.strip():
                size = ln["spans"][0]["size"] if ln["spans"] else 11
                out.append({"text": text, "rect": pymupdf.Rect(ln["bbox"]), "chars": chars, "size": size})
    return sorted(out, key=lambda l: (round(l["rect"].y0), l["rect"].x0))


def _underscore_runs(line):
    """Runs of 3+ underscores inside a text line -> (rect, baseline)."""
    runs, cur = [], []
    for c in line["chars"] + [{"c": "", "bbox": (0, 0, 0, 0), "origin": (0, 0)}]:
        if c["c"] == "_":
            cur.append(c)
        else:
            if len(cur) >= 3:
                r = pymupdf.Rect(cur[0]["bbox"]) | pymupdf.Rect(cur[-1]["bbox"])
                runs.append((r, cur[0]["origin"][1]))
            cur = []
    return runs


def _is_option_row(line, marks):
    """Answer-option rows ("a) 1861", or a row of bubbles/boxes) aren't part of the question text."""
    first = line["text"].strip().split(" ")[0]
    if LETTER_OPT.match(first):
        return True
    return any(abs((m.y0 + m.y1) / 2 - (line["rect"].y0 + line["rect"].y1) / 2) < 6 for m in marks)


def _words(page):
    return [(pymupdf.Rect(w[:4]), w[4]) for w in page.get_text("words")]


def _segments(page):
    """Stroked drawings -> (horizontal segments, vertical segments, closed rects, small marks).
    Filled-only shapes (backgrounds, highlight fills) are ignored: they are decoration, not blanks."""
    H, V, rects, bubbles = [], [], [], []
    big = page.rect.width * page.rect.height * 0.8
    for d in page.get_drawings():
        if d.get("color") is None:          # no stroke: a fill (page background, shading)
            continue
        r = pymupdf.Rect(d["rect"])
        if r.width * r.height > big:
            continue
        kinds = {it[0] for it in d["items"]}
        if "c" in kinds and 5 <= r.width <= 18 and abs(r.width - r.height) < 2.5:
            bubbles.append(r)
            continue
        for it in d["items"]:
            if it[0] == "l":
                p1, p2 = it[1], it[2]
                if abs(p1.y - p2.y) < 0.8:
                    H.append(pymupdf.Rect(min(p1.x, p2.x), p1.y, max(p1.x, p2.x), p1.y))
                elif abs(p1.x - p2.x) < 0.8:
                    V.append(pymupdf.Rect(p1.x, min(p1.y, p2.y), p1.x, max(p1.y, p2.y)))
            elif it[0] == "re":
                rr = pymupdf.Rect(it[1])
                if rr.height <= 1.5:
                    H.append(pymupdf.Rect(rr.x0, rr.y1, rr.x1, rr.y1))
                else:
                    rects.append(rr)
            elif it[0] == "qu":
                rects.append(it[1].rect)
    return H, V, rects, bubbles


def _boxes_from_lines(H, V, tol=3):
    """Rebuild rectangles drawn as four separate lines (Google Docs, Word and many exporters
    draw boxes that way). Returns (boxes, horizontal segments that aren't box edges)."""
    boxes, used = [], set()
    for i, top in enumerate(H):
        for j, bot in enumerate(H):
            if j == i or bot.y0 - top.y0 < 12 or abs(top.x0 - bot.x0) > tol or abs(top.x1 - bot.x1) > tol:
                continue
            def side(x):
                return any(abs(v.x0 - x) <= tol and v.y0 <= top.y0 + tol and v.y1 >= bot.y0 - tol for v in V)
            if side(top.x0) and side(top.x1):
                boxes.append(pymupdf.Rect(min(top.x0, bot.x0), top.y0, max(top.x1, bot.x1), bot.y0))
                used.update((i, j))
    # keep only the tightest box for each top edge (a top line can pair with several bottoms)
    boxes.sort(key=lambda b: (round(b.y0), b.height))
    tight = []
    for b in boxes:
        if not any(abs(b.y0 - t.y0) < tol and abs(b.x0 - t.x0) < tol and abs(b.x1 - t.x1) < tol for t in tight):
            tight.append(b)
    return tight, [h for k, h in enumerate(H) if k not in used]


def _drawings(page):
    """Answer lines, answer boxes, checkboxes and bubbles drawn as vector graphics.
    Boxes come back as (answer_area, label): a box with instructions printed at its top
    ("Critique Box: explain why...") has its answer area below that text."""
    words = _words(page)
    H, V, rects, bubbles = _segments(page)
    line_boxes, H = _boxes_from_lines(H, V)
    squares, boxes = [], []
    for r in rects + line_boxes:
        if 5 <= r.width <= 18 and abs(r.width - r.height) < 2.5:
            squares.append(r)
        elif r.width >= 36 and r.height >= 16:
            inside = [(w, t) for w, t in words if r.contains(w)]
            if not inside:
                boxes.append((r, None))
                continue
            last = max(w.y1 for w, _ in inside)
            if r.y1 - last >= 22:           # printed instructions at the top, room to write below
                label = " ".join(t for _, t in sorted(inside, key=lambda wt: (round(wt[0].y0), wt[0].x0)))
                boxes.append((pymupdf.Rect(r.x0, last + 2, r.x1, r.y1), label[:90]))
    # an answer line has empty space above it; text right above means it's an underline or table rule
    answer_lines = [ln for ln in H if ln.width >= 36 and not any(
        w.intersects(pymupdf.Rect(ln.x0 + 2, ln.y0 - 12, ln.x1 - 2, ln.y0 - 1)) for w, _ in words)]
    return answer_lines, boxes, squares, bubbles


def scan_page(page):
    pno = page.number + 1
    lines = _lines(page)
    words = _words(page)
    answer_lines, boxes, squares, bubbles = _drawings(page)

    # questions: a numbered line (or one ending in "?") plus its continuation lines
    marks = bubbles + squares
    questions = []
    for ln in lines:
        m = Q_START.match(ln["text"])
        h = HEADING.match(ln["text"])
        if h:
            questions.append({"number": f"{h.group(1)[:4].lower()}{h.group(2).lower()}", "heading": True,
                              "rect": pymupdf.Rect(ln["rect"]), "text": ln["text"].strip(), "size": ln["size"]})
        elif m or (ln["text"].rstrip().endswith("?") and not questions):
            questions.append({"number": m.group(1) if m else str(len(questions) + 1),
                              "rect": pymupdf.Rect(ln["rect"]), "text": ln["text"].strip(), "size": ln["size"]})
        elif questions and not questions[-1].get("heading") and 0 < ln["rect"].y0 - questions[-1]["rect"].y1 < ln["size"] * 0.8 \
                and not _underscore_runs(ln) and len(questions[-1]["text"]) < 400 \
                and not _is_option_row(ln, marks):
            questions[-1]["text"] += " " + ln["text"].strip()      # wrapped question text
            questions[-1]["rect"] |= ln["rect"]

    def owner(y):
        """Index of the question an item at height y belongs to (the last one starting above it)."""
        idx = None
        for i, q in enumerate(questions):
            if q["rect"].y0 - 3 <= y:
                idx = i
        return idx

    spaces = {i: [] for i in range(len(questions))}
    choices = {i: [] for i in range(len(questions))}
    fields = []

    def add_space(kind, rect, baseline, label=None):
        i = owner(rect.y0)
        item = {"kind": kind, "rect": rect, "baseline": baseline}
        if label and kind == "box":
            item["label"] = label
        if i is None:
            item["label"] = label
            fields.append(item)
        else:
            spaces[i].append(item)

    for ln in lines:
        for r, base in _underscore_runs(ln):
            label = "".join(c["c"] for c in ln["chars"] if c["bbox"][2] <= r.x0 + 0.5).strip()
            label = re.split(r"_{3,}", label)[-1].strip() or label
            add_space("blank", r, base, label[-40:])
    for r in answer_lines:
        add_space("line", pymupdf.Rect(r.x0, r.y0 - 16, r.x1, r.y0), r.y0 - 2.5)
    for r, label in boxes:
        if label is None:   # empty box: use the text line just above it as its label ("MLA heading:")
            above = [l for l in lines if 0 <= r.y0 - l["rect"].y1 <= 24 and l["rect"].x0 < r.x1]
            label = above[-1]["text"].strip() if above else None
        add_space("box", r, None, label)

    # choices: bubbles / squares with the text to their right
    for kind, marks in (("bubble", bubbles), ("checkbox", squares)):
        for m in marks:
            i = owner(m.y0)
            if i is None:
                continue
            row = sorted([(w, t) for w, t in words if abs((w.y0 + w.y1) / 2 - (m.y0 + m.y1) / 2) < 6 and w.x0 > m.x1],
                         key=lambda wt: wt[0].x0)
            label, rect = [], None
            for w, t in row:
                if any(o.x0 > m.x1 + 1 and o.x0 < w.x0 for o in marks):   # stop at the next mark
                    break
                label.append(t)
                rect = w if rect is None else rect | w
            choices[i].append({"marker": kind, "rect": m, "text": " ".join(label), "text_rect": rect})
    # lettered options without drawn marks, and True/False style word pairs
    for i, q in enumerate(questions):
        if choices[i]:
            continue
        nxt = questions[i + 1]["rect"].y0 if i + 1 < len(questions) else page.rect.y1
        region = [(w, t) for w, t in words if q["rect"].y0 - 1 <= w.y0 < nxt]
        for k, (w, t) in enumerate(region):
            if LETTER_OPT.match(t) and w.y0 > q["rect"].y0 + 1:
                text_words = []
                for w2, t2 in region[k + 1:]:
                    if LETTER_OPT.match(t2) or abs(w2.y0 - w.y0) > 3:
                        break
                    text_words.append((w2, t2))
                r = w
                for w2, _ in text_words:
                    r = r | w2
                choices[i].append({"marker": "letter", "rect": r, "text": " ".join([t] + [t2 for _, t2 in text_words]),
                                   "text_rect": r})
        # option pairs like "True / False" or "Yes   No": both words on one line, close together.
        # The last such pair wins, so "True or False: ... True / False" picks the answer options.
        pair = []
        for a_word, b_word in PAIRS:
            for k, (w, t) in enumerate(region):
                if t.strip(".,:;()/").lower() != a_word:
                    continue
                for w2, t2 in region[k + 1:k + 4]:
                    if t2.strip(".,:;()/").lower() == b_word and abs(w2.y0 - w.y0) < 3 and w2.x0 - w.x1 < 60:
                        pair = [(w, t), (w2, t2)]
        if len(pair) >= 2 and not choices[i]:
            for w, t in pair:
                choices[i].append({"marker": "word", "rect": w, "text": t.strip(".,:;()"), "text_rect": w})

    # a question with nowhere to write: offer the empty space below it
    all_h, all_v, _, _ = _segments(page)     # box edges too: free space never crosses a drawn line
    taken = [w for w, _ in words] + answer_lines + [b for b, _ in boxes] + all_h
    for i, q in enumerate(questions):
        if spaces[i] or choices[i]:
            continue
        top = q["rect"].y1 + 3
        below = [t.y0 for t in taken if t.y0 > top and t.x1 > q["rect"].x0 and t.x0 < page.rect.x1 - 36]
        bottom = min(below + [page.rect.y1 - 40]) - 4
        if bottom - top >= 16:
            spaces[i].append({"kind": "space", "rect": pymupdf.Rect(q["rect"].x0 + 14, top, page.rect.x1 - 72, bottom),
                              "baseline": None})

    out_q = []
    for i, q in enumerate(questions):
        qid = f"p{pno}-{q['number']}" if q.get("heading") else f"p{pno}-q{q['number']}"
        sp = sorted(spaces[i], key=lambda s: (round(s["rect"].y0), s["rect"].x0))
        out_q.append({
            "id": qid, "text": q["text"], "rect": _r(q["rect"]),
            "spaces": [{"id": f"{qid}-s{k}", "kind": s["kind"], "rect": _r(s["rect"]), "label": s.get("label"),
                        "baseline": s["baseline"] and round(s["baseline"], 1),
                        "room": _room(s)} for k, s in enumerate(sp, 1)],
            "choices": [{"id": f"{qid}-c{k}", "marker": c["marker"], "text": c["text"], "rect": _r(c["rect"]),
                         "text_rect": c["text_rect"] and _r(c["text_rect"])}
                        for k, c in enumerate(sorted(choices[i], key=lambda c: (round(c["rect"].y0), c["rect"].x0)), 1)],
        })
    out_f = [{"id": f"p{pno}-f{k}", "label": f.get("label"), "kind": f["kind"], "rect": _r(f["rect"]),
              "baseline": f["baseline"] and round(f["baseline"], 1), "room": _room(f)}
             for k, f in enumerate(sorted(fields, key=lambda f: (round(f["rect"].y0), f["rect"].x0)), 1)]
    return {"page": pno, "questions": out_q, "fields": out_f}


def _r(rect):
    return [round(v, 1) for v in rect]


def _room(space):
    r = space["rect"]
    helv = pymupdf.Font("helv")
    per_line = int(r.width / helv.text_length("n", 11))
    lines = 1 if space["kind"] in ("blank", "line") else max(1, int((r.height - 8) // 14))
    return f"about {per_line} characters per line at 11pt" + ("" if lines == 1 else f", {lines} lines")


def scan(doc):
    pages = [scan_page(p) for p in doc]
    # An answer box at the top of a page, before any question on it, usually belongs to the
    # last question of the previous page (the box got pushed over the page break).
    last_q = None
    for pr in pages:
        if last_q is not None:
            keep = []
            for f in pr["fields"]:
                if f["kind"] in ("box", "line") and not (f.get("label") or "").rstrip().endswith(":"):
                    f = dict(f, id=f"{last_q['id']}-s{len(last_q['spaces']) + 1}", page=pr["page"],
                             note="continues from the previous page")
                    f.pop("label", None) if f.get("label") is None else None
                    last_q["spaces"].append(f)
                else:
                    keep.append(f)
            pr["fields"] = keep
        if pr["questions"]:
            last_q = pr["questions"][-1]
    n_q = sum(len(p["questions"]) for p in pages)
    notes = []
    for p in pages:
        if not doc[p["page"] - 1].get_text("text").strip():
            notes.append(f"Page {p['page']} has no text layer (scanned). Run OCR first (pdf skill), or answer by coordinates.")
    if doc.is_form_pdf:
        notes.append("This PDF has real fillable form fields: fill those with the pdf skill (FORMS.md), then use this "
                     "for any printed questions that aren't fields.")
    return {"pages": pages, "questions": n_q, "notes": notes}


# ------------------------------------------------------------------ applying

def _index(scan_result):
    idx = {}
    for p in scan_result["pages"]:
        for q in p["questions"]:
            for s in q["spaces"]:
                idx[s["id"]] = dict(s, page=s.get("page", p["page"]), question=q["id"],
                                    siblings=[x["id"] for x in q["spaces"]])
            for c in q["choices"]:
                idx[c["id"]] = dict(c, page=p["page"], question=q["id"])
        for f in p["fields"]:
            idx[f["id"]] = dict(f, page=p["page"], siblings=[f["id"]])
    return idx


class Writer:
    def __init__(self, doc, style, ink_color, font_path):
        self.doc, self.style, self.rgb = doc, style, ink_color
        self.hand_path, self.hand_name = (font_path if font_path is not None else (None, None))
        self.hand_font = None

    def font(self, style):
        if style == "handwriting":
            if self.hand_font is None:
                if self.hand_path is None:
                    self.hand_path, self.hand_name = handwriting_font()
                self.hand_font = pymupdf.Font(fontfile=self.hand_path) if self.hand_path else pymupdf.Font("heit")
            return self.hand_font
        return pymupdf.Font("helv")

    def write_line(self, page, x, baseline, text, size, style, rgb, seed):
        if style == "handwriting":
            handwrite_lines(page, pymupdf.Rect(x, baseline - size, x + 2000, baseline + 4), [text], self.font(style),
                            self.hand_path, size, rgb, seed)
        else:
            page.insert_text((x, baseline), text, fontsize=size, fontname="helv", color=rgb)


def fit_lines(text, font, size, min_size, widths):
    """Largest size (>= min_size) at which text wraps into the given line widths. -> (size, lines) or None."""
    s = size
    while s >= min_size - 1e-6:
        out, rest = [], text.split()
        for w in widths:
            if not rest:
                break
            line = ""
            while rest and font.text_length((line + " " + rest[0]).strip(), s) <= w:
                line = (line + " " + rest.pop(0)).strip()
            if not line:            # a single word longer than the line
                break
            out.append(line)
        if not rest:
            return s, out
        s -= 0.5
    return None


def apply(doc, answers, style, rgb, font_arg, scan_result):
    idx = _index(scan_result)
    writer = Writer(doc, style, rgb, (font_arg, Path(font_arg).stem) if font_arg else None)
    report, changed, used = [], set(), set()
    for n, a in enumerate(answers, 1):
        entry = {"n": n, "target": a.get("space") or a.get("choose") or a.get("after_text") or a.get("at")}
        try:
            st = a.get("style", style)
            size0, min_size = STYLE_SIZE[st]
            size0 = float(a.get("size", size0))
            rgb_a = color(a["color"]) if a.get("color") else rgb
            if "choose" in a:
                c = idx.get(a["choose"])
                if not c or "marker" not in c:
                    raise ValueError(f"no choice with id {a['choose']!r} (run scan)")
                page = doc[c["page"] - 1]
                _mark(page, c, a.get("mark", "auto"), rgb_a, n)
                entry.update(done=True, page=c["page"], marked=c["text"])
                changed.add(c["page"] - 1)
            elif "space" in a:
                s = idx.get(a["space"])
                if not s or "kind" not in s:
                    raise ValueError(f"no space with id {a['space']!r} (run scan)")
                if a["space"] in used:
                    raise ValueError(f"{a['space']} already holds an earlier answer (or its overflow)")
                page = doc[s["page"] - 1]
                font = writer.font(st)
                if s["kind"] in ("blank", "line"):
                    # this line plus the following unused line-type spaces of the same question
                    chain = [s]
                    for sid in s["siblings"][s["siblings"].index(a["space"]) + 1:]:
                        nx = idx[sid]
                        if nx["kind"] != "line" or sid in used:
                            break
                        chain.append(nx)
                    widths = [x["rect"][2] - x["rect"][0] - 4 for x in chain]
                    fit = fit_lines(a["text"], font, size0, min_size, widths)
                    if not fit:
                        raise ValueError(f"doesn't fit: {len(chain)} line(s), {s['room']}. Shorten the answer.")
                    size, lines = fit
                    for k, (sp, line) in enumerate(zip(chain, lines)):
                        writer.write_line(page, sp["rect"][0] + 2, sp["baseline"] - (0 if sp["kind"] == "line" else 1.5),
                                          line, size, st, rgb_a, n * 31 + k)
                        used.add(next(i for i in idx if idx[i] is sp) if sp is not s else a["space"])
                    entry.update(done=True, page=s["page"], size=size, lines_used=len(lines))
                else:
                    r = pymupdf.Rect(s["rect"])
                    inner = pymupdf.Rect(r.x0 + 5, r.y0 + 4, r.x1 - 5, r.y1 - 3)
                    if a.get("star"):   # "draw a star in the box": star at the start, text beside it
                        star = hand_star(inner.x0 + 9, inner.y0 + 9, 17, n * 13)
                        ink_a = page.add_ink_annot([[tuple(p) for p in st_] for st_ in star])
                        ink_a.set_colors(stroke=color(a.get("star_color", "orange")))
                        ink_a.set_border(width=1.6)
                        tag(ink_a)
                        inner.x0 += 24
                    s_try = size0
                    while True:
                        lh = s_try * (1.15 if st == "handwriting" else 1.3)
                        n_lines = max(1, int((inner.height - s_try * 0.3) // lh) + 1)
                        fit = fit_lines(a["text"], font, s_try, s_try, [inner.width] * n_lines)
                        if fit or s_try <= min_size:
                            break
                        s_try -= 0.5
                    if not fit:
                        raise ValueError(f"doesn't fit in the {s['kind']} ({s['room']}). Shorten the answer.")
                    size, lines = fit
                    lh = size * (1.15 if st == "handwriting" else 1.3)
                    for k, line in enumerate(lines):
                        writer.write_line(page, inner.x0, inner.y0 + size + k * lh, line, size, st, rgb_a, n * 31 + k)
                    entry.update(done=True, page=s["page"], size=size, lines_used=len(lines))
                used.add(a["space"])
                changed.add(s["page"] - 1)
            else:
                page = doc[int(a.get("page", 1)) - 1]
                if "after_text" in a:
                    hits = find_text(page, a["after_text"], "first")
                    if not hits:
                        raise ValueError(f"after_text {a['after_text']!r} not found on page {page.number + 1}")
                    x, base = hits[0].x1 + 5, hits[0].y1 - hits[0].height * 0.22
                else:
                    pt = to_unrotated(page, a["at"])
                    x, base = pt.x, pt.y
                writer.write_line(page, x, base, a["text"], size0, st, rgb_a, n * 31)
                entry.update(done=True, page=page.number + 1, size=size0)
                changed.add(page.number)
        except (ValueError, KeyError) as e:
            entry.update(done=False, problem=str(e))
        report.append(entry)
    return report, changed, writer


def _mark(page, c, mark, rgb, seed):
    r = pymupdf.Rect(c["rect"])
    kind = c["marker"]
    if mark == "auto":
        mark = {"bubble": "fill", "checkbox": "check", "letter": "circle", "word": "circle"}[kind]
    if mark == "fill":
        center = pymupdf.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
        page.draw_circle(center, min(r.width, r.height) * 0.36, color=rgb, fill=rgb, width=0)
        return
    if mark == "circle":
        target = pymupdf.Rect(c["text_rect"]) if c.get("text_rect") and kind in ("bubble", "checkbox") else r
        if kind in ("bubble", "checkbox") and c.get("text_rect"):
            target = r | pymupdf.Rect(c["text_rect"])
        strokes = hand_ellipse(target, 3, seed)
    elif mark == "check":
        s = max(r.height, 9) * 1.15
        strokes = hand_check(r.x0 + r.width * 0.1, r.y0 - s * 0.25, s, seed)
    elif mark == "x":
        strokes = hand_cross(pymupdf.Rect(r.x0 + 1.5, r.y0 + 1.5, r.x1 - 1.5, r.y1 - 1.5), seed)
    else:
        raise ValueError(f"unknown mark {mark!r}")
    a = page.add_ink_annot([[tuple(p) for p in s] for s in strokes])
    a.set_colors(stroke=rgb)
    a.set_border(width=1.5)
    tag(a)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("pdf")
    p = sub.add_parser("apply"); p.add_argument("pdf"); p.add_argument("answers")
    p.add_argument("-o", "--out"); p.add_argument("--preview"); p.add_argument("--dpi", type=int, default=110)
    p.add_argument("--style", choices=["typed", "handwriting"], default="typed")
    p.add_argument("--color", default=None, help="ink color (default: black for typed, pen blue for handwriting)")
    p.add_argument("--font", help="handwriting .ttf (default: your system's or Caveat)")
    a = ap.parse_args()

    doc = pymupdf.open(a.pdf)
    if a.cmd == "scan":
        out_json(scan(doc))
        return
    src = Path(a.pdf)
    out = Path(a.out) if a.out else src.with_name(f"{src.stem}-answered.pdf")
    if out.resolve() == src.resolve():
        sys.exit("Refusing to overwrite the input; pass a different -o.")
    answers = json.loads(sys.stdin.read() if a.answers == "-" else Path(a.answers).read_text("utf-8"))
    answers = answers.get("answers", answers) if isinstance(answers, dict) else answers
    rgb = color(a.color) if a.color else (color("ink") if a.style == "handwriting" else (0.05, 0.05, 0.1))
    report, changed, writer = apply(doc, answers, a.style, rgb, a.font, scan(doc))
    doc.save(out, garbage=3, deflate=True)
    previews = []
    if a.preview and changed:
        Path(a.preview).mkdir(parents=True, exist_ok=True)
        done = pymupdf.open(out)
        previews = [render(done[i], str(Path(a.preview) / f"{out.stem}-p{i + 1}.png"), a.dpi) for i in sorted(changed)]
    problems = [r for r in report if not r["done"]]
    res = {"output": str(out), "answers": report, "written": len(report) - len(problems),
           "problems": len(problems), "previews": previews}
    if a.style == "handwriting" or any(x.get("style") == "handwriting" for x in answers):
        res["handwriting_font"] = writer.hand_name or "Helvetica italic (no handwriting font found)"
    out_json(res)


if __name__ == "__main__":
    main()
