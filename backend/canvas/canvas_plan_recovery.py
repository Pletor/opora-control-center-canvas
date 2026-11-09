"""Recover only frozen native plans, never rebuild IDs or guess mixed SQL outcomes."""
from copy import deepcopy

from backend.canvas.canvas_plan_build import Built
from backend.canvas.payload_errors import NextStep
from backend.editor.agent_memory.desktop_v3_state import fill_defaults


def blocked(message):
    raise NextStep(message, code="operation_incomplete",
                   hint="Retry the identical POST /api/canvas-plan after restoring its exact recorded context; legacy or callback receipts need explicit manual reconciliation.")


def graph_value(graph):
    return {"nodes": sorted(({**n, "x": round(n["x"]), "y": round(n["y"])} for n in graph["nodes"]), key=lambda n: n["id"]),
            "edges": sorted(graph["edges"], key=lambda e: e["id"])}


def sql_value(service, store, project, workspace, built, wid_of):
    state = store.current(project, workspace)
    documents = []
    for kind, values in (("spec", built.specs), ("text", built.texts)):
        storage, field = (service.specs, "fields") if kind == "spec" else (service.texts, "text")
        for node in sorted(values):
            actual = storage.read((project, wid_of(node), node))
            documents.append({"node": node, "kind": kind, "workspace": wid_of(node),
                              "revision": actual["revision"], "value": actual[field]})
    return {"state": state["state"], "revision": state["revision"], "documents": documents}


def prepare(service, store, project, workspace, built, wid_of, before, result, callback, owner):
    sql = sql_value(service, store, project, workspace, built, wid_of)
    after = deepcopy(sql)
    after.update(state=fill_defaults(deepcopy(built.state)), revision=sql["revision"] + int(built.state_changed))
    for item in after["documents"]:
        item["revision"] += 1
        item["value"] = (built.specs if item["kind"] == "spec" else built.texts)[item["node"]]
    from backend.canvas.opora_execution_repin import freeze_candidates
    return {"version": 1, "recoverable": not callback, "prepared": result,
            "built": {key: sorted(value) if isinstance(value, set) else value for key, value in vars(built).items()},
            "beforeGraph": before, "sqlBefore": sql, "sqlAfter": after,
            "repins": freeze_candidates(service, project, workspace, owner), "repinOwner": owner,
            "written": False}


def restore(intent):
    if not isinstance(intent, dict) or intent.get("version") != 1 or not intent.get("recoverable"):
        blocked("This pending operation has no safely recoverable native postimage.")
    built = Built({}, {})
    built.__dict__.update(deepcopy(intent["built"]))
    return built


def classify(service, store, project, workspace, built, wid_of, intent):
    actual = sql_value(service, store, project, workspace, built, wid_of)
    # SQL is a single atomic aggregate. Per-document mixed pre/post is never recoverable.
    before, after = actual == intent["sqlBefore"], actual == intent["sqlAfter"]
    graph = graph_value(service.view(project, workspace)["graph"])
    graph_before, graph_after = graph == graph_value(intent["beforeGraph"]), graph == graph_value(built.new_graph())
    if not (before or after) or not (graph_before or graph_after):
        blocked("Native stores diverged from this operation's exact preimage and postimage.")
    if intent["written"]:
        if not after or not graph_after:
            blocked("Committed native operation no longer matches its recorded postimage.")
        return "post"
    if not before:
        blocked("SQL postimage lacks this operation's durable commit marker.")
    return "graph-only" if graph_after and not graph_before else "pre"


def owner_of(built, workspace):
    from backend.canvas.architecture_graph import ids, split
    from backend.canvas.project_architecture import ARCHITECTURE_WID
    owned = ids(split(built.new_graph())[0])[0]
    return lambda node: ARCHITECTURE_WID if node in owned else workspace


def resume(service, store, project, workspace, receipt, intent, actor):
    built = restore(intent)
    wid_of = owner_of(built, workspace)
    with service.lock_for(project):
        phase = classify(service, store, project, workspace, built, wid_of, intent)
    return persist(service, store, project, workspace, receipt, intent, built, wid_of, actor, phase)


def persist(service, store, project, workspace, receipt, intent, built, wid_of, actor, phase, after_write=None):
    try:
        return _persist(service, store, project, workspace, receipt, intent, built, wid_of, actor, phase, after_write)
    except NextStep:
        raise  # Preserve an already explicit mixed-state/reconciliation refusal.
    except Exception as error:
        # OP-B171BE.first-error: the frozen intent exists and native data may already be committed.
        raise NextStep(f"Canvas operation {receipt.identifier} is incomplete; native changes may already be stored.",
                       code="operation_incomplete",
                       hint=f"Resume with the identical POST /api/canvas-plan and operationId {receipt.identifier}. "
                            "Do not generate new IDs or a new request; mixed state requires explicit reconciliation.") from error


def _persist(service, store, project, workspace, receipt, intent, built, wid_of, actor, phase, after_write=None):
    from backend.canvas.canvas_plan import _write
    from backend.canvas.operation_readback import verify_plan
    from backend.canvas.opora_execution_repin import finish_candidates
    result = intent["prepared"]
    revision = intent["sqlAfter"]["revision"]
    db = service.db_for(project)

    def committed(db, refs):
        if "researchSource" in result:
            from backend.canvas.research_canvas_draft import prepare
            prepare(service, project, workspace, result["researchSource"])
        if after_write is not None:
            after_write(db, refs)
        intent["written"] = True
        receipt.progress(db, intent)  # commits with the entire SQL aggregate, never before it

    if phase != "post":
        _write(service, store, project, workspace, service.view(project, workspace)["digest"],
               intent["sqlBefore"]["revision"], built, wid_of, committed, actor=actor,
               graph_written=phase == "graph-only")
    saved = service.view(project, workspace)
    verify_plan(service, store, project, workspace, built, wid_of, saved, revision)
    # Also fence document revisions; equal content with a later revision is not our postimage.
    if sql_value(service, store, project, workspace, built, wid_of) != intent["sqlAfter"]:
        blocked("Native SQL revisions no longer match the operation postimage.")
    response = {**result, "digest": saved["digest"], "revision": revision}
    if "researchSource" in result:
        from backend.canvas.research_canvas_draft import evidence
        response["canvasDraft"] = evidence(service, project, workspace, built, wid_of, saved, revision,
                                           intent["beforeGraph"], intent["sqlBefore"]["state"])
    moved = finish_candidates(service, project, workspace, receipt, intent)
    if intent["repins"]:
        response["rePinned"] = moved
    with service.lock_for(project), db:
        receipt.complete(db, response)
    return response
