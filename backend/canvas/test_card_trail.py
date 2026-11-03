"""Stopa práce karty: čistá projekce syrových faktů (docs/stopa-prace-karty.md)."""
from backend.canvas.card_trail import project_trail, recent

SHA_A, SHA_B = "a" * 40, "b" * 40


def run(execution, state, created, steps=(), receipts=(), checkpoints=(), owner="agent:builder", expires=None):
    return {"record": {"executionId": execution, "owner": owner, "createdAt": created, "state": state,
                       "expiresAt": expires, "assignment": {"steps": list(steps)}},
            "receipts": list(receipts), "checkpoints": list(checkpoints)}


def receipt(summary, step_results=(), checks=None):
    result = {"summary": summary, "stepResults": list(step_results)}
    if checks is not None:
        result["selfChecks"] = {"headSha": SHA_A, "checks": checks}
    return {"result": result}


def step_result(step, status, notes="", checks=None, commits=None):
    evidence = {"notes": notes}
    if checks is not None:
        evidence["checks"] = checks
    if commits is not None:
        evidence["commits"] = commits
    return {"stepId": step, "status": status, "evidence": evidence}


STEPS = [{"id": "s1", "title": "Test modulu", "files": ["backend/x/**"]}, {"id": "s2", "title": "Dokumentace"}]


def facts(**extra):
    return {"nodeId": "n0", "runs": [], "tickets": [], "events": [], "activity": [], "edges": [], "names": {},
            "reports": {}, "pr": None, "missing": [], "files": None, **extra}


def test_empty_card_has_empty_trail():
    trail = project_trail(facts(missing=["steps"]))
    assert trail == {"nodeId": "n0", "now": None, "runs": [], "pr": None, "missing": ["steps"], "recent": [],
                     "ports": [], "judgment": [], "filesKnown": False, "afterMerge": None}


def test_steps_added_after_the_merge_leave_a_trace_entry():
    found = {"afterMerge": ["steps"], "afterMergeEvidence": {"executionId": "e1", "number": 22, "mergeSha": "787f3941aa",
                                                              "steps": [{"id": "s3", "title": "Docs"}]}}
    entry = project_trail(facts(missing=["human_close"], afterMerge=found))["afterMerge"]
    assert entry == {"requirements": ["steps"], "number": 22, "mergeSha": "787f3941aa", "executionId": "e1",
                     "steps": [{"id": "s3", "title": "Docs"}], "source": "det",
                     "label": "Kroky přibyly po sloučení PR #22 (787f394) – uznány sloučením, mimo standardní proces:"
                              " kroky: s3 Docs."}


def test_reported_run_carries_steps_checks_commits_files_and_sources():
    checks = [{"name": "npm-test", "command": "npm test", "status": "passed"},
              {"name": "pytest", "command": "uv run pytest", "status": "failed"}]
    done = receipt("Doplnil test.", [step_result("s1", "done", "test x", ["npm test", "uv run pytest"], [SHA_A])], checks)
    trail = project_trail(facts(runs=[run("e1", "reported", "2026-10-31T10:00:00+00:00", STEPS, [done])],
                                files={SHA_A: ["backend/x/a.py", "docs/a.md"]}, pr={"number": 7, "state": "open"}))
    (only,) = trail["runs"]
    assert only["summary"] == "Doplnil test." and only["source"] == "agent" and only["state"] == "reported"
    first, second = only["steps"]
    assert first == {"stepId": "s1", "title": "Test modulu", "status": "done",
                     "checks": [{"name": "npm test", "status": "green"}, {"name": "uv run pytest", "status": "red"}],
                     "commits": [SHA_A], "notes": "test x", "source": "agent",
                     "files": ["backend/x/a.py", "docs/a.md"], "allowed": ["backend/x/**"]}
    assert second["status"] == "pending" and second["source"] == "det" and "files" not in second
    assert trail["pr"] == {"number": 7, "state": "open"} and trail["filesKnown"] is True
    assert [item["code"] for item in trail["judgment"]] == ["files_mismatch"]


