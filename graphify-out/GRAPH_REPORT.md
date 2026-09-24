# Graph Report - Agent-telegram-gmail  (2026-09-24)

## Corpus Check
- 40 files · ~27,300 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 1, .example 1, .css 1)

## Summary
- 423 nodes · 624 edges · 34 communities (22 shown, 12 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 21 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d73720e6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- provision.py
- Files, folders and search
- main.cpp
- core.py
- web.py
- telegram_service.py
- hardware.py
- app.js
- Config
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

## God Nodes (most connected - your core abstractions)
1. `Core` - 19 edges
2. `create_app()` - 18 edges
3. `Settings` - 16 edges
4. `State` - 15 edges
5. `TelegramService` - 15 edges
6. `Files, folders and search` - 15 edges
7. `Agent` - 14 edges
8. `LLM` - 14 edges
9. `Capture` - 13 edges
10. `VisualMemory` - 13 edges

## Surprising Connections (you probably didn't know these)
- `Core` --uses--> `Agent`  [INFERRED]
  desktop/glasses_agent/core.py → desktop/glasses_agent/agent.py
- `Core` --uses--> `Settings`  [INFERRED]
  desktop/glasses_agent/core.py → desktop/glasses_agent/config.py
- `make_client()` --uses--> `Settings`  [INFERRED]
  desktop/glasses_agent/telegram_service.py → desktop/glasses_agent/config.py
- `TelegramService` --uses--> `Settings`  [INFERRED]
  desktop/glasses_agent/telegram_service.py → desktop/glasses_agent/config.py
- `Core` --uses--> `State`  [INFERRED]
  desktop/glasses_agent/core.py → desktop/glasses_agent/config.py

## Import Cycles
- None detected.

## Communities (34 total, 12 thin omitted)

### Community 0 - "provision.py"
Cohesion: 0.07
Nodes (37): argparse, _env(), _env_int(), load(), Path, Settings from desktop/.env plus small runtime state in desktop/data/state.json., Values learned at runtime that must survive restarts (ids, chosen model)., Human-readable setup gaps, shown on the dashboard's checklist. (+29 more)

### Community 1 - "Files, folders and search"
Cohesion: 0.12
Nodes (15): Archives, Attributes, hidden files, "blocked" downloads, Big files and disk usage, Copy, move, rename, Delete safely: to the Recycle Bin, Duplicates, Files, folders and search, Find files (+7 more)

### Community 2 - "main.cpp"
Cohesion: 0.13
Nodes (34): arduino, arduinojson, camera_fb_t, esp_camera, addWifiNetworks(), b64(), blink(), captureAndSend() (+26 more)

### Community 3 - "core.py"
Cohesion: 0.07
Nodes (25): base64, collections, Agent, The AI's brain: describes frames, and chats with the owner using two tools., Put the frame's description into the chat history, so follow-ups like 'how much…, Wires the pieces together and holds the live status the dashboard shows., Per-component health: state is ok | warn | error | off., Status (+17 more)

### Community 4 - "web.py"
Cohesion: 0.06
Nodes (22): asyncio, BaseModel, Gmail backup path. Each device has its own Gmail account: glasses Gmail…, Loupe: local AI for ESP32 camera glasses., create_app(), capture_json(), captures(), LookBody (+14 more)

### Community 5 - "telegram_service.py"
Cohesion: 0.12
Nodes (15): _as_peer(), bot_username(), display_name(), _is_image(), make_client(), Path, RuntimeError, The AI's own Telegram user account, driven with Telethon. Three members share… (+7 more)

### Community 6 - "hardware.py"
Cohesion: 0.29
Nodes (11): dataclasses, detect(), fits(), Hardware, Work out how much GPU memory this machine has and which model fits in it.…, Largest vision + tools model that fits entirely in GPU memory., recommend(), report() (+3 more)

### Community 7 - "app.js"
Cohesion: 0.33
Nodes (10): ago(), api(), boardAction(), esc(), refreshModels(), refreshPorts(), refreshSheet(), refreshStatus() (+2 more)

### Community 8 - "Config"
Cohesion: 0.18
Nodes (11): Config, btnPin, gmPass, gmTo, gmUser, pollSeconds, tgChat, tgFrom (+3 more)

### Community 9 - "2026-09-23 — v1 built ("Loupe")"
Cohesion: 0.11
Nodes (17): 2026-09-23 — Session start (cloud session), 2026-09-23 — Spec received, 2026-09-23 — v1 built ("Loupe"), 2026-09-24 — `windows-control` skill, Blocked on, Done, Done, For future sessions (+9 more)

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

## Knowledge Gaps
- **128 isolated node(s):** `seen`, `wifiJson`, `tgToken`, `tgChat`, `tgFrom` (+123 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 249 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Core` connect `Core` to `provision.py`, `core.py`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `create_app()` connect `web.py` to `provision.py`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `Settings` connect `provision.py` to `telegram_service.py`, `core.py`, `Core`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `Core` (e.g. with `Agent` and `Settings`) actually correct?**
  _`Core` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `Settings` (e.g. with `Core` and `build_payload()`) actually correct?**
  _`Settings` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `State` (e.g. with `Core` and `build_payload()`) actually correct?**
  _`State` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `TelegramService` (e.g. with `Settings` and `State`) actually correct?**
  _`TelegramService` has 2 INFERRED edges - model-reasoned connections that need verification._