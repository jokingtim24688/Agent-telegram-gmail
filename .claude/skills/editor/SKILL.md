---
name: editor
description: >-
  Mark up, fill in and edit existing PDFs the way a person with a pen would: highlight text in any color,
  underline, circle, box, arrows, stars, check marks, hand-drawn pen marks, handwriting-style notes, typed
  comment boxes and sticky notes; answer worksheets, quizzes, questionnaires and critique boxes (writing
  answers on the lines or in the boxes, filling bubbles, ticking checkboxes, circling True/False); change
  words in place (dates, names, amounts) with a matching font; and do bigger rewrites through a PDF to Word
  to PDF round trip that is checked for layout damage. Use it whenever the user hands over a PDF and wants
  something marked, highlighted, annotated, graded, commented, answered, completed, filled in or reworded,
  even if they just say "do this worksheet", "highlight the thesis", "circle the total", or "change the date
  on this". Works with the pdf skill, which handles fillable form fields, OCR, merging and splitting.
---

# Editor: mark up, answer and edit PDFs

A PDF can't be edited like a Word file, but almost everything a person does to one with a pen
or a PDF app can be done here, with the result checked visually before it's handed back.

## Setup (once per machine)

```bash
pip install pymupdf               # everything except the Word round trip
pip install pdf2docx              # only for round trips (also needs LibreOffice or Microsoft Word)
```

Run the scripts from `scripts/` in this skill's folder with `python scripts/<name>.py`. All of
them print JSON reports, and none overwrite their input (they write `<name>-marked.pdf`,
`-answered.pdf`, `-edited.pdf` or the path given with `-o`).

## Step 1: always look first

```bash
python scripts/inspect_pdf.py file.pdf              # pages, text vs scanned, forms, signatures, advice
python scripts/inspect_pdf.py file.pdf --text 2     # read page 2
python scripts/render.py file.pdf                   # PNG of every page, then LOOK at them
```

Read the text and look at every page before deciding anything. The inspect report's `advice`
covers the cases that change the plan:
- **Scanned pages (no text layer):** nothing can be found by its words. Run OCR through the
  **pdf skill** first, or work by coordinates (`render.py --grid`).
- **Digitally signed:** any change breaks the signature. Ask first, and keep the original.
- **Real fillable form fields** (`has_form: true`): those are the pdf skill's job (see below).

## Step 2: pick the job

| The user wants... | Do this |
|---|---|
| Highlights, underlines, circles, arrows, stars, check marks, notes, comments, "grade/mark this" | **Markup** → `annotate.py` |
| A worksheet, quiz, questionnaire or critique boxes completed, or blanks / lines / boxes answered | **Answer** → `fill.py` |
| A PDF with real fillable form fields filled in (tax, application or registration forms) | **pdf skill** → its `FORMS.md`, "Fillable fields" |
| A printed form of labels and blanks ("Name: ____", "SSN: ____") with no questions to think about | **pdf skill** `FORMS.md`, "Non-fillable fields", or `fill.py` (both work) |
| A few words changed: a date, name, price, typo | **In-place edit** → `edit_text.py` |
| Paragraphs rewritten, sections added, text that must reflow | **Round trip** → `roundtrip.py` |
| OCR, merge, split, rotate, extract tables, encrypt | **pdf skill** |

Many requests combine these. For a worksheet like "highlight the thesis in each paragraph, then
critique it in the box", run `annotate.py` first and then `fill.py` on its output.

