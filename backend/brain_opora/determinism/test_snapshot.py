"""Snímek pro srdce: pevný tvar §3, deterministický text, strop znaků a čtení faktů z projektu."""
import json
import subprocess

import pytest

from backend.brain_opora.determinism import (
    brain_files,
    gate,
    intake,
    kinds,
    snapshot,
    tokens,
)
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService
from backend.canvas.test_graph_card import node

FACTS = {"project": "p1", "name": "Zahrada", "workspace": "main", "goal": "",
         "pages": [{"id": "home", "name": "Domů", "path": "/", "goal": "Uvěřit, že to zvládnu.", "feel": "klidná"},
                   {"id": "kontakt", "name": "Kontakt", "path": "/kontakt", "goal": "", "feel": ""}],
         "cards": [{"id": "home", "name": "Domů", "stage": "ready"}],
         "workTickets": [{"ticketId": "tk_1", "seq": 1, "status": "delivered", "body": {"build": "Hero\nUdělej hero."},
                          "machine": {"cardId": "home", "department": "design",
                                      "successors": [{"cardId": "kontakt", "name": "Kontakt"}]}, "sessionId": "gs_1", "updatedAt": "2026-10-29T07:00:00Z"},
                         {"ticketId": "tk_2", "seq": 2, "status": "issued", "body": {"build": "Formulář"},
                          "machine": {"cardId": None}, "sessionId": None, "updatedAt": "2026-10-29T08:00:00Z"}],
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
             "TICKETY PRÁCE: issued 1 · claimed 0 · in_progress 0 · needs_answer 0 · delivered 1 · verified 0 · failed 0",
             "LÍSTKY ČEKAJÍCÍ:", "POSLEDNÍ KONTROLY:"]
    positions = [text.index(head) for head in heads]
    assert positions == sorted(positions)
    assert "- Domů · home · / · ready · cíl: Uvěřit, že to zvládnu." in text
    assert "- Kontakt · kontakt · /kontakt · closed" in text
    assert text.index("[issued] Formulář") < text.index("[delivered] Hero")  # nejnovější tickety první
    assert "- [issued] Formulář (tk_2)\n" in text
    assert "- [delivered] Hero (tk_1) · karta home · oddělení design · následníci 1 · drží gs_1 od 2026-10-29T07:00:00Z" in text  # titulek, karta, držitel
    assert "FRONTA ÚKOLŮ" not in text and "DORUČENÍ" not in text and "ht_2" not in text  # staré úkoly snímek nečte
    assert '- gt_1 ask {"q": "Jaká barva?"}' in text and "- ht_1 abcdef123456 green" in text
    assert snapshot.render(FACTS) == text


def test_render_prefers_project_goal_and_falls_back_to_cards():
    facts = {**FACTS, "goal": "Prodat sazenice.", "pages": []}
    text = snapshot.render(facts)
    assert "ZÁMĚR: Prodat sazenice." in text and "- Domů · home · ready" in text
    empty = snapshot.render({**facts, "goal": "", "cards": [], "tickets": [], "checks": []})
    assert "ZÁMĚR: —" in empty and "- (prázdný plán)" in empty and empty.count("- žádné") == 9  # lístky, kontroly, git, čtyři části okolí, dílna a výzkum


def test_render_is_cut_at_the_hard_limit():
    many = [{"ticketId": f"tk_{i}", "seq": i, "body": {"build": "x" * 300}, "status": "issued",
             "machine": {"cardId": None}, "sessionId": None} for i in range(200)]
    text = snapshot.render({**FACTS, "workTickets": many}, limit=500)
    assert len(text) <= 500 and text.endswith(snapshot.CUT)
    assert len(snapshot.render({**FACTS, "workTickets": many})) <= snapshot.LIMIT


