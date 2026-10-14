"""Jediný příkaz pro běh aplikace: čte opora.toml (+ opora.local.toml), sestaví frontend, spustí backend.

    uv run opora                      # produkční profil z [app]
    uv run opora --profile preview    # profil z [profiles.preview]
    uv run opora --port 8791 --data .data/kopie --no-open
    uv run opora --check              # jen vypíše výslednou konfiguraci

Soubor `.env` v kořeni repa (je-li) doplní prostředí backendu jen o proměnné, které systém nemá; hodnoty se nevypisují.
"""

import argparse
import os
import re
import socket
import subprocess
import sys
import threading
import tomllib
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "opora.toml"
LOCAL_CONFIG = ROOT / "opora.local.toml"
DOTENV = ROOT / ".env"
DOTENV_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ENV_BY_KEY = {
    "graphify_python": "OPORA_GRAPHIFY_PYTHON",
}
SOURCE_DIRS = ("frontend", "index.html", "vite.config.ts", "package.json")


def load_config(path: Path = CONFIG, local: Path = LOCAL_CONFIG) -> dict:
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    if local.exists():
        merge(config, tomllib.loads(local.read_text(encoding="utf-8")))
    return config


def merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge(base[key], value)
        else:
            base[key] = value
    return base


def resolve(config: dict, profile: str | None = None, **overrides) -> dict:
    """Výsledné nastavení: [app] + [build] + vybraný profil + přepisy z příkazové řádky."""
    app = dict(config.get("app", {}))
    build = dict(config.get("build", {}))
    if profile:
        profiles = config.get("profiles", {})
        if profile not in profiles:
            raise ValueError(f"Profil '{profile}' v opora.toml není. K dispozici: {', '.join(sorted(profiles)) or 'žádný'}.")
        for key, value in profiles[profile].items():
            (build if key in ("frontend", "command") else app)[key] = value
    for key, value in overrides.items():
        if value is not None:
            app[key] = value
    port = int(app.get("port", 8740))
    if not 1 <= port <= 65535:
        raise ValueError("Port musí být 1–65535.")
    return {
        "host": str(app.get("host", "127.0.0.1")),
        "port": port,
        "data": str(app.get("data", ".data/production")),
        "open_browser": bool(app.get("open_browser", False)),
        "title": str(app.get("title", "Opora Canvas")),
        "frontend": str(build.get("frontend", "auto")),
        "build_command": str(build.get("command", "npm run build")),
        "integrations": {k: str(v) for k, v in config.get("integrations", {}).items() if v},
        # Poskytovatel Jev (docs/schranka-neurony.md §7); platnost a varování hlídá backend (typesafe_client).
        "jev_provider": str(config.get("jev", {}).get("provider", "typesafe")),
        # Zrcadlo (docs/zrcadlo.md): výchozí vypnuto; loopback a platnost adresy hlídá backend (mirror_client).
        "mirror": mirror_settings(config.get("mirror", {})),
        "profile": profile or "app",
    }


def mirror_settings(section) -> dict:
    """`[mirror] enabled, url, projects` z TOML; cokoli jiného než `enabled = true` = vypnuto."""
    section = section if isinstance(section, dict) else {}
    projects = section.get("projects", [])
    return {"enabled": section.get("enabled") is True, "url": str(section.get("url", "")),
            "projects": [str(item) for item in projects] if isinstance(projects, list) else []}


def load_dotenv(path: Path = DOTENV, environ=os.environ) -> int:
    """Doplní z `.env` (`KLÍČ=hodnota`) jen proměnné, které prostředí nemá (systém má přednost); vrací počet.

    Prázdné řádky a `#` komentáře se přeskočí, uvozovky kolem hodnoty se odstraní, neplatný řádek se tiše
    vynechá. Hodnoty (klíče API) se nikdy nevypisují ani nelogují."""
    if not path.is_file():
        return 0
    applied = 0
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if key.startswith("export "):
            key = key[len("export "):].strip()
        if not DOTENV_KEY.fullmatch(key):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key not in environ:
            environ[key] = value
            applied += 1
    return applied


