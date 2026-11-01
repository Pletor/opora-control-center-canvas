"""Spouštěče karet a ruční změny plánu (docs/navrhy/2026-10-30-metriky-a-spoustece.md §4), bez modelu.

Pevná tabulka, žádný engine. `evaluate` je čistá funkce nad fakty karet (měřák `card_gauge`) a historií hotových
karet; `facts` je fakta jednou přečte, `wakes` z nich udělá vstupy dávky srdce a značku „už jsem budil“ zapíše
do `heart_triggers` (klíč `trigger:card:<nodeId>:<druh>:<stav>`), takže stejný stav srdce nebudí dvakrát:

- `card.too_big`: štítek XL u karty `ready` (štítek „?“ chudých podkladů nepouští); stav `XL<body>@<prostor>`,
  jiné body (přeplánovaná karta, pořád XL) budí znovu;
- `card.retry`: `failures` ≥ 2; stav = ID posledního selhaného běhu, každé další selhání budí znovu;
- `card.step_failed` (PLAN-002): poslední běh karty odevzdal výsledek (ProcessSync `reported`), aspoň jeden krok
  nahlásil `failed` a běh nemá otevřený ani sloučený PR (karta by jinak visela v review bez PR); stav = ID běhu,
  stejný běh budí jednou, nový selhaný běh znovu; detail nese krok, jeho poznámku a pokyn přepsat kroky karty;
- `card.stalled`: běžící běh starší než 3× medián doby běhu hotových karet se stejným štítkem a bez události kroku
  (`step.*`) za tu dobu; stav = ID běhu;
- `card.over_budget`: `costUsd` > 2× medián; cena zatím chybí (`costUsd` null, §7), takže se nevyhodnocuje;
- `graph.human_change` (řez 3, odchylka): člověk přijal návrh plánu (`changeset.accepted` s autorem `human`;
  ruční uložení plátna událost nemá); klíč `trigger:graph:<revize>:human_change`.

Mediány jsou z hotových karet projektu (`done.confirmed`) podle štítku; méně než `HISTORY` karet se štítkem =
`stalled` ani `over_budget` neběží. Spouštěč nic nezapisuje na plátno, jen budí.
"""
import json
from datetime import datetime
from statistics import median

from backend.canvas import card_gauge
from database.repositories.heart_triggers import HeartTriggers

CARD_KINDS = ("card.too_big", "card.retry", "card.step_failed", "card.stalled", "card.over_budget")
HUMAN_CHANGE = "graph.human_change"
RETRY_FAILURES = 2
STALL_FACTOR, BUDGET_FACTOR = 3, 2
NOTES = 400  # nejvýš znaků poznámky selhaného kroku v detailu
STEP_FAILED_ADVICE = ("zadání koliduje s repem → přepiš kroky karty návrhem změny (fields.steps) podle skutečného"
                      " stavu main, kartu vrať k převzetí; čísla migrací = poslední na main + 1")
HISTORY = 5  # nejméně hotových karet se štítkem pro medián
LIVE = ("reported", "running", "ready", "blocked", "needs-steps")  # hodnocené stavy karet, v pořadí priority
CARDS = 40  # nejvýš karet prostoru, které se vyhodnotí (ProcessSync v pořadí grafu)
SPACES = 5  # nejvýš prostorů s přijatým plánem na projekt


def _seconds(value):
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except (TypeError, ValueError):
        return None


def _higher(effort):
    """Úsilí o stupeň výš (strop `max`); bez úsilí (XL) None."""
    if effort not in card_gauge.EFFORTS:
        return None
    return card_gauge.EFFORTS[min(card_gauge.EFFORTS.index(effort) + 1, len(card_gauge.EFFORTS) - 1)]


