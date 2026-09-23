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
