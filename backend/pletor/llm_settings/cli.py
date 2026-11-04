"""Verze CLI nástroje (`<cesta> --version`) s krátkým timeoutem; chybějící nebo neodpovídající nástroj = None."""
import subprocess

TIMEOUT = 5


def version(path, run=subprocess.run):
    if not path:
        return None
    try:
        done = run([path, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                   timeout=TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    line = (done.stdout or "").strip().splitlines()
    return line[0][:100] if done.returncode == 0 and line else None
