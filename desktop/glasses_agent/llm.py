"""Thin async client for a local Ollama server (same API on Windows/CUDA and macOS/Metal)."""
from __future__ import annotations

import asyncio
import base64
import re
from typing import Callable

import httpx

THINK_RE = re.compile(r"<think>.*?</think>", re.S)


class OllamaError(RuntimeError):
    pass


class ToolsUnsupported(OllamaError):
    pass


class LLM:
    def __init__(self, base_url: str, model: Callable[[], str]):
        self.base_url = base_url
        self._model = model
        self._http = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(300, connect=5))
        # One GPU: run one generation at a time so a capture and a chat reply
        # don't fight over VRAM and both crawl.
        self._gpu = asyncio.Lock()

    @property
    def model(self) -> str:
        return self._model()

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "30m",
            "options": {"num_ctx": 8192, "temperature": 0.4},
        }
        if tools:
            body["tools"] = tools
        async with self._gpu:
            try:
                r = await self._http.post("/api/chat", json=body)
            except httpx.ConnectError as e:
                raise OllamaError(
                    f"Ollama isn't answering at {self.base_url}. Start the Ollama app "
                    "(or run `ollama serve`) and try again."
                ) from e
        if r.status_code == 404:
            raise OllamaError(f"Model {self.model} isn't downloaded yet. Run: ollama pull {self.model}")
        if r.status_code == 400 and "does not support tools" in r.text:
            raise ToolsUnsupported(self.model)
        if r.status_code >= 400:
            raise OllamaError(f"Ollama error {r.status_code}: {r.text[:300]}")
        msg = r.json().get("message", {})
        msg["content"] = THINK_RE.sub("", msg.get("content") or "").strip()
        return msg

    async def see(self, jpeg: bytes, prompt: str, system: str) -> str:
        msg = await self.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": prompt, "images": [base64.b64encode(jpeg).decode()]},
        ])
        return msg["content"] or "(the model returned an empty answer)"

    async def installed(self) -> dict[str, float]:
        """name -> size in GB of every model Ollama has on disk."""
        r = await self._http.get("/api/tags", timeout=5)
        r.raise_for_status()
        return {m["name"]: round(m.get("size", 0) / 1024**3, 1) for m in r.json().get("models", [])}

    async def loaded(self) -> list[dict]:
        r = await self._http.get("/api/ps", timeout=5)
        r.raise_for_status()
        return [{"name": m["name"], "vram_gb": round(m.get("size_vram", 0) / 1024**3, 1),
                 "total_gb": round(m.get("size", 0) / 1024**3, 1)} for m in r.json().get("models", [])]

    async def aclose(self) -> None:
        await self._http.aclose()
