"""Tabulka druhů: každý druh je úplný, jeho příklad projde kontrolou i schématem, role určuje viditelnost,
pracovník druh srdce nepošle a `state` vrátí výstup podle schématu."""
import pytest

from backend.brain_opora.determinism import gate, kinds, task_queue
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.kind_schemas import SCHEMAS
from backend.canvas.canvas_service import CanvasService

WORKER = {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}}
TYPES = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool, "null": type(None)}


def conforms(value, schema, path="$"):
    """Chyby tvaru `value` proti podmnožině JSON Schema, kterou tabulka používá (prázdný seznam = sedí)."""
    types = schema.get("type")
    if types is not None:
        names = types if isinstance(types, list) else [types]
        if not any(isinstance(value, TYPES[name]) and not (name == "integer" and isinstance(value, bool))
                   for name in names):
            return [f"{path}: čekám {names}, je {type(value).__name__}"]
    if value is None:
        return []
    errors = []
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} není v {schema['enum']}")
    if isinstance(value, dict) and "properties" in schema:
        errors += [f"{path}: chybí {key}" for key in schema.get("required", []) if key not in value]
        if schema.get("additionalProperties") is False:
            errors += [f"{path}: navíc {key}" for key in value if key not in schema["properties"]]
        for key, item in value.items():
            if key in schema["properties"]:
                errors += conforms(item, schema["properties"][key], f"{path}.{key}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            errors += conforms(item, schema["items"], f"{path}[{index}]")
    return errors


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    yield canvas
    canvas.close()


def test_every_kind_is_complete_and_its_example_passes_check_and_schema():
    assert list(kinds.KINDS) == ["next", "ask", "report", "change", "state", "inbox", "release", "task.create",
                                 "task.cancel", "ticket.answer", "escalate"]
    assert set(SCHEMAS) == set(kinds.KINDS)
    for name, kind in kinds.KINDS.items():
        public = kind.public()
        assert public["role"] in ("worker", "heart") and public["description"] and public["sync"] == (
            name not in ("ask", "change"))
        assert all(code["hint"] for code in public["codes"]) and "invalid_payload" in {c["code"] for c in public["codes"]}
        assert conforms(public["example"], public["input"]) == [], name
        kind.check(public["example"])
    assert {kind.name for kind in kinds.TABLE if kind.role == "heart"} == {"task.create", "task.cancel",
                                                                            "ticket.answer", "escalate"}


def test_role_decides_the_visible_kinds():
    worker = [kind["kind"] for kind in kinds.visible("worker")]
    assert worker == ["next", "ask", "report", "change", "state", "inbox", "release"]
    assert [kind["kind"] for kind in kinds.visible("heart")] == list(kinds.KINDS)
    assert kinds.visible("human") == kinds.visible("heart")


def test_unknown_kind_lists_allowed_kinds_and_bad_bodies_name_the_example():
    assert kinds.request_payload({"kind": "ask"}) == ("ask", {})
    with pytest.raises(GateError) as caught:
        kinds.request_payload({"kind": "deploy", "body": {}})
    assert caught.value.status == 422 and "next, ask, report, change, state, inbox" in caught.value.hint
    for name, body in (("ask", {"q": "?"}), ("change", {"proposal": "x"}), ("task.create", {"title": "x"}),
                       ("task.create", {**SCHEMAS["task.create"][2], "project": "draft"}), ("escalate", {}),
                       ("ticket.answer", {"ticketId": "gt_1"}), ("task.cancel", {"taskId": "../x"}),
                       ("release", {"taskId": "ht_1"}), ("release", {"taskId": "ht_1", "reason": " "})):
        with pytest.raises(GateError) as caught:
            kinds.KINDS[name].check(body)
        assert caught.value.code == "invalid_payload" and caught.value.hint, name


def test_worker_cannot_send_a_heart_kind_and_no_ticket_is_made(service):
    session = gate.authenticate(service, gate.open_session(service, WORKER)["token"])
    with pytest.raises(GateError) as caught:
        kinds.run(service, session, {"kind": "task.create", "body": SCHEMAS["task.create"][2]})
    assert caught.value.status == 403 and caught.value.code == "heart_required" and caught.value.hint
    assert service.db_for("draft").execute("SELECT COUNT(*) FROM gate_tickets").fetchone()[0] == 0


def test_state_is_a_compact_view_with_the_held_task(service):
    rules = {"context": {"rules": ["Komentáře česky.", "Bez nových závislostí."]}}
    task_queue.create(service, {"project": "draft", "workspace": "draft", "title": "Stránka",
                                "body": {"do": "x", **rules}})
    session = gate.authenticate(service, gate.open_session(service, WORKER)["token"])
    before = kinds.run(service, session, {"kind": "state"})["answer"]
    assert before["myTask"] is None and before["queue"] == {"ready": 1, "assigned": 0, "done": 0, "failed": 0}
    assert before["rules"] == ["Komentáře česky.", "Bez nových závislostí."]
    held = kinds.run(service, session, {"kind": "next"})["answer"]["task"]
    after = kinds.run(service, session, {"kind": "state", "body": {}})
    assert after["status"] == "answered" and after["answer"]["myTask"] == held
    assert after["answer"]["project"] == {"id": "draft", "name": after["answer"]["project"]["name"],
                                          "workspace": "draft"}
    assert conforms(after["answer"], SCHEMAS["state"][1]) == []
    # Lístky zodpovězené branou do schránky nejdou.
    assert gate.inbox(service, session, 0)["tickets"] == []
