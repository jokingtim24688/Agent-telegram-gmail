"""Work out how much GPU memory this machine has and which model fits in it.

Windows/Linux + NVIDIA: dedicated VRAM from nvidia-smi.
Apple Silicon: unified memory; macOS lets the GPU use roughly 2/3 of it
(3/4 above 36 GB) by default, so that's what we count as usable.
"""
from __future__ import annotations

import platform
import subprocess
from dataclasses import asdict, dataclass

# Approximate Ollama download sizes at the default 4-bit quantization.
# "vision" matters: the glasses send photos, so a text-only model can't see them.
CATALOG = [
    {"name": "qwen3-vl:2b", "size_gb": 1.9, "vision": True, "tools": True,
     "note": "Emergency option for machines with under 4 GB of GPU memory. Reads text poorly."},
    {"name": "qwen3-vl:4b", "size_gb": 3.3, "vision": True, "tools": True,
     "note": "Fast, and good enough for scenes. Misreads small print more often."},
    {"name": "qwen3-vl:8b", "size_gb": 6.1, "vision": True, "tools": True,
     "note": "Best fit for 8 GB cards. Strong at reading signs, labels and screens."},
    {"name": "qwen3-vl:30b", "size_gb": 19.0, "vision": True, "tools": True,
     "note": "Mixture-of-experts: big-model quality at small-model speed. Needs a Mac with 32 GB or more."},
    {"name": "llama3.2-vision:11b", "size_gb": 7.8, "vision": True, "tools": False,
     "note": "Fills 8 GB completely, so the context spills to CPU. Can't call tools, so no /look from chat."},
    {"name": "hermes3:8b", "size_gb": 4.7, "vision": False, "tools": True,
     "note": "Text only. It can chat, but it can't see anything the glasses send."},
]

# Headroom for the KV cache at ~8k context plus the CUDA/Metal runtime.
OVERHEAD_GB = 1.2


@dataclass
class Hardware:
    os: str
    cpu: str
    gpu: str
    memory_gb: float      # dedicated VRAM, or total unified memory on Apple Silicon
    usable_gb: float      # what a model can actually occupy
    unified: bool


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def detect() -> Hardware:
    system = platform.system()
    cpu = platform.processor() or platform.machine()

    if system == "Darwin":
        cpu = _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or cpu
        total = int(_run(["sysctl", "-n", "hw.memsize"]) or 0) / 1024**3
        share = 0.75 if total > 36 else 0.66
        return Hardware("macOS", cpu, f"{cpu} GPU (unified memory)", round(total, 1),
                        round(total * share, 1), True)

    if system == "Windows":
        name = _run(["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_Processor).Name"])
        cpu = name or cpu

    smi = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    if smi:
        name, mib = [p.strip() for p in smi.splitlines()[0].split(",")]
        vram = int(mib) / 1024
        return Hardware(system, cpu, name, round(vram, 1), round(vram, 1), False)

    return Hardware(system, cpu, "No NVIDIA GPU found (Ollama will run on the CPU)", 0.0, 0.0, False)


def fits(model_size_gb: float, hw: Hardware) -> bool:
    return model_size_gb + OVERHEAD_GB <= hw.usable_gb


def recommend(hw: Hardware) -> str:
    """Largest vision + tools model that fits entirely in GPU memory."""
    best = "qwen3-vl:4b"  # CPU fallback: slow, but it still works
    for m in CATALOG:
        if m["vision"] and m["tools"] and fits(m["size_gb"], hw):
            best = m["name"]
    return best


def report(hw: Hardware, installed: dict[str, float]) -> dict:
    rec = recommend(hw)
    rows = []
    for m in CATALOG:
        row = dict(m)
        row["installed"] = m["name"] in installed
        if row["installed"]:
            row["size_gb"] = installed[m["name"]]
        row["fits"] = fits(row["size_gb"], hw)
        row["recommended"] = m["name"] == rec
        rows.append(row)
    known = {m["name"] for m in CATALOG}
    for name, size in installed.items():
        if name not in known:
            rows.append({"name": name, "size_gb": size, "vision": None, "tools": None,
                         "note": "Installed locally. Loupe can't tell whether this model has vision.",
                         "installed": True, "fits": fits(size, hw), "recommended": False})
    return {"hardware": asdict(hw), "overhead_gb": OVERHEAD_GB, "recommended": rec, "models": rows}
