"""Talk to the glasses over USB: write credentials, read status, flash firmware.

The board speaks one JSON object per line (see firmware/glasses/src/main.cpp).
Log lines from the board start with "# " and are skipped here.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports

from .config import FIRMWARE_DIR, Settings, State

ESPRESSIF_VID = 0x303A  # native USB on the ESP32-S3


class ProvisionError(RuntimeError):
    pass


def ports() -> list[dict]:
    out = []
    for p in list_ports.comports():
        out.append({
            "device": p.device,
            "description": p.description or "",
            "likely_glasses": p.vid == ESPRESSIF_VID,
        })
    out.sort(key=lambda p: not p["likely_glasses"])
    return out


def _open(port: str) -> serial.Serial:
    s = serial.Serial()
    s.port = port
    s.baudrate = 115200
    s.timeout = 0.2
    # Keep DTR/RTS low: toggling them resets the ESP32-S3 on some USB setups.
    s.dtr = False
    s.rts = False
    try:
        s.open()
    except serial.SerialException as e:
        text = str(e).lower()
        if "access" in text or "busy" in text or "permission" in text:
            raise ProvisionError(
                f"{port} is busy. Close anything else that has it open (the PlatformIO serial monitor, "
                "Arduino IDE, another Loupe window) and try again.") from e
        raise ProvisionError(f"Couldn't open {port}: {e}. Unplug the glasses, plug them back in, "
                             "then pick the port again.") from e
    return s


def send(port: str, payload: dict, wait_s: float = 8.0) -> dict:
    with _open(port) as s:
        time.sleep(0.3)
        s.reset_input_buffer()
        s.write((json.dumps(payload) + "\n").encode())
        s.flush()
        deadline = time.time() + wait_s
        buf = b""
        while time.time() < deadline:
            buf += s.read(512)
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if line.startswith(b"{"):
                    try:
                        return json.loads(line)
                    except ValueError:
                        continue
    raise ProvisionError(
        f"The board on {port} didn't answer. Check that the Loupe firmware is flashed "
        "(the Flash firmware button), then try again.")


def build_payload(settings: Settings, state: State, wifi: list[dict], btn_pin: int | None = None) -> dict:
    """Everything the glasses need, gathered from .env and what the AI account learned at login."""
    missing = []
    if not settings.glasses_bot_token:
        missing.append("GLASSES_BOT_TOKEN in desktop/.env")
    if not state.get("me_id"):
        missing.append("the AI account's login (run: python -m glasses_agent login)")
    if not state.get("group_id"):
        missing.append("the group (start Loupe once with the AI logged in; it creates the group)")
    wifi = [w for w in wifi if w.get("ssid")]
    if not wifi:
        missing.append("at least one Wi-Fi network")
    if missing:
        raise ProvisionError("Can't set up the glasses yet. Missing: " + "; ".join(missing) + ".")

    payload = {
        "cmd": "provision",
        "wifi": [{"ssid": w["ssid"], "pass": w.get("pass", "")} for w in wifi[:3]],
        "tg_token": settings.glasses_bot_token,
        "tg_chat": str(state.get("group_id")),
        "tg_from": str(state.get("me_id")),  # the only sender the glasses obey
    }
    if settings.glasses_gmail and settings.glasses_gmail_app_password and settings.ai_gmail:
        payload.update(gm_user=settings.glasses_gmail, gm_pass=settings.glasses_gmail_app_password,
                       gm_to=settings.ai_gmail)
    if btn_pin is not None:
        payload["btn_pin"] = int(btn_pin)
    return payload


def find_pio() -> str | None:
    found = shutil.which("pio") or shutil.which("platformio")
    if found:
        return found
    home = Path.home() / ".platformio" / "penv"
    for candidate in (home / "Scripts" / "pio.exe", home / "bin" / "pio"):
        if candidate.exists():
            return str(candidate)
    return None


def flash(port: str | None) -> tuple[bool, str]:
    pio = find_pio()
    if not pio:
        return False, ("PlatformIO isn't installed. Install the PlatformIO extension in Antigravity, "
                       f"or run: {sys.executable} -m pip install platformio")
    cmd = [pio, "run", "-d", str(FIRMWARE_DIR), "-t", "upload"]
    if port:
        cmd += ["--upload-port", port]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    output = (proc.stdout + proc.stderr)[-4000:]
    return proc.returncode == 0, output
