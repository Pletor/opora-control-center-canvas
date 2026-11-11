"""Sken webu přes REA do návrhu plánu stránky (`docs/navrhy/2026-11-10-platno-2.md`, verze 3 a 6).

Běží na pozadí (vlákno), stav je v paměti a v souboru `projects/<id>/page-plan-scans/<scanId>.json`, takže ho čtení
najde i po restartu (běh přerušený restartem = `failed`). Výzkumník je výzkumník srdce, jen jeho stavebnice: stažení
cíle bez modelu (`research_fetch.prefetch`), prohlížeč pro REA (`opora_research.find_browser`), příkazová řádka
výzkumníka s nástroji REA a Haiku (`research_desk.gather_command`), MCP REA (`command.REA_MCP`), proces s časovým
limitem a zabitím celého stromu (`opora_heart._execute`). Prompt a validace návrhu jsou v `page_plan_proposal.py`,
snímky stránky a výřezy boxů v `page_plan_capture.py` (soubory leží ve složce skenu `<scanId>/`).

Sken nic nezapisuje do grafu: převzetí dělá klient přes `POST /api/page-plan` (s `scanId`, sken pak nese
`outcome: adopted`) a `/api/canvas-plan`; zahození nese `outcome: discarded`. `state` zůstává `done`.
"""
import json
import re
import threading
import time
import uuid
from urllib.parse import urlsplit

from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.heart.research_digest import last_object
from backend.project.architecture import page_plan_capture
from backend.project.architecture.page_plan import find_page
from backend.project.architecture.page_plan_proposal import ScanFailed, prompt_for, proposal_of

SCAN_ID, SCAN_DIR = re.compile(r"[0-9a-f]{32}"), "page-plan-scans"
URL_MAX, NOTE_MAX = 500, 300
TIMEOUT = 420  # s; po něm `_execute` zabije celý strom procesu
TURNS = 30  # layout, design z CSS, toky a selektory potřebují víc kol než stůl výzkumu (12 kol = error_max_turns)
LIVE = {}  # scanId → záznam běžícího nebo dokončeného skenu tohoto procesu
GUARD = threading.Lock()
FIELDS = ("scanId", "pageId", "url", "state", "outcome", "error", "cost", "proposal")


def _folder(service, pid):
    return service.folder(pid).path / SCAN_DIR


def _write(service, record):
    """Soubor skenu atomicky (dočasný + přejmenování): čtení nikdy nenarazí na rozepsaný JSON."""
    folder = _folder(service, record["project"])
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / f"{record['scanId']}.json.tmp"
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    temporary.replace(folder / f"{record['scanId']}.json")


def _failure(out, err):
    """Důvod selhání `claude -p`: text chyby z posledního řádku JSON, jinak konec stderr nebo stdout."""
    for raw in reversed((out or "").strip().splitlines()):
        try:
            value = json.loads(raw)
        except ValueError:
            continue
        if isinstance(value, dict) and value.get("type") == "result":
            return str(value.get("result") or value.get("subtype") or "neznámá chyba")[-300:]
    return ((err or "").strip() or (out or "").strip() or "prázdný výstup")[-300:]


