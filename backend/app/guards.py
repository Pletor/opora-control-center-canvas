"""Registr pojistek OPORY: režim enforce|warn|off na pojistku a projekt (docs/navrhy/2026-11-13-denik-chyb.md §9).

`mode` se volá na horké cestě (agent-state pod zámkem projektu), proto čte tabulku `opora_guards` jednou do
mezipaměti procesu; `set_mode` a `configure` ji zahodí, změna platí hned. Prázdná tabulka = výchozí režimy
z katalogu = dnešní chování. Zablokování i varování jde do deníku chyb frontou (`error_log.submit`).
"""
import sqlite3
from pathlib import Path

from backend.app import error_log, errors

MODES = ("enforce", "warn", "off")
CATALOG = {
    "content_manifest": {
        "protects": "Agent nepracuje nad textem, kresbou ani konfigurací karty, které člověk neschválil (manifest obsahu před převzetím).",
        "default": "enforce", "agent_may_toggle": True, "source": "card",
        "lever": "Přijmi změněný obsah karty (návrh obsahu) nebo vrať živý obsah na přijatý; jinak PUT /api/pletor/guards/content_manifest."},
    "confirmed_reopen": {
        "protects": "Potvrzená (uzavřená) karta se nemění změnou grafu, dokud ji někdo znovu neotevře.",
        "default": "enforce", "agent_may_toggle": True, "source": "card",
        "lever": "Znovu otevři potvrzenou kartu (uzavření karty); jinak PUT /api/pletor/guards/confirmed_reopen."},
    "budget": {
        "protects": "Karta se nepřebírá donekonečna: strop pokusů a kol oprav z rozpočtu, který nastavil člověk.",
        "default": "enforce", "agent_may_toggle": False, "source": "card",
        "lever": "Člověk zvýší rozpočet karty (nová politika rozpočtu) nebo přepne pojistku budget ve Velínu."},
    "sql_context_pin": {
        "protects": "Kontext běhu karty (SQL generace a vazby) se nezmění bez záznamu.",
        "default": "enforce", "agent_may_toggle": False, "source": "integrity", "wired": False,
        "lever": "Checkpoint pinu kontextu (opora_context_bindings); zatím nenapojeno na registr."},
    "heart_hour_cap": {
        "protects": "Srdce nepřekročí strop dávek za hodinu (náklady a limity předplatného).",
        "default": "enforce", "agent_may_toggle": False, "source": "heart",
        "linked": "PUT /api/pletor/heart/caps", "lever": "Člověk změní per_hour v PUT /api/pletor/heart/caps."},
    "gate_setting": {
        "protects": "Srdce nejedná v projektu bez povolení brány.",
        "default": "enforce", "agent_may_toggle": False, "source": "gate",
        "linked": "nastavení projektu: brána (backend/brain_opora/determinism/gate_setting.py)",
        "lever": "Člověk přepne bránu projektu v nastavení projektu."},
    "agent_autonomy": {
        "protects": "Kroky „jen člověk“ dělá agent jen v projektu s plnou autonomií.",
        "default": "enforce", "agent_may_toggle": False, "source": "server",
        "linked": "nastavení projektu: settings.agentAutonomy (backend/project_setup/project_hub.py)",
        "lever": "Člověk zapne plnou autonomii agentů v nastavení projektu."},
}

_path = None
_cache = None


def configure(data_root):
    global _path, _cache
    _path = None if data_root is None else Path(data_root) / "registry.sqlite"
    _cache = None


def _modes():
    """`{(id, project): mode}`; chyba čtení vrátí prázdno bez uložení (příští volání to zkusí znovu)."""
    global _cache
    if _cache is not None:
        return _cache
    if _path is None or not _path.exists():
        _cache = {}
        return _cache
    try:
        db = sqlite3.connect(_path, timeout=2)
        try:
            rows = db.execute("SELECT id, project, mode FROM opora_guards").fetchall()
        finally:
            db.close()
    except sqlite3.Error:
        return {}
    _cache = {(guard, project): mode for guard, project, mode in rows}
    return _cache


def mode(guard, project=""):
    """Režim pojistky: projektový přebije aplikační, jinak výchozí z katalogu. Nikdy nečte databázi dvakrát."""
    modes = _modes()
    return modes.get((guard, project or "")) or modes.get((guard, "")) or CATALOG[guard]["default"]


def check(guard, project, *, blocked, message, subject=None, lever=None):
    """True = blokovat. enforce zapíše `blocked`, warn zapíše varování a pustí dál, off mlčí."""
    if not blocked:
        return False
    current = mode(guard, project)
    if current == "off":
        return False
    entry = CATALOG[guard]
    enforce = current == "enforce"
    error_log.submit(entry["source"], "blocked", message if enforce else f"pojistka {guard} ve warn: by blokovala: {message}",
                     severity="warn", project=project or None, subject=subject, lever=lever or entry["lever"],
                     data={"guard": guard, "mode": current})
    return enforce


def read(project=""):
    """Katalog s aktuálním režimem a jeho původem (projekt / aplikace / výchozí)."""
    modes = _modes()
    out = []
    for guard, entry in CATALOG.items():
        origin = ("project" if project and (guard, project) in modes else "app" if (guard, "") in modes else "default")
        out.append({"id": guard, **{k: v for k, v in entry.items() if k != "source"}, "wired": entry.get("wired", True),
                    "mode": mode(guard, project), "origin": origin})
    return out


def set_mode(guard, project, value, actor, reason):
    """Zapíše režim (projekt '' = celá aplikace), zahodí mezipaměť a změnu zapíše do deníku. `actor` = (druh, jméno).
    Neplatný vstup ValueError; kdo smí přepínat, řeší routa."""
    global _cache
    if guard in CATALOG and CATALOG[guard].get("wired") is False:
        raise ValueError(f"Pojistka {guard} zatím není napojená na registr; přepnutí by nic nezměnilo.")
    if guard not in CATALOG or "linked" in CATALOG[guard]:
        raise ValueError(f"Pojistku {guard} tudy přepnout nejde." + (f" Přepíná ji {CATALOG[guard]['linked']}." if guard in CATALOG else ""))
    if value not in MODES:
        raise ValueError("Režim je enforce, warn nebo off.")
    if _path is None or not _path.exists():
        raise ValueError("Registr pojistek není nastavený.")
    db = sqlite3.connect(_path, timeout=5)
    try:
        with db:
            db.execute("INSERT INTO opora_guards VALUES(?,?,?,?,?,?,?) ON CONFLICT(id, project) DO UPDATE SET mode=excluded.mode,"
                       " changed_at=excluded.changed_at, changed_by=excluded.changed_by, reason=excluded.reason",
                       (guard, "project" if project else "app", project or "", value, errors.now(),
                        ":".join(part for part in actor if part), reason or ""))
    finally:
        db.close()
    _cache = None
    error_log.submit(CATALOG[guard]["source"], "guard", f"pojistka {guard} → {value}: {reason or 'bez důvodu'}",
                     severity="warn", project=project or None, subject=guard, actor=actor,
                     data={"guard": guard, "mode": value})
