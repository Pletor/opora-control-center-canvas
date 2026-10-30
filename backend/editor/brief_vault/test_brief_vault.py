"""Schránka zadání: append-only revize s CAS, split bez ztráty zadání, research → promote,
měkké smazání, guardy člověka a izolace projektu / prostoru."""
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.activity_log import HumanRequired
from backend.editor.brief_vault.brief_vault import BriefVault
from backend.editor.node.test_removals import ORIGIN, SCOPE, install_graph, node

CHAPTERS = "Úvod vrstvy.\n\n3.1 Architektura\nTabulky.\n\n3.2 Chunks\nřádek 3.3 uvnitř\n\n3.37 Version activation"


@pytest.fixture
def vault(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, {"nodes": [node("s1", kind="sector"), node("c1", "s1")], "edges": []})
        yield BriefVault(app.state.service)


def op(vault, name, actor="agent", **fields):
    return vault.apply({**SCOPE, "op": name, **fields}, actor=actor, agent="work-1")


def rows(vault, fragment_id):
    db = vault.canvas.db_for("draft")
    return [tuple(row) for row in db.execute(
        "SELECT revision,text,title,note,by,actor FROM brief_fragment_revisions WHERE fragment_id=? ORDER BY revision",
        (fragment_id,))]


def root(vault, text=CHAPTERS):
    return op(vault, "create", scopeNodeId="s1", discipline="be", title="3. VRSTVA", text=text)["fragment"]


def test_create_and_revise_append_revisions_with_cas(vault):
    fragment = root(vault)
    assert fragment["revision"] == 1 and fragment["scopeNodeId"] == "s1" and fragment["by"] == "work-1"
    revised = op(vault, "revise", fragmentId=fragment["id"], expectedRevision=1, text="nový", note="zpřesnění")
    assert revised["fragment"]["revision"] == 2
    history = rows(vault, fragment["id"])
    assert [item[:2] for item in history] == [(1, CHAPTERS), (2, "nový")]  # starý text zůstal doslovně
    assert history[1][3] == "zpřesnění" and history[1][5] == "agent"
    with pytest.raises(ValueError, match="změnil"):
        op(vault, "revise", fragmentId=fragment["id"], expectedRevision=1, text="souběh", note="x")
    with pytest.raises(ValueError, match="nic nemění"):
        op(vault, "revise", fragmentId=fragment["id"], expectedRevision=2, text="nový", note="x")
    with pytest.raises(ValueError, match="note"):
        op(vault, "revise", fragmentId=fragment["id"], expectedRevision=2, text="bez poznámky", note=" ")
    assert len(rows(vault, fragment["id"])) == 2


def test_create_validates_scope_parent_and_text(vault):
    for fields in ({"scopeNodeId": "neni"}, {"parentId": "neni"}, {}, {"scopeNodeId": "s1", "parentId": "x"}):
        with pytest.raises(ValueError):
            op(vault, "create", title="T", text="t", **fields)
    with pytest.raises(ValueError):
        op(vault, "create", scopeNodeId="", title="T", text="a\0b")
    with pytest.raises(ValueError):
        op(vault, "create", scopeNodeId="", title="T", text="x" * 64001)
    with pytest.raises(ValueError):
        op(vault, "create", scopeNodeId="", title="T", text="t", extra=1)
    canvas_root = op(vault, "create", scopeNodeId="", discipline="ux", title="Plátno", text="")["fragment"]
    child = op(vault, "create", parentId=canvas_root["id"], title="Dítě", text="d")["fragment"]
    assert child["parentId"] == canvas_root["id"] and child["scopeNodeId"] is None and child["ord"] == 1


def test_split_keeps_every_character_or_rejects(vault):
    fragment = root(vault)
    result = op(vault, "split", fragmentId=fragment["id"], expectedRevision=1, splitter="heading-number")
    titles = [child["title"] for child in result["children"]]
    assert titles == ["Úvod vrstvy.", "3.1 Architektura", "3.2 Chunks", "3.37 Version activation"]
    texts = [vault.fragment("draft", "draft", child["id"])["fragment"]["text"] for child in result["children"]]
    assert "\n\n".join(texts) == CHAPTERS and "řádek 3.3 uvnitř" in texts[2]
    # Rodič si nechal plný text a žádnou novou revizi.
    assert rows(vault, fragment["id"])[-1][:2] == (1, CHAPTERS)
    with pytest.raises(ValueError, match="podfragmenty"):
        op(vault, "split", fragmentId=fragment["id"], expectedRevision=1, splitter="heading-number")


