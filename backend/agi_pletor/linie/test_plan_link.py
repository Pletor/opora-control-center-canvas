"""Vazba kuličky na plán a revize zadání (L7d): stavy vazby, zmrazené vydání, stale_plan, board podle plánu, fronty."""
import threading

import pytest

from backend.agi_pletor.linie import board, branches, plan_link, plan_view, rows, work
from backend.agi_pletor.linie.test_board import NO_PR
from backend.agi_pletor.linie.test_merge import GREEN
from backend.agi_pletor.linie.test_work import BODY, NOW, agent_commit, refused, setup  # noqa: F401 (fixture)
from backend.canvas.canvas_service import CanvasService

CARD = {"id": "karta", "kind": "node", "name": "Karta plánu"}
PAGE = {"id": "stranka", "kind": "node", "name": "Stránka"}


class Canvas:
    """Graf a revize zadání karet; `nodes=None` = graf nejde přečíst."""

    def __init__(self, nodes, revisions=None):
        self.nodes, self.revisions = nodes, revisions or {}
        self.registry_lock, self.db = threading.RLock(), None

    def view(self, project, workspace):
        if self.nodes is None:
            raise ValueError("Lokální projekty používají pouze pracovní prostor draft.")
        return {"graph": {"nodes": self.nodes}}

    def node_spec(self, project, workspace, node):
        if node not in {n["id"] for n in self.view(project, workspace)["graph"]["nodes"]}:
            raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
        return {"revision": self.revisions.get(node, 0), "fields": {}}


def ticket(card=None, intent=None, **work):
    machine = {"cardId": card, "cardVersion": 99, **({"intent": intent} if intent else {})}
    return {"ticketId": "tk_1", "workspaceId": "main", "machine": machine, "work": work or None}


def test_resolve_states():
    canvas = Canvas([CARD, {"id": "sektor", "kind": "sector"}], {"karta": 4})
    none = plan_link.resolve(canvas, "p", ticket())
    assert (none["state"], none["planCardId"], none["text"]) == ("none", None, "bez plánu")
    linked = plan_link.resolve(canvas, "p", ticket("karta"))
    assert {k: linked[k] for k in ("state", "planCardId", "directionCardId", "cardRevision")} == {
        "state": "linked", "planCardId": "karta", "directionCardId": None, "cardRevision": 4}  # plán bez směru smí
    for card in ("smazana", "sektor"):  # sektor není karta plánu
        gone = plan_link.resolve(canvas, "p", ticket(card))
        assert gone["state"] == "card_missing" and gone["planCardId"] is None and "bez plánu" not in gone["text"]
    down = plan_link.resolve(Canvas(None), "p", ticket("karta"))
    assert down["state"] == "source_unavailable" and "bez plánu" not in down["text"]


def test_issue_reads_revision_from_server_not_client():
    found = plan_link.issue(Canvas([CARD], {"karta": 2}), "p", ticket("karta"), NOW)
    assert found == {"cardId": "karta", "cardRevision": 2, "at": NOW}  # machine.cardVersion = 99 se nečte
    assert plan_link.issue(Canvas([CARD]), "p", ticket(), NOW) == {"cardId": None, "cardRevision": None, "at": NOW}


def test_direction_is_page_intent_of_same_project(tmp_path):
    service = CanvasService(tmp_path / "data")
    try:
        for flow, kind, project in (("wf_p", "page_intent", "p"), ("wf_lib", "library_flow", "p"),
                                    ("wf_cizi", "page_intent", "q")):
            service.db.execute("INSERT INTO flow_workflows(id,kind,project_id,name,created_at,owner_ref)"
                               " VALUES(?,?,?,?,?,?)", (flow, kind, project, flow, NOW, f"opora:page:stranka-{flow}"))
            service.db.execute("INSERT INTO flow_workflow_versions(id,workflow_id,n,graph,hash,status,created_at)"
                               " VALUES(?,?,1,'{}','h','active',?)", ("v_" + flow, flow, NOW))
        assert plan_link.direction(service, "p", ticket(intent={"workflowVersionId": "v_wf_p"})) == "stranka-wf_p"
        for version in ("v_wf_lib", "v_wf_cizi", "v_nic"):  # jiný druh, cizí projekt, neznámá verze
            assert plan_link.direction(service, "p", ticket(intent={"workflowVersionId": version})) is None
        assert plan_link.direction(service, "p", ticket()) is None
    finally:
        service.close()


def test_settle_marks_card_with_two_directions_ambiguous():
    def link(card, direction):
        return {"state": "linked", "planCardId": card, "directionCardId": direction, "cardRevision": 1, "text": ""}
    links = plan_link.settle([link("a", "s1"), link("a", "s2"), link("b", "s1"), link("b", None)])
    assert [(item["state"], item["directionCardId"]) for item in links] == [
        ("ambiguous", None), ("ambiguous", None), ("linked", "s1"), ("linked", None)]
    assert "víc kandidátů směru" in links[0]["text"]


@pytest.fixture
def carded(setup, monkeypatch):
    """Fixture `setup` + ticket srdce s kartou `karta` (klient poslal cardVersion 99), graf podvržený na instanci."""
    service, repo, tid = setup
    canvas = Canvas([CARD, PAGE], {"karta": 2})
    monkeypatch.setattr(service, "view", canvas.view)
    monkeypatch.setattr(service, "node_spec", canvas.node_spec)
    heart = "tk_" + "c" * 32
    with work.store_for(service, "draft") as store:
        store.insert(heart, "main", "issued", BODY, {"cardId": "karta", "cardVersion": 99, "pins": []}, NOW)
    row = rows.add(service.root, "draft", "Plán", "work")["id"]
    work.attach(service, "draft", heart, {"rowId": row, "branch": "feat/plan", "baseBranch": "develop"}, NOW,
                root=repo)
    return service, repo, tid, heart, canvas


