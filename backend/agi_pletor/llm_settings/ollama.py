"""Ollama na tomto počítači: nainstalované modely (`/api/tags`), co leží v GPU (`/api/ps`) a VRAM z `nvidia-smi`.

VRAM je vedle Ollamy proto, že o GPU se s ní dělí XTTS (hlas Pletora, ~2,3 GB).
"""
import subprocess

from backend.agi_pletor import brains

TIMEOUT = 3
GB = 1024 ** 3


def vram(run=subprocess.run):
    """`{totalGb, usedGb, freeGb}` první GPU NVIDIA, nebo None bez `nvidia-smi`."""
    try:
        done = run(["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"],
                   capture_output=True, text=True, timeout=TIMEOUT, check=True)
        total, used = (int(part) for part in done.stdout.splitlines()[0].split(","))
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None
    return {"totalGb": round(total / 1024, 1), "usedGb": round(used / 1024, 1), "freeGb": round((total - used) / 1024, 1)}


def read(transport=brains.http, run=subprocess.run):
    gpu = vram(run)
    try:
        tags = transport("GET", "/api/tags", None, TIMEOUT).get("models") or []
        ps = transport("GET", "/api/ps", None, TIMEOUT).get("models") or []
    except (OSError, ValueError, AttributeError) as error:
        return {"available": False, "reason": f"Ollama neodpovídá na 127.0.0.1:11434 ({error})"[:200],
                "installed": [], "loaded": [], "vram": gpu}
    return {
        "available": True,
        "installed": [{"name": item["name"], "sizeGb": round((item.get("size") or 0) / GB, 1)} for item in tags],
        "loaded": [{"name": item["name"], "vramGb": round((item.get("size_vram") or 0) / GB, 1)} for item in ps],
        "vram": gpu,
    }