def test_split_with_parts_mismatch_is_rejected_without_writes(vault):
    fragment = root(vault, "A\n\nB")
    before = vault.canvas.db_for("draft").execute("SELECT COUNT(*) FROM brief_fragment_revisions").fetchone()[0]
    for parts in ([{"title": "a", "text": "A"}, {"title": "b", "text": "C"}],
                  [{"title": "a", "text": "A\n\nB"}],
                  [{"title": "a", "text": "A"}, {"title": "b", "text": "B"}, {"title": "c", "text": ""}]):
        with pytest.raises(ValueError):
            op(vault, "split", fragmentId=fragment["id"], expectedRevision=1, parts=parts)
    with pytest.raises(ValueError):
        op(vault, "split", fragmentId=fragment["id"], expectedRevision=1, splitter="heading-number")
    assert vault.canvas.db_for("draft").execute("SELECT COUNT(*) FROM brief_fragment_revisions").fetchone()[0] == before
    ok = op(vault, "split", fragmentId=fragment["id"], expectedRevision=1,
            parts=[{"title": "a", "text": "A"}, {"title": "b", "text": "B"}])
    assert [child["ord"] for child in ok["children"]] == [1, 2]


def test_split_parts_may_end_at_a_single_line_break_but_never_drop_or_add_text(vault):
    """Kapitola hned pod posledním řádkem předchozí (bez prázdného řádku) se dá oddělit `parts`; spojení sedí doslovně."""
    text = "Úvod.\n\n3.1 Architektura\nTabulky.\n3.2 Chunks\nŘádky.\n\n\n3.3 Q&A"
    fragment = root(vault, text)
    for parts in ([{"title": "a", "text": "Úvod."}, {"title": "b", "text": "3.1 Architektura\nTabulky.3.2 Chunks\nŘádky."},
                   {"title": "c", "text": "3.3 Q&A"}],
                  [{"title": "a", "text": "Úvod.\n"}, {"title": "b", "text": "3.1 Architektura\nTabulky.\n3.2 Chunks\nŘádky."},
                   {"title": "c", "text": "\n3.3 Q&A"}, {"title": "d", "text": "navíc"}]):
        with pytest.raises(ValueError, match="spojení"):
            op(vault, "split", fragmentId=fragment["id"], expectedRevision=1, parts=parts)
    parts = [{"title": "Úvod", "text": "Úvod."}, {"title": "3.1", "text": "3.1 Architektura\nTabulky."},
             {"title": "3.2", "text": "3.2 Chunks\nŘádky.\n"}, {"title": "3.3", "text": "3.3 Q&A"}]
    children = op(vault, "split", fragmentId=fragment["id"], expectedRevision=1, parts=parts)["children"]
    texts = [vault.fragment("draft", "draft", child["id"])["fragment"]["text"] for child in children]
    assert texts == [part["text"] for part in parts]
    assert texts[0] + "\n\n" + texts[1] + "\n" + texts[2] + "\n\n" + texts[3] == text


def test_research_promote_new_parent_revision_and_marks_research_ready(vault):
    fragment = root(vault, "Verze se přepíná.")
    research = op(vault, "research", fragmentId=fragment["id"], title="Atomické přepnutí", text="Použít transakci.")["fragment"]
    assert research["kind"] == "research" and research["stage"] == "research"
    tree = vault.tree("draft", "draft", "s1")["roots"][0]
    assert tree["status"] == "research"
    with pytest.raises(ValueError):
        op(vault, "promote", fragmentId=fragment["id"], expectedRevision=1, note="není research")
    promoted = op(vault, "promote", fragmentId=research["id"], expectedRevision=1, note="závěr researche",
                  text="Verze se přepíná v jedné transakci.")
    assert promoted["fragment"]["revision"] == 2 and promoted["research"]["stage"] == "ready"
    assert "Povýšen research" in promoted["fragment"]["note"]
    assert rows(vault, fragment["id"])[0][1] == "Verze se přepíná."


