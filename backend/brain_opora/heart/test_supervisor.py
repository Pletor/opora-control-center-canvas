"""Supervisor srdce s falešným časem a procesem: buzení, okno 20 s, jedna dávka na projekt, strop a spánek."""
import json

import pytest

from backend.brain_opora.determinism import brain_files, gate, gate_setting, kinds
from backend.brain_opora.heart import batch, supervisor
from backend.brain_opora.heart.process import Outcome
from backend.canvas.canvas_service import CanvasService

OK = {"is_error": False, "session_id": "11111111-1111-1111-1111-111111111111", "total_cost_usd": 0.01,
      "num_turns": 3, "usage": {"input_tokens": 100}, "modelUsage": {"claude-haiku-4-5": {"costUSD": 0.01}}}
LIMITED = {"is_error": True, "result": "You've hit your session limit"}


class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


class Runner:
    def __init__(self):
        self.calls, self.result = [], OK

    def __call__(self, line, *, cwd, env, stdin_text, timeout):
        self.calls.append(stdin_text)
        return Outcome(0, json.dumps(self.result), "")


@pytest.fixture
def setup(tmp_path):
    service = CanvasService(tmp_path / "data")
    service.db_for("draft")
    gate_setting.write(service, {"project": "draft", "enabled": True})
    clock, runner, held = Clock(), Runner(), []
    heart = supervisor.HeartSupervisor(service, base_url="http://127.0.0.1:9", runner=runner, clock=clock,
                                       spawn=lambda fn: fn(), find=lambda: "claude",
                                       git_spawn=lambda fn: fn())
    yield service, heart, clock, runner, held
    service.close()


def ask(service, body):
    session = gate.authenticate(service, gate.open_session(
        service, {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}})["token"])
    return kinds.run(service, session, {"kind": "ask", "body": body})


def test_enabled_only_on_loopback_and_not_off():
    assert supervisor.enabled({}) is True
    assert supervisor.enabled({"OPORA_HEART": "off"}) is False
    assert supervisor.enabled({"OPORA_CANVAS_HOST": "0.0.0.0"}) is False
    assert supervisor.enabled({"OPORA_CANVAS_HOST": "localhost"}) is True


def test_human_message_wakes_at_once_and_is_journaled(setup):
    service, heart, clock, runner, _ = setup
    assert heart.message("draft", "draft", "Chci web o dvou stránkách.") == 1
    assert heart.run_once() == ["draft"]
    assert "ZPRÁVA ČLOVĚKA: Chci web o dvou stránkách." in runner.calls[0] and "PROJEKT" in runner.calls[0]
    status = heart.status("draft")
    assert status["batches"][-1]["status"] == "ok" and status["session"]["batches"] == 1 and status["pending"] == 0
    assert status["running"] is False and status["sleeping"] is False
    assert status["activeWorkspace"] is None  # srdce zatím žádný plán nepřijalo
    (heart.brain("draft") / "active_workspace.json").write_text('{"workspace": "w1"}', encoding="utf-8")
    assert heart.status("draft")["activeWorkspace"] == "w1"


def test_human_message_is_durable_and_reaches_the_next_snapshot(setup):
    service, heart, clock, runner, _ = setup
    heart.message("draft", "draft", "Jen dvě stránky, žádný blog.")
    assert brain_files.messages(heart.brain("draft"), "draft") == [
        {"at": "1970-01-12T13:46:40Z", "workspace": "draft", "text": "Jen dvě stránky, žádný blog."}]
    heart.run_once()
    assert "ZPRÁVY ČLOVĚKA:" + chr(10) + "- 1970-01-12T13:46:40Z Jen dvě stránky, žádný blog." in runner.calls[0]


def test_relayed_message_wakes_at_once_and_is_marked_in_the_snapshot(setup):
    """Relé záměru (docs/brain-heart-orchestrator.md §8): `via` se uloží a snímek ho ukáže."""
    _, heart, _, runner, _ = setup
    assert heart.message("draft", "draft", "Web o dvou stránkách.", via="office") == 1
    assert brain_files.messages(heart.brain("draft"), "draft")[0]["via"] == "office"
    assert heart.run_once() == ["draft"]
    assert "- 1970-01-12T13:46:40Z Web o dvou stránkách. (přes office)" in runner.calls[0]