def test_receipt_wins_over_checkpoint_and_running_run_is_now():
    checkpoint = step_result("s1", "failed", "první pokus")
    running = run("e2", "running", "2026-10-31T11:00:00Z", STEPS, checkpoints=[checkpoint, step_result("s1", "done")],
                  expires=1_793_448_000)
    older = run("e1", "reported", "2026-10-31T09:00:00Z", STEPS, [receipt("", [step_result("s1", "done", "x")])],
                [checkpoint], owner="agent:heart")
    trail = project_trail(facts(runs=[older, running]))
    assert [item["executionId"] for item in trail["runs"]] == ["e2", "e1"]
    assert trail["now"] == {"owner": "agent:builder", "since": "2026-10-31T11:00:00Z", "until": "2026-10-31T12:00:00Z",
                            "stepId": "s2", "source": "det"}
    assert trail["runs"][1]["steps"][0]["status"] == "done"  # výsledek přepíše průběžný krok
    assert trail["runs"][1]["source"] == "det"  # prázdné shrnutí nemá autora
    assert {item["code"] for item in trail["judgment"]} == {"delivered_without_evidence", "missing_summary"}


def ticket(ticket_id, status, execution=None, delivery=None):
    return {"ticketId": ticket_id, "status": status, "sessionId": "gs_office", "createdAt": "2026-10-31T12:00:00+00:00",
            "body": {"build": "Oprav test\nPodrobnosti."}, "delivery": delivery,
            "machine": {"cardId": "n0", "executionId": execution, "cardVersion": None}}


def test_work_ticket_without_execution_becomes_single_step_run_and_bound_one_is_its_execution():
    held = ticket("tk_1", "in_progress")
    bound = ticket("tk_2", "delivered", execution="e9")
    trail = project_trail(facts(tickets=[held, bound]))
    (only,) = trail["runs"]
    assert only["ticketId"] == "tk_1" and only["owner"] == "gs_office" and only["state"] == "in_progress"
    assert only["steps"][0]["title"] == "Oprav test" and only["steps"][0]["status"] == "pending"
    assert trail["now"]["owner"] == "gs_office" and trail["now"]["stepId"] == "tk_1"
    done = project_trail(facts(tickets=[ticket("tk_3", "delivered", delivery={"summary": "Hotovo.", "sha": SHA_B})],
                               files={SHA_B: ["src/x.ts"]}))["runs"][0]
    assert done["summary"] == "Hotovo." and done["source"] == "agent" and done["reported"]
    assert done["steps"][0] == {"stepId": "tk_3", "title": "Oprav test", "status": "done", "checks": [],
                                "commits": [SHA_B], "notes": "", "source": "det", "files": ["src/x.ts"]}


def test_recent_merges_events_and_activity_newest_first_and_skips_noise():
    events = [{"at": "2026-10-31T10:00:00.000Z", "kind": "lease.heartbeat", "actor": {"kind": "agent", "name": "b"}},
              {"at": "2026-10-31T10:05:00.000Z", "kind": "step.done", "actor": {"kind": "agent", "name": "b"},
               "title": "Krok hotový", "source": "opora"},
              {"at": "2026-10-31T10:07:00.000Z", "kind": "tool.use", "actor": {"kind": "agent", "name": "b"},
               "title": "Edit x.py", "source": "agent-office"}]
    activity = [{"at": "2026-10-31T10:06:00+00:00", "actor": "agent", "agent": "heart", "label": "Kroky karty: 2 kroky",
                 "status": 200},
                {"at": "2026-10-31T10:08:00+00:00", "actor": "human", "agent": "", "label": "x", "status": 409}]
    items = recent(events, activity)
    assert [item["label"] for item in items] == ["Edit x.py", "Kroky karty: 2 kroky", "Krok hotový"]
    assert [item["source"] for item in items] == ["agent", "det", "det"]
    assert items[1]["who"] == "heart" and items[1]["kind"] == "write"
    many = [{"at": f"2026-10-31T10:{minute:02d}:00Z", "kind": "step.done", "actor": {}} for minute in range(30)]
    assert len(recent(many, [])) == 10


def test_ports_list_outgoing_edges_with_last_message():
    edges = [{"id": "e2", "source": "n0", "target": "n2"}, {"id": "e1", "source": "n0", "target": "n1"},
             {"id": "e3", "source": "n5", "target": "n0"}]
    reports = {"e1": {"summary": "Hotové API", "handoff": "Použij /x", "by": "agent", "agent": "builder",
                      "updatedAt": "2026-10-31T10:00:00Z"},
               "e2": {"summary": "Plán", "handoff": "", "by": "human", "updatedAt": "2026-10-31T09:00:00Z"}}
    trail = project_trail(facts(edges=edges, names={"n1": "Karta 1", "n2": "Karta 2"}, reports=reports))
    assert [(item["edgeId"], item["targetName"], item["source"]) for item in trail["ports"]] == [
        ("e1", "Karta 1", "agent"), ("e2", "Karta 2", "human")]
    assert trail["ports"][0]["by"] == "builder" and trail["ports"][0]["handoff"] == "Použij /x"
