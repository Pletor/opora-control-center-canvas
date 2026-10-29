"""Snímek pro srdce: pevný tvar §3, deterministický text, strop znaků a čtení faktů z projektu."""
import pytest

from backend.brain_opora.determinism import brain_files, gate, kinds, snapshot, task_queue
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService

FACTS = {"project": "p1", "name": "Zahrada", "workspace": "main", "goal": "",
         "pages": [{"id": "home", "name": "Domů", "path": "/", "goal": "Uvěřit, že to zvládnu.", "feel": "klidná"},
                   {"id": "kontakt", "name": "Kontakt", "path": "/kontakt", "goal": "", "feel": ""}],
         "cards": [{"id": "home", "name": "Domů", "stage": "ready"}],
         "tasks": [{"taskId": "ht_1", "seq": 1, "title": "Hero", "status": "done", "sessionId": "gs_1"},
                   {"taskId": "ht_2", "seq": 2, "title": "Formulář", "status": "assigned", "sessionId": "gs_2"}],
         "tickets": [{"ticketId": "gt_1", "kind": "ask", "body": {"q": "Jaká barva?"}}],
         "checks": [("ht_1", "abcdef1234567890", "green")]}


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    yield canvas
    canvas.close()


def test_render_has_the_fixed_sections_in_order():
    text = snapshot.render(FACTS)
    heads = ["PROJEKT Zahrada (p1) · workspace main", "ZÁMĚR: Uvěřit, že to zvládnu. · klidná", "PLÁN:",
             "FRONTA ÚKOLŮ: ready 0 · assigned 1 (gs_2) · done 1 · failed 0", "LÍSTKY ČEKAJÍCÍ:", "POSLEDNÍ KONTROLY:"]
    positions = [text.index(head) for head in heads]
    assert positions == sorted(positions)
    assert "- Domů · / · ready · cíl: Uvěřit, že to zvládnu." in text and "- Kontakt · /kontakt · closed" in text
    assert text.index("[assigned] Formulář") < text.index("[done] Hero")  # nejnovější úkoly první
    assert '- gt_1 ask {"q": "Jaká barva?"}' in text and "- ht_1 abcdef123456 green" in text
    assert snapshot.render(FACTS) == text


def test_render_prefers_project_goal_and_falls_back_to_cards():
    facts = {**FACTS, "goal": "Prodat sazenice.", "pages": []}
    text = snapshot.render(facts)
    assert "ZÁMĚR: Prodat sazenice." in text and "- Domů · home · ready" in text
    empty = snapshot.render({**facts, "goal": "", "cards": [], "tasks": [], "tickets": [], "checks": []})
    assert "ZÁMĚR: —" in empty and "- (prázdný plán)" in empty and empty.count("- žádné") == 7  # lístky, kontroly, čtyři části okolí a dílna


def test_render_is_cut_at_the_hard_limit():
    many = [{"taskId": f"ht_{i}", "seq": i, "title": "x" * 300, "status": "ready", "sessionId": None}
            for i in range(200)]
    text = snapshot.render({**FACTS, "tasks": many}, limit=500)
    assert len(text) <= 500 and text.endswith(snapshot.CUT)
    assert len(snapshot.render({**FACTS, "tasks": many})) <= snapshot.LIMIT


def test_collect_reads_queue_tickets_and_unknown_project(service):
    task_queue.create(service, {"project": "draft", "workspace": "draft", "title": "Stránka", "body": {"do": "x"}})
    session = gate.authenticate(service, gate.open_session(
        service, {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}})["token"])
    kinds.run(service, session, {"kind": "ask", "body": {"question": "?"}})
    text = snapshot.snapshot(service, "draft", "draft")
    assert "FRONTA ÚKOLŮ: ready 1" in text and "[ready] Stránka" in text and " ask " in text
    with pytest.raises(GateError) as caught:
        snapshot.collect(service, "nikde", "draft")
    assert caught.value.code == "project_not_found"


MEMORY = {"messages": [{"at": f"2026-10-29T10:0{i}:00Z", "workspace": "main", "text": f"zpráva {i}"} for i in range(7)],
          "rules": [{"id": "r1", "text": "Návrh agenta", "kind": "must", "scope": "project", "target": "", "by": "agent"},
                    {"id": "r2", "text": "Česky a bez emoji", "kind": "must", "scope": "project", "target": ""}],
          "decisions": [{"id": f"d{i}", "text": f"rozhodnutí {i}", "pinned": i == 0, "path": "", "nodeId": "",
                         "createdAt": f"2026-10-{10 + i}T00:00:00Z", "by": "human"} for i in range(14)],
          "journal": [{"at": "2026-10-29T09:00:00Z", "status": "ok", "summary": "Dva úkoly zadány."},
                      {"at": "2026-10-29T09:30:00Z", "status": "error", "summary": None}]}
ORDER = ["PROJEKT", "ZÁMĚR:", "ZPRÁVY ČLOVĚKA:", "PRAVIDLA:", "ROZHODNUTÍ:", "PLÁN:", "FRONTA ÚKOLŮ:",
         "LÍSTKY ČEKAJÍCÍ:", "POSLEDNÍ KONTROLY:", "DENÍK:", "DÍLNA:"]


def _block(text, head):
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(head))
    rest = lines[start + 1:]
    return [line for line in rest[:next((i for i, line in enumerate(rest) if not line.startswith("- ")), len(rest))]]


