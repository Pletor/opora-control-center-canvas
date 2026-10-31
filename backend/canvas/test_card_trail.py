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
    return {"nodeId": "n0", "runs": [], "tasks": [], "events": [], "activity": [], "edges": [], "names": {},
            "reports": {}, "pr": None, "missing": [], "files": None, **extra}


def test_empty_card_has_empty_trail():
    trail = project_trail(facts(missing=["steps"]))
    assert trail == {"nodeId": "n0", "now": None, "runs": [], "pr": None, "missing": ["steps"], "recent": [],
                     "ports": [], "judgment": [], "filesKnown": False}


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


def test_gate_task_becomes_single_step_run_with_owner_from_events():
    task = {"taskId": "ht_1", "title": "Oprav test", "status": "assigned", "attempts": 1, "createdBy": "heart",
            "createdAt": "2026-10-31T12:00:00+00:00", "body": {"files": ["src/x.ts"]},
            "report": {"sha": SHA_B, "summary": "", "checks": [{"name": "npm test", "status": "red"}]}}
    events = [{"kind": "gate.task", "actor": {"kind": "agent", "name": "worker-3"}, "data": {"taskId": "ht_1"},
               "at": "2026-10-31T12:01:00Z", "title": "Úkol přidělen"}]
    trail = project_trail(facts(tasks=[task], events=events, files={SHA_B: ["src/x.ts"]}))
    (only,) = trail["runs"]
    assert only["taskId"] == "ht_1" and only["owner"] == "worker-3" and only["state"] == "assigned"
    assert only["steps"][0]["checks"] == [{"name": "npm test", "status": "red"}]
    assert only["steps"][0]["files"] == ["src/x.ts"]
    assert trail["now"]["owner"] == "worker-3" and trail["now"]["stepId"] == "ht_1"
    assert trail["judgment"] == []  # jeden červený pokus a úkol ještě běží


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
