"""Snímek pro srdce: pevný tvar §3, deterministický text, strop znaků a čtení faktů z projektu."""
import pytest

from backend.brain_opora.determinism import gate, snapshot, task_queue
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
    assert "ZÁMĚR: —" in empty and "- (prázdný plán)" in empty and empty.count("- žádné") == 2


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
    gate.create_request(service, session, {"kind": "ask", "body": {"q": "?"}})
    text = snapshot.snapshot(service, "draft", "draft")
    assert "FRONTA ÚKOLŮ: ready 1" in text and "[ready] Stránka" in text and " ask " in text
    with pytest.raises(GateError) as caught:
        snapshot.collect(service, "nikde", "draft")
    assert caught.value.code == "project_not_found"
