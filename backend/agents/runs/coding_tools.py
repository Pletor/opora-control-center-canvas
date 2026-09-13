"""Úzké nástroje pro skutečný, ale výslovně ohraničený coding test."""
import hashlib
import os
import re
import stat
import subprocess
from pathlib import Path

IMAGE = "sha256:7ce4b6dfe35e55397b7cda544f8a13f191b7ae28dc5aad71fe664dbc9bc2623f"
ALLOWED = ["calculator.py"]


class ScopedFiles:
    def __init__(self, root):
        self.root = Path(root).absolute()
        if self.root.resolve() != self.root:
            raise ValueError("Pracovní cesta nesmí být přesměrovaná.")

    def path(self, name):
        if name not in ALLOWED:
            raise ValueError("Soubor není v povoleném scope.")
        path = self.root / name
        if self.root.resolve() != self.root or path.resolve() != path:
            raise ValueError("Přesměrovaná cesta není povolena.")
        info = path.stat()
        if info.st_nlink != 1 or not stat.S_ISREG(info.st_mode) or info.st_size > 64000:
            raise ValueError("Soubor nemá bezpečný tvar.")
        return path

    def read(self, name):
        return self.path(name).read_text(encoding="utf-8")

    def write(self, name, content):
        if not isinstance(content, str) or len(content) > 16000 or "\0" in content:
            raise ValueError("Neplatný nebo příliš dlouhý obsah.")
        path = self.path(name)
        path.write_text(content, encoding="utf-8")
        saved = self.path(name).read_bytes()
        return {"path": name, "sha256": hashlib.sha256(saved).hexdigest(), "bytes": len(saved)}


def container_name(run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise ValueError("Neplatná identita testu.")
    return "opora-canvas-" + run_id


def docker(*args, timeout=12):
    return subprocess.run(["docker", *args], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env={k: v for k, v in os.environ.items() if not k.startswith("DOCKER_")})


def cleanup_container(run_id):
    name = container_name(run_id)
    try:
        # Přesné serverové ID, žádný globální prune či name-based kill.
        docker("rm", "-f", name)
        result = docker("container", "ls", "-a", "--filter", "name=^/" + name + "$", "--format", "{{.Names}}")
        return result.returncode == 0 and not result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False


def run_tests(root, run_id):
    files = ScopedFiles(root)
    source = files.path("calculator.py")
    oracle = Path(__file__).with_name("coding_oracle.py").resolve()
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    name = container_name(run_id)
    try:
        result = docker("run", "--rm", "--pull=never", "--name", name,
                        "--network=none", "--read-only", "--cap-drop=ALL",
                        "--security-opt=no-new-privileges", "--memory=128m", "--cpus=1",
                        "--pids-limit=32", "--user=65534:65534", "--tmpfs=/tmp:rw,noexec,nosuid,size=16m",
                        "--mount", f"type=bind,source={source},target=/work/calculator.py,readonly",
                        "--mount", f"type=bind,source={oracle},target=/runner/oracle.py,readonly",
                        IMAGE, "python", "-I", "-B", "/runner/oracle.py", timeout=25)
        output = (result.stdout + result.stderr)[-16000:]
        return {"command": "python -I -B /runner/oracle.py (Docker, network=none)", "exitCode": result.returncode, "output": output, "sourceSha256": source_hash, "image": IMAGE}
    finally:
        if not cleanup_container(run_id):
            raise OSError("Zastavení testovacího kontejneru nebylo ověřeno.")