def test_worker_ticket_waits_for_the_window_and_own_escalation_does_not_wake(setup):
    service, heart, clock, runner, _ = setup
    assert heart.run_once() == []  # první průchod nastaví kurzor na konec outboxu
    ticket = ask(service, {"question": "Jakou barvu?"})
    assert heart.run_once() == [] and heart.status("draft")["pending"] == 1
    clock.now += supervisor.WINDOW + 1
    assert heart.run_once() == ["draft"]
    assert f"LÍSTEK {ticket['ticketId']} (ask)" in runner.calls[0] and "Jakou barvu?" in runner.calls[0]
    heart_session = gate.tokens.verify(service, heart.tokens[("draft", "draft")])
    kinds.run(service, heart_session, {"kind": "escalate", "body": {"text": "Pro člověka"}})
    clock.now += supervisor.WINDOW + 1
    assert heart.run_once() == [] and heart.status("draft")["pending"] == 0


def test_answered_ticket_is_dropped_before_the_batch(setup):
    service, heart, clock, runner, _ = setup
    heart.run_once()
    ticket = ask(service, {"question": "?"})
    heart.run_once()
    gate.answer(service, "draft", ticket["ticketId"], {"answer": "Ano"})
    clock.now += supervisor.WINDOW + 1
    assert heart.run_once() == ["draft"] and runner.calls == []  # nic k řešení, proces se nespustil


def test_one_batch_per_project_six_automatic_per_hour_and_human_bypasses(setup):
    service, heart, clock, runner, _ = setup
    parked = []
    heart.spawn = parked.append
    heart.message("draft", "draft", "první")
    assert heart.run_once() == ["draft"]
    heart.message("draft", "draft", "během dávky")
    assert heart.run_once() == []  # dávka projektu ještě běží
    parked.pop()()
    heart.spawn = lambda fn: fn()
    assert heart.run_once() == ["draft"] and "během dávky" in runner.calls[-1]
    for number in range(supervisor.PER_HOUR):  # automatické dávky (lístky) mají strop
        ask(service, {"question": f"otázka {number}"})
        heart.run_once()
        clock.now += supervisor.WINDOW + 1
        assert heart.run_once() == ["draft"]
    ask(service, {"question": "sedmá"})
    heart.run_once()
    clock.now += supervisor.WINDOW + 1
    assert heart.run_once() == [] and heart.next_allowed("draft", clock.now) > clock.now
    heart.message("draft", "draft", "zpráva člověka strop obchází")
    assert heart.run_once() == ["draft"] and "sedmá" in runner.calls[-1]
    ask(service, {"question": "osmá"})
    heart.run_once()
    clock.now += supervisor.WINDOW + 1
    assert heart.run_once() == []
    clock.now += supervisor.HOUR
    assert heart.run_once() == ["draft"]


def test_batch_without_live_inputs_does_not_count_toward_the_cap(setup):
    service, heart, clock, runner, _ = setup
    for number in range(supervisor.PER_HOUR + 2):  # lístky vyřešené dřív, než dávka začne
        heart._add("draft", "draft", {"type": "ticket", "ticketId": f"gone-{number}", "kind": "ask"}, clock.now)
        assert heart.run_once() == ["draft"]
    assert runner.calls == [] and heart.next_allowed("draft", clock.now) == clock.now


def test_rate_limit_sleeps_and_keeps_inputs(setup):
    service, heart, clock, runner, _ = setup
    runner.result = LIMITED
    heart.message("draft", "draft", "Plán")
    heart.run_once()
    status = heart.status("draft")
    assert status["sleeping"] is True and status["pending"] == 1 and status["batches"][-1]["status"] == "rate_limited"
    runner.result = OK
    clock.now += supervisor.RATE_SLEEP - 1
    assert heart.run_once() == []
    clock.now += 2
    assert heart.run_once() == ["draft"] and "Plán" in runner.calls[-1]


def test_gate_off_and_missing_claude_drop_the_batch(setup):
    service, heart, clock, runner, _ = setup
    heart.find = lambda: None
    heart.message("draft", "draft", "x")
    heart.run_once()
    assert heart.status("draft")["error"] == "Claude Code nenalezen." and runner.calls == []
    heart.find = lambda: "claude"
    gate_setting.write(service, {"project": "draft", "enabled": False})
    heart.message("draft", "draft", "y")
    clock.now += 60
    heart.run_once()
    assert heart.status("draft")["error"] == "Brána projektu je vypnutá." and runner.calls == []
    assert batch.read_journal(heart.brain("draft")) == []