def research(url, note, folder):
    """Výchozí spouštěč: `(text odpovědi, cena USD)` jednoho běhu výzkumníka nad stránkou; ScanFailed při selhání."""
    from backend.brain_opora.heart import (
        command,
        opora_heart,
        opora_research,
        research_desk,
        research_fetch,
    )

    claude = research_desk.find_claude()
    if not claude:
        raise ScanFailed("Nenalezen spustitelný `claude`; sken potřebuje Claude Code na tomto počítači.")
    research_fetch.prefetch([url], folder)
    browser, mcp = opora_research.find_browser(), folder / command.REA_MCP_NAME
    if browser:
        mcp.write_text(json.dumps(command.REA_MCP), encoding="utf-8")
    line = research_desk.gather_command(claude, data_dir=folder, rea=bool(browser), mcp_path=mcp, turns=TURNS)
    rea = research_desk.REA_HINT.replace("<B>", json.dumps(str(browser))) if browser else ""
    prompt = prompt_for(url, note, rea)
    _exit, out, err, timed_out = opora_heart._execute(line, str(folder), {**research_desk.child_env(),
                                                                          **research_desk.RESEARCH_ENV},
                                                      timeout=TIMEOUT, input_text=prompt)
    (folder / "research.out.jsonl").write_text(out or "", encoding="utf-8")  # důkaz běhu pro diagnózu
    answer, cost = research_desk.claude_result(out)
    if timed_out:
        raise ScanFailed(f"Sken nestihl {TIMEOUT} s; proces byl ukončen.")
    if answer is None:
        # `claude -p` hlásí chybu v posledním řádku stdout (`is_error`, `result`), stderr bývá prázdný.
        raise ScanFailed(f"Výzkumník nevrátil odpověď (exit {_exit}): " + _failure(out, err))
    return answer, cost


def finish(answer, url, folder, capture=None):
    """Odpověď výzkumníka → návrh se snímky (`captures`), bez služby: jde spustit i z terminálu."""
    selectors = {}
    proposal = proposal_of(last_object(answer), selectors)
    captures, notes = (capture or page_plan_capture.capture)(url, selectors, folder)
    if captures:
        proposal["captures"] = captures
    proposal["notes"] = proposal["notes"] + notes
    return proposal


def _run(service, record, runner):
    folder = _folder(service, record["project"]) / record["scanId"]
    folder.mkdir(parents=True, exist_ok=True)
    final = {}
    try:
        answer, cost = runner(record["url"], record.get("note"), folder)
        final["cost"] = round(cost, 6)
        final.update(state="done", proposal=finish(answer, record["url"], folder))
    except ScanFailed as error:
        final.update(state="failed", error=str(error))
    except Exception as error:  # noqa: BLE001 - sken na pozadí nesmí zůstat viset v `running`
        final.update(state="failed", error=f"Sken spadl: {type(error).__name__}: {error}"[:500])
    final["finishedAt"] = time.time()
    _write(service, {**record, **final})  # soubor dřív než paměť: kdo vidí konec v paměti, najde ho i v souboru
    record.update(final)


def start(service, payload, runner=None):
    """`{scanId, state: "running"}`; stránka musí existovat, URL je http(s). Na stránku běží nejvýš jeden sken."""
    keys = {"project", "workspace", "pageId", "url"}
    if not isinstance(payload, dict) or not keys <= set(payload) <= keys | {"note"}:
        raise GateError(422, "invalid_payload", "Tělo je {project, workspace, pageId, url, note?}.",
                        "url je adresa webu http(s).")
    url, note = payload["url"], payload.get("note")
    parts = urlsplit(url) if isinstance(url, str) else None
    if not parts or parts.scheme not in ("http", "https") or not parts.netloc or len(url) > URL_MAX or " " in url:
        raise GateError(422, "invalid_payload", "url je adresa http(s) do 500 znaků.", "https://example.com/kurz")
    if note is not None and (not isinstance(note, str) or not note.strip() or len(note) > NOTE_MAX):
        raise GateError(422, "invalid_payload", f"note je text 1–{NOTE_MAX} znaků.", "Prázdnou poznámku vynechte.")
    pid, wid = payload["project"], payload["workspace"]
    with service.reading(pid):
        find_page(service.view(pid, wid)["graph"], payload["pageId"])
    with GUARD:
        if any(item["state"] == "running" and (item["project"], item["workspace"], item["pageId"])
               == (pid, wid, payload["pageId"]) for item in LIVE.values()):
            raise GateError(409, "scan_running", "Na této stránce už sken běží.", "Počkejte na jeho výsledek (GET scan).")
        record = {"scanId": uuid.uuid4().hex, "project": pid, "workspace": wid, "pageId": payload["pageId"],
                  "url": url, **({"note": note} if note else {}), "state": "running", "startedAt": time.time()}
        LIVE[record["scanId"]] = record
    _write(service, record)
    threading.Thread(target=_run, args=(service, record, runner or research), daemon=True,
                     name=f"page-plan-scan-{record['scanId'][:8]}").start()
    return {"scanId": record["scanId"], "state": "running"}


