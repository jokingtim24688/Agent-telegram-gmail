# Graph Report - Agent-telegram-gmail  (2026-09-23)

## Corpus Check
- 18 files · ~10,392 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 1, .example 1, .css 1)

## Summary
- 265 nodes · 487 edges · 13 communities (10 shown, 3 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 21 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `270be39a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- provision.py
- core.py
- main.cpp
- Core
- web.py
- telegram_service.py
- hardware.py
- app.js
- Config
- 2026-09-23 — Spec received
- GmailBackup
- setup_macos.sh

## God Nodes (most connected - your core abstractions)
1. `Core` - 19 edges
2. `create_app()` - 18 edges
3. `Settings` - 16 edges
4. `State` - 15 edges
5. `TelegramService` - 15 edges
6. `Agent` - 14 edges
7. `LLM` - 14 edges
8. `Capture` - 13 edges
9. `VisualMemory` - 13 edges
10. `Config` - 13 edges

## Surprising Connections (you probably didn't know these)
- `Agent` --uses--> `LLM`  [INFERRED]
  desktop/glasses_agent/agent.py → desktop/glasses_agent/llm.py
- `Agent` --uses--> `ToolsUnsupported`  [INFERRED]
  desktop/glasses_agent/agent.py → desktop/glasses_agent/llm.py
- `Core` --uses--> `Settings`  [INFERRED]
  desktop/glasses_agent/core.py → desktop/glasses_agent/config.py
- `interactive_login()` --uses--> `Settings`  [INFERRED]
  desktop/glasses_agent/telegram_service.py → desktop/glasses_agent/config.py
- `make_client()` --uses--> `Settings`  [INFERRED]
  desktop/glasses_agent/telegram_service.py → desktop/glasses_agent/config.py

## Import Cycles
- None detected.

## Communities (13 total, 3 thin omitted)

### Community 0 - "provision.py"
Cohesion: 0.08
Nodes (32): argparse, _env(), _env_int(), load(), Path, Settings from desktop/.env plus small runtime state in desktop/data/state.json., Values learned at runtime that must survive restarts (ids, chosen model)., Human-readable setup gaps, shown on the dashboard's checklist. (+24 more)

### Community 1 - "core.py"
Cohesion: 0.08
Nodes (26): asyncio, base64, collections, The AI's brain: describes frames, and chats with the owner using two tools., Wires the pieces together and holds the live status the dashboard shows., Gmail backup path. Each device has its own Gmail account: glasses Gmail…, LLM, OllamaError (+18 more)

### Community 2 - "main.cpp"
Cohesion: 0.13
Nodes (34): arduino, arduinojson, camera_fb_t, esp_camera, addWifiNetworks(), b64(), blink(), captureAndSend() (+26 more)

### Community 3 - "Core"
Cohesion: 0.09
Nodes (13): Agent, Put the frame's description into the chat history, so follow-ups like 'how much…, Core, Path, Telegram first. If that fails, fall back to email so nothing gets lost., Per-component health: state is ok | warn | error | off., Tool + /look + dashboard button: make the glasses take a photo now., If this frame answers a /look, return that question (once). (+5 more)

### Community 4 - "web.py"
Cohesion: 0.08
Nodes (15): BaseModel, Loupe: local AI for ESP32 camera glasses., create_app(), capture_json(), captures(), LookBody, ModelBody, PortBody (+7 more)

### Community 5 - "telegram_service.py"
Cohesion: 0.11
Nodes (17): _as_peer(), bot_username(), display_name(), interactive_login(), _is_image(), make_client(), Path, RuntimeError (+9 more)

### Community 6 - "hardware.py"
Cohesion: 0.29
Nodes (11): dataclasses, detect(), fits(), Hardware, Work out how much GPU memory this machine has and which model fits in it.…, Largest vision + tools model that fits entirely in GPU memory., recommend(), report() (+3 more)

### Community 7 - "app.js"
Cohesion: 0.33
Nodes (10): ago(), api(), boardAction(), esc(), refreshModels(), refreshPorts(), refreshSheet(), refreshStatus() (+2 more)

### Community 8 - "Config"
Cohesion: 0.18
Nodes (11): Config, btnPin, gmPass, gmTo, gmUser, pollSeconds, tgChat, tgFrom (+3 more)

### Community 9 - "2026-09-23 — Spec received"
Cohesion: 0.22
Nodes (8): 2026-09-23 — Session start (cloud session), 2026-09-23 — Spec received, Blocked on, Model decision (draft), Next steps (once context arrives), Open decision: which Telegram account the AI uses, Progress, What the cloud session found

## Knowledge Gaps
- **17 isolated node(s):** `seen`, `wifiJson`, `tgToken`, `tgChat`, `tgFrom` (+12 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 112 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Core` connect `Core` to `provision.py`, `core.py`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **Why does `create_app()` connect `web.py` to `provision.py`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Why does `Settings` connect `provision.py` to `core.py`, `Core`, `telegram_service.py`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `Core` (e.g. with `Agent` and `Settings`) actually correct?**
  _`Core` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `Settings` (e.g. with `Core` and `build_payload()`) actually correct?**
  _`Settings` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `State` (e.g. with `Core` and `build_payload()`) actually correct?**
  _`State` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `TelegramService` (e.g. with `Settings` and `State`) actually correct?**
  _`TelegramService` has 2 INFERRED edges - model-reasoned connections that need verification._