def test_mvp_proposal_by_agent_and_human_only_guards(vault):
    fragment = root(vault)
    proposed = op(vault, "propose-mvp", fragmentIds=[fragment["id"]])
    assert proposed["changed"][0]["mvp"] == "proposed"
    for name, fields in (("set-mvp", {"fragmentIds": [fragment["id"]], "mvp": "yes"}),
                         ("delete", {"fragmentId": fragment["id"], "expectedRevision": 2, "note": "pryč"}),
                         ("restore", {"fragmentId": fragment["id"], "expectedRevision": 2, "revision": 1, "note": "zpět"})):
        for actor in ("agent", "unknown"):
            with pytest.raises(HumanRequired) as error:
                op(vault, name, actor=actor, **fields)
            assert error.value.actor == actor
    assert op(vault, "set-mvp", actor="human", fragmentIds=[fragment["id"]], mvp="yes")["changed"][0]["mvp"] == "yes"
    # Rozhodnutí člověka agent návrhem nepřepíše.
    assert op(vault, "propose-mvp", fragmentIds=[fragment["id"]])["skipped"] == [fragment["id"]]


def test_soft_delete_hides_subtree_and_restore_brings_old_revision_back(vault):
    fragment = root(vault)
    op(vault, "split", fragmentId=fragment["id"], expectedRevision=1, splitter="heading-number")
    deleted = op(vault, "delete", actor="human", fragmentId=fragment["id"], expectedRevision=1, note="omyl")
    assert deleted["fragment"]["deleted"] is True
    assert vault.tree("draft", "draft")["roots"] == []
    with pytest.raises(ValueError, match="smazaný"):
        op(vault, "revise", fragmentId=fragment["id"], expectedRevision=2, text="x", note="x")
    assert rows(vault, fragment["id"])[0][1] == CHAPTERS  # text nezmizel
    restored = op(vault, "restore", actor="human", fragmentId=fragment["id"], expectedRevision=2, revision=1, note="vrátit")
    assert restored["fragment"]["revision"] == 3 and restored["fragment"]["deleted"] is False
    roots = vault.tree("draft", "draft")["roots"]
    assert roots[0]["coverage"]["leaves"] == 4 and roots[0]["coverage"]["saved"] == 4


def test_project_and_workspace_isolation(vault, tmp_path):
    fragment = root(vault)
    db = vault.canvas.db_for("draft")
    db.execute("UPDATE brief_fragment_revisions SET workspace_id='other' WHERE fragment_id=?", (fragment["id"],))
    db.commit()
    assert vault.tree("draft", "draft")["roots"] == []
    with pytest.raises(ValueError, match="neexistuje"):
        vault.fragment("draft", "draft", fragment["id"])
    with pytest.raises(ValueError, match="neexistuje"):
        op(vault, "revise", fragmentId=fragment["id"], expectedRevision=1, text="x", note="x")


def test_fragment_read_returns_text_history_children_and_path(vault):
    fragment = root(vault)
    children = op(vault, "split", fragmentId=fragment["id"], expectedRevision=1, splitter="heading-number")["children"]
    detail = vault.fragment("draft", "draft", children[1]["id"])
    assert detail["fragment"]["text"].startswith("3.1 Architektura")
    assert [item["title"] for item in detail["path"]] == ["3. VRSTVA", "3.1 Architektura"]
    assert detail["scopeNodeId"] == "s1" and len(detail["history"]) == 1 and detail["cards"] == []
    whole = vault.fragment("draft", "draft", fragment["id"])
    assert [child["title"] for child in whole["children"]][1] == "3.1 Architektura"
    assert "text" not in vault.tree("draft", "draft")["roots"][0]


def test_new_brief_and_question_fragments_become_intake_entries_but_revisions_and_research_do_not(vault):
    """Vstupní brána (docs/navrhy/2026-10-30-vstupni-brana.md §6): jen nový fragment `brief` / `question`."""
    fragment = root(vault, text="Přidej hybridní vyhledávání.")
    op(vault, "revise", fragmentId=fragment["id"], expectedRevision=1, text="Přidej vyhledávání.", note="kratší")
    op(vault, "research", fragmentId=fragment["id"], title="Ověření", text="Změřit bm25.")
    question = op(vault, "question", fragmentId=fragment["id"], title="Jaký jazyk?")["fragment"]
    op(vault, "create", scopeNodeId="s1", discipline="be", title="Znovu", text="přidej hybridní VYHLEDÁVÁNÍ")
    db = vault.canvas.db_for("draft")
    rows = [tuple(row) for row in db.execute(
        "SELECT source, source_ref, text, verdict FROM intake_entries ORDER BY created_at, rowid")]
    assert rows[:2] == [("brief_fragment", fragment["id"], "Přidej hybridní vyhledávání.", "pending"),
                        ("brief_fragment", question["id"], "Jaký jazyk?", "pending")]
    assert rows[2][2:] == ("přidej hybridní VYHLEDÁVÁNÍ", "duplicate") and len(rows) == 3