def _record(service, scan_id, pid, wid):
    """Záznam skenu z paměti, jinak ze souboru; jiný projekt či prostor = 404. Soubor `running` bez běhu = přerušený."""
    valid = isinstance(scan_id, str) and SCAN_ID.fullmatch(scan_id)
    record = LIVE.get(scan_id) if valid else None
    if record is None and valid and service.project_exists(pid):
        path = _folder(service, pid) / f"{scan_id}.json"
        if path.is_file():
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("state") == "running":
                record.update(state="failed", error="Sken přerušil restart serveru; spusťte ho znovu.")
    if record is None or (record["project"], record["workspace"]) != (pid, wid):
        raise GateError(404, "scan_not_found", "Sken neexistuje.", "scanId vrací POST /api/page-plan/scan.")
    return record


def get(service, scan_id, pid, wid):
    """`{scanId, pageId, url, state, outcome?, error?, cost?, proposal?}`."""
    record = _record(service, scan_id, pid, wid)
    return {key: record[key] for key in FIELDS if key in record}


def proposal_sections(service, scan_id, pid, wid, page_id):
    """Boxy hotového skenu stránky pro `source: "scan"` při převzetí; jiný stav, stránka nebo zahozený = 409."""
    found = get(service, scan_id, pid, wid)
    if found["state"] != "done" or found["pageId"] != page_id or found.get("outcome") == "discarded":
        raise GateError(409, "scan_not_ready", "Sken není hotový, patří jiné stránce, nebo byl zahozen.",
                        "Převezměte jen nezahozený návrh se state done téže stránky.")
    return found["proposal"]["sections"]


def mark(service, scan_id, pid, wid, outcome):
    """`outcome` adopted / discarded hotového skenu (soubor i paměť); jiný už zapsaný výsledek = 409."""
    with GUARD:
        record = _record(service, scan_id, pid, wid)
        if record["state"] != "done" or record.get("outcome") not in (None, outcome):
            raise GateError(409, "scan_closed", f"Sken je {record.get('outcome') or record['state']}, nejde ho označit.",
                            "Označit jde jen hotový sken, který ještě nebyl převzat ani zahozen.")
        _write(service, {**record, "outcome": outcome})
        if scan_id in LIVE:
            LIVE[scan_id]["outcome"] = outcome
    return get(service, scan_id, pid, wid)


def latest(service, pid, wid, page_id, adopted=False):
    """Poslední hotový sken stránky bez `outcome` (`{scanId, state, proposal, cost, …}`), jinak 404; `adopted=True`
    bere i převzatý sken (snímky živé karty, `backend/canvas/live_card.py`)."""
    found, folder = [], _folder(service, pid) if service.project_exists(pid) else None
    for path in folder.glob("*.json") if folder and folder.is_dir() else ():
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (record.get("project"), record.get("workspace"), record.get("pageId"), record.get("state")) == (
                pid, wid, page_id, "done") and (adopted or not record.get("outcome")):
            found.append(record)
    if not found:
        raise GateError(404, "scan_not_found", "Stránka nemá hotový nepřevzatý sken.", "Spusťte POST /api/page-plan/scan.")
    record = max(found, key=lambda item: item.get("finishedAt") or 0)
    return {key: record[key] for key in FIELDS if key in record}


def capture_file(service, scan_id, pid, wid, name):
    """Cesta k PNG snímku skenu; jen jména ze záznamu (`proposal.captures`), nic jiného ze složky."""
    captures = (_record(service, scan_id, pid, wid).get("proposal") or {}).get("captures") or {}
    path = _folder(service, pid) / scan_id / name
    if name not in {captures.get("page"), *(captures.get("sections") or {}).values()} - {None} or not path.is_file():
        raise GateError(404, "capture_not_found", "Snímek v tomto skenu není.", "Jména snímků jsou v proposal.captures.")
    return path
