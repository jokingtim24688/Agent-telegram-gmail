# Graph Report - Agent-telegram-gmail  (2026-09-25)

## Corpus Check
- 49 files · ~40,856 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 1, .example 1, .css 1)

## Summary
- 578 nodes · 995 edges · 46 communities (32 shown, 14 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 26 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `757ec0b0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- provision.py
- Files, folders and search
- main.cpp
- LLM
- web.py
- telegram_service.py
- hardware.py
- app.js
- pathlib
- 2026-09-23 — v1 built ("Loupe")
- Loupe: a local AI for ESP32 camera glasses
- setup_macos.sh
- Core
- System and hardware
- Network
- Automation and UI control
- Developer setup
- Office, printing and media
- Settings and personalization
- Troubleshooting
- Security and user accounts
- Apps and processes
- Windows control
- display.ps1
- out_json
- fill.py
- annotate.py
- _common.py
- core.py
- find_text
- _placements
- Editor: mark up, answer and edit PDFs
- Capture
- Settings
- Agent
- handwrite_lines

## God Nodes (most connected - your core abstractions)
1. `apply()` - 26 edges
2. `Core` - 19 edges
3. `create_app()` - 18 edges
4. `out_json()` - 17 edges
5. `find_text()` - 16 edges
6. `Settings` - 16 edges
7. `State` - 15 edges
8. `TelegramService` - 15 edges
9. `Files, folders and search` - 15 edges
10. `Agent` - 14 edges

## Surprising Connections (you probably didn't know these)
- `Done: `.claude/skills/editor/`` --references--> `scan()`  [INFERRED]
  Progress.md → .claude/skills/editor/scripts/fill.py
- `Markup: `annotate.py`` --references--> `ink()`  [INFERRED]
  .claude/skills/editor/SKILL.md → .claude/skills/editor/scripts/annotate.py
- `Answering questions: `fill.py`` --references--> `scan()`  [INFERRED]
  .claude/skills/editor/SKILL.md → .claude/skills/editor/scripts/fill.py
- `Agent` --uses--> `LLM`  [INFERRED]
  desktop/glasses_agent/agent.py → desktop/glasses_agent/llm.py
- `Agent` --uses--> `ToolsUnsupported`  [INFERRED]
  desktop/glasses_agent/agent.py → desktop/glasses_agent/llm.py

## Import Cycles
- None detected.

## Communities (46 total, 14 thin omitted)

### Community 0 - "provision.py"
Cohesion: 0.10
Nodes (31): find_soffice(), main(), probe(), PDF -> Word -> PDF, for rewrites that need text to reflow. python roundtrip.py…, to_docx(), to_pdf(), word_available(), dataclasses (+23 more)

### Community 1 - "Files, folders and search"
Cohesion: 0.12
Nodes (15): Archives, Attributes, hidden files, "blocked" downloads, Big files and disk usage, Copy, move, rename, Delete safely: to the Recycle Bin, Duplicates, Files, folders and search, Find files (+7 more)

### Community 2 - "main.cpp"
Cohesion: 0.09
Nodes (45): arduino, arduinojson, camera_fb_t, esp_camera, addWifiNetworks(), b64(), blink(), captureAndSend() (+37 more)

### Community 3 - "LLM"
Cohesion: 0.15
Nodes (9): base64, LLM, OllamaError, RuntimeError, Thin async client for a local Ollama server (same API on Windows/CUDA and…, name -> size in GB of every model Ollama has on disk., ToolsUnsupported, httpx (+1 more)

### Community 4 - "web.py"
Cohesion: 0.09
Nodes (14): BaseModel, create_app(), capture_json(), captures(), LookBody, ModelBody, PortBody, ProvisionBody (+6 more)

### Community 5 - "telegram_service.py"
Cohesion: 0.08
Nodes (21): Path, Values learned at runtime that must survive restarts (ids, chosen model)., State, _as_peer(), bot_username(), display_name(), interactive_login(), _is_image() (+13 more)

### Community 6 - "hardware.py"
Cohesion: 0.40
Nodes (9): detect(), fits(), Hardware, Work out how much GPU memory this machine has and which model fits in it.…, Largest vision + tools model that fits entirely in GPU memory., recommend(), report(), _run() (+1 more)

### Community 7 - "app.js"
Cohesion: 0.33
Nodes (10): ago(), api(), boardAction(), esc(), refreshModels(), refreshPorts(), refreshSheet(), refreshStatus() (+2 more)

### Community 8 - "pathlib"
Cohesion: 0.09
Nodes (20): diff_pages(), gray(), main(), Compare two PDFs: did the layout survive, and what text changed? python…, Group changed pixels into separate boxes: mark coarse grid cells that contain a…, (fraction of pixels changed, [changed regions as Rects in PDF points])., _regions(), side_by_side() (+12 more)

### Community 9 - "2026-09-23 — v1 built ("Loupe")"
Cohesion: 0.09
Nodes (21): 2026-09-23 — Session start (cloud session), 2026-09-23 — Spec received, 2026-09-23 — v1 built ("Loupe"), 2026-09-24 — `windows-control` skill, 2026-09-25 — `editor` skill (PDF markup, answering, editing), Blocked on, Done, Done (+13 more)

### Community 10 - "Loupe: a local AI for ESP32 camera glasses"
Cohesion: 0.14
Nodes (13): 1. Accounts (once), 2. Install on the computer, 3. Configure, log in, run, 4. Flash and set up the glasses, Files, Hardware, Known limits, Loupe: a local AI for ESP32 camera glasses (+5 more)

### Community 13 - "Core"
Cohesion: 0.20
Nodes (6): Core, Path, Telegram first. If that fails, fall back to email so nothing gets lost., Tool + /look + dashboard button: make the glasses take a photo now., If this frame answers a /look, return that question (once)., A frame arrived (Telegram group or Gmail backup): describe it, store it, report…

### Community 14 - "System and hardware"
Cohesion: 0.15
Nodes (12): Battery (laptops), Disks and storage health, Drivers and devices, Hardware peripherals, Logs: what just crashed or went wrong, Performance: "why is my PC slow?", Power, sleep, shutdown, Quick snapshot (+4 more)

### Community 15 - "Network"
Cohesion: 0.17
Nodes (11): Current state, Firewall, Hosts file (block or redirect a domain), Network, Network drives and sharing, Ports and connections, Proxy, Remote access to this PC (+3 more)

### Community 16 - "Automation and UI control"
Cohesion: 0.18
Nodes (10): Automation and UI control, Clipboard, Driving GUI apps (when there's no CLI or API), Environment variables and PATH, Hotkeys and text expansion, Notifications and speech, React to changes: file watchers, Registry (+2 more)

### Community 17 - "Developer setup"
Cohesion: 0.18
Nodes (10): Core toolchain via winget, Developer setup, GPU / CUDA, Long paths, symlinks, Developer Mode, OpenSSH, Ports and dev servers, PowerShell environment, Windows features (+2 more)

### Community 18 - "Office, printing and media"
Cohesion: 0.20
Nodes (9): Audio and video (ffmpeg), Excel, Images, Office automation through COM (desktop Office only), Office, printing and media, Outlook (classic), PDFs, Printing (+1 more)

### Community 19 - "Settings and personalization"
Cohesion: 0.20
Nodes (9): Accessibility, Changing settings through Group Policy / HKLM, Display, Mouse, keyboard, typing, Notifications and Focus, Settings and personalization, Settings deep links (`Start-Process ms-settings:<page>`), Sound (+1 more)

### Community 20 - "Troubleshooting"
Cohesion: 0.20
Nodes (9): Access denied, An app won't open or crashes on start, Bluescreens and random restarts, Disk full, Explorer, Start menu or taskbar frozen, "My PC is slow", Running commands, Time and sign-in problems (+1 more)

### Community 21 - "Security and user accounts"
Cohesion: 0.22
Nodes (8): BitLocker / device encryption, Is something suspicious running?, Local users and groups, Microsoft Defender, Passwords and secrets for scripts, Privacy quick wins (user-level, reversible), Security and user accounts, UAC, SmartScreen, "Windows protected your PC"

### Community 22 - "Apps and processes"
Cohesion: 0.29
Nodes (6): Apps and processes, Default apps, Installing, updating and removing apps: winget, Launching apps, Startup apps, What's running, and closing things

### Community 23 - "Windows control"
Cohesion: 0.29
Nodes (6): Before running anything: know your shell, Bundled scripts, How careful to be, Where to look, Windows control, Working style

### Community 34 - "out_json"
Cohesion: 0.14
Nodes (22): main(), out_json(), pages_of(), 1-based page spec (None/'all' | 3 | [1,3] | '2-5') -> list of 0-based indexes., render(), apply_edit(), background(), choose_font() (+14 more)

### Community 35 - "fill.py"
Cohesion: 0.13
Nodes (22): _boxes_from_lines(), _drawings(), fit_lines(), _index(), _is_option_row(), _lines(), _r(), Rebuild rectangles drawn as four separate lines (Google Docs, Word and many… (+14 more)

### Community 36 - "annotate.py"
Cohesion: 0.17
Nodes (21): apply(), edge_point(), ink(), _point(), range_quads(), Line-by-line boxes covering every word from the one at start_rect to the one at…, Mark up a PDF: highlights, pen drawings, text boxes, notes, stamps. python…, Where a line from `toward` to the rect's centre crosses the rect's border… (+13 more)

### Community 37 - "_common.py"
Cohesion: 0.14
Nodes (21): _cache_dir(), _download_caveat(), hand_arrow(), hand_bracket(), hand_check(), hand_cross(), hand_ellipse(), hand_line() (+13 more)

### Community 38 - "core.py"
Cohesion: 0.17
Nodes (12): asyncio, The AI's brain: describes frames, and chats with the owner using two tools., Wires the pieces together and holds the live status the dashboard shows., Loupe: local AI for ESP32 camera glasses., Loupe desktop. python -m glasses_agent login sign the AI's Telegram account in…, Visual memory: every frame the glasses send, with what the AI said about it.…, json, logging (+4 more)

### Community 39 - "find_text"
Cohesion: 0.24
Nodes (11): argparse, find_text(), _norm(), Text inside a rect, reading only its vertical middle band. Line boxes overlap…, Hits of `text` on a page, as rects (or lists of quads with quads=True).…, text_in(), union_rect(), find() (+3 more)

### Community 40 - "_placements"
Cohesion: 0.21
Nodes (12): measure(), bounds(), is_free(), near_rect(), fit(), occupied(), _placements(), The page rectangle in native (unrotated) coordinates. (+4 more)

### Community 41 - "Editor: mark up, answer and edit PDFs"
Cohesion: 0.18
Nodes (10): Answering questions: `fill.py`, Big rewrites: `roundtrip.py` (PDF → Word → PDF), Editor: mark up, answer and edit PDFs, How to answer well, Markup: `annotate.py`, Setup (once per machine), Small text changes: `edit_text.py`, Step 1: always look first (+2 more)

### Community 42 - "Capture"
Cohesion: 0.29
Nodes (3): Capture, Path, VisualMemory

### Community 43 - "Settings"
Cohesion: 0.20
Nodes (5): Human-readable setup gaps, shown on the dashboard's checklist., Settings, Per-component health: state is ok | warn | error | off., Status, run()

## Knowledge Gaps
- **137 isolated node(s):** `seen`, `wifiJson`, `tgToken`, `tgChat`, `tgFrom` (+132 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 302 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `scan()` connect `fill.py` to `Editor: mark up, answer and edit PDFs`, `out_json`, `2026-09-23 — v1 built ("Loupe")`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `Done: `.claude/skills/editor/`` connect `2026-09-23 — v1 built ("Loupe")` to `fill.py`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `Core` (e.g. with `Agent` and `Settings`) actually correct?**
  _`Core` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `seen`, `wifiJson`, `tgToken` to the rest of the system?**
  _137 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `provision.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09803921568627451 - nodes in this community are weakly interconnected._
- **Should `Files, folders and search` be split into smaller, more focused modules?**
  _Cohesion score 0.125 - nodes in this community are weakly interconnected._
- **Should `main.cpp` be split into smaller, more focused modules?**
  _Cohesion score 0.08599290780141844 - nodes in this community are weakly interconnected._