def medians(done):
    """`{štítek: {seconds, costUsd}}` z hotových karet `[{label, seconds, costUsd}]`; jen štítky s aspoň `HISTORY`
    kartami. Medián ceny je None, dokud cenu nemá aspoň `HISTORY` karet."""
    groups = {}
    for item in done:
        groups.setdefault(item.get("label"), []).append(item)
    result = {}
    for label, items in groups.items():
        seconds = [item["seconds"] for item in items if isinstance(item.get("seconds"), (int, float))]
        costs = [item["costUsd"] for item in items if isinstance(item.get("costUsd"), (int, float))]
        if label and len(items) >= HISTORY:
            result[label] = {"seconds": median(seconds) if len(seconds) >= HISTORY else None,
                             "costUsd": median(costs) if len(costs) >= HISTORY else None}
    return result


def _hit(kind, card, state, detail):
    return {"kind": kind, "nodeId": card["nodeId"], "title": card.get("title") or card["nodeId"],
            "detail": detail, "state": state}


def too_big(card):
    if card.get("status") != "ready" or card.get("evidence") == "thin" or card.get("label") != card_gauge.XL:
        return None
    state = f"XL{card.get('points', 0):g}@{card.get('workspace')}"
    return _hit("card.too_big", card, state, f"XL ({card.get('points', 0):g} b.), nepředávat, rozděl")


def retry(card):
    if card.get("status") == "reported" or card.get("failures", 0) < RETRY_FAILURES or not card.get("failedRun"):
        return None
    higher = _higher(card.get("effort"))
    advice = f"doporučeno effort {higher}" if higher else "rozděl kartu"
    return _hit("card.retry", card, card["failedRun"], f"{card['failures']}× selhal, {advice}")


def _short(text, limit=NOTES):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def step_failed(card):
    """Odevzdaný běh se selhaným krokem a bez PR (`stepFailed` z `facts`); stav = ID běhu."""
    failed = card.get("stepFailed")
    if not failed or failed.get("pulled") or not failed.get("runId"):
        return None
    notes = _short(failed.get("notes")) or "bez poznámky"
    return _hit("card.step_failed", card, failed["runId"],
                f"krok {failed.get('stepId')} selhal (běh {failed['runId']}): {notes} — {STEP_FAILED_ADVICE}")


def stalled(card, typical):
    seconds = (typical.get(card.get("label")) or {}).get("seconds")
    age, run = card.get("age"), card.get("runId")
    if seconds is None or age is None or not run or age <= STALL_FACTOR * seconds:
        return None
    since = card.get("sinceStep")
    if since is not None and since <= STALL_FACTOR * seconds:
        return None  # krok se pohnul v posledních 3× medián
    return _hit("card.stalled", card, run, f"běží {round(age / 60)} min (medián {card.get('label')} "
                                           f"{round(seconds / 60)} min), bez kroku")


def over_budget(card, typical):
    """Připraveno: cena běhu zatím chybí (`costUsd` null), takže bez ceny nic nevrací."""
    cost, limit = card.get("costUsd"), (typical.get(card.get("label")) or {}).get("costUsd")
    if cost is None or limit is None or not card.get("runId") or cost <= BUDGET_FACTOR * limit:
        return None
    return _hit("card.over_budget", card, card["runId"], f"{cost:.2f} USD, medián {limit:.2f} USD")


def evaluate(cards, done):
    """Spouštěče karet `[{kind, nodeId, title, detail, state}]` z faktů karet a hotových karet (pořadí tabulky)."""
    typical, found = medians(done), []
    for card in cards:
        for hit in (too_big(card), retry(card), step_failed(card), stalled(card, typical), over_budget(card, typical)):
            if hit is not None:
                found.append(hit)
    return found


def card_key(hit):
    return f"trigger:card:{hit['nodeId']}:{hit['kind'].split('.', 1)[1]}:{hit['state']}"


def graph_key(revision):
    return f"trigger:graph:{revision}:human_change"


def item_of(hit):
    """Vstup dávky srdce."""
    return {"type": "cardTrigger", "kind": hit["kind"], "nodeId": hit["nodeId"], "title": hit["title"],
            "detail": hit["detail"]}


def spaces(db, project):
    """Prostory projektu s přijatým plánem (jen tam karty běží); nejvýš `SPACES`."""
    rows = db.execute("SELECT workspace_id FROM opora_spec_refs WHERE project_id=? ORDER BY workspace_id LIMIT ?",
                      (project, SPACES)).fetchall()
    return [row[0] for row in rows]


