"""Dotaz Claude Code na oprávnění → rozhodnutí backendu (docs/asistent.md §5.1). Čistá logika.

CLI s `--permission-prompt-tool stdio` posílá `control_request` `can_use_tool` pro každý nástroj
mimo `ALLOWED_TOOLS`. Člověk smí schválit jediné: `Bash` s příkazem `python …opora_write.py <cesta> …`
bez řetězení, přesměrování a substituce. Všechno ostatní backend zamítne sám, bez UI.
"""

from __future__ import annotations

import json
import re
import shlex

AUTO_DENY_MESSAGE = "Asistent zapisuje jen na plátno přes opora_write.py."
DENY_MESSAGE = "Člověk zápis zamítl."
TIMEOUT_MESSAGE = "Bez odpovědi do 10 min platí zamítnutí."
SUMMARY_LIMIT = 2000
REASON_LIMIT = 300
VALUE_LIMIT = 60

# Shodně se seznamem v `opora_write.py` (WRITE_ROUTES).
WRITE_ROUTES = frozenset({
    "/api/graph", "/api/node-spec", "/api/node-text", "/api/desktop-v3/state", "/api/desktop-v3/block",
    "/api/desktop-v3/agent-workspace", "/api/desktop-v3/agent-output",
})
# Celý příkaz: python, skript `…opora_write.py`, cesta a volby. Žádný znak, který by v shellu
# řetězil (`;`, `&`, `|`), přesměroval (`<`, `>`), substituoval (`` ` ``, `$`) nebo zalomil řádek.
# Cesta ke skriptu s mezerou musí být v uvozovkách; jméno souboru je vždy přesně `opora_write.py`.
COMMAND = re.compile(
    r"^python3?(?:\.exe)? +"
    r"(?:\"(?P<quoted>(?:[^\"$`;&|<>\r\n]*[/\\])?opora_write\.py)\""
    r"|(?P<plain>(?:[A-Za-z0-9_.:~/\\-]*[/\\])?opora_write\.py))"
    r" +(?P<route>/api/[a-z0-9/-]+)(?P<rest>(?: +[^;&|<>`$\r\n]*)?)$"
)
# Čtení bez dotazu (§5.1): backend je pustí sám místo volného vzoru v `--allowedTools`. Vzor
# `Bash(python *opora_read.py*)` by pustil i `python -c "…" x/opora_read.py`, tedy libovolný kód.
# Tady musí skript následovat hned po `python` a jméno souboru je přesně `opora_read.py`.
READ_COMMAND = re.compile(
    r"^python3?(?:\.exe)? +"
    r"(?:\"(?:[^\"$`;&|<>\r\n]*[/\\])?opora_read\.py\""
    r"|(?:[A-Za-z0-9_.:~/\\-]*[/\\])?opora_read\.py)"
    r"(?: +[^;&|<>`$\r\n]*)?$"
)
GRAPHIFY_COMMAND = re.compile(r"^graphify +query(?: +[^;&|<>`$\r\n]*)?$")
OPTIONS = {"--project": "project", "--workspace": "workspace", "--json": "json", "--json-file": "jsonFile"}


def _value(value):
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False) if len(value) <= VALUE_LIMIT else f"text {len(value)} zn."
    if isinstance(value, bool) or value is None or isinstance(value, (int, float)):
        return json.dumps(value)
    if isinstance(value, list):
        return f"seznam {len(value)} pol."
    if isinstance(value, dict):
        keys = ", ".join(list(value)[:8]) + (", …" if len(value) > 8 else "")
        return f"objekt {{{keys}}}"
    return type(value).__name__


def payload_summary(payload):
    """Klíče payloadu a jejich velikosti, krátké hodnoty celé; nikdy celé texty. Nejvýš 2000 znaků."""
    parts = [f"{key}: {_value(value)}" for key, value in payload.items() if key not in ("project", "workspace")]
    text = " · ".join(parts) or "prázdný payload"
    return text if len(text) <= SUMMARY_LIMIT else text[: SUMMARY_LIMIT - 1] + "…"


def parse_write(command):
    """`python …opora_write.py <cesta> --project P --workspace W (--json J | --json-file F)` → dict | None."""
    if not isinstance(command, str):
        return None
    match = COMMAND.match(command.strip())
    if not match or match["route"] not in WRITE_ROUTES:
        return None
    try:
        tokens = shlex.split(match["rest"] or "", posix=True)
    except ValueError:
        return None
    found = {}
    while tokens:
        option = tokens.pop(0)
        if option not in OPTIONS or not tokens or OPTIONS[option] in found:
            return None
        found[OPTIONS[option]] = tokens.pop(0)
    if not found.get("project") or not found.get("workspace") or ("json" in found) == ("jsonFile" in found):
        return None
    parsed = {"route": match["route"], "project": found["project"], "workspace": found["workspace"],
              "script": match["quoted"] or match["plain"], "node": None}
    if "jsonFile" in found:
        parsed["payloadSummary"] = f"payload ze souboru {found['jsonFile'][:200]}"
        return parsed
    try:
        payload = json.loads(found["json"])
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    node = payload.get("nodeId", payload.get("node"))
    parsed["node"] = node if isinstance(node, str) else None
    parsed["payloadSummary"] = payload_summary(payload)
    return parsed


def is_read(command):
    """Čtecí příkaz skillu (`opora_read.py`) nebo `graphify query` bez řetězení a substituce."""
    if not isinstance(command, str):
        return False
    command = command.strip()
    return bool(READ_COMMAND.match(command) or GRAPHIFY_COMMAND.match(command))


def classify(request):
    """`request` z `control_request` → ("auto_allow", None), ("auto_deny", zpráva) nebo ("ask", zápis)."""
    data = request if isinstance(request, dict) else {}
    tool_input = data.get("input") if isinstance(data.get("input"), dict) else {}
    if data.get("tool_name") != "Bash":
        return "auto_deny", AUTO_DENY_MESSAGE
    if is_read(tool_input.get("command")):
        return "auto_allow", None
    parsed = parse_write(tool_input.get("command"))
    if parsed is None:
        return "auto_deny", AUTO_DENY_MESSAGE
    return "ask", parsed


def reason_of(request):
    """Krátký důvod dotazu pro kartu schválení: popis od CLI, jinak popis příkazu."""
    data = request if isinstance(request, dict) else {}
    tool_input = data.get("input") if isinstance(data.get("input"), dict) else {}
    for value in (tool_input.get("description"), data.get("description")):
        if isinstance(value, str) and value.strip():
            text = " ".join(value.split())
            return text if len(text) <= REASON_LIMIT else text[: REASON_LIMIT - 1] + "…"
    return "Zápis na plátno přes opora_write.py."


def response(request_id, decision, tool_input=None, note=None):
    """`control_response` na stdin CLI: allow vrací původní input, deny nese zprávu."""
    if decision == "allow":
        answer = {"behavior": "allow", "updatedInput": tool_input if isinstance(tool_input, dict) else {}}
    elif decision == "deny":
        answer = {"behavior": "deny", "message": note.strip() if isinstance(note, str) and note.strip() else DENY_MESSAGE}
    else:
        raise ValueError("Rozhodnutí je allow nebo deny.")
    return {"type": "control_response",
            "response": {"subtype": "success", "request_id": request_id, "response": answer}}


def error_response(request_id, message):
    """Odpověď na `control_request`, který backend neobsluhuje (jiný subtype než can_use_tool)."""
    return {"type": "control_response", "response": {"subtype": "error", "request_id": request_id, "error": message}}


INITIALIZE = {"type": "control_request", "request_id": "init", "request": {"subtype": "initialize"}}
