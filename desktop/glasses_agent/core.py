"""Wires the pieces together and holds the live status the dashboard shows."""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from . import hardware
from .agent import Agent
from .config import DATA, Settings, State
from .llm import LLM, OllamaError
from .memory import Capture, VisualMemory

log = logging.getLogger(__name__)

LOOK_WINDOW_S = 90  # how long a /look question waits for its photo


class Status:
    """Per-component health: state is ok | warn | error | off."""

    def __init__(self):
        self.components: dict[str, dict] = {}

    def set(self, name: str, state: str, detail: str) -> None:
        prev = self.components.get(name, {})
        if prev.get("state") != state or prev.get("detail") != detail:
            log.info("%s: %s — %s", name, state, detail)
        self.components[name] = {"state": state, "detail": detail, "since": time.time()}


class Core:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.state = State()
        self.status = Status()
        self.memory = VisualMemory(DATA)
        self.hw = hardware.detect()
        self.llm = LLM(settings.ollama_url, self.model)
        self.agent = Agent(self.llm, self.memory, lambda: self.state.get("owner_name", ""),
                           self.request_snapshot)
        self.pending_look: tuple[str, float] | None = None
        self.glasses_seen: float | None = None
        self.glasses_info: dict[str, str] = {}
        self.busy: str | None = None
        self.telegram = None  # set by __main__ (TelegramService)
        self.gmail = None     # set by __main__ (GmailBackup)
        for name in ("glasses", "telegram", "ollama", "gmail"):
            self.status.set(name, "off", "starting…")

    # ---- model choice: dashboard pick > .env MODEL > best fit for this machine
    def model(self) -> str:
        return self.state.get("model") or self.settings.model or hardware.recommend(self.hw)

    # ---- glasses
    def glasses_heard(self, info: dict[str, str] | None = None) -> None:
        self.glasses_seen = time.time()
        if info:
            self.glasses_info = info
        self.status.set("glasses", "ok", "online")

    async def request_snapshot(self, question: str) -> str:
        """Tool + /look + dashboard button: make the glasses take a photo now."""
        if not self.telegram or not self.telegram.ready:
            return "Can't reach the glasses: the AI's Telegram account isn't connected."
        self.pending_look = (question, time.time())
        await self.telegram.send_snap()
        return ("Snapshot requested. The glasses usually answer within 5–10 seconds, "
                "and the photo will be described automatically. Tell the owner you're taking a look.")

    def _question_for_frame(self, reason: str) -> str:
        """If this frame answers a /look, return that question (once)."""
        if self.pending_look and reason == "remote":
            question, asked = self.pending_look
            self.pending_look = None
            if time.time() - asked < LOOK_WINDOW_S:
                return question
        return ""

    async def handle_frame(self, jpeg: bytes, *, source: str, reason: str,
                           question: str = "") -> Capture | None:
        """A frame arrived (Telegram group or Gmail backup): describe it, store it, report it."""
        if reason != "owner-photo":
            self.glasses_heard()
        question = question or self._question_for_frame(reason)
        if question:
            prompt = (f"This photo was just taken because I asked: \"{question}\". "
                      "Answer my question from what's in the photo, and read any text that helps.")
        else:
            prompt = self.settings.capture_prompt
        self.busy = "Looking at a new frame"
        try:
            answer = await self.agent.describe(jpeg, prompt)
            self.status.set("ollama", "ok", self.model())
        except OllamaError as e:
            self.status.set("ollama", "error", str(e))
            answer = f"I got the photo but couldn't look at it: {e}"
        finally:
            self.busy = None
        cap = self.memory.add(jpeg, source=source, reason=reason, prompt=prompt, answer=answer,
                              question=question)
        self.agent.remember(cap)
        return cap

    async def chat(self, text: str) -> str:
        self.busy = "Writing a reply"
        try:
            answer = await self.agent.reply(text)
            self.status.set("ollama", "ok", self.model())
            return answer
        except OllamaError as e:
            self.status.set("ollama", "error", str(e))
            return f"My local model isn't working right now: {e}"
        finally:
            self.busy = None

    async def notify_owner(self, text: str, photo: Path | None = None) -> None:
        """Telegram first. If that fails, fall back to email so nothing gets lost."""
        if self.telegram and self.telegram.ready:
            try:
                await self.telegram.send_group(text, photo)
                return
            except Exception as e:  # noqa: BLE001 — any Telegram failure should trigger the fallback
                log.warning("telegram send failed, falling back to email: %s", e)
        if self.gmail:
            await self.gmail.email_owner("Loupe", text, photo)

    # ---- background health check for Ollama
    async def watch_ollama(self) -> None:
        while True:
            try:
                installed = await self.llm.installed()
                m = self.model()
                if m in installed or f"{m}:latest" in installed:
                    if self.status.components["ollama"]["state"] != "error":
                        self.status.set("ollama", "ok", m)
                else:
                    self.status.set("ollama", "warn", f"{m} isn't downloaded. Run: ollama pull {m}")
            except Exception:  # noqa: BLE001
                self.status.set("ollama", "error",
                                f"Ollama isn't running at {self.settings.ollama_url}. Open the Ollama app.")
            if self.glasses_seen and time.time() - self.glasses_seen > 15 * 60:
                self.status.set("glasses", "warn", "quiet for 15+ min")
            await asyncio.sleep(10)