def test_attach_freezes_issued_and_accept_pairs_sha_with_card_revision(carded):
    service, repo, editor, heart, canvas = carded
    found = work.get(service, "draft", heart)
    assert found["work"]["issued"] == {"cardId": "karta", "cardRevision": 2, "at": NOW}  # server, ne klient (99)
    assert found["plan"]["state"] == "linked" and found["plan"]["diff"] is False
    assert work.get(service, "draft", editor)["work"]["issued"] == {"cardId": None, "cardRevision": None, "at": NOW}
    head = agent_commit(repo, branch="feat/plan")
    work.report(service, "draft", heart, head, GREEN, None, NOW, "agent:t")
    accepted = work.accept(service, "draft", heart, head, "ok", NOW, untested=True)
    assert accepted["work"]["acceptance"]["cardRevision"] == 2 and accepted["summary"]["key"] == "accepted"
    work.allow_merge(service, "draft", heart, None, NOW)

    canvas.revisions["karta"] = 3  # kritéria karty se změnila, sha ne
    stale = work.get(service, "draft", heart)
    assert stale["summary"]["key"] == "stale_plan" and stale["axes"]["acceptance"]["state"] == "stale_plan"
    assert "accept" in stale["allowed"] and "merge" not in stale["allowed"]
    assert stale["summary"]["next"] == "Potvrďte přijetí vůči nové revizi zadání (karta R3)."
    assert stale["plan"]["diff"] is True and stale["plan"]["cardRevision"] == 3
    again = work.accept(service, "draft", heart, head, "znovu", NOW, untested=True)
    assert again["work"]["acceptance"]["cardRevision"] == 3 and again["work"]["mergeAllowed"] is None
    assert [item["cardRevision"] for item in again["work"]["acceptanceHistory"]] == [2]  # staré přijetí v historii
    assert again["summary"]["key"] == "accepted"


def test_deleted_card_is_card_missing_not_without_plan(carded):
    service, _, editor, heart, canvas = carded
    canvas.nodes = [PAGE]
    gone = work.get(service, "draft", heart)["plan"]
    assert gone["state"] == "card_missing" and gone["text"] == "karta plánu karta v projektu chybí"
    assert work.get(service, "draft", editor)["plan"]["state"] == "none"


def test_board_by_plan_is_same_snapshot_and_queues_match_summary(carded, monkeypatch):
    service, repo, editor, heart, _ = carded
    found = board.board(service, "draft", "main", repo, pr_lookup=NO_PR)
    reads = []
    monkeypatch.setattr(branches, "_heads", lambda root: reads.append(root) or [])
    by_plan = board.grouped(service, "draft", "main", repo, "plan", found["snapshot"]["id"], pr_lookup=NO_PR)
    assert reads == [] and by_plan["snapshot"] == found["snapshot"] and by_plan["group"] == "plan"
    assert [(b["ticketId"], b["mark"]) for b in by_plan["balls"]] == [(b["ticketId"], b["mark"]) for b in found["balls"]]
    rows_of = {b["ticketId"]: b["rowId"] for b in by_plan["balls"]}
    assert rows_of == {editor: "plan:none", heart: "plan:karta"}
    assert [(r["id"], r["type"], r["name"], r["parent"]) for r in by_plan["rows"]] == [
        ("plan:karta", "plan", "Karta plánu", None), ("plan:none", "plan", "bez plánu", None)]
    assert {b["ticketId"]: b["rowId"] for b in found["balls"]} != rows_of  # výsledek podle větví zůstal netknutý
    keys = [b["summary"]["key"] for b in found["balls"]]
    assert keys == ["todo", "todo"] and all(b["queues"] == ["ticketsTodo"] for b in found["balls"])
    assert found["queues"] == {"plansWaiting": 1, "ticketsTodo": 2, "humanDecisions": 0, "officeTasks": 0,
                               "gitQueue": 0, "human": []}  # stránka bez ticketu čeká, karta plánu má ticket
    assert refused(lambda: board.grouped(service, "draft", "main", repo, "plan", "snap_nic")).code == \
        "snapshot_not_found"


def test_group_puts_direction_above_plan_and_unverified_apart():
    def ball(tid, state, card=None, direction=None):
        return {"ticketId": tid, "rowId": "feat", "plan": {"state": state, "planCardId": card,
                                                           "directionCardId": direction}}
    found = {"balls": [ball("a", "linked", "k1", "s"), ball("b", "card_missing"), ball("c", "linked", "k2")],
             "rows": [], "snapshot": {"id": "snap_x"}}
    grouped = plan_view.group(found, {"s": "Stránka", "k1": "Hero"})
    assert [(r["id"], r["type"], r["parent"], r["depth"]) for r in grouped["rows"]] == [
        ("dir:s", "dir", None, 0), ("plan:k1", "plan", "dir:s", 1), ("plan:k2", "plan", None, 0),
        ("plan:unverified", "plan", None, 0)]
    assert [b["rowId"] for b in grouped["balls"]] == ["plan:k1", "plan:unverified", "plan:k2"]