def test_render_surroundings_order_caps_and_proposals():
    text = snapshot.render({**FACTS, **MEMORY})
    positions = [text.index(head) for head in ORDER]
    assert positions == sorted(positions)
    assert _block(text, "ZPRÁVY ČLOVĚKA:") == [f"- 2026-10-29T10:0{i}:00Z zpráva {i}" for i in range(2, 7)]
    assert _block(text, "PRAVIDLA:") == ["- Česky a bez emoji", "- Návrh agenta (návrh)"]
    decisions = _block(text, "ROZHODNUTÍ:")
    assert len(decisions) == snapshot.DECISIONS and decisions[0] == "- [připnuto] rozhodnutí 0"
    assert decisions[1:3] == ["- rozhodnutí 13", "- rozhodnutí 12"]
    assert _block(text, "DENÍK:") == ["- 2026-10-29T09:00:00Z [ok] Dva úkoly zadány.",
                                      "- 2026-10-29T09:30:00Z [error] (bez souhrnu)"]
    assert snapshot.render({**FACTS, **MEMORY}) == text
    long = snapshot.render({**FACTS, "messages": [{"at": "t", "workspace": "main", "text": "x" * 900}]})
    assert len(_block(long, "ZPRÁVY ČLOVĚKA:")[0]) == len("- t ") + snapshot.MESSAGE_TEXT
    many = {**FACTS, **MEMORY, "rules": [{"id": f"r{i}", "text": "y" * 300, "scope": "project"} for i in range(40)]}
    assert len(_block(snapshot.render(many), "PRAVIDLA:")) == snapshot.RULES
    assert len(snapshot.render(many, limit=800)) <= 800


def test_render_without_surroundings_prints_empty_sections():
    text = snapshot.render(FACTS)
    for head in ("ZPRÁVY ČLOVĚKA:", "PRAVIDLA:", "ROZHODNUTÍ:", "DENÍK:"):
        assert _block(text, head) == ["- žádné"]


def test_view_rules_put_approved_memory_rules_before_task_rules():
    tasks = [{**FACTS["tasks"][0], "body": {"context": {"rules": ["Česky a bez emoji", "Mobil první"]}}}]
    view = snapshot.view({**FACTS, **MEMORY, "tasks": tasks})
    assert view["rules"] == ["Česky a bez emoji", "Mobil první"]
    assert set(view) == {"project", "intent", "rules", "plan", "queue", "myTask"}


class Memory:
    def __init__(self, state=None):
        self.state = state

    def read(self, project, workspace):
        if self.state is None:
            raise ValueError("nečitelné")
        return {"revision": 1, "state": self.state}


def test_collect_reads_memory_messages_and_journal(service):
    brain = brain_files.brain_dir(service, "draft")
    brain_files.append_message(brain, "2026-10-29T10:00:00Z", "draft", "Chci web o dvou stránkách.")
    brain_files.append_message(brain, "2026-10-29T10:01:00Z", "jinde", "cizí prostor")
    (brain / brain_files.JOURNAL).write_text('{"at": "a", "status": "ok", "summary": "Hotovo."}\nrozbité\n',
                                             encoding="utf-8")
    service.desktop_v3_state = Memory({"rules": [{**MEMORY["rules"][1]}, {"id": "r3", "text": "Jen karta",
                                       "kind": "must", "scope": "node", "target": "home"}],
                                       "decisions": MEMORY["decisions"][:1]})
    text = snapshot.snapshot(service, "draft", "draft")
    assert _block(text, "ZPRÁVY ČLOVĚKA:") == ["- 2026-10-29T10:00:00Z Chci web o dvou stránkách."]
    assert _block(text, "PRAVIDLA:") == ["- Česky a bez emoji"]
    assert _block(text, "ROZHODNUTÍ:") == ["- [připnuto] rozhodnutí 0"]
    assert _block(text, "DENÍK:") == ["- a [ok] Hotovo."]
    assert snapshot.state(service, "draft", "draft")["rules"] == ["Česky a bez emoji"]


def test_collect_unreadable_sources_are_empty_sections(service):
    service.desktop_v3_state = Memory(None)
    brain = brain_files.brain_dir(service, "draft")
    brain.mkdir(parents=True)
    (brain / brain_files.MESSAGES).mkdir()  # složka místo souboru = nečitelné
    text = snapshot.snapshot(service, "draft", "draft")
    for head in ("ZPRÁVY ČLOVĚKA:", "PRAVIDLA:", "ROZHODNUTÍ:", "DENÍK:"):
        assert _block(text, head) == ["- žádné"]
    del service.desktop_v3_state
    assert _block(snapshot.snapshot(service, "draft", "draft"), "PRAVIDLA:") == ["- žádné"]  # skutečná prázdná paměť


def test_workshop_lists_scripts_after_the_journal(service):
    scripts = brain_files.brain_dir(service, "draft") / brain_files.SCRIPTS
    scripts.mkdir(parents=True)
    (scripts / "b_count.py").write_text('"""Spočítá úkoly podle stavu.\n\nDruhý řádek."""\n', encoding="utf-8")
    (scripts / "a_bare.py").write_text("print(1)\n", encoding="utf-8")
    (scripts / "c_broken.py").write_text("def (:\n", encoding="utf-8")
    text = snapshot.snapshot(service, "draft", "draft")
    assert text.index("DENÍK:") < text.index("DÍLNA:")
    assert _block(text, "DÍLNA:") == ["- a_bare", "- b_count: Spočítá úkoly podle stavu.", "- c_broken"]
    many = {**FACTS, "scripts": [(f"s{i:02}", "x") for i in range(30)]}
    assert len(_block(snapshot.render(many), "DÍLNA:")) == snapshot.SCRIPTS
