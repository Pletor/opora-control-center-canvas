"""Snímek pro srdce: pevný tvar §3, deterministický text, strop znaků a čtení faktů z projektu."""
import json
import subprocess

import pytest

from backend.brain_opora.determinism import brain_files, gate, kinds, snapshot, task_queue
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService

FACTS = {"project": "p1", "name": "Zahrada", "workspace": "main", "goal": "",
         "pages": [{"id": "home", "name": "Domů", "path": "/", "goal": "Uvěřit, že to zvládnu.", "feel": "klidná"},
                   {"id": "kontakt", "name": "Kontakt", "path": "/kontakt", "goal": "", "feel": ""}],
         "cards": [{"id": "home", "name": "Domů", "stage": "ready"}],
         "tasks": [{"taskId": "ht_1", "seq": 1, "title": "Hero", "status": "done", "sessionId": "gs_1"},
                   {"taskId": "ht_2", "seq": 2, "title": "Formulář", "status": "assigned", "sessionId": "gs_2",
                    "updatedAt": "2026-10-29T08:00:00Z"}],
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
    assert "- [assigned] Formulář (ht_2) · drží gs_2 od 2026-10-29T08:00:00Z" in text  # od kdy úkol drží
    assert "- [done] Hero (ht_1)\n" in text
    assert '- gt_1 ask {"q": "Jaká barva?"}' in text and "- ht_1 abcdef123456 green" in text
    assert snapshot.render(FACTS) == text


def test_render_prefers_project_goal_and_falls_back_to_cards():
    facts = {**FACTS, "goal": "Prodat sazenice.", "pages": []}
    text = snapshot.render(facts)
    assert "ZÁMĚR: Prodat sazenice." in text and "- Domů · home · ready" in text
    empty = snapshot.render({**facts, "goal": "", "cards": [], "tasks": [], "tickets": [], "checks": []})
    assert "ZÁMĚR: —" in empty and "- (prázdný plán)" in empty and empty.count("- žádné") == 9  # lístky, kontroly, git, čtyři části okolí, dílna a výzkum


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
         "LÍSTKY ČEKAJÍCÍ:", "POSLEDNÍ KONTROLY:", "GIT:", "DENÍK:", "DÍLNA:"]


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


def test_research_line_shows_next_from_the_first_approach_line():
    assert snapshot.research_next("Další krok: spike – změřit\nVerdikt: unverified") == "spike"
    assert snapshot.research_next("Verdikt výzkumníka: feasible") == "" and snapshot.research_next(None) == ""
    item = {"id": "r1", "kind": "research", "title": "Limit", "verdict": "feasible", "confidence": "high",
            "next": "plan", "status": "done"}
    assert _block(snapshot.render({**FACTS, "research": [item]}), "VÝZKUM:") == [
        "- výzkum Limit (r1) · feasible/high · next plan · done"]


def _link(execution, node, state, number=None, sha=None, awaiting=0):
    return {"execution_id": execution, "node_id": node, "state": state, "number": number, "merge_sha": sha,
            "awaiting_human_close": awaiting}


def test_work_states_from_newest_execution_and_its_pr_link():
    executions = [{"executionId": "e5", "nodeId": "run", "state": "running", "owner": "agent:dev"},
                  {"executionId": "e4", "nodeId": "done", "state": "reported", "owner": "a"},
                  {"executionId": "e3", "nodeId": "pr", "state": "running", "owner": "a"},
                  {"executionId": "e2", "nodeId": "free", "state": "released", "owner": "a"},
                  {"executionId": "e1", "nodeId": "run", "state": "reported", "owner": "a"}]
    links = [_link("e3", "pr", "open", 12), _link("e0", "merged", "merged", 9, "abcdef123456", 1),
             _link("e9", "old", "merged", 3, "1234567890")]
    work = snapshot.work_states(executions, links)
    assert work == {"run": "běží (agent:dev)", "done": "odevzdáno", "pr": "PR #12", "free": "volná",
                    "merged": "sloučeno abcdef1 · čeká na uzavření", "old": "sloučeno 1234567"}
    text = snapshot.render({**FACTS, "pages": [], "work": {"home": "PR #12"}})
    assert "- Domů · home · ready · PR #12" in text
    assert "- Domů · / · ready · volná · cíl:" in snapshot.render({**FACTS, "work": {}})


def test_git_section_after_checks_is_capped():
    text = snapshot.render({**FACTS, "git": [f"{i:07} commit {i}" for i in range(12)]})
    assert text.index("POSLEDNÍ KONTROLY:") < text.index("GIT:") < text.index("DENÍK:")
    assert _block(text, "GIT:")[:2] == ["- 0000000 commit 0", "- 0000001 commit 1"]
    assert len(_block(text, "GIT:")) == snapshot.GIT_COMMITS
    long = _block(snapshot.render({**FACTS, "git": ["x" * 300] * 10}), "GIT:")
    assert sum(len(row) + 1 for row in long) <= snapshot.GIT_CHARS


def _git(root, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(root), *args],
                   check=True, capture_output=True)


def test_snapshot_reads_recent_commits_of_the_source_and_survives_a_broken_one(service, tmp_path):
    source = tmp_path / "zdroj"
    source.mkdir()
    _git(source, "init", "-q")
    for number in range(12):
        (source / "f.txt").write_text(str(number), encoding="utf-8")
        _git(source, "add", "f.txt")
        _git(source, "commit", "-q", "-m", f"Krok {number}")
    project = service.project_hub.local_project({"name": "Zdroj", "path": str(source), "confirmed": True})["id"]
    rows = _block(snapshot.snapshot(service, project, "draft"), "GIT:")
    assert len(rows) == 10 and rows[0].endswith(" Krok 11") and len(rows[0].split()[1]) >= 7
    assert "GIT:" not in json.dumps(snapshot.state(service, project, "draft"), ensure_ascii=False)  # stav pro pracovníky git nečte
    (source / ".git" / "HEAD").write_text("rozbité", encoding="utf-8")
    assert _block(snapshot.snapshot(service, project, "draft"), "GIT:") == ["- žádné"]
    assert _block(snapshot.snapshot(service, "draft", "draft"), "GIT:") == ["- žádné"]  # bez zdroje