def test_collect_reads_work_tickets_question_tickets_and_unknown_project(service):
    _, token = tokens.issue_heart(service, "draft", "draft")
    heart = gate.authenticate(service, token, roles=("heart",))
    kinds.run(service, heart, {"kind": "ticket.issue", "body": {"body": {
        "essence": "Proč.", "build": "Stránka\nPostav ji.", "doneCriteria": ["npm test projde"]}, "cardId": "home"}})
    session = gate.authenticate(service, gate.open_session(
        service, {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}})["token"])
    kinds.run(service, session, {"kind": "ask", "body": {"question": "?"}})
    text = snapshot.snapshot(service, "draft", "draft")
    assert "TICKETY PRÁCE: issued 1" in text and "[issued] Stránka (tk_" in text and " · karta home" in text
    assert " ask " in text
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
ORDER = ["PROJEKT", "ZÁMĚR:", "ZPRÁVY ČLOVĚKA:", "PRAVIDLA:", "ROZHODNUTÍ:", "PLÁN:", "TICKETY PRÁCE:",
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
    relayed = snapshot.render({**FACTS, "messages": [{"at": "t", "workspace": "main", "text": "Web", "via": "office"},
                                                     {"at": "t", "workspace": "main", "text": "Já", "via": 7}]})
    assert _block(relayed, "ZPRÁVY ČLOVĚKA:") == ["- t Web (přes office)", "- t Já"]
    many = {**FACTS, **MEMORY, "rules": [{"id": f"r{i}", "text": "y" * 300, "scope": "project"} for i in range(40)]}
    assert len(_block(snapshot.render(many), "PRAVIDLA:")) == snapshot.RULES
    assert len(snapshot.render(many, limit=800)) <= 800


def test_render_without_surroundings_prints_empty_sections():
    text = snapshot.render(FACTS)
    for head in ("ZPRÁVY ČLOVĚKA:", "PRAVIDLA:", "ROZHODNUTÍ:", "DENÍK:"):
        assert _block(text, head) == ["- žádné"]


def test_view_has_approved_memory_rules_ticket_counts_and_the_held_ticket():
    work = [{**item, "workspaceId": "main", "feedback": [], "createdAt": "t"} for item in FACTS["workTickets"]]
    view = snapshot.view({**FACTS, **MEMORY, "workTickets": work}, "gs_1")
    assert view["rules"] == ["Česky a bez emoji"]
    assert set(view) == {"project", "intent", "rules", "plan", "tickets", "myTicket"}
    assert view["tickets"]["delivered"] == 1 and view["tickets"]["issued"] == 1 and view["myTicket"]["ticketId"] == "tk_1"
    assert snapshot.view({**FACTS, "workTickets": work}, "gs_cizi")["myTicket"] is None


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
                    "merged": "sloučeno abcdef1 · čeká na uzavření", "old": "sloučeno 1234567 · nezapsáno"}
    text = snapshot.render({**FACTS, "pages": [], "work": {"home": "PR #12"}})
    assert "- Domů · home · ready · PR #12" in text
    assert "- Domů · home · / · ready · volná · cíl:" in snapshot.render({**FACTS, "work": {}})


def test_blocked_card_names_its_predecessor_and_what_it_waits_for():
    cards = [{"id": key, "name": name, "stage": "ready"} for key, name in
             (("rls", "RLS"), ("auth", "Auth"), ("db", "Data"), ("ui", "UI"), ("run", "Běh"))]
    facts = {**FACTS, "pages": [], "cards": cards,
             "work": {"auth": "PR #12", "db": "sloučeno 1234567 · nezapsáno", "run": "běží (agent:dev)"},
             "blocked": {"rls": ["auth"], "ui": ["auth", "db", "x"], "run": ["auth"]},
             "names": {"rls": "RLS", "auth": "Auth", "db": "Data", "ui": "UI", "run": "Běh"}}
    text = snapshot.render(facts)
    assert "- RLS · rls · ready · blokovaná – čeká na Auth: PR #12 otevřený\n" in text
    assert "- UI · ui · ready · blokovaná – čeká na Auth: PR #12 otevřený; Data: sloučeno 1234567 · nezapsáno +1" in text
    assert "- Běh · run · ready · běží (agent:dev)" in text  # běžící karta zůstává běžící
    assert "- Auth · auth · ready · PR #12\n" in text and "- Data · db · ready · sloučeno 1234567 · nezapsáno" in text
    assert "blokovaná" not in snapshot.render({**facts, "blocked": {}})


def test_collect_reads_blockers_from_the_card_graph(service):
    current = service.view("draft", "draft")
    service.save_graph("draft", "draft", {"nodes": [node("a"), node("b")],
                                          "edges": [{"id": "e1", "source": "b", "target": "a"}]}, current["digest"])
    facts = snapshot.collect(service, "draft", "draft")
    assert facts["blocked"] == {"a": ["b"]} and set(facts["names"]) >= {"a", "b"}


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



