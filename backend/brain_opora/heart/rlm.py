"""Knihovna dílny srdce (docs/brain-heart.md §3b), jen standardní knihovna. Supervisor ji před každou dávkou
zkopíruje do `brain/dilna/rlm.py`; skripty ze `scripts/` ji importují (`import rlm`), když běží přes
`python opora_heart.py run`.

    load(name)                    data z `ctx <name>` (`data/<name>.json`)
    files(pattern="*")            relativní cesty souborů zdroje (fnmatch na celou cestu s `/`), bez node_modules aj.
    read(path, start=None, end=None)  text souboru zdroje, volitelně řádky start..end (od 1, včetně)
    grep(pattern, paths=None)     [{path, line, text}] pro regulární výraz přes soubory zdroje
    chunks(items, size)           seznam po dávkách velikosti `size`
    sub(prompt, items, parallel=4)  jeden `claude -p --model haiku` bez nástrojů na položku; odpovědi v pořadí vstupu

Zdroj (`OPORA_SOURCE_ROOT`) je jen ke čtení a cesta mimo něj se odmítne. `sub` smí za jeden `run` nejvýš
`SUB_CAP` volání (počítá je soubor `OPORA_RLM_LOG`, ze kterého `run` sečte cenu) a sub-volání nevolá dál
(`OPORA_RLM_DEPTH`). Klíče API se z prostředí sub-volání odstraní: běží pod předplatným.
"""
import fnmatch
import json
import os
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = re.compile(r"[A-Za-z0-9_-]+\Z")
SKIP = {"node_modules", ".git", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit", ".turbo", ".cache",
        "coverage", "__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache", "target"}
GREP_MAX_BYTES = 2_000_000
SUB_CAP, SUB_TIMEOUT = 20, 100
# Kopie `command.STRIPPED` (knihovna je jen stdlib a leží mimo balíček backendu).
STRIPPED = ("ANTHROPIC_API_KEY", "TYPESAFE_API_KEY", "CELERIS_API_KEY", "OPORA_HEART_TOKEN")
_LOCK = threading.Lock()
_RESERVED = [0]  # sub-volání rezervovaná v tomto procesu (strop platí i pro souběžná volání `sub`)


def load(name):
    """Data, která nahrál `python opora_heart.py ctx <name>`."""
    if not NAME.match(name):
        raise ValueError(f"Neplatné jméno dat {name!r}.")
    return json.loads((HERE / "data" / f"{name}.json").read_text(encoding="utf-8"))


def root():
    value = os.environ.get("OPORA_SOURCE_ROOT", "")
    if not value or not Path(value).is_dir():
        raise RuntimeError("Projekt nemá připojený zdroj (OPORA_SOURCE_ROOT chybí).")
    return Path(value).resolve()


def _inside(path):
    base = root()
    target = (base / path).resolve()
    if target != base and base not in target.parents:
        raise ValueError(f"Cesta {path!r} vede mimo zdroj projektu.")
    return target


def files(pattern="*"):
    """Relativní cesty (`/`) souborů zdroje, které odpovídají `pattern`, seřazené."""
    base, found = root(), []
    for folder, dirs, names in os.walk(base):
        dirs[:] = sorted(name for name in dirs if name not in SKIP and not os.path.islink(os.path.join(folder, name)))
        for name in names:
            rel = os.path.relpath(os.path.join(folder, name), base).replace("\\", "/")
            if fnmatch.fnmatch(rel, pattern):
                found.append(rel)
    return sorted(found)


def read(path, start=None, end=None):
    """Text souboru zdroje; se `start`/`end` jen řádky start..end (číslováno od 1, včetně)."""
    text = _inside(path).read_text(encoding="utf-8", errors="replace")
    if start is None and end is None:
        return text
    lines = text.splitlines(keepends=True)
    return "".join(lines[max((start or 1) - 1, 0):end])


def grep(pattern, paths=None):
    """Řádky odpovídající regulárnímu výrazu: `[{path, line, text}]`; velké a nečitelné soubory se přeskočí."""
    regex, hits = re.compile(pattern), []
    for path in files() if paths is None else paths:
        target = _inside(path)
        try:
            if target.stat().st_size > GREP_MAX_BYTES:
                continue
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits += [{"path": path, "line": number, "text": line.rstrip("\r")}
                 for number, line in enumerate(text.split("\n"), 1) if regex.search(line)]
    return hits


def chunks(items, size):
    """`items` po kouscích velikosti `size`."""
    if size < 1:
        raise ValueError("size musí být aspoň 1.")
    items = list(items)
    return [items[index:index + size] for index in range(0, len(items), size)]


def find_claude(which=shutil.which):
    """Kopie `command.find_claude`: na Windows nejdřív `claude.exe`, pak `claude.cmd`."""
    for name in ("claude.exe", "claude.cmd", "claude") if os.name == "nt" else ("claude",):
        found = which(name)
        if found:
            return found
    return None


def sub_command(claude):
    """Sub-volání bez nástrojů, bez MCP, bez nastavení a bez lomítkových příkazů; text jde na stdin."""
    return [claude, "-p", "--model", "haiku", "--output-format", "json", "--tools", "", "--strict-mcp-config",
            "--setting-sources", "", "--disable-slash-commands"]


def sub_env():
    env = {key: value for key, value in os.environ.items() if key not in STRIPPED}
    env.update({"OPORA_RLM_DEPTH": "1", "PYTHONIOENCODING": "utf-8"})
    return env


def _call(line, text, env):
    """Jedno sub-volání; vrací `(odpověď nebo None, cena USD)`."""
    try:
        done = subprocess.run(line, input=text, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=env, cwd=str(HERE), timeout=SUB_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None, 0.0
    for raw in reversed((done.stdout or "").strip().splitlines()):
        try:
            value = json.loads(raw)
        except ValueError:
            continue
        if isinstance(value, dict):
            answer = None if value.get("is_error") else value.get("result")
            return answer, float(value.get("total_cost_usd") or 0)
    return None, 0.0


def _log():
    value = os.environ.get("OPORA_RLM_LOG", "")
    if not value:
        raise RuntimeError("sub běží jen ve skriptu spuštěném přes `python opora_heart.py run`.")
    return Path(value)


def _used(log):
    try:
        return len(log.read_text(encoding="utf-8").splitlines())
    except OSError:
        return 0


def _text(prompt, item):
    body = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
    return f"{prompt}\n\n---\n{body}"


def sub(prompt, items, parallel=4, call=_call):
    """Jeden levný úsudek (Haiku) na položku; odpovědi v pořadí `items` (None = selhalo)."""
    if os.environ.get("OPORA_RLM_DEPTH"):
        raise RuntimeError("Sub-volání nevolá další sub-volání (hloubka 1).")
    items, log = list(items), _log()
    with _LOCK:
        used = max(_RESERVED[0], _used(log))
        if used + len(items) > SUB_CAP:
            raise RuntimeError(f"Nejvýš {SUB_CAP} sub-volání za jeden run (použito {used}).")
        _RESERVED[0] = used + len(items)
        log.touch()
    claude = find_claude()
    if not claude:
        raise RuntimeError("Nenalezen spustitelný `claude`.")
    line, env = sub_command(claude), sub_env()

    def one(item):
        answer, cost = call(line, _text(prompt, item), env)
        with _LOCK, log.open("a", encoding="utf-8") as file:
            file.write(json.dumps({"ok": answer is not None, "costUsd": round(cost, 6)}) + "\n")
        return answer

    with ThreadPoolExecutor(max_workers=max(1, min(parallel, 8))) as pool:
        return list(pool.map(one, items))
