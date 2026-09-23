"""The AI's brain: describes frames, and chats with the owner using two tools."""
from __future__ import annotations

import json
import logging
from collections import deque
from typing import Awaitable, Callable

from .llm import LLM, ToolsUnsupported
from .memory import Capture, VisualMemory

log = logging.getLogger(__name__)

SYSTEM = """You are Loupe, the assistant built into {owner}'s camera glasses. You talk with them in a \
Telegram group. The glasses have a camera but no screen and no speaker, so everything you say \
arrives as a Telegram message on their phone.

- Keep replies short and concrete. They're often walking or holding something.
- When they ask about what's in front of them right now ("what's this?", "read that sign"), \
call look_through_glasses. Don't guess.
- When they ask about something they saw earlier, call search_visual_memory.
- Every photo you've seen has a timestamp, so you can say things like "at 14:02 you were looking at…".
- Never pretend you can see something you haven't been shown."""

TOOLS = [
    {"type": "function", "function": {
        "name": "look_through_glasses",
        "description": "Make the glasses take a photo right now. The photo arrives a few seconds later "
                       "and gets answered automatically with the question you pass here.",
        "parameters": {"type": "object", "properties": {
            "question": {"type": "string", "description": "What to find out from the photo."}},
            "required": ["question"]}}},
    {"type": "function", "function": {
        "name": "search_visual_memory",
        "description": "Search descriptions of earlier photos from the glasses, newest first.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Words to look for, e.g. 'receipt total' or 'bus'."}},
            "required": ["query"]}}},
]


class Agent:
    def __init__(self, llm: LLM, memory: VisualMemory, owner_name: Callable[[], str],
                 request_snapshot: Callable[[str], Awaitable[str]]):
        self.llm = llm
        self.memory = memory
        self.owner_name = owner_name
        self.request_snapshot = request_snapshot
        self.history: deque[dict] = deque(maxlen=16)

    def _system(self) -> str:
        return SYSTEM.format(owner=self.owner_name() or "the owner")

    async def describe(self, jpeg: bytes, prompt: str) -> str:
        return await self.llm.see(jpeg, prompt, self._system())

    def remember(self, cap: Capture) -> None:
        """Put the frame's description into the chat history, so follow-ups like
        'how much was it again?' work without another photo."""
        self.history.append({"role": "assistant",
                             "content": f"[Photo from the glasses at {cap.when()}] {cap.answer}"})

    async def _call_tool(self, name: str, args: dict) -> str:
        if name == "look_through_glasses":
            return await self.request_snapshot(str(args.get("question") or "What am I looking at?"))
        if name == "search_visual_memory":
            hits = self.memory.search(str(args.get("query", "")))
            if not hits:
                return "No earlier photos match that."
            return "\n".join(f"- {c.when()}: {c.answer}" for c in hits)
        return f"Unknown tool {name}"

    async def reply(self, text: str) -> str:
        self.history.append({"role": "user", "content": text})
        messages = [{"role": "system", "content": self._system()}, *self.history]
        tools = TOOLS
        for _ in range(4):
            try:
                msg = await self.llm.chat(messages, tools=tools)
            except ToolsUnsupported:
                log.warning("%s can't call tools; answering without /look or memory search", self.llm.model)
                tools = None
                continue
            calls = msg.get("tool_calls") or []
            if not calls:
                answer = msg.get("content") or "…"
                self.history.append({"role": "assistant", "content": answer})
                return answer
            messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": calls})
            for call in calls:
                fn = call.get("function", {})
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                result = await self._call_tool(fn.get("name", ""), args)
                messages.append({"role": "tool", "tool_name": fn.get("name", ""), "content": result})
        return "I got stuck in a loop of tool calls. Try asking again another way."