def test_ticket_queued_before_the_first_poll_wakes_after_restart_once(setup):
    """Ztracené buzení: lístek vznikl, než supervisor poprvé přečetl outbox (restart serveru). První průchod ho
    dožene hned; vlastní eskalace srdce a lístek, který dávka `ok` už viděla, se znovu nebudí."""
    service, heart, clock, runner, _ = setup
    ticket = ask(service, {"question": "Před restartem?"})
    assert heart.run_once() == ["draft"] and heart.status("draft")["pending"] == 0
    assert f"LÍSTEK {ticket['ticketId']} (ask)" in runner.calls[0]
    heart_session = gate.tokens.verify(service, heart.tokens[("draft", "draft")])
    kinds.run(service, heart_session, {"kind": "escalate", "body": {"text": "Pro člověka"}})
    restarted = supervisor.HeartSupervisor(service, base_url="http://127.0.0.1:9", runner=runner, clock=clock,
                                           spawn=lambda fn: fn(), find=lambda: "claude", git_spawn=lambda fn: fn())
    clock.now += supervisor.WINDOW + 1
    assert restarted.run_once() == [] and restarted.status("draft")["pending"] == 0  # dávka ok lístek viděla
    assert len(runner.calls) == 1


def test_restart_catches_up_unanswered_ticket_and_message_without_duplicates(setup):
    service, heart, clock, runner, _ = setup
    ticket = ask(service, {"question": "Ztracený?"})
    answered = ask(service, {"question": "Už zodpovězený"})
    gate.answer(service, "draft", answered["ticketId"], {"answer": "Ano"})
    brain_files.append_message(heart.brain("draft"), supervisor._iso(clock.now - 60), "draft", "Zpráva před pádem")
    brain_files.append_message(heart.brain("draft"), "1970-01-01T00:00:00Z", "draft", "Prastará zpráva")
    heart._add("draft", "draft", {"type": "ticket", "ticketId": ticket["ticketId"], "kind": "ask"}, clock.now)
    assert heart.run_once() == ["draft"]  # dohnaný lístek je v dávce jednou, zodpovězený a prastará zpráva ne
    sent = runner.calls[0]
    assert sent.count(f"LÍSTEK {ticket['ticketId']}") == 1 and answered["ticketId"] not in sent.split("VSTUPY")[-1]
    assert "ZPRÁVA ČLOVĚKA: Zpráva před pádem" in sent and "ZPRÁVA ČLOVĚKA: Prastará zpráva" not in sent


def change(service, proposal):
    session = gate.authenticate(service, gate.open_session(
        service, {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}})["token"])
    return kinds.run(service, session, {"kind": "change", "body": {"proposal": proposal, "reason": "proto"}})


def test_same_human_sentence_is_kept_but_does_not_wake_the_heart(setup):
    """Vstupní brána (docs/navrhy/2026-10-30-vstupni-brana.md §3): stejná věta člověka = `duplicate`, srdce spí."""
    service, heart, clock, runner, _ = setup
    assert heart.message("draft", "draft", "Přidej hybridní vyhledávání.") == 1
    assert heart.run_once() == ["draft"]
    first = runner.calls[0].split("VSTUPY TÉTO DÁVKY")[-1]
    assert "ZPRÁVA ČLOVĚKA: Přidej hybridní vyhledávání. [vstup ie_" in first and " · pending]" in first
    clock.now += 60
    assert heart.message("draft", "draft", "přidej HYBRIDNÍ vyhledávání") == 0
    assert heart.status("draft")["pending"] == 0 and heart.run_once() == [] and len(runner.calls) == 1
    saved = brain_files.messages(heart.brain("draft"), "draft")
    assert saved[-1]["text"] == "přidej HYBRIDNÍ vyhledávání" and saved[-1]["duplicate"].startswith("ie_")
    restarted = supervisor.HeartSupervisor(service, base_url="http://127.0.0.1:9", runner=runner, clock=clock,
                                           spawn=lambda fn: fn(), find=lambda: "claude", git_spawn=lambda fn: fn())
    assert restarted.run_once() == [] and len(runner.calls) == 1  # ani dohánění po restartu duplicitu nebudí


def test_repeated_change_ticket_still_wakes_with_a_duplicate_mark(setup):
    """Lístek pracovníka může být oprávněné opakování: srdce se budí, řádek nese jen značku duplicity."""
    service, heart, clock, runner, _ = setup
    heart.run_once()
    first, second = change(service, "Rozdělit kartu hledání."), change(service, "rozdělit kartu hledání")
    heart.run_once()
    clock.now += supervisor.WINDOW + 1
    assert heart.run_once() == ["draft"]
    sent = runner.calls[-1].split("VSTUPY TÉTO DÁVKY")[-1]
    assert f"LÍSTEK {first['ticketId']} (change)" in sent and f"LÍSTEK {second['ticketId']} (change)" in sent
    line = next(row for row in sent.splitlines() if second["ticketId"] in row)
    assert " · duplicate · podobné: ie_" in line