**Using the pdf skill.** Invoke it (in Claude Code it's named `anthropic-skills:pdf`), and for
forms read its `FORMS.md` and follow those steps exactly. Its scripts check field IDs and box
overlaps before writing anything. If the pdf skill isn't available, fillable fields can still be
set with PyMuPDF: `for w in page.widgets(): w.field_value = ...; w.update()`.

## Markup: `annotate.py`

```bash
python scripts/annotate.py in.pdf ops.json -o out.pdf --preview previews/
```

`ops.json` is a list of operations. Every one can target a phrase (`"text"`), or coordinates
read off `render.py --grid` (`"rect"`, `"at"`, `"from"`, `"to"`). The full list is in
`python scripts/annotate.py -h`. The ones you'll use most:

```json
[
  {"op": "highlight", "text": "net 30 days", "color": "yellow"},
  {"op": "highlight", "text": "To readers a graphic", "to_text": "they went through.", "color": "green", "page": 1},
  {"op": "circle", "text": "$1,240.00"},
  {"op": "pen_arrow", "from": [470, 600], "to_text": "$1,240.00"},
  {"op": "star", "text": "Paragraph 3"},
  {"op": "check", "text": "Site measurement"},
  {"op": "cross", "text": "Revisions"},
  {"op": "pen_underline", "text": "Permit drawing set", "double": true},
  {"op": "textbox", "text": "Why 2 hours of revisions?", "near_text": "$170.00"},
  {"op": "sticky", "near_text": "billing@", "content": "Called 3/20"},
  {"op": "handwrite", "text": "Paid by check #512", "near_text": "Total due"},
  {"op": "remove"}
]
```

What to know:
- **Whole sentences:** use a range (`"text"` = the first few words, `"to_text"` = the last few)
  instead of pasting the full sentence. PDFs often have run-together words, line breaks and
  curly quotes that make exact long matches fail. Add `"page"` when the phrase repeats.
- **Highlight colors** are automatically the light highlighter shades ("blue" is light blue),
  so the text stays readable.
- **Pen marks** (`circle`, `pen_arrow`, `pen_underline`, `check`, `cross`, `star`, `bracket`,
  `ink`) are ink annotations with a natural wobble. `handwrite` uses a handwriting font: the
  user's own `.ttf` via `"font"`, otherwise Windows' Ink Free / Segoe Print, macOS's Bradley
  Hand, or Caveat (downloaded once, free license).
- **Placement** (`near_text`) looks for empty space: beside the text, then the margins, then
  the nearest empty band. The report says where each note went, and if it had to cover text.
- Everything except `handwrite` and `image` is a real annotation: the user can move or delete it
  in any PDF viewer, and `{"op": "remove"}` deletes every mark this skill added.

## Answering questions: `fill.py`

```bash
python scripts/fill.py scan in.pdf > scan.json
python scripts/fill.py apply in.pdf answers.json -o out.pdf --style typed --preview previews/
```

`scan` finds the questions (numbered items, "?" lines, and headings like "Paragraph 3:",
"Part B", "Passage 2"), and for each one:
- **spaces** to write in: underscore blanks, ruled lines, empty boxes, boxes with instructions
  printed at the top (the space below the instructions), or empty space under the question;
- **choices:** bubbles, checkboxes, lettered options, and pairs like True/False or Yes/No;
- **fields** that aren't questions: "Name: ____", "Date: ____", an "MLA heading" box.

It rebuilds boxes drawn as four separate lines (Google Docs and Word export them that way),
and a box pushed onto the next page stays attached to its question.

```json
[
  {"space": "p1-q1-s1", "text": "Paris"},
  {"space": "p1-q3-s1", "text": "Long answers continue onto the question's next ruled lines automatically."},
  {"choose": "p1-q2-c2"},
  {"choose": "p1-q5-c1"}, {"choose": "p1-q5-c3"},
  {"space": "p2-para3-s1", "star": true, "text": "Strong. The hook..."},
  {"space": "p1-f1", "text": "<the user's name>"}
]
```

`--style handwriting` writes in blue pen with the handwriting font. `typed` (the default) suits
digital hand-ins. Answers that can't fit even at the minimum size are **not written**. The
report gives the room available so you can shorten the answer and re-run. Choices are marked
the natural way: bubbles filled, boxes ticked, lettered options and True/False circled
(override with `"mark": "check" | "x" | "fill" | "circle"`).

### How to answer well

- **Read everything first**, including directions, examples, word banks and any passage the
  questions refer to. Follow the worksheet's own instructions ("explain why", "complete
  sentences", "show your work", "draw a star if strong"). Those are the grading criteria.
- **Answer correctly and specifically.** Quote or point to the text when the task is about a
  text. For math, get the arithmetic right (compute it; don't eyeball it), and write the
  working if asked.
- **Match the space.** A blank line gets a word or short phrase. A box gets a few sentences
  sized to the box (the scan reports its room).
- **Never invent personal information:** names, teacher or class, dates of birth, addresses,
  ID numbers, signatures, or personal opinions the user must own. Leave those spaces empty and
  ask. Fill them afterwards in a second `apply` run on the output. The same goes for anything
  legal, medical, tax or government: fill only with facts the user gave you.
- If you're unsure of an answer, say so in your message and don't pretend. Offer to change it.

## Small text changes: `edit_text.py`

```bash
python scripts/edit_text.py in.pdf edits.json -o out.pdf --preview previews/
# edits.json: [{"find": "March 3, 2026", "replace": "March 10, 2026"}, {"find": "$1,240.00", "replace": "$1,315.00", "page": 1}]
```

The old words are really removed (redacted), and the new ones are written at the same spot,
size and color, in the document's own font when it has all the needed letters (otherwise the
nearest standard font). The background color under the text is matched. The script refuses,
and explains why, when the new text would collide with the next words on the line, span
several lines, or need shrinking below 85%. Those cases need the round trip. Matching is
case-sensitive by default (`"match_case": false` to relax).

## Big rewrites: `roundtrip.py` (PDF → Word → PDF)

```bash
python scripts/roundtrip.py probe in.pdf --work tmp/        # 1. does this PDF survive the trip at all?
python scripts/roundtrip.py to-docx in.pdf tmp/in.docx      # 2. convert
#    3. edit tmp/in.docx with python-docx (or the docx skill)
python scripts/roundtrip.py to-pdf tmp/in.docx out.pdf      # 4. convert back (Word on Windows, else LibreOffice)
python scripts/compare.py in.pdf out.pdf --out diff/        # 5. what moved? look at diff/*.png
```

Always probe first. Converting shifts fonts, tables and columns in many documents even before
any edit. If the probe reports `survives_round_trip: false`, show the user the side-by-side
images and suggest in-place edits instead, or get their OK to accept the shifted layout.

## Step 3: check before handing back

Every script can write previews (`--preview dir`). **Look at them.** Check that each mark is
where it should be, that nothing covers text, that answers are in the right boxes, and that
highlights start and end on the right words. For edits and round trips, `compare.py` gives a
verdict (`identical layout` / `changed where edited` / `layout drift`) plus side-by-side images
with each change boxed. Fix and re-run until it's right. The ops and answers files make
re-runs cheap.

When done, tell the user what was done (counts by kind), anything left blank on purpose (and
why), anything the scripts refused, and the output path. Keep the original file untouched.
