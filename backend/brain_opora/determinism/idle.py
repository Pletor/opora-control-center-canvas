"""Spouštěč prázdné fronty `idle.frontier_empty` (OPORA-002), bez modelu.

Srdce budí jen události; po sloučení poslední karty plán nemá co předat, nic neběží a pipeline stojí. Tento spouštěč
čte stejný dokument jako agenti (`AgentState.read`, docs/oporahub-agent-state.md) a nepočítá stav druhým výpočtem:

- fronta je prázdná, když přijatý plán (`heads.acceptedHead`) nemá kartu k převzetí (etapa `claim` 0), nic neběží
  (`work` 0), žádný výsledek nečeká na review ani PR (`evidence`, `review` 0, `merge` bez `pull_requests_open`);
- čeká-li rozhodnutí člověka (`decisions`) nebo otevřená otázka srdce pro člověka (eskalace), důvod je
  `waiting_human` a srdce se nebudí (čeká se na člověka, ne na srdce);
- prázdná fronta trvající aspoň `IDLE_MINUTES` od poslední činnosti prostoru (`ACTIVITY` v outboxu) dá vstup
  `{"type": "idle", "reason": "frontier_empty", ...}` jednou na stav: značka `trigger:idle:<prostor>:<revize>:<sloučeno>`
  v `heart_triggers`, takže nová revize plánu nebo další sloučená karta smí budit znovu, stejný stav ne.
"""
from datetime import UTC, datetime

from database.repositories.gate_tickets import GateTicketStore
from database.repositories.heart_triggers import HeartTriggers

IDLE_MINUTES = 10
FRONTIER_EMPTY, WAITING_HUMAN = "frontier_empty", "waiting_human"
# Činnost prostoru, od které se měří stání (poslední z nich je „od kdy fronta stojí“).
ACTIVITY = ("merge.done", "result.reported", "stage.changed", "lease.claimed", "card.closed", "changeset.accepted")
_CLOSED = ("card_closed", "plan_written_back")


def _stages(state):
    return {item["id"]: item for item in state.get("stages") or []}


def done_count(state):
    """Sloučené karty: počet sloučených PR (etapa `merge`); bez modulu PR uzavřené karty ze seznamu."""
    merge = _stages(state).get("merge") or {}
    if merge.get("health") != "not_connected":
        return int(merge.get("count") or 0)
    return sum(entry.get("reason") in _CLOSED for entry in state.get("cards") or [])


def reason(state, questions):
    """`frontier_empty` | `waiting_human` | None (práce je, nebo plán není přijatý). `questions` = počet otevřených
    otázek srdce pro člověka."""
    stages = _stages(state)
    if not (state.get("heads") or {}).get("acceptedHead"):
        return None
    if any((stages.get(name) or {}).get("count") for name in ("claim", "work")):
        return None
    # Evidence a review podle karet, ne podle počtu etapy: `stale_evidence` umí počítat i výsledek bez karty v etapě.
    if any(card.get("stage") in ("evidence", "review") for card in state.get("cards") or []):
        return None
    if (stages.get("merge") or {}).get("reason") == "pull_requests_open":
        return None
    if state.get("decisions") or questions:
        return WAITING_HUMAN
    return FRONTIER_EMPTY


def key(workspace, revision, done):
    return f"trigger:idle:{workspace}:{revision}:{done}"


def last_activity(db, project, workspace):
    """ISO čas poslední události `ACTIVITY` prostoru, nebo None."""
    marks = ",".join("?" * len(ACTIVITY))
    row = db.execute(f"SELECT MAX(at) FROM opora_events WHERE project_id=? AND workspace_id=? AND kind IN ({marks})",
                     (project, workspace, *ACTIVITY)).fetchone()
    return row[0] if row else None


def facts(service, project, workspace):
    """`(agent-state, otevřené otázky pro člověka, poslední činnost)` prostoru."""
    from backend.canvas.opora_agent_state import AgentState

    state = AgentState(service).read(project, workspace)
    with service.reading(project):
        db = service.db_for(project)
        questions = len(GateTicketStore(db, project).escalations(workspace, 1))
        since = last_activity(db, project, workspace)
    return state, questions, since


def _seconds(value):
    try:
        moment = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).timestamp()


def evaluate(state, questions, since, workspace, now):
    """`(důvod, klíč, vstup | None)`: vstup jen při prázdné frontě trvající aspoň `IDLE_MINUTES`."""
    found = reason(state, questions)
    if found != FRONTIER_EMPTY:
        return found, None, None
    start = _seconds(since)
    if start is None or now - start < IDLE_MINUTES * 60:
        return found, None, None
    done, revision = done_count(state), state["heads"]["acceptedHead"]
    item = {"type": "idle", "reason": FRONTIER_EMPTY, "since": since,
            "cardsTotal": int(state.get("cardsTotal") or 0), "done": done}
    return found, key(workspace, revision, done), item


def wakes(service, project, workspaces, at, now, read=facts):
    """`([(prostor, vstup idle)], {prostor: důvod})` pro prostory s přijatým plánem; značky zapíše v jedné transakci.
    Chyba jednoho prostoru nevadí ostatním (volající ji zaloguje celou, proto se tu nepolyká)."""
    reasons, hits = {}, []
    for workspace in workspaces:
        state, questions, since = read(service, project, workspace)
        found, mark, item = evaluate(state, questions, since, workspace, now)
        reasons[workspace] = found
        if item is not None:
            hits.append((workspace, mark, item))
    if not hits:
        return [], reasons
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            store = HeartTriggers(db)
            return [(space, item) for space, mark, item in hits if store.fire(mark, space, at)], reasons