def test_spaces_section_only_for_git_projects_after_git_and_capped():
    assert "PROSTORY:" not in snapshot.render(FACTS)  # lokální projekt (spaces None) sekci nemá
    space = {"id": "a" * 32, "domain": "Web", "branch": "work/" + "a" * 32, "free": 2, "running": 1, "done": 3}
    text = snapshot.render({**FACTS, "spaces": [space, {**space, "id": "b" * 32, "branch": "vlastni", "free": None}]})
    assert text.index("GIT:") < text.index("PROSTORY:") < text.index("DENÍK:")
    assert _block(text, "PROSTORY:") == [f"- {'a' * 32} · doména Web · karty volné 2 · běží 1 · hotové 3",
                                         f"- {'b' * 32} · doména Web · vlastni · karty ?"]
    assert _block(snapshot.render({**FACTS, "spaces": []}), "PROSTORY:") == ["- žádné"]
    many = _block(snapshot.render({**FACTS, "spaces": [space] * 30}), "PROSTORY:")
    assert many[-1].startswith("- … a další") and sum(len(row) + 1 for row in many) <= snapshot.SPACES_CHARS


def test_spaces_of_a_local_project_are_none(service):
    assert snapshot._spaces(service, "draft") is None


def test_intake_section_lists_recent_entries_and_is_omitted_when_empty(service):
    """VSTUPY (docs/navrhy/2026-10-30-vstupni-brana.md §4): ID, stanovisko a začátek věty; bez vstupů sekce chybí."""
    assert "VSTUPY:" not in snapshot.render(FACTS)
    entries = [{"id": f"ie_{number}", "verdict": "duplicate" if number % 2 else "pending", "text": "věta " * 40}
               for number in range(12)]
    text = snapshot.render({**FACTS, "intake": entries})
    rows = _block(text, "VSTUPY:")
    assert len(rows) == 8 and rows[0].startswith("- ie_0 · pending · věta") and rows[1].startswith("- ie_1 · duplicate")
    assert all(len(row) <= len("- ie_00 · duplicate · ") + 100 for row in rows)
    assert text.index("LÍSTKY ČEKAJÍCÍ:") < text.index("VSTUPY:") < text.index("POSLEDNÍ KONTROLY:")
    db = service.db_for("draft")
    with db:
        intake.record(db, "draft", "heart_message", None, "Přidej hledání.", "2026-10-30T10:00:00Z")
    assert [entry["text"] for entry in snapshot.collect(service, "draft", "draft")["intake"]] == ["Přidej hledání."]


def test_intake_section_shows_jev_confidence_and_area_and_hides_heart_decisions(service):
    """Řez 2: stanovisko od Jevu nese jistotu a oblast; vstup, který srdce potvrdilo, ze snímku zmizí."""
    entries = [{"id": "ie_1", "verdict": "later_extension", "layer": "jev", "confidence": 0.82, "areaId": "a1",
                "text": "Přidej hybridní hledání."}]
    rows = _block(snapshot.render({**FACTS, "intake": entries}), "VSTUPY:")
    assert rows == ["- ie_1 · later_extension (jev 0.82) · oblast a1 · Přidej hybridní hledání."]
    db = service.db_for("draft")
    with db:
        entry = intake.record(db, "draft", "heart_message", None, "Přidej filtr.", "2026-10-30T10:00:00Z")
        db.execute("UPDATE intake_entries SET layer='heart', verdict='done' WHERE id=?", (entry["id"],))
    assert snapshot.collect(service, "draft", "draft")["intake"] == []


def test_plan_shows_the_run_tag_of_open_cards_and_highlights_xl():
    cards = [{"id": "a", "name": "A", "stage": "ready"}, {"id": "b", "name": "B", "stage": "ready"}]
    facts = {**FACTS, "pages": [], "cards": cards,
             "runs": {"a": "[S · sonnet+opus]", "b": "[XL – nepředávat, rozděl]"}}
    text = snapshot.render(facts)
    assert "- A · a · ready · [S · sonnet+opus]\n" in text and "- B · b · ready · [XL – nepředávat, rozděl]" in text
    assert "[S ·" not in snapshot.render({**facts, "runs": {}})


def test_collect_tags_open_cards_from_the_graph(service):
    current = service.view("draft", "draft")
    service.save_graph("draft", "draft", {"nodes": [node("a"), node("b")],
                                          "edges": [{"id": "e1", "source": "b", "target": "a"}]}, current["digest"])
    facts = snapshot.collect(service, "draft", "draft")
    assert set(facts["runs"]) == {card["id"] for card in facts["cards"]}
    # Karty bez kroků a souborů nemají z čeho měřit: štítek „?“ (chudé podklady, §7 řez 2 – doplněk).
    assert set(facts["runs"].values()) == {"[? – doplň kroky a soubory]"}


