# Loupe: a local AI for ESP32 camera glasses

Press the button on your glasses, and a few seconds later your phone tells you what you're looking at.
It reads signs, labels, receipts and screens. You can also type `/look is this the 42 bus?` in
Telegram: the glasses take the shot, and the AI answers that question from the photo.

Everything runs on your own computer: **Windows with an NVIDIA GPU**, or a **Mac with Apple
Silicon**. The model runs locally through [Ollama](https://ollama.com), so no photo ever goes to
a cloud AI.

```
  glasses (XIAO ESP32S3 Sense)                        your PC
  ┌──────────────────────────┐                ┌──────────────────────────────┐
  │ button ─▶ camera ─▶ JPEG │                │ Loupe (python -m glasses_agent)
  │ glasses bot token        │                │  ├─ AI Telegram account      │
  │ glasses Gmail (backup)   │                │  ├─ Ollama: qwen3-vl         │
  └────────┬────────┬────────┘                │  ├─ visual memory (captures) │
           │        │                         │  └─ dashboard :8765          │
           │        └── email frame ───────▶ AI Gmail ◀── IMAP poll ───────┤
           ▼                                                               │
   Telegram group "Loupe" ◀────────── reads / replies (Telethon) ──────────┘
     members: you · glasses bot · AI account
```

## Who listens to whom

All three accounts are in one Telegram group. Each one only acts on messages from specific
senders. Senders are matched by **numeric Telegram user ID**, which Loupe looks up from the
@usernames you configure. Display names aren't unique and anyone can copy one, so they're never
used for matching.

| Member | Acts on | Ignores |
|---|---|---|
| **AI account** | you (`OWNER`) and the glasses bot | everyone else in the group or in its DMs |
| **Glasses** | the AI account only (`/snap`, `/ping`) | everyone, including you |
| **You** | whatever you like | |

The glasses bot runs with Telegram's default privacy mode, so it only receives commands
addressed to it (`/snap@your_glasses_bot`). The AI always sends commands that way.

## Why these parts

- **The model: Qwen3-VL 8B.** The glasses send photos, so the model has to understand images.
  Hermes 3 is text-only. Llama 3.2 Vision 11B fills all 8 GB of an RTX 4060 and spills onto the
  CPU. Qwen3-VL 8B needs about 6 GB, reads text in photos well, and can call tools (that's how
  `/look` works). The dashboard measures your GPU and picks the largest model that fits. A Mac
  with 16–24 GB also gets the 8B model; one with 32 GB or more gets `qwen3-vl:30b`.
- **The AI's account: a real Telegram account you own.** Register it with your own prepaid SIM,
  so you're the only one who can recover it. Don't use a bought account: the seller still has
  its phone number, so they can take it back and read every photo.
- **The glasses: a bot.** An ESP32 can't run a full Telegram client, but it can use the Bot API.
- **Gmail: backup only.** The glasses and the AI each get their own Gmail account. If Telegram
  fails, the glasses email the frame to the AI's inbox. If the AI can't reach Telegram, it emails
  its answer to `OWNER_EMAIL`. Losing the glasses exposes only the glasses' own Gmail account.

## Hardware

- Seeed Studio **XIAO ESP32S3 Sense** (the camera and 8 MB of PSRAM are on the expansion board).
- A momentary push button from **D0 (GPIO 1)** to **GND**. You can change the pin in the dashboard.
- The orange user LED flashes once when a frame was sent, and three times fast when it failed.

## Setup

### 1. Accounts (once)

1. **The AI's Telegram account.** Sign up in the Telegram app with your second SIM. Then go to
   <https://my.telegram.org>, log in **as that account**, open *API development tools*, and note
   the `api_id` and `api_hash`.
2. **The glasses bot.** In Telegram, message **@BotFather**, send `/newbot`, and copy the token.
3. **Gmail backup (optional).** Create two Gmail accounts, one for the glasses and one for the AI.
   Turn on 2-Step Verification for each, then create an App Password for each at
   <https://myaccount.google.com/apppasswords>.

### 2. Install on the computer

Windows (PowerShell, from the repo folder):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

Mac (Apple Silicon):

```bash
bash scripts/setup_macos.sh
```

Each script installs Python and Ollama if needed, creates `desktop/.venv`, installs the
dependencies plus PlatformIO, copies `.env.example` to `.env`, and downloads the best model for
the machine.

### 3. Configure, log in, run

1. Fill in `desktop/.env`. Every field is explained in the file.
2. Sign the AI's account in. Telegram sends a login code to that account:
   ```
   cd desktop
   .venv\Scripts\python -m glasses_agent login        # Windows
   .venv/bin/python -m glasses_agent login            # Mac
   ```
3. Start Loupe: `python -m glasses_agent` (using the same venv Python). The dashboard opens at
   <http://127.0.0.1:8765>. On the first run, the AI creates the **Loupe** group, adds the glasses
   bot, and adds you. If your privacy settings block that, it DMs you an invite link instead.

### 4. Flash and set up the glasses

Plug the glasses in over USB-C. Then, in the dashboard's **Glasses board** panel:

1. **Flash firmware.** This runs PlatformIO. The first build downloads the ESP32 toolchain, which
   takes a few minutes. You can also press Upload in Antigravity's PlatformIO sidebar, or run
   `pio run -d firmware/glasses -t upload`.
2. Enter up to three Wi-Fi networks (home, phone hotspot, …) and press **Write to glasses**. Your
   Wi-Fi details, the bot token, the group ID, the AI account's user ID, and the glasses' Gmail
   login are saved in the board's flash memory. The firmware itself contains no secrets.
3. The glasses restart and join Wi-Fi. Press **Ping over Telegram**. A `#status` line from the
   glasses should appear in the group.

The same steps work from a terminal:

```
python -m glasses_agent ports
python -m glasses_agent flash --port COM5
python -m glasses_agent provision --port COM5 --wifi "Home:password" --wifi "Phone:password"
python -m glasses_agent doctor
```

## Using it

- **Button on the glasses**: the photo goes to the group, and the AI replies to it with what it sees.
- **`/look [question]`** in the group: the glasses take a photo now, and the AI answers your question.
- **Plain chat**: "what was the Wi-Fi password at the café?" The AI searches everything the
  glasses have shown it (its *visual memory*).
- **Send the AI a photo of your own**: it describes it, and treats your caption as the question.
- **The dashboard**: every frame lands on a contact sheet you can search. It also shows the model
  fit for your GPU, who's listening to whom, and board setup.

## Files

```
firmware/glasses/          PlatformIO project for the XIAO ESP32S3 Sense
  src/main.cpp             camera, Telegram sendPhoto, Gmail SMTP backup, group listener, USB provisioning
  include/ca_certs.h       root CAs the board trusts (Telegram: Go Daddy G2; Gmail: GTS R1/R4)
desktop/glasses_agent/
  telegram_service.py      the AI's Telegram account: group creation, sender allowlist, /look
  agent.py                 system prompt, tool calls (look_through_glasses, search_visual_memory)
  llm.py                   Ollama client (the same code on CUDA and Metal)
  hardware.py              GPU/unified-memory detection and model choice
  memory.py                visual memory: JPEGs + captures.jsonl
  gmail_backup.py          IMAP poll for frames sent by email, and SMTP fallback to you
  provision.py             USB serial provisioning and PlatformIO flashing
  web.py, static/          localhost-only dashboard
scripts/                   one-shot setup for Windows and macOS
graphify-out/wiki/         knowledge-graph wiki of this repo (start at index.md)
```

## Security notes

- `desktop/.env`, `desktop/data/` (captures, state) and `*.session` are git-ignored. The Telethon
  `.session` file works like a password for the AI's account, so keep it private.
- The dashboard binds to `127.0.0.1` only and rejects requests whose Host header isn't localhost.
  That blocks DNS-rebinding attacks from web pages.
- The board checks TLS certificates against the bundled root CAs. If Telegram or Google ever
  switch CAs, sends will fail with a TLS error. As a stopgap you can re-provision with
  `"tls_insecure": true` while `ca_certs.h` gets updated.

## Known limits

- The firmware was written and reviewed by hand, but it hasn't been compiled in CI yet. The first
  `pio run` on your machine is the real compile check.
- If the group ever gets upgraded to a supergroup (Telegram does this when you change certain
  admin settings), its ID changes. Delete `group_id` from `desktop/data/state.json`, restart
  Loupe, and write the settings to the glasses again.
- Frames taken with no Wi-Fi are dropped. Saving them to the SD card is a natural next step, as
  are voice questions through the Sense board's microphone.
