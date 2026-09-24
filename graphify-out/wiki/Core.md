# Core

> 14 nodes

## Key Concepts

- **Core** (19 connections) — `desktop/glasses_agent/core.py`
- **.handle_frame()** (6 connections) — `desktop/glasses_agent/core.py`
- **.model()** (4 connections) — `desktop/glasses_agent/core.py`
- **.notify_owner()** (3 connections) — `desktop/glasses_agent/core.py`
- **._question_for_frame()** (3 connections) — `desktop/glasses_agent/core.py`
- **.chat()** (2 connections) — `desktop/glasses_agent/core.py`
- **.glasses_heard()** (2 connections) — `desktop/glasses_agent/core.py`
- **.request_snapshot()** (2 connections) — `desktop/glasses_agent/core.py`
- **.watch_ollama()** (2 connections) — `desktop/glasses_agent/core.py`
- **Path** (1 connections)
- **Telegram first. If that fails, fall back to email so nothing gets lost.** (1 connections) — `desktop/glasses_agent/core.py`
- **Tool + /look + dashboard button: make the glasses take a photo now.** (1 connections) — `desktop/glasses_agent/core.py`
- **If this frame answers a /look, return that question (once).** (1 connections) — `desktop/glasses_agent/core.py`
- **A frame arrived (Telegram group or Gmail backup): describe it, store it, report…** (1 connections) — `desktop/glasses_agent/core.py`

## Relationships

- [core.py](core.py.md) (8 shared connections)
- [provision.py](provision.py.md) (4 shared connections)

## Source Files

- `desktop/glasses_agent/core.py`

## Audit Trail

- EXTRACTED: 23 (77%)
- INFERRED: 7 (23%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*