def newest_mtime(paths) -> float:
    latest = 0.0
    for item in paths:
        if item.is_file():
            latest = max(latest, item.stat().st_mtime)
        elif item.is_dir():
            for file in item.rglob("*"):
                if file.is_file():
                    latest = max(latest, file.stat().st_mtime)
    return latest


def frontend_stale(root: Path) -> bool:
    index = root / "dist" / "index.html"
    if not index.is_file():
        return True
    return newest_mtime(root / name for name in SOURCE_DIRS) > index.stat().st_mtime


def ensure_frontend(root: Path, mode: str, command: str) -> str:
    if mode == "never":
        return "přeskočeno (frontend = never)"
    if mode == "auto" and not frontend_stale(root):
        return "aktuální, nesestavuje se"
    print(f"[opora] sestavuji frontend: {command}", flush=True)
    result = subprocess.run(command, shell=True, cwd=root, check=False)
    if result.returncode:
        sys.exit(f"[opora] sestavení frontendu selhalo (kód {result.returncode})")
    return "sestaveno"


def port_free(host: str, port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex((host, port)) != 0


def apply_environment(settings: dict, environ=os.environ) -> list[str]:
    environ["OPORA_CANVAS_PORT"] = str(settings["port"])
    environ["OPORA_CANVAS_DATA"] = settings["data"]
    environ["OPORA_JEV_PROVIDER"] = settings["jev_provider"]
    mirror = settings["mirror"]
    environ["OPORA_MIRROR_URL"] = mirror["url"] if mirror["enabled"] else ""
    environ["OPORA_MIRROR_PROJECTS"] = ",".join(mirror["projects"]) if mirror["enabled"] else ""
    applied = []
    for key, value in settings["integrations"].items():
        name = ENV_BY_KEY.get(key)
        if name and not environ.get(name):
            environ[name] = value
            applied.append(name)
    return applied


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Spustí Opora Control Center podle opora.toml.")
    parser.add_argument("--profile", help="název profilu z [profiles.*]")
    parser.add_argument("--port", type=int)
    parser.add_argument("--data", help="adresář s daty (canvas.sqlite)")
    parser.add_argument("--no-open", action="store_true", help="neotvírat prohlížeč")
    parser.add_argument("--no-build", action="store_true", help="nesestavovat frontend")
    parser.add_argument("--check", action="store_true", help="jen vypsat výslednou konfiguraci a skončit")
    args = parser.parse_args(argv)
    loaded = load_dotenv()
    if loaded:
        print(f"[opora] .env: doplněno {loaded} proměnných (hodnoty se nevypisují)")

    try:
        settings = resolve(load_config(), args.profile, port=args.port, data=args.data)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        sys.exit(f"[opora] chyba konfigurace: {exc}")
    if args.no_open:
        settings["open_browser"] = False
    if args.no_build:
        settings["frontend"] = "never"
    data = (ROOT / settings["data"]).resolve()
    url = f"http://{settings['host']}:{settings['port']}/"

    print(f"[opora] profil: {settings['profile']} | {url} | data: {data}")
    if args.check:
        for key in ("frontend", "build_command", "open_browser", "integrations", "jev_provider", "mirror"):
            print(f"[opora] {key}: {settings[key]}")
        return 0
    if not port_free(settings["host"], settings["port"]):
        sys.exit(f"[opora] port {settings['port']} je obsazený; běží už jiná instance?")

    print(f"[opora] frontend: {ensure_frontend(ROOT, settings['frontend'], settings['build_command'])}")
    data.mkdir(parents=True, exist_ok=True)
    applied = apply_environment(settings)
    if applied:
        print(f"[opora] integrace z opora.toml: {', '.join(applied)}")

    sys.path.insert(0, str(ROOT))
    import uvicorn

    from backend.app import create_app

    if settings["open_browser"]:
        threading.Timer(1.2, webbrowser.open, args=(url,)).start()
    uvicorn.run(create_app(data), host=settings["host"], port=settings["port"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
