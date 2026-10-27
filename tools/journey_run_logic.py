"""Čisté funkce runneru cesty zákazníka (`docs/brana-cesty.md` §2 a §3), bez prohlížeče a bez sítě.

`tools/journey_run.py` z nich skládá přehrání plánu `opora.journey-plan/1` a doklad `opora.journey-run/1`.
"""
from __future__ import annotations

import json
import shlex
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

PLAN_SCHEMA = "opora.journey-plan/1"
RUN_SCHEMA = "opora.journey-run/1"
REASON_MAX = 300
COMMAND_MAX = 500
LOG_URL_MAX = 500
MISSING_FORM_DATA = "chybí data formuláře"
# Klíč fixtures, který začíná nebo obsahuje znak selektoru, je CSS selektor; jinak je to popisek pole.
_SELECTOR_MARKS = ("#", ".", "[", ">", ":", "=")


def normalize_path(url: str) -> str:
    """Pathname URL po přechodu: bez query a hash, bez koncového `/` (kromě kořene)."""
    path = urlsplit(url).path or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    return path


def page_url(base_url: str, open_path: str) -> str:
    """baseUrl + open; `open` je cesta od kořene aplikace, ne relativní k cestě v baseUrl."""
    base = base_url.rstrip("/")
    return base + (open_path if open_path.startswith("/") else "/" + open_path)


def href_matches(href: str | None, current_url: str, expect_path: str) -> bool:
    """Míří odkaz (i relativní) na `expectPath`? Porovnává se jen normalizovaná cesta."""
    if not href or href.startswith(("javascript:", "mailto:", "tel:")):
        return False
    if href.startswith("#"):
        return False
    return normalize_path(urljoin(current_url, href)) == normalize_path(expect_path)


def element_strategy(segment: dict) -> dict:
    """Jak v `scope` najít prvek přechodu.

    - s `text`: `get_by_role(role, name=text)`, role v pořadí `roles` (submit jen tlačítko);
    - `click` bez textu: odkaz, jehož `href` míří na `expectPath`;
    - `submit` bez textu: tlačítko odeslání formuláře v `scope`.
    """
    action = segment.get("do") or "click"
    text = segment.get("text")
    if text:
        roles = ["button"] if action == "submit" else ["link", "button"]
        return {"kind": "role", "roles": roles, "name": text}
    if action == "submit":
        return {"kind": "submit-button",
                "selector": "button[type=submit], input[type=submit], button:not([type])"}
    return {"kind": "href", "expectPath": segment["expectPath"]}


def fixture_key(journey_id: str, to_step: str) -> str:
    return f"{journey_id}/{to_step}"


def load_fixtures(path: str | Path | None) -> dict:
    """Načte fixtures `{"<journeyId>/<to>": {selector|label: hodnota}}`; bez souboru prázdná mapa."""
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("fixtures musí být JSON objekt {\"<journeyId>/<to>\": {pole: hodnota}}")
    for key, fields in data.items():
        if not isinstance(fields, dict):
            raise TypeError(f"fixtures[{key!r}] musí být objekt {{selector nebo popisek: hodnota}}")
    return data


def form_data(fixtures: dict, journey_id: str, to_step: str) -> dict[str, str] | None:
    """Data formuláře pro přechod, nebo None (segment pak selže s důvodem „chybí data formuláře“)."""
    fields = fixtures.get(fixture_key(journey_id, to_step))
    if not fields:
        return None
    return {str(key): "" if value is None else str(value) for key, value in fields.items()}


def field_target(key: str) -> tuple[str, str]:
    """`("selector", key)` pro CSS selektor, jinak `("label", key)` pro popisek pole."""
    stripped = key.strip()
    if stripped.startswith(_SELECTOR_MARKS) or any(mark in stripped for mark in ("[", "#")):
        return "selector", stripped
    return "label", stripped


def short_reason(text: str) -> str:
    """Důvod neúspěchu: první neprázdný řádek, nejvýš 300 znaků (§3)."""
    line = next((part.strip() for part in str(text).splitlines() if part.strip()), "neznámá chyba")
    return line if len(line) <= REASON_MAX else line[: REASON_MAX - 1] + "…"


def segment_result(segment: dict, ok: bool, reason: str | None = None) -> dict:
    result = {"from": segment["from"], "to": segment["to"], "ok": bool(ok)}
    if not ok:
        result["reason"] = short_reason(reason or "neznámá chyba")
    return result


def command_line(argv: list[str], interpreter: str = "python") -> str:
    """Skutečný příkazový řádek (cesta skriptu s lomítky), oříznutý na 500 znaků."""
    parts = [interpreter, argv[0].replace("\\", "/"), *argv[1:]] if argv else [interpreter]
    line = shlex.join(parts)
    return line if len(line) <= COMMAND_MAX else line[: COMMAND_MAX - 1] + "…"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def check_plan(plan: object) -> dict:
    """Ověří, že odpověď serveru je plán, kterému runner rozumí."""
    if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"server nevrátil plán {PLAN_SCHEMA}")
    segments = plan.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("plán nemá žádný segment")
    for segment in segments:
        for key in ("from", "to", "open", "scope", "expectPath"):
            if not isinstance(segment.get(key), str):
                raise TypeError(f"segment plánu nemá {key}")
    return plan


def build_run(plan: dict, command: str, at: str, results: list[dict], log_url: str | None = None) -> dict:
    """Doklad `opora.journey-run/1` (§3); `passed` se nepíše, server ho odvodí."""
    run = {
        "schema": RUN_SCHEMA,
        "applicationId": plan["applicationId"],
        "journeyId": plan["journeyId"],
        "planDigest": plan["digest"],
        "command": command[:COMMAND_MAX],
        "at": at,
        "segments": [segment_result(r, r["ok"], r.get("reason")) for r in results],
    }
    if log_url:
        run["logUrl"] = log_url[:LOG_URL_MAX]
    return run


def run_passed(plan: dict, run: dict) -> bool:
    """Stejné pravidlo jako server: všechny segmenty plánu jsou v dokladu a všechny `ok`."""
    done = {(s["from"], s["to"]) for s in run["segments"] if s["ok"]}
    return all((s["from"], s["to"]) in done for s in plan["segments"])