def test_jev_classifies_pending_input_before_the_batch_only_when_allowed(setup):
    """Řez 2 (docs/navrhy/2026-10-30-vstupni-brana.md §4, §7): Jev zařadí vstup v dávce, ne ve zprávě; vypnuto = nic,
    porucha Jevu dávku nezastaví."""
    from backend.brain_opora.determinism import intake_setting

    service, _, clock, runner, _ = setup
    clock.now = 1_793_354_400.0  # 2026-10-30T10:00:00Z, vstup patří do dnešního stropu
    calls = []

    def evaluate(state, questions):
        calls.append(state["text"])
        if "rozbij" in state["text"]:
            raise RuntimeError("Jev spadl")
        return {"verdict": {"choice": "later_extension", "confidence": 0.9}}

    heart = supervisor.HeartSupervisor(service, base_url="http://127.0.0.1:9", runner=runner, clock=clock,
                                       spawn=lambda fn: fn(), find=lambda: "claude", git_spawn=lambda fn: fn(),
                                       jev=lambda: evaluate)
    heart.message("draft", "draft", "Přidej hybridní vyhledávání.")
    heart.run_once()
    assert calls == [] and " · pending]" in runner.calls[-1]  # výchozí stav: Jev vypnutý
    intake_setting.write(service, {"project": "draft", "jev": True})
    clock.now += 3600
    assert heart.message("draft", "draft", "Přidej export do PDF.") == 1 and calls == []  # zpráva nečeká na Jev
    assert heart.run_once() == ["draft"]
    assert calls == ["Přidej export do PDF.", "Přidej hybridní vyhledávání."]  # nejdřív vstup dávky
    line = next(row for row in runner.calls[-1].splitlines() if "ZPRÁVA ČLOVĚKA: Přidej export" in row)
    assert " · later_extension · jev 0.90 · podobné: ie_" in line
    assert "(jev 0.90)" in runner.calls[-1].split("VSTUPY:")[1]  # snímek už nese stanovisko Jevu
    clock.now += 3600
    heart.message("draft", "draft", "Tohle rozbij.")
    assert heart.run_once() == ["draft"] and heart.status("draft")["batches"][-1]["status"] == "ok"
    assert "Tohle rozbij. [vstup ie_" in runner.calls[-1] and heart.errors.get("draft") is None


def test_reached_milestone_wakes_the_heart_once_after_card_closed_without_a_new_event(setup):
    """Spouštěč `milestone.done` (docs/navrhy/2026-10-30-metriky-a-spoustece.md §4): po `card.closed` splněný aktivní
    milník budí srdce jednou s odloženými požadavky; další poll ani restart supervisoru ho nebudí znovu."""
    from backend.canvas.opora_events import emit_event
    from database.repositories.intake_milestones import IntakeMilestones
    from database.repositories.intake_requirements import IntakeRequirements

    service, heart, clock, runner, _ = setup
    db = service.db_for("draft")
    with db:
        IntakeMilestones(db).insert({"id": "ms_1", "workspaceId": "draft", "areaId": "a1", "title": "Hledání",
                                     "criteria": [{"id": "c1", "text": "t", "cards": ["n1"]}], "status": "proposed",
                                     "createdAt": "t0"})
        IntakeMilestones(db).activate("ms_1")
        IntakeRequirements(db).insert({"id": "rq_1", "workspaceId": "draft", "areaId": "a1", "title": "Hybridní",
                                       "status": "deferred", "openCondition": "ms_1", "createdAt": "t1"})
    heart.poll_events(clock.now)  # první čtení: milník ještě nesplněný
    assert heart.pending.get("draft", []) == []
    with db:
        db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES('draft','draft',1,?,'t')",
                   (json.dumps({"nodes": {"n1": {"done": {"confirmed": True}}}}),))
        emit_event(db, project_id="draft", workspace_id="draft", kind="card.closed", node_id="n1", actor="human",
                   data={})
    heart.poll_events(clock.now)
    [(workspace, item, due)] = heart.pending["draft"]
    assert (workspace, due) == ("draft", clock.now + supervisor.WINDOW)
    assert item == {"type": "milestoneDone", "milestoneId": "ms_1", "title": "Hledání", "areaId": "a1",
                    "deferred": [{"id": "rq_1", "title": "Hybridní"}]}
    with db:
        emit_event(db, project_id="draft", workspace_id="draft", kind="card.closed", node_id="n1", actor="human",
                   data={})
    heart.poll_events(clock.now)
    heart.cursors.clear()  # restart: první čtení znovu
    heart.poll_events(clock.now)
    assert len(heart.pending["draft"]) == 1
    clock.now += supervisor.WINDOW
    assert heart.run_once() == ["draft"]
    assert "MILNÍK SPLNĚN ms_1 „Hledání“ (oblast a1): odložené požadavky k otevření: rq_1 „Hybridní“" in runner.calls[-1]
    assert "- milník ms_1 „Hledání“ splněn – odložené požadavky k otevření: rq_1" in runner.calls[-1]  # snímek
    assert "POŽADAVKY:\n- rq_1 · deferred (po ms_1) · oblast a1 · Hybridní" in runner.calls[-1]
    assert IntakeRequirements(db).get("rq_1")["status"] == "deferred"


