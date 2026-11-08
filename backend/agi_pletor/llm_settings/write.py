"""Zápis modelu LLM (M2, zúžený): `model` do `~/.claude/settings.json`, `model` + `model_reasoning_effort` do `~/.codex/config.toml`.

Cesty jen z `Path.home()`; před zápisem záloha `<soubor>.bak-<YYYYMMDD-HHMMSS>`, ostatní klíče zůstanou.
Soubory s tajemstvím (`auth.json`, `.credentials.json`, `.env`) se nikdy neotevírají.
"""
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from backend.agi_pletor.llm_settings import claude, codex

REASONING = ("low", "medium", "high")
_MODEL = re.compile(r"[A-Za-z0-9._:\-]{1,100}")


def check_model(model):
    if not isinstance(model, str) or not _MODEL.fullmatch(model):
        raise ValueError("model je neprázdný řetězec do 100 znaků z písmen, číslic a znaků - . _ :")
    return model


def reasoning_levels(model):
    """Úrovně reasoning modelu z cache Codexu; model bez nich (nebo prázdná cache) = `REASONING`."""
    found = next((item["reasoning"] for item in codex.models() if item["id"] == model), None)
    return tuple(found) if found else REASONING


def _backup(path: Path):
    """Záloha existujícího souboru vedle něj; vrací její název (nebo None, když soubor ještě nebyl)."""
    if not path.is_file():
        return None
    copy = path.with_name(f"{path.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(path, copy)
    return copy.name


def claude_model(model, effort=None):
    """`effort` None = výchozí (klíč `effortLevel` se odstraní)."""
    check_model(model)
    if effort is not None and effort not in claude.EFFORTS:
        raise ValueError(f"effort je {', '.join(claude.EFFORTS)}.")
    path = Path.home() / ".claude" / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if not isinstance(settings, dict):
        raise ValueError("settings.json není objekt, nepřepisuji ho.")
    backup = _backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    settings = {key: value for key, value in settings.items() if key != "effortLevel"}
    settings.update(model=model, **({"effortLevel": effort} if effort else {}))
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**claude.read(), "backup": backup}


def _set_top_level(text: str, values: dict) -> str:
    """Nahradí nebo doplní klíče nad první tabulkou `[...]`; zbytek souboru zůstane beze změny (shortcut: jen jednořádkové hodnoty)."""
    lines = text.splitlines()
    end = next((i for i, line in enumerate(lines) if line.lstrip().startswith("[")), len(lines))
    for key, value in values.items():
        row = f"{key} = {json.dumps(value)}"
        at = next((i for i in range(end) if re.match(rf"\s*{key}\s*=", lines[i])), None)
        if value is None:  # None = klíč pryč (výchozí)
            if at is not None:
                del lines[at]
                end -= 1
        elif at is None:
            lines.insert(end, row)
            end += 1
        else:
            lines[at] = row
    return "\n".join(lines) + "\n"


def codex_model(model, reasoning=None):
    check_model(model)
    levels = reasoning_levels(model)
    if reasoning is not None and reasoning not in levels:
        raise ValueError(f"reasoning je {', '.join(levels)}.")
    path = Path.home() / ".codex" / "config.toml"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    backup = _backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    values = {"model": model, "model_reasoning_effort": reasoning or None}
    path.write_text(_set_top_level(text, values), encoding="utf-8")
    return {**codex.read(), "backup": backup}
