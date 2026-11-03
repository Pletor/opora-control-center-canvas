"""Piny Brainu v ticketu: výchozí ponytail a opora-control-center, přidané ID artefaktu, po pluginech, neznámé ID 422, dělník je vidí."""
from backend.brain import registry, seed
from backend.brain.test_seed import fake_ponytail
from backend.brain_opora.determinism.test_ticket import ISSUE, heart, refused, send, service, worker  # noqa: F401
from database.repositories.tickets import TicketStore


def test_issue_adds_default_ponytail_and_requested_pins_by_plugin(service, tmp_path):  # noqa: F811
    seed.ensure(service.db, service.root, ponytail_cache=fake_ponytail(tmp_path / "cache"))
    brain = heart(service)
    plain = send(service, brain, "ticket.issue", ISSUE)["ticket"]["machine"]["pins"]
    ponytail = registry.active(service.db, "opora:brain:skill:ponytail")
    assert plain[0] == {"pin": ponytail["pin"], "plugin": "ponytail", "version": ponytail["version"],
                        "zip": f"/api/brain-registry/pins/ponytail@{ponytail['version'][:12]}.zip"}
    assert [pin["plugin"] for pin in plain] == ["ponytail", "opora-control-center"]
    heart_pin = registry.active(service.db, "opora:brain:skill:heart")["pin"]
    issued = send(service, brain, "ticket.issue",
                  {**ISSUE, "pins": ["opora:brain:skill:vyslech", heart_pin]})["ticket"]
    assert [pin["plugin"] for pin in issued["machine"]["pins"]] == ["ponytail", "opora-control-center", "opora-heart"]
    stored = TicketStore(service.db_for("draft"), "draft").get(issued["ticketId"])
    assert stored["machine"]["pins"] == issued["machine"]["pins"]
    claimed = send(service, worker(service), "ticket.claim", {"ticketId": issued["ticketId"]})["ticket"]
    assert claimed["machine"]["pins"] == issued["machine"]["pins"]


def test_unknown_or_malformed_pin_is_422(service, tmp_path):  # noqa: F811
    seed.ensure(service.db, service.root, ponytail_cache=tmp_path / "chybi")
    brain = heart(service)
    for pins in (["opora:brain:skill:nic"], ["opora:brain:skill:heart@" + "0" * 12], ["ponytail@5.3.3"], "x"):
        wrong = refused(service, brain, "ticket.issue", {**ISSUE, "pins": pins})
        assert wrong.status == 422 and wrong.code == "invalid_payload" and wrong.hint, pins
    assert TicketStore(service.db_for("draft"), "draft").list("draft") == []