def test_human_acceptance_of_a_plan_wakes_the_heart_once_per_revision(setup):
    """Spouštěč `graph.human_change` (řez 3): `changeset.accepted`, jehož revizi přijal člověk, budí srdce jednou;
    přijetí srdcem (autor `agent`) nebudí."""
    from backend.canvas.opora_events import emit_event

    service, heart, clock, runner, _ = setup
    db = service.db_for("draft")
    heart.poll_events(clock.now)  # první čtení
    with db:
        for identifier, kind in (("r1", "agent"), ("r2", "human")):
            record = {"id": identifier, "by": {"kind": kind, "name": "x"}, "createdAt": "2026-10-30T1" + identifier[1]}
            db.execute("INSERT INTO opora_spec_revisions VALUES('draft','draft',?,NULL,?,?,?)",
                       (identifier, "p" + identifier, record["createdAt"], json.dumps(record)))
            emit_event(db, project_id="draft", workspace_id="draft", kind="changeset.accepted", actor="human",
                       data={"proposalId": "p" + identifier, "acceptedHead": identifier})
    heart.poll_events(clock.now)
    [(workspace, item, due)] = heart.pending["draft"]
    assert (workspace, due, item["type"], item["revision"]) == ("draft", clock.now + supervisor.WINDOW, "humanChange", 2)
    heart.cursors.clear()  # restart: událost už outbox nepřinese a značka drží
    heart.poll_events(clock.now)
    assert len(heart.pending["draft"]) == 1
    clock.now += supervisor.WINDOW
    assert heart.run_once() == ["draft"]
    assert "- SPOUŠTĚČ graph.human_change: člověk změnil plán (revize 2)" in runner.calls[-1]


def test_card_triggers_run_on_first_read_after_events_at_most_once_a_minute_and_every_ten_minutes(setup, monkeypatch):
    service, heart, clock, runner, _ = setup
    calls = []

    def wakes(service, project, workspaces, at, now):
        calls.append(workspaces)
        return [("w1", {"type": "cardTrigger", "kind": "card.retry", "nodeId": "n1", "title": "T", "detail": "d"})]

    monkeypatch.setattr(supervisor, "card_wakes", wakes)
    heart.poll_events(clock.now)
    assert calls == [None]  # první čtení: všechny prostory s přijatým plánem
    assert heart.pending["draft"][0][1]["type"] == "cardTrigger"
    heart._cards("draft", {"w1"}, clock.now + 30)  # událost do minuty počká
    assert calls == [None]
    heart._cards("draft", set(), clock.now + supervisor.CARD_GAP)
    assert calls == [None, {"w1"}]
    heart._cards("draft", set(), clock.now + supervisor.CARD_GAP + 1)  # bez události nic
    heart._cards("draft", set(), clock.now + supervisor.CARD_GAP + supervisor.CARD_POLL)
    assert calls == [None, {"w1"}, None]


def test_status_shows_the_running_batch_with_its_inputs_and_clears_it_after(setup):
    _, heart, _, _, _ = setup
    seen = []

    def watching(line, *, cwd, env, stdin_text, timeout):
        seen.append(heart.status("draft")["current"])
        return Outcome(0, json.dumps(OK), "")

    heart.runner = watching
    assert heart.status("draft")["current"] is None
    heart.message("draft", "draft", "Přidej stránku kontaktů.")
    assert heart.run_once() == ["draft"]
    assert seen[0]["startedAt"] == "1970-01-12T13:46:40Z"
    assert [(item["type"], item["text"]) for item in seen[0]["inputs"]] == [("message", "Přidej stránku kontaktů.")]
    assert seen[0]["startedAt"] == heart.status("draft")["batches"][-1]["at"]  # stejný čas jako deník dávek
    assert heart.status("draft")["current"] is None