def test_plan_rows_carry_full_ids_of_pages_cards_areas_and_sectors():
    """Řádky PLÁN nesou plné ID, ať srdce kvůli `member` a `milestone` nevolá `ctx tree`, `plan-of` ani `snapshot`."""
    facts = {**FACTS, "cards": [{"id": "home", "name": "Domů", "stage": "ready"},
                                {"id": "n_upload", "name": "[task] Nahrání souborů", "stage": "ready"}],
             "areas": [{"id": "a_import", "name": "Import dat"}],
             "sectors": [{"id": "s_mvp", "name": "MVP", "memberOf": "a_import"}, {"id": "s_web", "name": "Web",
                                                                                  "memberOf": None}]}
    plan = snapshot.render(facts).split("PLÁN:\n")[1].split("\nTICKETY PRÁCE")[0].splitlines()
    assert plan == ["- Domů · home · / · ready · cíl: Uvěřit, že to zvládnu.", "- Kontakt · kontakt · /kontakt · closed",
                    "- [task] Nahrání souborů · n_upload · ready", "- oblast Import dat · a_import",
                    "- sektor MVP · s_mvp · oblast a_import", "- sektor Web · s_web"]


def test_plan_puts_cards_with_work_before_the_cap():
    """Přes PAGES holých karet se karta s prací a blokovaná karta na konci grafu stejně dostanou do PLÁNU s ID."""
    cards = [{"id": f"c{i}", "name": f"Architektura {i}", "stage": "plan"} for i in range(snapshot.PAGES + 5)]
    cards += [{"id": "blk", "name": "Blokovaná", "stage": "ready"}, {"id": "run", "name": "Běží", "stage": "ready"}]
    facts = {**FACTS, "pages": [], "cards": cards, "work": {"run": "běží (agent:dev)"}, "blocked": {"blk": ["run"]},
             "names": {"run": "Běží"}}
    plan = snapshot.render(facts).split("PLÁN:\n")[1].split("\nTICKETY PRÁCE")[0].splitlines()
    assert len(plan) == snapshot.PAGES and plan[0].startswith("- Běží · run · ready · běží")
    assert plan[1].startswith("- Blokovaná · blk · ready · blokovaná") and plan[2].startswith("- Architektura 0 · c0")


def test_milestones_section_lists_active_milestones_with_full_id_and_criteria():
    active = {"id": "ms_262a0cc0", "title": "Obrazovka 501", "areaId": "a_import", "done": False,
              "criteria": [{"id": "c1", "text": "Formulář", "done": True, "cards": [{"id": "n_form", "done": True}]},
                           {"id": "c2", "text": "Export", "done": False,
                            "cards": [{"id": "n_exp", "done": False}, {"id": "n_csv", "done": False}]}]}
    text = snapshot.render({**FACTS, "work": {}, "active_milestones": [active]})
    assert ("MILNÍKY:\n- milník ms_262a0cc0 „Obrazovka 501“ aktivní · oblast a_import · kritéria 1/2: "
            "c1 hotovo (n_form); c2 čeká (n_exp, n_csv)") in text
    assert "MILNÍKY:" not in snapshot.render({**FACTS, "work": {}})


def test_collect_reads_active_milestones_of_the_workspace(service):
    from database.repositories.intake_milestones import IntakeMilestones
    db = service.db_for("draft")
    with db:
        IntakeMilestones(db).insert({"id": "ms_1", "workspaceId": "draft", "areaId": "a1", "title": "Hledání",
                                     "criteria": [{"id": "c1", "text": "Pole", "cards": ["n1"]}],
                                     "status": "proposed", "createdAt": "t0"})
        IntakeMilestones(db).activate("ms_1")
    facts = snapshot.collect(service, "draft", "draft")
    assert [item["id"] for item in facts["active_milestones"]] == ["ms_1"]
    assert "- milník ms_1 „Hledání“ aktivní · oblast a1 · kritéria 0/1: c1 čeká (n1)" in snapshot.render(facts)


def test_collect_lists_areas_and_sectors_of_the_canvas(service):
    view = service.view("draft", "draft")
    graph = {"nodes": [{"id": "ar", "parentId": None, "kind": "area", "name": "Oblast", "purpose": "", "x": 0, "y": 0,
                        "size": {"w": 400, "h": 300}},
                       {"id": "se", "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0,
                        "memberOf": "ar"}], "edges": []}
    service.save_graph("draft", "draft", graph, view["digest"])
    facts = snapshot.collect(service, "draft", "draft")
    assert facts["areas"] == [{"id": "ar", "name": "Oblast"}]
    assert facts["sectors"] == [{"id": "se", "name": "Sektor", "memberOf": "ar"}]