def failed_step(runs, run):
    """`{stepId, notes}` prvního kroku běhu `run` hlášeného `failed`, nebo None: nejdřív `stepResults` nejnovějšího
    výsledku (`deliver` / `results`), pak průběžná hlášení kroků (`opora_execution_steps`), od nejnovějšího."""
    reported = [item for receipt in reversed(runs.receipts(run))
                for item in (receipt.get("result") or {}).get("stepResults", [])]
    reported += reversed(runs.steps(run))
    item = next((item for item in reported if isinstance(item, dict) and item.get("status") == "failed"), None)
    if item is None:
        return None
    return {"stepId": item.get("stepId"), "notes": (item.get("evidence") or {}).get("notes") or ""}


def facts(service, project, workspace, now):
    """`(karty, hotové)` prostoru jedním čtením: karty `ProcessSync` (stav `ready` / `running` / `blocked` /
    `needs-steps` / `reported`, nejvýš `CARDS`) s profilem běhu, běhy (`tally`), stářím, poslední událostí kroku a
    u `reported` selhaným krokem odevzdaného běhu (`stepFailed: {runId, stepId, notes, pulled}`, `pulled` = běh má
    otevřený nebo sloučený PR); hotové karty se štítkem a dobou běhu (claim → poslední hlášení výsledku)."""
    from backend.canvas.opora_changesets import OporaChangesets
    from backend.canvas.opora_event_stage import confirmed_nodes
    from backend.canvas.opora_plan_steps import steps_of
    from backend.canvas.opora_process_sync import ProcessSync
    from database.repositories import opora_events
    from database.repositories.opora_execution_pull_requests import list_execution_pull_requests
    from database.repositories.opora_executions import Executions

    # Všechny karty, pak živé stavy a teprve z nich `CARDS`: prvních `CARDS` v pořadí grafu jsou u velkého plánu
    # hotové a nenaplánované karty a živé (třeba `reported` se selhaným krokem, PLAN-002) by spouštěč neviděl.
    # Pořadí `LIVE` je priorita: odevzdané a běžící karty před čekajícími na kroky, jinak je stovka karet
    # `needs-steps` / `blocked` vytlačí za `CARDS` (PLAN-002); uvnitř stavu zůstává pořadí grafu.
    items = sorted((item for item in ProcessSync(service).read(project, workspace, limit=None)["items"]  # vlastní zámky
                    if item.get("status") in LIVE), key=lambda item: LIVE.index(item["status"]))[:CARDS]
    graph = service.view(project, workspace)["graph"]
    accepted = {item["nodeId"]: item for item in OporaChangesets(service).context(project, workspace)["acceptedDocuments"]}
    index = card_gauge.graph_index(graph)
    cards = [node for node in index["nodes"] if index["nodes"][node].get("kind") in card_gauge.CARD_KINDS]
    delivered = {item["nodeId"]: item["currentExecution"]["id"] for item in items
                 if item.get("status") == "reported" and (item.get("currentExecution") or {}).get("results")}
    with service.reading(project):
        db = service.db_for(project)
        runs = Executions(db, project, workspace)
        history, reported = runs.history(), runs.reported_at()
        linked = list_execution_pull_requests(db, project, workspace)
        steps_at = opora_events.last_step_at(db, project, workspace)
        closed = confirmed_nodes(db, project, workspace, cards)
        broken = {node: {"runId": run, **found} for node, run in delivered.items()
                  if (found := failed_step(runs, run)) is not None}

    def run_of(node):
        return card_gauge.profile(index["nodes"][node], graph, steps_of((accepted.get(node) or {}).get("fields")), index)

    tally, newest, failed = card_gauge.tally(history, linked), {}, {}
    pulled = {item.get("executionId") for item in linked or [] if item.get("state") in ("open", "merged")}
    broken = {node: {**found, "pulled": found["runId"] in pulled} for node, found in broken.items()}
    for record in history:  # od nejnovějšího
        newest.setdefault(record["nodeId"], record)
        if record.get("state") in card_gauge.ENDED_WITHOUT_RESULT and record.get("executionId") not in pulled:
            failed.setdefault(record["nodeId"], record["executionId"])
    result = []
    for item in items:
        node = item["nodeId"]
        if node not in index["nodes"]:
            continue
        run, latest = run_of(node), newest.get(node) or {}
        claimed, step = _seconds(latest.get("createdAt")), _seconds(steps_at.get(node))
        active = latest.get("state") == "running" and (latest.get("expiresAt") or 0) > now
        result.append({"nodeId": node, "title": item.get("name"), "workspace": workspace, "status": item["status"],
                       "label": run["label"], "evidence": run["evidence"], "points": run["points"],
                       "effort": run["effort"], "failures": (tally.get(node) or {}).get("failures", 0),
                       "failedRun": failed.get(node), "runId": latest.get("executionId") if active else None,
                       "age": now - claimed if active and claimed is not None else None,
                       "sinceStep": now - step if step is not None else None, "costUsd": None,
                       "stepFailed": broken.get(node)})
    done = []
    for node in closed:
        record = next((item for item in history if item["nodeId"] == node and item["executionId"] in reported), None)
        if record is None:
            continue
        start, end = _seconds(record.get("createdAt")), _seconds(reported[record["executionId"]])
        done.append({"label": run_of(node)["label"], "costUsd": None,
                     "seconds": end - start if start is not None and end is not None and end >= start else None})
    return result, done


