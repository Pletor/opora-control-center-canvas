"""Dotaz Claude Code na oprávnění → rozhodnutí backendu (docs/asistent.md §5.1). Čistá logika.

CLI s `--permission-prompt-tool stdio` posílá `control_request` `can_use_tool` pro každý nástroj
mimo `ALLOWED_TOOLS`. Člověk smí schválit jediné: `Bash` s příkazem `python …opora_write.py <cesta> …`
bez řetězení, přesměrování a substituce. Bez dotazu projde čtecí Bash a `Write` konceptu do adresáře
konceptů té session (docs/davka-planu.md §2). `opora_write.py /api/canvas-plan … --dry-run` nic nezapisuje
(jen ověří dávku), proto projde bez dotazu; `--dry-run` u jiné cesty se zamítne (§3). Všechno ostatní backend zamítne sám, bez UI.
Jediné I/O: `resolve` cest a čtení konceptu u `--json-file` (souhrn ukazuje skutečný obsah).
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from pathlib import Path

from backend.canvas.canvas_plan_summary import plan_summary as canvas_plan_summary

AUTO_DENY_MESSAGE = "Asistent zapisuje jen na plátno přes opora_write.py."
DENY_MESSAGE = "Člověk zápis zamítl."
TIMEOUT_MESSAGE = "Bez odpovědi do 10 min platí zamítnutí."
SUMMARY_LIMIT = 2000
REASON_LIMIT = 300
VALUE_LIMIT = 60
# Koncept zápisu (docs/davka-planu.md §2): stejný strop jako `MAX_PAYLOAD` v `opora_write.py`.
DRAFT_LIMIT = 2 * 1024 * 1024
DRAFT_SUFFIX = ".json"

# Shodně se seznamem v `opora_write.py` (WRITE_ROUTES).
WRITE_ROUTES = frozenset({
    "/api/desktop-v3/lease",
    "/api/desktop-v3/realize-source",
    "/api/canvas-layout",
    "/api/desktop-v3/assignment-snapshot",
    "/api/canvas-versions",
    "/api/desktop-v3/rule", "/api/desktop-v3/decision",
    "/api/graph", "/api/node-spec", "/api/node-text", "/api/desktop-v3/state", "/api/desktop-v3/block",
    "/api/desktop-v3/agent-workspace", "/api/desktop-v3/agent-output", "/api/canvas-plan",
    "/api/desktop-v3/pipeline",
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
# Cesta je připnutá ke složce skillu (upgrade-opora #42): podstrčený `x/opora_read.py` jinde neprojde.
READ_COMMAND = re.compile(
    r"^python3?(?:\.exe)? +"
    r"(?:\"(?:[^\"$`;&|<>\r\n]*[/\\])?opora-control-center[/\\]scripts[/\\]opora_read\.py\""
    r"|(?:[A-Za-z0-9_.:~/\\-]*[/\\])?opora-control-center[/\\]scripts[/\\]opora_read\.py)"
    r"(?: +[^;&|<>`$\r\n]*)?$"
)
# Převzetí a snímek zadání nemění obsah karty: bez dotazu, jinak by člověk schvaloval každý heartbeat.
NO_PROMPT_ROUTES = frozenset({"/api/desktop-v3/lease", "/api/desktop-v3/assignment-snapshot"})
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


# Dávka plánu (docs/davka-planu.md §3): souhrn počtů místo klíčů, aby člověk viděl, co přidá.
# Text počítá `canvas_plan_summary` — tentýž, jaký vrátí `/api/canvas-plan`.
def plan_summary(payload):
    """Souhrn dávky `/api/canvas-plan` z nepřeloženého `plan`; u `dryRun` s upozorněním."""
    text = canvas_plan_summary(payload.get("plan"))
    if payload.get("dryRun") is True:
        text = "Jen ověření (dryRun), nic nezapíše. " + text
    return text if len(text) <= SUMMARY_LIMIT else text[: SUMMARY_LIMIT - 1] + "…"


def state_summary(payload):
    """Celý stav (`/api/desktop-v3/state`): co zápis obsahuje, aby člověk neschvaloval naslepo."""
    raw_state, raw_nodes, raw_rules = payload.get("state"), None, None
    state = raw_state if isinstance(raw_state, dict) else {}
    raw_nodes, raw_rules = state.get("nodes"), state.get("rules")
    nodes = raw_nodes if isinstance(raw_nodes, dict) else {}
    rules = raw_rules if isinstance(raw_rules, list) else []
    closed = sum(1 for node in nodes.values() if isinstance(node, dict) and isinstance(node.get("done"), dict)
                 and node["done"].get("confirmed") is True)
    proposed = sum(1 for node in nodes.values() if isinstance(node, dict) and isinstance(node.get("done"), dict)
                   and node["done"].get("by") == "agent" and node["done"].get("confirmed") is False)
    text = (f"Celý stav plátna: {len(nodes)} karet · {len(rules)} pravidel · uzavřeno {closed} · "
            f"návrhů uzavření {proposed}. Zápis přepíše stav; pravidla člověka a uzavření server agentovi nedovolí změnit.")
    return text if len(text) <= SUMMARY_LIMIT else text[: SUMMARY_LIMIT - 1] + "…"


def summary_of(route, payload):
    if route == "/api/canvas-plan":
        return plan_summary(payload)
    return state_summary(payload) if route == "/api/desktop-v3/state" else payload_summary(payload)


def _inside_drafts(value, drafts_dir, *, must_exist):
    """Rozlišená cesta souboru `*.json` uvnitř adresáře konceptů session, jinak None.

    `resolve` odstraní `..` a následuje symlinky, takže odkaz ven skončí mimo adresář. Cesta musí být
    absolutní (relativní by backend rozlišil od jiného cwd než CLI) a adresář konceptů musí existovat.
    """
    if not isinstance(value, str) or not value or drafts_dir is None or "\x00" in value:
        return None
    try:
        drafts = Path(drafts_dir).resolve(strict=True)
        candidate = Path(value)
        if not candidate.is_absolute() or not drafts.is_dir():
            return None
        resolved = candidate.resolve(strict=must_exist)
    except (OSError, RuntimeError, ValueError):
        return None
    name = resolved.name
    # Dvojtečka ve jménu je alternativní datový proud NTFS (`x:y.json`), ne soubor konceptu.
    if resolved == drafts or not resolved.is_relative_to(drafts) or ":" in name:
        return None
    return resolved if name.endswith(DRAFT_SUFFIX) and name != DRAFT_SUFFIX else None


def is_draft_write(tool_input, drafts_dir):
    """`Write` konceptu: `file_path` v adresáři konceptů té session, `*.json`, obsah do 2 MiB."""
    content = tool_input.get("content")
    if not isinstance(content, str) or len(content.encode("utf-8", "surrogatepass")) > DRAFT_LIMIT:
        return False
    return _inside_drafts(tool_input.get("file_path"), drafts_dir, must_exist=False) is not None


def read_draft(value, drafts_dir):
    """Koncept pro `--json-file`: (rozlišená cesta, sha256 obsahu, JSON objekt) nebo None."""
    path = _inside_drafts(value, drafts_dir, must_exist=True)
    if path is None or not path.is_file():
        return None
    try:
        with open(path, "rb") as handle:
            raw = handle.read(DRAFT_LIMIT + 1)
        if len(raw) > DRAFT_LIMIT:
            return None
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError):
        return None
    return (path, hashlib.sha256(raw).hexdigest(), payload) if isinstance(payload, dict) else None


def draft_digest(value, drafts_dir):
    """Otisk konceptu v okamžiku rozhodnutí; povolení platí jen pro obsah, který člověk viděl."""
    draft = read_draft(value, drafts_dir)
    return draft[1] if draft else None


def parse_write(command, drafts_dir=None):
    """`python …opora_write.py <cesta> --project P --workspace W (--json J | --json-file F)` → dict | None.

    `--json-file` platí jen pro koncept v `drafts_dir` (adresář konceptů session): souhrn je z obsahu
    souboru a `fileDigest` je jeho otisk, který správce ověří těsně před povolením.
    """
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
    dry_run = False
    while tokens:
        option = tokens.pop(0)
        if option == "--dry-run":  # volba bez hodnoty, nejvýš jednou
            if dry_run:
                return None
            dry_run = True
            continue
        if option not in OPTIONS or not tokens or OPTIONS[option] in found:
            return None
        found[OPTIONS[option]] = tokens.pop(0)
    if not found.get("project") or not found.get("workspace") or ("json" in found) == ("jsonFile" in found):
        return None
    if dry_run and match["route"] != "/api/canvas-plan":
        return None
    parsed = {"route": match["route"], "project": found["project"], "workspace": found["workspace"],
              "script": match["quoted"] or match["plain"], "node": None}
    if "jsonFile" in found:
        draft = read_draft(found["jsonFile"], drafts_dir)
        if draft is None:
            return None
        path, digest, payload = draft
        parsed["jsonFile"], parsed["fileDigest"] = str(path), digest
    else:
        try:
            payload = json.loads(found["json"])
        except ValueError:
            return None
        if not isinstance(payload, dict):
            return None
    node = payload.get("nodeId", payload.get("node"))
    parsed["node"] = node if isinstance(node, str) else None
    if dry_run:
        parsed["dryRun"] = True
        payload = {**payload, "dryRun": True}
    parsed["payloadSummary"] = summary_of(match["route"], payload)
    return parsed


def is_read(command):
    """Čtecí příkaz skillu (`opora_read.py`) nebo `graphify query` bez řetězení a substituce."""
    if not isinstance(command, str):
        return False
    command = command.strip()
    return bool(READ_COMMAND.match(command) or GRAPHIFY_COMMAND.match(command))


def classify(request, drafts_dir=None):
    """`request` z `control_request` → ("auto_allow", None), ("auto_deny", zpráva) nebo ("ask", zápis).

    `drafts_dir` je adresář konceptů session, jíž dotaz patří; bez něj žádný koncept neprojde.
    """
    data = request if isinstance(request, dict) else {}
    tool_input = data.get("input") if isinstance(data.get("input"), dict) else {}
    if data.get("tool_name") == "Write" and is_draft_write(tool_input, drafts_dir):
        return "auto_allow", None
    if data.get("tool_name") != "Bash":
        return "auto_deny", AUTO_DENY_MESSAGE
    if is_read(tool_input.get("command")):
        return "auto_allow", None
    parsed = parse_write(tool_input.get("command"), drafts_dir)
    if parsed is None:
        return "auto_deny", AUTO_DENY_MESSAGE
    if parsed.get("dryRun") and parsed["route"] == "/api/canvas-plan":
        return "auto_allow", None  # jen ověření, nic nezapíše (docs/davka-planu.md §3)
    if parsed["route"] in NO_PROMPT_ROUTES:
        return "auto_allow", None
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
