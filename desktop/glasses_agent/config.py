"""Settings from desktop/.env plus small runtime state in desktop/data/state.json."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent  # desktop/
DATA = ROOT / "data"
FIRMWARE_DIR = ROOT.parent / "firmware" / "glasses"

DEFAULT_CAPTURE_PROMPT = (
    "This photo was just taken by the camera on my glasses, so it shows what I'm looking at. "
    "In two or three sentences, say what it is. Read out any text that's legible "
    "(signs, labels, screens, prices). Don't open with 'The image shows'."
)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


@dataclass
class Settings:
    # AI Telegram account (a real user account you own, driven through Telethon)
    tg_api_id: int
    tg_api_hash: str
    tg_phone: str
    # Who the AI listens to (usernames, resolved to numeric ids at startup)
    owner: str
    # Glasses bot (its token is written onto the board; the PC only uses it to look up the bot's name)
    glasses_bot_token: str
    group_title: str
    # Local model
    ollama_url: str
    model: str
    capture_prompt: str
    # Gmail backup (each device has its own account)
    ai_gmail: str
    ai_gmail_app_password: str
    glasses_gmail: str
    glasses_gmail_app_password: str
    owner_email: str
    gmail_poll_seconds: int
    dashboard_port: int

    @property
    def session_path(self) -> Path:
        return DATA / "ai_account"  # Telethon adds .session

    @property
    def gmail_enabled(self) -> bool:
        return bool(self.ai_gmail and self.ai_gmail_app_password and self.glasses_gmail)

    def problems(self) -> list[str]:
        """Human-readable setup gaps, shown on the dashboard's checklist."""
        out = []
        if not (self.tg_api_id and self.tg_api_hash):
            out.append("TG_API_ID / TG_API_HASH are empty. Get them at my.telegram.org → API development tools, "
                       "signed in as the AI's Telegram account.")
        if not self.tg_phone:
            out.append("TG_PHONE is empty. Use the phone number of the AI's Telegram account, e.g. +15551234567.")
        if not self.owner:
            out.append("OWNER is empty. Put your personal @username there; the AI ignores everyone else.")
        if not self.glasses_bot_token:
            out.append("GLASSES_BOT_TOKEN is empty. Create the glasses bot with @BotFather and paste its token.")
        if not self.gmail_enabled:
            out.append("Gmail backup is off. Fill AI_GMAIL, AI_GMAIL_APP_PASSWORD and GLASSES_GMAIL to turn it on.")
        return out


def load() -> Settings:
    load_dotenv(ROOT / ".env")
    DATA.mkdir(parents=True, exist_ok=True)
    return Settings(
        tg_api_id=_env_int("TG_API_ID", 0),
        tg_api_hash=_env("TG_API_HASH"),
        tg_phone=_env("TG_PHONE"),
        owner=_env("OWNER"),
        glasses_bot_token=_env("GLASSES_BOT_TOKEN"),
        group_title=_env("GROUP_TITLE", "Loupe"),
        ollama_url=_env("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
        model=_env("MODEL"),
        capture_prompt=_env("CAPTURE_PROMPT") or DEFAULT_CAPTURE_PROMPT,
        ai_gmail=_env("AI_GMAIL"),
        ai_gmail_app_password=_env("AI_GMAIL_APP_PASSWORD").replace(" ", ""),
        glasses_gmail=_env("GLASSES_GMAIL"),
        glasses_gmail_app_password=_env("GLASSES_GMAIL_APP_PASSWORD").replace(" ", ""),
        owner_email=_env("OWNER_EMAIL"),
        gmail_poll_seconds=max(20, _env_int("GMAIL_POLL_SECONDS", 60)),
        dashboard_port=_env_int("DASHBOARD_PORT", 8765),
    )


class State:
    """Values learned at runtime that must survive restarts (ids, chosen model)."""

    def __init__(self, path: Path = DATA / "state.json"):
        self.path = path
        try:
            self._d = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            self._d = {}

    def get(self, key: str, default=None):
        return self._d.get(key, default)

    def set(self, **values) -> None:
        self._d.update(values)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._d, indent=2), "utf-8")
        tmp.replace(self.path)