CONFLICT = {"id": "c" * 40, "subject": "Upravit cíl karty a", "items": [
    {"key": "spec:a:goal", "base": "Start", "ours": "Náš cíl", "theirs": "Přijatý cíl"}]}


def test_render_lists_open_proposal_conflicts_only_when_present():
    text = snapshot.render({**FACTS, "conflicts": [CONFLICT], "conflictsTotal": 1})
    assert ("KONFLIKTY NÁVRHŮ:\n- " + "c" * 40 + " · Upravit cíl karty a · spec:a:goal: náš → Náš cíl"
            " | přijato Přijatý cíl") in text
    assert "KONFLIKTY NÁVRHŮ" not in snapshot.render(FACTS)
    many = snapshot.render({**FACTS, "conflicts": [CONFLICT] * 5, "conflictsTotal": 9})
    assert _block(many, "KONFLIKTY NÁVRHŮ:")[-1] == "- … a další (5)" and len(_block(many, "KONFLIKTY NÁVRHŮ:")) == 5


def test_collect_reads_open_auto_rebase_conflicts(service):
    from backend.canvas.opora_auto_rebase import AutoRebase
    from backend.canvas.test_opora_auto_rebase import propose
    from backend.canvas.test_opora_changesets import accept, baseline
    from backend.canvas.test_project_architecture import domain, page

    current = service.view("draft", "draft")
    service.save_graph("draft", "draft", {"nodes": [node("a"), node("b"), domain(), page()], "edges": []},
                       current["digest"])
    root = baseline(service)
    propose(service, "a", goal="Ours")
    accept(service, propose(service, "a", goal="Theirs"), root["id"])
    assert snapshot.collect(service, "draft", "draft")["conflicts"] == []
    AutoRebase(service).run("draft", "draft")
    facts = snapshot.collect(service, "draft", "draft")
    assert facts["conflictsTotal"] == 1 and facts["conflicts"][0]["subject"] == "Edit a"
    assert facts["conflicts"][0]["items"][0]["key"] == "spec:a:goal"
    assert "KONFLIKTY NÁVRHŮ:" in snapshot.render(facts)


def test_open_heart_escalations_section_newest_first_capped_and_absent_without_any():
    """OTÁZKY U ČLOVĚKA (docs/brain-heart-channel.md §6): plné ID · čas · zkrácený text, nejvýš 5 řádků."""
    assert "OTÁZKY U ČLOVĚKA" not in snapshot.render(FACTS)
    asked = [{"ticketId": f"gt_{i}", "createdAt": f"2026-10-31T10:0{i}:00Z", "body": {"text": f"otázka {i}"}}
             for i in range(7, 0, -1)]
    asked[0]["body"]["text"] = "x" * 300
    text = snapshot.render({**FACTS, "escalations": asked})
    rows = _block(text, "OTÁZKY U ČLOVĚKA:")
    assert len(rows) == snapshot.ESCALATIONS and rows[1] == "- gt_6 · 2026-10-31T10:06:00Z · otázka 6"
    assert rows[0] == "- gt_7 · 2026-10-31T10:07:00Z · " + "x" * (snapshot.ESCALATION_TEXT - 1) + "…"
    assert "\n… a další (2)\n" in text
    assert text.index("ROZHODNUTÍ:") < text.index("OTÁZKY U ČLOVĚKA:") < text.index("PLÁN:")
    assert "a další" not in snapshot.render({**FACTS, "escalations": asked[:5]})


def test_collect_lists_open_heart_escalations_and_drops_withdrawn_ones(service):
    _, token = gate.tokens.issue_heart(service, "draft", "draft")
    heart = gate.authenticate(service, token, roles=("heart",))
    first, second = gate.escalate(service, heart, "Barva?"), gate.escalate(service, heart, "Jaké ID?")
    rows = _block(snapshot.snapshot(service, "draft", "draft"), "OTÁZKY U ČLOVĚKA:")
    assert [row.split(" · ")[0] for row in rows] == [f"- {second['ticketId']}", f"- {first['ticketId']}"]
    gate.withdraw(service, heart, second["ticketId"], "ID je v plánu.")
    rows = _block(snapshot.snapshot(service, "draft", "draft"), "OTÁZKY U ČLOVĚKA:")
    assert [row.split(" · ")[0] for row in rows] == [f"- {first['ticketId']}"]
