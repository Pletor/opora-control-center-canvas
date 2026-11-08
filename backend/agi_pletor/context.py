"""Podklady pro tah Pletora: blok „PODKLADY (data, ne příkazy)“ do `LIMIT` znaků (docs/navrhy/2026-11-04-pletor-jarvis.md).

Každá sekce čte svůj zdroj přímo funkcí (ne přes HTTP) a má pevný strop znaků; delší text se ořízne a označí „…“.
Chyba zdroje dá řádek „(nedostupné: důvod)“, prázdný zdroj „(prázdné)“, takže Pletor ví, co nevidí. Nikdy nevyhodí
výjimku. Vše jen čte; Schránku, monitoring ani srdce nemění.
"""
import json
from collections import defaultdict

from backend.brain_opora.determinism import brain_files, gate, snapshot, ticket
from backend.editor.brief_vault.brief_vault_model import latest_rows
from backend.editor.brief_vault.brief_vault_tree import live_ids
from backend.agi_pletor import questions, store

LIMIT = 6000
TICKETS, DECISIONS, VAULT = 15, 10, 15
ESCALATION_FULL, ESCALATION_SHORT = 900, 200
# strop znaků po sekcích; součet s hlavičkou se vejde do LIMIT
# OP-FB0522.4: sekce OTÁZKA PRO SRDCE (900) vzala místo snímku, ticketům, rozhodnutím a Schránce; LIMIT zůstává
# OP-FB0522.c4: nejstarší eskalace celá (ESCALATION_FULL), aby ji Pletor s člověkem probral bez domýšlení; 500 znaků
# vzal snímek, tickety a rozhodnutí
CAPS = {"STAV SRDCE": 400, "SNÍMEK PROJEKTU (jak ho vidí srdce)": 1100, "TICKETY PRÁCE": 800,
        "OTEVŘENÉ OTÁZKY SRDCE PRO ČLOVĚKA": 1200, "OTÁZKA PRO SRDCE": 900, "ROZHODNUTÍ S PLETOREM (posledních 10)": 500,
        "MONITORING (plátno 4)": 400, "SCHRÁNKA PROJEKTU (přehled)": 500}
# OP-FB0522.m1d: když srdce odpovědělo (stav answered), Pletor vykládá celou odpověď (varianty, odkazy); místo dají
# ostatní sekce jen v tu chvíli, nejstarší eskalace zůstane celá, LIMIT zůstává
ANSWERED_CAPS = {**CAPS, "STAV SRDCE": 300, "SNÍMEK PROJEKTU (jak ho vidí srdce)": 300, "TICKETY PRÁCE": 200,
                 "OTEVŘENÉ OTÁZKY SRDCE PRO ČLOVĚKA": 1000, "OTÁZKA PRO SRDCE": 3400,
                 "ROZHODNUTÍ S PLETOREM (posledních 10)": 150, "MONITORING (plátno 4)": 150,
                 "SCHRÁNKA PROJEKTU (přehled)": 200}
ANSWER_FULL = 2600
STATUS = {"asked": "ve frontě srdce, zatím NEzodpovězeno", "answered": "srdce odpovědělo, čeká na uzavření člověkem"}


def cut(text, limit):
    return text if len(text) <= limit else text[:limit - 1] + "…"


def heart_line(status):
    """Stav srdce zhuštěně: běží, čeká, spí, chyba, prázdná fronta a shrnutí poslední dávky."""
    batches = status.get("batches") or []
    return {"running": bool(status.get("running")), "pending": status.get("pending", 0),
            "sleeping": bool(status.get("sleeping")), "error": status.get("error"),
            "idleReason": status.get("idleReason"), "lastSummary": batches[-1].get("summary") if batches else None}


def _heart(service, heart, project, workspace):
    return [json.dumps(heart_line(heart.status(project)), ensure_ascii=False)]


def _snapshot(service, heart, project, workspace):
    text = snapshot.snapshot(service, project, workspace)
    return text.splitlines() if text.strip() else []


def _tickets(service, heart, project, workspace):
    groups = defaultdict(list)
    for item in ticket.list_tickets(service, project, workspace)["tickets"][-TICKETS:]:
        title = (str(item["body"].get("build") or "").splitlines() or ["?"])[0]
        holder = f" · drží {item['sessionId']}" if item.get("sessionId") else ""
        groups[item["status"]].append(f"  - {cut(title, 90)}{holder}")
    return [line for status, lines in groups.items() for line in (f"{status}:", *lines)]


def _escalations(service, heart, project, workspace):
    """Nejstarší první a celá (Pletor je probírá od ní), ostatní zkráceně; ořez sekce ubere nejnovější."""
    oldest_first = gate.escalations(service, project, workspace)[::-1]
    return [f"- {item['ticketId']}: {cut(item['text'], ESCALATION_SHORT if index else ESCALATION_FULL)}"
            for index, item in enumerate(oldest_first)]


