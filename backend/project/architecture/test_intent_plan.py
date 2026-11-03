"""Plán přehrání záměru stránky (§6): pořadí toku `main`, kroky, očekávání, selektory sekcí a digest verze."""

import sqlite3

import pytest

from backend.project.architecture.intent_plan import (
    IntentNotFound,
    active_version,
    intent_plan,
    main_order,
)
from database.schema.project_schema import REGISTRY_SCHEMA, ensure_flow_owner_ref


def node(nid, kind, **params):
    return {"id": nid, "type": f"intent.{kind}", "params": params}


def edge(eid, source, target, kind="main"):
    port = "data" if kind == "data" else "main"
    return {"id": eid, "source_node": source, "source_port": port, "target_node": target, "target_port": port,
            "kind": kind}


# Pořadí uzlů v grafu je schválně jiné než pořadí toku.
GRAPH = {"nodes": [node("ok", "done", claim="/dekujeme", check="path"),
                   node("err", "error", when="špatný e-mail", shows="chyba"),
                   node("fix", "action", do="type", section="form", text="znovu"),
                   node("send", "action", do="submit", section="form"),
                   node("in", "entry", **{"from": "kampaň"}),
                   node("mail", "reaction", does="send_email", expect="e-mail s videem"),
                   node("type", "action", do="type", section="form", text="a@b.cz"),
                   node("data", "data", fields=[], to="crm"),
                   node("seen", "view", section="hero", shows="nabídka")],
         "edges": [edge("1", "in", "seen"), edge("2", "seen", "type"), edge("3", "type", "send"),
                   edge("4", "send", "err"), edge("5", "err", "fix"), edge("6", "send", "mail"),
                   edge("7", "mail", "ok"), edge("8", "type", "data", "data")]}
VERSION = {"id": "v1", "workflow_id": "w1", "hash": "a" * 64, "graph": GRAPH}
ARCHITECTURE = {"nodes": [{"id": "web", "parentId": None,
                           "site": {"kind": "application", "environments": [{"host": "localhost:3000"}]}},
                          {"id": "sekce", "parentId": "web"},
                          {"id": "landing", "parentId": "sekce", "site": {"kind": "page", "path": "/video"}}]}


def test_main_order_follows_main_from_entry_and_skips_the_error_branch():
    assert [n["id"] for n in main_order(GRAPH)] == ["in", "seen", "type", "send", "mail", "ok"]


def test_plan_has_steps_expectations_section_scopes_and_the_version_digest():
    plan = intent_plan(ARCHITECTURE, "landing", VERSION)
    assert {key: plan[key] for key in ("schema", "pageId", "workflowVersionId", "digest", "path", "baseUrl")} == {
        "schema": "opora.intent-plan/1", "pageId": "landing", "workflowVersionId": "v1",
        "digest": "sha256:" + "a" * 64, "path": "/video", "baseUrl": "http://localhost:3000"}
    assert plan["nodes"] == [
        {"nodeId": "type", "kind": "step", "do": "type", "scope": '[data-opora-section="form"]', "text": "a@b.cz"},
        {"nodeId": "send", "kind": "step", "do": "submit", "scope": '[data-opora-section="form"]'},
        {"nodeId": "mail", "kind": "expect", "check": "email", "value": "e-mail s videem", "does": "send_email"},
        {"nodeId": "ok", "kind": "expect", "check": "path", "value": "/dekujeme"}]


def test_page_outside_the_architecture_opens_root_without_base_url():
    plan = intent_plan({"nodes": []}, "nikde", VERSION)
    assert plan["path"] == "/" and "baseUrl" not in plan


def test_without_active_version_there_is_no_plan():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(REGISTRY_SCHEMA)
    ensure_flow_owner_ref(db)
    with pytest.raises(IntentNotFound):
        active_version(db, "p", "landing")
