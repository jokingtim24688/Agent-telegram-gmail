"""Loupe desktop.

  python -m glasses_agent login        sign the AI's Telegram account in (once)
  python -m glasses_agent              run the AI + dashboard (http://127.0.0.1:8765)
  python -m glasses_agent ports        list USB serial ports
  python -m glasses_agent provision --port COM5 --wifi "Home:pass" --wifi "Phone:pass"
  python -m glasses_agent flash --port COM5
  python -m glasses_agent doctor       check setup without starting anything
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import webbrowser

from . import config, hardware, provision


def _wifi_arg(value: str) -> dict:
    ssid, sep, password = value.partition(":")
    if not sep:
        raise argparse.ArgumentTypeError('use "SSID:password"')
    return {"ssid": ssid, "pass": password}


async def run(settings: config.Settings, open_browser: bool) -> None:
    import uvicorn

    from .core import Core
    from .gmail_backup import GmailBackup
    from .telegram_service import TelegramService
    from .web import create_app

    core = Core(settings)
    core.telegram = TelegramService(core)
    core.gmail = GmailBackup(core)

    server = uvicorn.Server(uvicorn.Config(create_app(core), host="127.0.0.1",
                                           port=settings.dashboard_port, log_level="warning"))
    url = f"http://127.0.0.1:{settings.dashboard_port}"
    print(f"Loupe is running. Dashboard: {url}  (Ctrl+C to stop)")
    print(f"Model: {core.model()} on {core.hw.gpu} ({core.hw.usable_gb} GB usable)")
    if open_browser:
        asyncio.get_running_loop().call_later(1.5, webbrowser.open, url)
    try:
        await asyncio.gather(server.serve(), core.telegram.run(), core.gmail.run(), core.watch_ollama())
    finally:
        await core.llm.aclose()


def doctor(settings: config.Settings) -> int:
    hw = hardware.detect()
    state = config.State()
    print(f"Machine:   {hw.os}, {hw.cpu}")
    print(f"GPU:       {hw.gpu}, {hw.usable_gb} GB usable for models")
    print(f"Model:     {state.get('model') or settings.model or hardware.recommend(hw)}"
          f"  (best fit here: {hardware.recommend(hw)})")
    print(f"AI acct:   {state.get('me_name') or 'not logged in'}")
    print(f"Group:     {settings.group_title if state.get('group_id') else 'not created yet'}")
    problems = settings.problems()
    for p in problems:
        print(f"  - {p}")
    if not problems:
        print("Config looks complete.")
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="glasses_agent", description="Loupe: local AI for ESP32 camera glasses")
    sub = parser.add_subparsers(dest="cmd")
    p_run = sub.add_parser("run", help="run the AI and the dashboard (default)")
    p_run.add_argument("--no-browser", action="store_true")
    sub.add_parser("login", help="sign the AI's Telegram account in")
    sub.add_parser("ports", help="list serial ports")
    sub.add_parser("doctor", help="check setup")
    p_prov = sub.add_parser("provision", help="write credentials onto the glasses over USB")
    p_prov.add_argument("--port", required=True)
    p_prov.add_argument("--wifi", type=_wifi_arg, action="append", required=True,
                        help='"SSID:password"; repeat for up to 3 networks (home, phone hotspot…)')
    p_prov.add_argument("--button-pin", type=int)
    p_flash = sub.add_parser("flash", help="build and upload the firmware with PlatformIO")
    p_flash.add_argument("--port")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = config.load()

    if args.cmd == "login":
        from .telegram_service import interactive_login
        if not (settings.tg_api_id and settings.tg_api_hash):
            print("Fill TG_API_ID and TG_API_HASH in desktop/.env first (from my.telegram.org).")
            return 1
        asyncio.run(interactive_login(settings))
        return 0
    if args.cmd == "ports":
        for p in provision.ports():
            mark = "  <- looks like the glasses" if p["likely_glasses"] else ""
            print(f"{p['device']:<14} {p['description']}{mark}")
        return 0
    if args.cmd == "doctor":
        return doctor(settings)
    if args.cmd == "provision":
        try:
            payload = provision.build_payload(settings, config.State(), args.wifi, args.button_pin)
            print(json.dumps(provision.send(args.port, payload)))
        except provision.ProvisionError as e:
            print(e)
            return 1
        return 0
    if args.cmd == "flash":
        ok, output = provision.flash(args.port)
        print(output)
        return 0 if ok else 1

    try:
        asyncio.run(run(settings, open_browser=not getattr(args, "no_browser", False)))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