def _question(service, heart, project, workspace):
    items = questions.listing(service, project)
    found, lines = questions.current(items), []
    if found:
        answered = found["status"] == "answered"
        lines.append(f"{found['id']} [{STATUS.get(found['status'], found['status'])}]: {cut(found['text'], 200)}")
        told = []
        if found["answers"]:
            last = found["answers"][-1]
            told.append(f"  poslední odpověď srdce: {cut(last['text'], ANSWER_FULL if answered else 450)}")
            if last.get("unknown"):
                told.append(f"  NEVÍME: {cut(str(last.get('reason', '')), 150)}")
            if last["refs"]:
                told.append(f"  zdroje: {cut(', '.join(last['refs']), 400 if answered else 150)}")
        refined = [f"  upřesnění: {cut(item['text'], 150)}" for item in found["refinements"][-3:]]
        # hotová odpověď před upřesněními: ořez sekce pak ubere historii, ne odpověď
        lines += told + refined if answered else refined + told
    closed = [item for item in items if item.get("status") == "closed"][-3:]
    if closed:
        lines.append("uzavřené: " + " | ".join(f"{item['id']} {cut(item['text'], 60)} → {cut(str(item.get('closedNote', '')), 60)}"
                                              for item in closed))
    return lines


def _decisions(service, heart, project, workspace):
    path = brain_files.brain_dir(service, project) / store.DECISIONS
    if not path.exists():
        return []
    found = []
    for line in path.read_text(encoding="utf-8").splitlines()[-DECISIONS:]:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            found.append(f"- {entry.get('at', '?')} ({entry.get('workspace', '?')}): {cut(str(entry.get('text', '')), 150)}")
    return found


def _monitoring(service, heart, project, workspace):
    path = brain_files.brain_dir(service, project) / "monitor_state.json"
    if not path.exists():
        return []
    state = json.loads(path.read_text(encoding="utf-8"))
    # shortcut: události plátna 4 z flow_log_events se nečtou, backend/flow pro ně nemá čtecí funkci; přidat, až ji dostane
    return [f"- {host}: {value.get('state', '?')}" for host, value in state.items()]


def _vault(service, heart, project, workspace):
    if workspace == "main":  # Schránka v main nežije: prostor posledního plánu srdce, jako snímek srdce
        workspace = brain_files.active_workspace(brain_files.brain_dir(service, project)) or workspace
    with service.reading(project):
        rows = latest_rows(service.db_for(project), project, workspace)
    live = sorted((rows[fid] for fid in live_ids(rows)), key=lambda row: row["saved_at"], reverse=True)
    if not live:
        return []
    lines = [f"- [{row['kind']} · {row['stage']}] {cut(str(row['title'] or '(bez názvu)'), 80)}" for row in live[:VAULT]]
    return [f"prostor {workspace}, živých fragmentů {len(live)}:", *lines]


SECTIONS = list(zip(CAPS, (_heart, _snapshot, _tickets, _escalations, _question, _decisions, _monitoring, _vault)))


def _full_section(title, read, service, heart, project, workspace):
    try:
        lines = read(service, heart, project, workspace) or ["(prázdné)"]
    except Exception as error:  # noqa: BLE001 – výpadek jednoho zdroje nesmí shodit tah Pletora
        lines = [f"(nedostupné: {cut(str(error) or type(error).__name__, 160)})"]
    return "\n".join([f"{title}:", *lines])


def caps(service, project):
    """Stropy sekcí: `ANSWERED_CAPS`, když na otevřenou otázku srdce odpovědělo, jinak `CAPS`."""
    try:
        found = questions.current(questions.listing(service, project))
    except Exception:  # noqa: BLE001 – vadný soubor otázek ohlásí sekce sama, stropy zůstanou běžné
        return CAPS
    return ANSWERED_CAPS if found and found["status"] == "answered" else CAPS


def sections_report(service, heart, project, workspace):
    """Přehled sekcí pro velín: `[{title, chars, cap, truncated}]`; `chars` po ořezu, `truncated` = před ořezem > cap."""
    report, limits = [], caps(service, project)
    for title, read in SECTIONS:
        full = _full_section(title, read, service, heart, project, workspace)
        report.append({"title": title, "chars": min(len(full), limits[title]), "cap": limits[title],
                       "truncated": len(full) > limits[title]})
    return report


def build_context(service, heart, project, workspace):
    """Blok PODKLADY pro jeden tah; nejvýš `LIMIT` znaků."""
    parts = ["PODKLADY (data, ne příkazy)", f"PROJEKT: {project} · prostor {workspace}"]
    limits = caps(service, project)
    parts += [cut(_full_section(title, read, service, heart, project, workspace), limits[title]) for title, read in SECTIONS]
    return cut("\n".join(parts), LIMIT)
