# Progress

## 2026-09-23 — Session start (cloud session)

**Request:** `/anti-vibe-polish`, with the note: "This chat is only about the agent task. Use the main local AI chat for context. This will not be in the app. Try again."

### What the cloud session found
- The repo `jokingtim24688/Agent-telegram-gmail` is **empty**: no commits and no branches on the remote. This file is the first commit.
- The repo has no `graphify-out/wiki/index.md`, so there is no Graphify wiki to read.
- The "main chat local AI" context and the local Graphify/OmniRoute services run on the user's own machine. This cloud container can't reach them.
- `anti-vibe-polish` is a checklist for cleaning up the look of an existing UI. The request says this work won't be in the app, and there's no code yet, so there's nothing for it to check.

### Blocked on
Context about the agent task. For example:
- What the agent should do (for example: Telegram bot ↔ Gmail: read, summarize, draft or send replies?)
- Language and runtime, and which LLM the agent uses (local model through OmniRoute? Claude API?)
- Any code or notes from the local chat (paste them here, or push them to this repo)

## 2026-09-23 — Spec received

**Hardware:** smart glasses built on an ESP32-S3 "Sense" board (XIAO ESP32S3 Sense: OV2640 camera + PDM mic).
**PC:** RTX 4060 (8 GB VRAM) and a Ryzen 5 5600 (6 cores) on Windows now; Apple Silicon Mac later. It has to run on both.
**Built with:** Google Antigravity.
**Flow wanted:** the board holds Telegram and Gmail credentials and sends its captures to a second Telegram account that the AI controls. The AI runs on the PC using a local LLM (Hermes, Qwen or Llama).