EXTRA = 5  # nejvýš vstupů z `extra` na průchod (zbytek přijde v dalším průchodu, značku ještě nemá)


def wakes(service, project, workspaces, at, now, extra=None):
    """Spouštěče karet: `[(prostor, vstup cardTrigger)]`, kterým srdce ještě nebudilo. `workspaces` None = prostory
    s přijatým plánem. Fakta se čtou mimo zámek; značky se zapíší v jedné transakci pod zámkem dat.
    `extra(karta) -> (klíč, vstup) | None` je další spouštěč nad stejnými fakty (krátký výslech karty
    `brief.card_hit`, docs/navrhy/2026-10-30-vyslech-srdce.md §2); jeho vstupy jdou za spouštěči karet."""
    if workspaces is None:
        with service.reading(project):
            workspaces = spaces(service.db_for(project), project)
    hits, others = [], []
    for workspace in sorted(workspaces)[:SPACES]:
        cards, done = facts(service, project, workspace, now)
        hits += [(workspace, card_key(hit), item_of(hit)) for hit in evaluate(cards, done)]
        others += [(workspace, *found) for found in map(extra, cards) if found] if extra else []
    if not hits and not others:
        return []
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            store = HeartTriggers(db)
            found = [(space, item) for space, key, item in hits if store.fire(key, space, at)]
            fresh = [(space, key, item) for space, key, item in others if not store.fired(key)][:EXTRA]
            return found + [(space, item) for space, key, item in fresh if store.fire(key, space, at)]


def human_change(db, project, workspace, revision, at):
    """Vstup `humanChange`, když revizi `revision` přijal člověk (autor `human`) a srdce na ni ještě nebudilo;
    přijetí srdcem (autor `agent`) nebudí. Transakci vlastní volající."""
    row = db.execute("SELECT content FROM opora_spec_revisions WHERE project_id=? AND workspace_id=? AND id=?",
                     (project, workspace, revision)).fetchone()
    record = json.loads(row[0]) if row else {}
    if (record.get("by") or {}).get("kind") != "human":
        return None
    number = db.execute("SELECT COUNT(*) FROM opora_spec_revisions WHERE project_id=? AND workspace_id=?"
                        " AND created_at<=?", (project, workspace, record.get("createdAt") or "")).fetchone()[0]
    if not HeartTriggers(db).fire(graph_key(revision), workspace, at):
        return None
    return {"type": "humanChange", "kind": HUMAN_CHANGE, "revision": number, "revisionId": revision,
            "subject": record.get("subject")}
