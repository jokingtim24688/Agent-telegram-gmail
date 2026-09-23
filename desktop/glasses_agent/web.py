"""Local dashboard at http://127.0.0.1:<DASHBOARD_PORT>. Bound to localhost only:
it can write credentials onto the glasses, so it must not be reachable from the network."""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import hardware, provision

STATIC = Path(__file__).parent / "static"


class LookBody(BaseModel):
    question: str = ""


class ModelBody(BaseModel):
    name: str


class Wifi(BaseModel):
    ssid: str
    password: str = ""


class ProvisionBody(BaseModel):
    port: str
    wifi: list[Wifi]
    btn_pin: int | None = None


class PortBody(BaseModel):
    port: str | None = None


def create_app(core) -> FastAPI:
    app = FastAPI(title="Loupe", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    port = core.settings.dashboard_port
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        # Blocks DNS-rebinding: a web page can't pose as localhost to reach this API.
        if request.headers.get("host") not in allowed_hosts:
            return PlainTextResponse("Loupe only answers on localhost.", status_code=403)
        return await call_next(request)

    def capture_json(c):
        d = asdict(c)
        d["image"] = f"/captures/{c.file}"
        d["when"] = c.when()
        return d

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/captures/{name}")
    async def capture_file(name: str):
        path = (core.memory.dir / name).resolve()
        if path.parent != core.memory.dir.resolve() or not path.exists():
            raise HTTPException(404)
        return FileResponse(path, media_type="image/jpeg")

    @app.get("/api/status")
    async def status():
        st = core.state
        return {
            "components": core.status.components,
            "model": core.model(),
            "busy": core.busy,
            "problems": core.settings.problems(),
            "glasses": {"seen": core.glasses_seen, "info": core.glasses_info},
            "pending_look": core.pending_look[0] if core.pending_look else None,
            "people": {
                "ai": st.get("me_name"),
                "owner": st.get("owner_name"),
                "glasses_bot": st.get("bot_username"),
                "group": core.settings.group_title if st.get("group_id") else None,
            },
            "captures": len(core.memory),
            "now": time.time(),
        }

    @app.get("/api/captures")
    async def captures(q: str = "", limit: int = 60):
        items = core.memory.search(q, limit) if q.strip() else core.memory.recent(limit)
        return {"items": [capture_json(c) for c in items]}

    @app.post("/api/look")
    async def look(body: LookBody):
        detail = await core.request_snapshot(body.question.strip() or "What am I looking at?")
        ok = detail.startswith("Snapshot requested")
        return {"ok": ok, "detail": "Asked the glasses for a photo." if ok else detail}

    @app.post("/api/ping")
    async def ping():
        if not (core.telegram and core.telegram.ready):
            return {"ok": False, "detail": "The AI's Telegram account isn't connected yet."}
        await core.telegram.send_ping()
        return {"ok": True, "detail": "Pinged. The glasses reply with a #status line in the group."}

    @app.get("/api/hardware")
    async def hw():
        try:
            installed = await core.llm.installed()
            loaded = await core.llm.loaded()
        except Exception:  # noqa: BLE001 — Ollama down: still show what fits
            installed, loaded = {}, []
        out = hardware.report(core.hw, installed)
        out.update(current=core.model(), loaded=loaded, ollama_up=bool(installed) or bool(loaded))
        return out

    @app.post("/api/model")
    async def set_model(body: ModelBody):
        core.state.set(model=body.name.strip())
        return {"ok": True, "detail": f"Loupe will use {core.model()} from the next message on."}

    @app.get("/api/ports")
    async def list_ports():
        return {"ports": provision.ports()}

    @app.post("/api/provision")
    async def do_provision(body: ProvisionBody):
        try:
            payload = provision.build_payload(
                core.settings, core.state,
                [{"ssid": w.ssid, "pass": w.password} for w in body.wifi], body.btn_pin)
            result = await asyncio.to_thread(provision.send, body.port, payload)
        except provision.ProvisionError as e:
            return {"ok": False, "detail": str(e)}
        if not result.get("ok"):
            return {"ok": False, "detail": f"The board rejected it: {result.get('error', result)}"}
        return {"ok": True, "detail": "Saved on the glasses. They're restarting and will join Wi-Fi; "
                                      "watch the group for their #status line."}

    @app.post("/api/board-status")
    async def board_status(body: PortBody):
        if not body.port:
            return {"ok": False, "detail": "Pick the glasses' USB port first."}
        try:
            return {"ok": True, "board": await asyncio.to_thread(provision.send, body.port, {"cmd": "status"}, 4.0)}
        except provision.ProvisionError as e:
            return {"ok": False, "detail": str(e)}

    @app.post("/api/flash")
    async def do_flash(body: PortBody):
        ok, output = await asyncio.to_thread(provision.flash, body.port)
        return {"ok": ok, "detail": "Firmware flashed." if ok else "Flashing failed. See the log below.",
                "output": output}

    return app