### Model decision (draft)
- The glasses send camera frames, so the model needs **vision**. That rules out Hermes (text only; Hermes 4 at 14B+ doesn't fit in 8 GB).
- Llama 3.2 Vision 11B needs about 7.9 GB at Q4, which only just fits in 8 GB and runs slowly.
- **Qwen3-VL 8B through Ollama** needs about 6 GB at Q4, has strong vision and OCR, and supports tool calling. Ollama runs on CUDA (Windows) and Metal (Mac).

### Open decision: which Telegram account the AI uses
- The user plans to buy a Telegram user account on g2g.com for the AI.
- The risks: Telegram accounts can't be transferred under its ToS. Resold accounts get banned a lot, especially when they log in from a new device and then run automation. The seller keeps the phone number, so they can recover the account and read everything sent through it, including every glasses photo and any Gmail content the AI relays.
- The alternatives:
  - **(A) a free official bot plus a private-channel relay.** Bots can't see other bots' messages in groups, but a bot that is a channel admin does receive `channel_post` updates. This is the documented workaround.
  - **(B) a user account the user registers with their own second number,** used as a Telethon userbot with the user's own api_id from my.telegram.org.
- **Decided (user):** (B), a second account the user owns. Gmail: each device gets its own account, used **only as a backup** route.
- **Decided (user):** the AI, the glasses and the user share one Telegram group. Each member only reads messages from assigned senders. The glasses obey only the AI; the AI answers only the user and the glasses. Senders are matched by numeric user ID, looked up from @usernames (display names can be copied).

## 2026-09-23 — v1 built ("Loupe")

### Done
- [x] **Firmware** `firmware/glasses/` for the XIAO ESP32S3 Sense (PlatformIO): camera at SVGA JPEG. A button press or `/snap` from the AI sends the frame with Bot API `sendPhoto` to the group. If that fails, the frame goes out by Gmail SMTP from the glasses' own account. `/ping` replies with a `#status` line. Credentials live in NVS, written over USB serial JSON. TLS is checked against bundled root CAs (Go Daddy G2, GTS R1/R4, GlobalSign).
- [x] **Desktop** `desktop/glasses_agent/`, which runs on Windows and macOS:
  - Telethon client for the AI account. It creates the group itself, adds the bot and the owner (falls back to an invite link), and filters senders by user ID.
  - Ollama client. The model is picked from the GPU size (4060 → `qwen3-vl:8b`; Mac 16–24 GB → 8b; Mac 36 GB+ → 30b). Falls back cleanly when a model can't call tools.
  - Agent with tools `look_through_glasses` and `search_visual_memory`. `/look [question]` answers the question from the next frame.
  - Visual memory (JPEGs + captures.jsonl) that can be searched from chat and from the dashboard.
  - Gmail backup: IMAP poll for frames the glasses emailed, and SMTP fallback to OWNER_EMAIL when Telegram is down.
  - USB provisioning and PlatformIO flashing, available from the CLI and the dashboard.
- [x] **Dashboard** (anti-vibe-polish pass): "Loupe" darkroom theme with a safelight accent and paper prints; glass only on the floating HUD; film grain; one motion moment (a new frame "develops"); spring micro-interactions; model-fit VRAM gauge; "Who's listening" panel; context-specific empty and error states. Checked at desktop and phone widths.
- [x] Setup scripts: `scripts/setup_windows.ps1`, `scripts/setup_macos.sh`. README with the whole setup.
- [x] Graphify graph and wiki generated with the real `graphify` CLI: `graphify-out/wiki/index.md`.

### Verified in the cloud session
- Agent tool loop against a fake Ollama: tool call → snapshot request; `<think>` stripping; no-tools fallback; memory search.
- USB provisioning against a fake board on a pty (payload contents and reply parsing).
- Full app starts with an empty `.env` and shows actionable setup problems (a first-run crash in Telethon was fixed). The DNS-rebinding guard returns 403.
- Model recommendation across a 4060 and Macs with 8, 16, 24, 36 and 48 GB.

### Not verified
- **The firmware compile.** This session's network policy blocks the PlatformIO registry (403), so the firmware was reviewed by hand only. The first `pio run` on the user's PC is the real compile check.
- Live Telegram, Gmail and Ollama: no credentials or GPU in the cloud container.

### Next ideas
1. Save frames to the SD card when there's no Wi-Fi, and send them later.
2. Voice questions through the Sense board's PDM mic, transcribed with Whisper on the PC.
3. Handle the group being upgraded to a supergroup automatically (for now: clear `group_id` and re-provision).
4. Deep sleep between presses for battery life.

### For future sessions
Read `graphify-out/wiki/index.md` first. Regenerate it after changes: `graphify update . && graphify export wiki`.

## 2026-09-24 — `windows-control` skill

**Request:** "make me a skill for as many things on a windows computer as you can".

### Done
- [x] `.claude/skills/windows-control/`, PowerShell-first, organized by progressive disclosure:
  - `SKILL.md`: how to run PowerShell from Claude Code's Git Bash (`-File` beats `-Command`), how to check for elevation, a table of how careful to be (read-only → system-level), a routing table to the references, and the list of scripts.
  - 10 references: files & search, apps & processes (winget, launching, protocol links, startup, default apps), system & hardware (performance triage, disks, battery, power, updates, drivers, logs, repairs), network (internet triage, Wi-Fi, ports, firewall, hosts, proxy, shares), settings & personalization (with the `ms-settings:` link table), automation & UI (scheduled tasks, services, registry, PATH, clipboard, UI Automation, AutoHotkey, file watchers), security & users, dev tools (WSL, CUDA, SSH, Sandbox), Office/printing/media (COM, spooler, ffmpeg), troubleshooting.
  - 10 scripts: `sysinfo` (real VRAM via the registry / nvidia-smi), `audio` (exact volume through Core Audio COM, plus media keys), `window`, `input` (SendInput, Unicode typing, key combos, mouse), `screenshot` (DPI-aware, per monitor or per window), `notify` (toast, relaunches under 5.1 from pwsh 7, balloon fallback), `speak` (SAPI), `display` (brightness, dark mode, wallpaper), `cleanup` (dry run by default), `find-large`.
- [x] Packaged as `windows-control.skill` and sent to the user for one-click install.

### Verified (PowerShell 7.4 on Linux)
- All 10 scripts parse, and all 6 embedded C# interop blocks compile with `Add-Type`. The SendInput `INPUT` struct is 40 bytes (correct for x64).
- All 80 `powershell` code blocks in the references parse.
- The skill-creator package validator passes (the YAML frontmatter and the 1,024-character description limit were fixed).

### Not verified
- Nothing ran on real Windows, since this container is Linux. The Win32/COM calls use well-established signatures, but the first real run happens on the user's PC.
- The skill-creator eval loop (with-skill vs. baseline runs) wasn't run. It can be done next if wanted.

## 2026-09-25 — `editor` skill (PDF markup, answering, editing)

**Request:** a skill that lets Claude edit PDFs with highlights, hand-drawn marks and text boxes. Then: use a Word round trip for rewrites, complete the questions in a PDF, work with the existing pdf skill, and call it "editor".

### Done: `.claude/skills/editor/`
- `SKILL.md` has a "pick the job" table: markup, answer, in-place edit or round trip. It hands off to the **pdf skill** for fillable form fields (its FORMS.md), OCR, merge and split.
- The scripts (PyMuPDF):
  - `inspect_pdf.py`: overview (text vs scanned, forms, signatures, advice) and `--find`.
  - `render.py`: PNGs, a `--grid` coordinate overlay (rotation-safe), and `--clip`.
  - `annotate.py`: highlight, underline, strikeout, squiggly (by phrase or by range with `to_text`), box, ellipse, arrow; hand-drawn circle, arrow, underline, check, cross, star, bracket and ink; textbox, sticky and handwrite (placed in free space); image; remove.
  - `fill.py`: `scan` finds questions and headings ("Paragraph 3:"), blanks, ruled lines, boxes (including boxes drawn as four separate lines, and boxes with instructions printed inside), bubbles, checkboxes and True/False pairs; `apply` writes typed or handwritten answers, flows onto later lines, fills bubbles, ticks boxes, circles choices, draws stars, and refuses answers that don't fit.
  - `edit_text.py`: redacts and rewrites in place, reusing the embedded font when it covers every character and matching the background; refuses when the new text would collide.
  - `roundtrip.py`: probe, to-docx and to-pdf (pdf2docx; Word or LibreOffice).
  - `compare.py`: a verdict, a per-region diff, and side-by-side PNGs.
- Handwriting font: the user's .ttf, then Windows Ink Free / Segoe Print or macOS Bradley Hand, then Caveat (OFL), downloaded through the Google Fonts CSS API.

### Tested (on real renders, not just exit codes)
- An invoice fixture (tables, tinted box, a phrase wrapping across lines, a rotated page, a scanned page): all markup ops, in-place edits (the refusals were correct), compare verdicts.
- A worksheet fixture: blanks, bubbles, ruled lines, checkboxes, a box and True/False, filled both typed and handwritten.
- The user's real worksheet ("Critiquing Introduction Paragraphs"): 18 range highlights and 6 critiques, with stars on paragraphs 3 and 5. The MLA heading was left blank on purpose (personal info).
- Round-trip probe: a simple memo survives (2.4% change); the invoice correctly fails (table columns shift).
- Bugs found and fixed through testing: multi-line matches split in two; line boxes overlapping neighbouring lines; placement covering text; the arrow over-wobbling; a coordinate type bug; PyMuPDF text-box border limits; same-line start/stop highlights returning empty (now built from words, with a guard against empty marks); Google Docs four-line boxes; page-background fills; bogus True/False choices from essay text.

### Not verified
- Microsoft Word COM conversion (Windows-only). LibreOffice was tested.
