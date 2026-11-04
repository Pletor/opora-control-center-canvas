import pytest

from backend.flow import library
from backend.flow.catalogs.test_data_flow import rag
from backend.flow.graph_check import FlowInvalid
from backend.flow.workflows import FlowConflict, FlowNotFound, create_draft


def folder(db, part="human", slug="ai-rag"):
    return next(f for f in library.list_library(db, part) if f["slug"] == slug)


def test_seed_is_idempotent_and_keeps_deleted_folders_away(db):
    library.seed_folders(db)
    library.seed_folders(db)
    slugs = [f["slug"] for f in library.list_library(db, "human")]
    assert slugs[0] == "database" and "ai-rag" in slugs and len(slugs) == len(library.DEFAULT_FOLDERS)
    library.delete_folder(db, folder(db, slug="other")["id"])
    library.seed_folders(db)
    assert "other" not in [f["slug"] for f in library.list_library(db, "human")]
    assert library.list_library(db, "agent") == []


def test_folders_crud_and_rules(db):
    created = library.create_folder(db, "agent", "rag-pokusy", "RAG pokusy")
    assert created["order"] == 0 and created["owner"] == "agent"
    with pytest.raises(FlowConflict) as taken:
        library.create_folder(db, "agent", "rag-pokusy", "Znovu")
    assert taken.value.code == "folder_taken"
    with pytest.raises(FlowInvalid):
        library.create_folder(db, "agent", "Velká Písmena", "X")
    updated = library.update_folder(db, created["id"], title="RAG", order=5)
    assert (updated["title"], updated["order"], updated["slug"]) == ("RAG", 5, "rag-pokusy")
    library.create_flow(db, created["id"], "ingest", "Ingest")
    with pytest.raises(FlowConflict) as full:
        library.delete_folder(db, created["id"])
    assert full.value.code == "folder_not_empty"
    with pytest.raises(FlowNotFound):
        library.get_folder(db, "nic")


def test_adopt_contribute_lineage_and_promote(db):
    library.seed_folders(db)
    db.execute("INSERT INTO projects(id,name) VALUES('p','P')")
    original = library.create_flow(db, folder(db)["id"], "rag", "RAG – ingest a dotaz", "Ingest a dotaz")
    assert original["ownerRef"] == "opora:library:human:ai-rag/rag" and original["versions"] == []
    with pytest.raises(FlowConflict) as empty:
        library.adopt(db, original["id"], "p")
    assert empty.value.code == "empty_flow"
    v1 = create_draft(db, original["id"], rag())

    copy = library.adopt(db, original["id"], "p", "node-rag")
    assert copy["projectId"] == "p" and copy["ownerRef"] == "opora:project-flow:node-rag"
    assert copy["derivedFrom"] == {"workflowId": original["id"], "versionId": v1["id"]}
    assert copy["activeN"] == 1 and copy["versions"][0]["graph"] == rag()
    with pytest.raises(FlowConflict):
        library.adopt(db, original["id"], "p", "node-rag")  # owner_taken
    with pytest.raises(FlowInvalid):
        library.adopt(db, copy["id"], "p")  # kopii z projektu se nepřebírá

    better = library.contribute(db, copy["id"], folder(db)["id"], "rag-v2", "RAG s rerankerem")
    assert better["derivedFrom"]["workflowId"] == copy["id"] and better["projectId"] is None
    detail = library.flow_detail(db, original["id"])
    assert detail["derivedCount"] == 1 and detail["projects"] == ["p"]
    assert [d["workflowId"] for d in library.flow_detail(db, copy["id"])["derived"]] == [better["id"]]
    flows = folder(db)["flows"]
    assert [(f["slug"], f["derivedCount"]) for f in flows] == [("rag", 1), ("rag-v2", 0)]

    with pytest.raises(FlowConflict):
        library.promote(db, original["id"])  # není z knihovny agenta
    agent_folder = library.create_folder(db, "agent", "ai-rag", "AI a RAG")
    learned = library.create_flow(db, agent_folder["id"], "rag-agent", "RAG agenta")
    promoted = library.promote(db, learned["id"])
    assert promoted["ownerRef"] == "opora:library:human:ai-rag/rag-agent"
    assert library.part_of(db, learned["id"]) == "human" and library.part_of(db, copy["id"]) is None


def test_cases_survive_versions_adopt_and_contribute(db):
    from backend.flow.test_simulate import BAD_CASE, OK_CASE, bmi_graph

    library.seed_folders(db)
    db.execute("INSERT INTO projects(id,name) VALUES('p','P')")
    graph = bmi_graph([OK_CASE, BAD_CASE])
    original = library.create_flow(db, folder(db)["id"], "bmi", "BMI")
    create_draft(db, original["id"], graph)
    assert library.flow_detail(db, original["id"])["versions"][0]["graph"]["cases"] == [OK_CASE, BAD_CASE]
    copy = library.adopt(db, original["id"], "p")
    assert copy["versions"][0]["graph"] == graph
    better = library.contribute(db, copy["id"], folder(db)["id"], "bmi-2", "BMI 2")
    assert better["versions"][0]["graph"]["cases"] == [OK_CASE, BAD_CASE]
