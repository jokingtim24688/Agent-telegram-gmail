"""Visual memory: every frame the glasses send, with what the AI said about it.

Stored as JPEGs in data/captures/ plus one JSON line per frame in captures.jsonl,
so it's easy to back up, grep, or delete by hand.
"""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

WORD_RE = re.compile(r"[a-z0-9]{3,}")


@dataclass
class Capture:
    id: int
    ts: float
    source: str     # "telegram" or "gmail"
    reason: str     # "button", "remote", "serial", "owner-photo"
    prompt: str
    answer: str
    file: str
    question: str = ""  # what the owner asked, if this frame answers a question

    def when(self) -> str:
        return time.strftime("%a %H:%M", time.localtime(self.ts))


class VisualMemory:
    def __init__(self, data_dir: Path):
        self.dir = data_dir / "captures"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index = data_dir / "captures.jsonl"
        self._lock = threading.Lock()
        self._items: list[Capture] = []
        if self.index.exists():
            for line in self.index.read_text("utf-8").splitlines():
                try:
                    self._items.append(Capture(**json.loads(line)))
                except (ValueError, TypeError):
                    continue

    def add(self, jpeg: bytes, *, source: str, reason: str, prompt: str, answer: str,
            question: str = "") -> Capture:
        with self._lock:
            cid = (self._items[-1].id + 1) if self._items else 1
            ts = time.time()
            name = time.strftime("%Y%m%d-%H%M%S", time.localtime(ts)) + f"-{cid:04d}.jpg"
            (self.dir / name).write_bytes(jpeg)
            cap = Capture(cid, ts, source, reason, prompt, answer, name, question)
            with self.index.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(cap)) + "\n")
            self._items.append(cap)
            return cap

    def path(self, cap: Capture) -> Path:
        return self.dir / cap.file

    def recent(self, limit: int = 60) -> list[Capture]:
        return list(reversed(self._items[-limit:]))

    def search(self, query: str, limit: int = 5) -> list[Capture]:
        words = set(WORD_RE.findall(query.lower()))
        if not words:
            return self.recent(limit)
        scored = []
        for cap in self._items:
            text = f"{cap.answer} {cap.question}".lower()
            score = sum(1 for w in words if w in text)
            if score:
                scored.append((score, cap.ts, cap))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [c for _, _, c in scored[:limit]]

    def __len__(self) -> int:
        return len(self._items)
