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
- Waiting on the user's choice before building.

### Next steps (once context arrives)
1. Scaffold the agent from the spec.
2. Generate `graphify-out/wiki/index.md` so future sessions can use the wiki instead of reading raw files.
3. Update this file after each step.
