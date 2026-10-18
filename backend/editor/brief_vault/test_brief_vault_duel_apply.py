"""Vítězný směr se uplatní sám při duel-decide (docs/schranka-duel.md §3.2): fragment dostane nový text a smyčka jde
od scoped, představa se změní jen proti aktuální obsahové verzi (`visionRef`), karta zůstává na člověku, souběžná
změna předmětu se nepřepíše; představu ruční op nezmění; body bez `visionRevision` se do trendu nepočítají (§3.3)."""
import json

from backend.editor.brief_vault.test_brief_vault_duel import (
    CHALLENGER, HUMAN, JUDGES, PROJECT, client, decide, get, open_duel, post,  # noqa: F401 (fixture client)
)
from backend.editor.brief_vault.test_brief_vault_gates import SCOPE, root, walk

ADOPT = {"outcome": "adopt", "reason": "Rozhodl člověk."}


def fragment(client, fragment_id):
    found = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": fragment_id})
    assert found.status_code == 200, found.text
    return found.json()


def text_of(client, fragment_id):
    return fragment(client, fragment_id)["fragment"]["text"]


def adopt(client, duel, **extra):
    return decide(client, duel, headers=HUMAN, override=ADOPT, **extra)


def test_adopt_on_fragment_revises_text_and_loop_restarts_from_scoped(client):
    subject = walk(client, root(client), "weighed")
    assert get(client, "next")["gate"] != "scoped"
    opened = post(client, headers=CHALLENGER, op="duel-open", subject={"kind": "fragment", "id": subject["id"]},
                  scopeNodeId="s1", incumbent={"text": "Importuj CSV.", "ref": {"fragmentId": subject["id"], "revision": 2}},
                  challenger={"text": "Importuj JSON místo CSV."})
    ref = opened["duel"]["incumbent"]["ref"]
    assert ref == {"fragmentId": subject["id"], "revision": 1}  # server, ne klient; revize posledního textu
    done = adopt(client, opened["fragment"])
    assert done["applied"] is True and done["decision"]["applied"] is True
    after = fragment(client, subject["id"])
    assert after["fragment"]["text"] == "Importuj JSON místo CSV."
    assert done["decision"]["appliedRevision"] == after["latestRevision"]
    assert f"Směr z duelu {opened['fragment']['id']}: adopt" in after["fragment"]["note"]
    head = get(client, "next")
    assert head["fragment"]["id"] == subject["id"] and head["gate"] == "scoped"


def test_keep_leaves_fragment_unchanged(client):
    subject = root(client)
    done = decide(client, open_duel(client, {"kind": "fragment", "id": subject["id"]})["fragment"])
    assert done["decision"]["outcome"] == "keep" and done["applied"] is False
    assert done["decision"]["applied"] is False and done["decision"]["appliedRevision"] is None
    assert fragment(client, subject["id"])["latestRevision"] == 1


def test_fragment_changed_meanwhile_is_not_overwritten(client):
    subject = root(client)
    duel = open_duel(client, {"kind": "fragment", "id": subject["id"]})["fragment"]
    post(client, op="propose-mvp", fragmentIds=[subject["id"]], note="")  # jen metadata: obsah se nemění
    changed = post(client, op="revise", fragmentId=subject["id"], expectedRevision=2, text="Importuj XML.", note="ruka")
    done = adopt(client, duel)
    assert done["applied"] is False and "změnil" in done["decision"]["reason"]
    assert text_of(client, subject["id"]) == "Importuj XML."
    assert fragment(client, subject["id"])["latestRevision"] == changed["fragment"]["revision"]


def test_metadata_change_does_not_block_apply(client):
    subject = root(client)
    duel = open_duel(client, {"kind": "fragment", "id": subject["id"]})["fragment"]
    post(client, op="propose-mvp", fragmentIds=[subject["id"]], note="")
    assert adopt(client, duel)["applied"] is True
    assert text_of(client, subject["id"]) == "Importuj JSON místo CSV."


def test_node_duel_is_not_applied_to_canvas(client):
    done = adopt(client, open_duel(client, {"kind": "node", "id": "c1"})["fragment"])
    assert done["applied"] is False and done["decision"]["reason"].startswith("kartu upraví člověk nebo agent")


def vision(client):
    return get(client, "vision", scopeNodeId="s1")


def start(client, text="V0"):
    return post(client, headers=HUMAN, op="vision-set", scopeNodeId="s1", text=text, note="Založení")["fragment"]


def align(client, duel_id, value):
    return post(client, headers=JUDGES[2], op="vision-align", scopeNodeId="s1", duelId=duel_id, score=value, note="shoda")


def kept(client):
    return decide(client, open_duel(client, PROJECT)["fragment"])["fragment"]["id"]


def vision_details(client, vision_id):
    db = client.app_state.service.db_for(SCOPE["project"])
    row = db.execute("SELECT revision, fields FROM brief_fragment_details WHERE project_id=? AND workspace_id=? AND "
                     "fragment_id=? ORDER BY revision DESC LIMIT 1",
                     (SCOPE["project"], SCOPE["workspace"], vision_id)).fetchone()
    return db, row["revision"], json.loads(row["fields"])


def store(db, vision_id, revision, fields):
    db.execute("UPDATE brief_fragment_details SET fields=? WHERE project_id=? AND workspace_id=? AND fragment_id=? "
               "AND revision=?", (json.dumps(fields, ensure_ascii=False), SCOPE["project"], SCOPE["workspace"],
                                  vision_id, revision))
    db.commit()


def test_project_adopt_changes_vision_and_alignments_do_not_invalidate(client):
    created = start(client)
    earlier = [kept(client) for _ in range(3)]
    duel = open_duel(client, PROJECT)
    assert duel["duel"]["visionRef"] == {"fragmentId": created["id"], "revision": 1}
    for value, item in zip((2, 5, 8), earlier, strict=True):
        found = align(client, item, value)
    assert found["point"]["visionRevision"] == 1 and found["trajectory"]["n"] == 3
    assert vision(client)["vision"]["revision"] == 4  # řádek roste, obsahová verze ne
    done = adopt(client, duel["fragment"])
    assert done["applied"] is True and done["decision"]["appliedRevision"] == 5
    assert done["appliedFragment"]["text"] == "Importuj JSON místo CSV."
    view = vision(client)
    assert view["vision"]["text"] == "Importuj JSON místo CSV." and view["vision"]["revision"] == 5
    assert view["trajectory"]["n"] == 0 and view["trajectory"]["state"] == "insufficient"
    post(client, op="vision-set", scopeNodeId="s1", fromDuel=duel["fragment"]["id"], note="znovu", expect=409)
    nxt = open_duel(client, PROJECT)
    assert nxt["duel"]["visionRef"] == {"fragmentId": created["id"], "revision": 5}


def test_vision_is_changed_only_by_project_duel(client):
    created = start(client)
    for op, extra in (("revise", {"text": "V1", "note": "ruka"}), ("split", {"parts": [{"title": "a", "text": "b"}]}),
                      ("set-discipline", {"discipline": "be", "note": "n"}), ("restore", {"revision": 1, "note": "n"})):
        refused = post(client, headers=HUMAN, op=op, fragmentId=created["id"], expectedRevision=1, expect=409, **extra)
        assert "představu mění jen duel" in str(refused), op
    assert "subject project" in str(open_duel(client, {"kind": "fragment", "id": created["id"]}, expect=409))
    assert vision(client)["vision"]["text"] == "V0" and vision(client)["vision"]["revision"] == 1


def test_project_vision_changed_meanwhile_keeps_decision_unapplied(client):
    created = start(client)
    duel = open_duel(client, PROJECT)["fragment"]
    db, revision, fields = vision_details(client, created["id"])  # jiná cesta posunula obsahovou verzi
    store(db, created["id"], revision, {**fields, "vision": {**fields["vision"], "directionRevision": 7}})
    done = adopt(client, duel)
    assert done["applied"] is False and done["decision"]["reason"] == "představa se mezitím změnila"
    assert done["decision"]["appliedRevision"] is None and vision(client)["vision"]["text"] == "V0"
    post(client, op="vision-set", scopeNodeId="s1", fromDuel=duel["id"], note="dotažení", expect=409)


def test_legacy_project_duel_without_ref_is_refused_by_from_duel(client):
    duel = open_duel(client, PROJECT)  # představa ještě není, vazba nevznikne
    assert "visionRef" not in duel["duel"]
    start(client)
    done = adopt(client, duel["fragment"])
    assert done["applied"] is False and "nebyl veden" in done["decision"]["reason"]
    post(client, op="vision-set", scopeNodeId="s1", fromDuel=duel["fragment"]["id"], note="dotažení", expect=409)
    assert vision(client)["vision"]["text"] == "V0"


def test_legacy_points_without_vision_revision_do_not_count(client):
    created = start(client)
    for value, item in zip((2, 5, 8), [kept(client) for _ in range(3)], strict=True):
        align(client, item, value)
    assert vision(client)["trajectory"]["n"] == 3
    db, revision, fields = vision_details(client, created["id"])
    for point in fields["vision"]["points"]:
        point.pop("visionRevision")
    store(db, created["id"], revision, fields)
    assert vision(client)["trajectory"]["n"] == 0  # přiřazení k cíli nejde doložit (§3.3)


SAME = "předmět už má tento text (beze změny)"


def open_against(client, subject_id, incumbent, challenger):
    return post(client, headers=CHALLENGER, op="duel-open", subject={"kind": "fragment", "id": subject_id},
                scopeNodeId="s1", incumbent={"text": incumbent}, challenger={"text": challenger})["fragment"]


def test_return_to_older_text_does_not_revive_its_gates(client):
    subject = walk(client, root(client), "weighed")  # V0 „Importuj CSV.“ s platným scoped + weighed
    changed = post(client, op="revise", fragmentId=subject["id"], expectedRevision=subject["revision"],
                   text="Importuj XML.", note="ruka")["fragment"]  # V1: brány zneplatněné otiskem
    assert fragment(client, changed["id"])["gateStep"] == 0
    done = adopt(client, open_against(client, subject["id"], "Importuj XML.", "Importuj CSV."))
    assert done["applied"] is True and text_of(client, subject["id"]) == "Importuj CSV."
    after = fragment(client, subject["id"])
    assert after["gateStep"] == 0 and after["gatesStale"] is False and not any(
        after["gates"][name] for name in ("scoped", "weighed"))
    head = get(client, "next")
    assert head["fragment"]["id"] == subject["id"] and head["gate"] == "scoped"


def test_adopt_under_deleted_ancestor_fails_closed(client):
    parent = root(client)
    child = post(client, op="create", parentId=parent["id"], title="Dítě", text="Importuj CSV.")["fragment"]
    duel = open_duel(client, {"kind": "fragment", "id": child["id"]})["fragment"]
    post(client, headers=HUMAN, op="delete", fragmentId=parent["id"], expectedRevision=1, note="pryč")
    before = fragment(client, child["id"])["latestRevision"]
    done = adopt(client, duel)
    assert done["applied"] is False and done["decision"]["applied"] is False
    assert done["decision"]["reason"] == "předmět nebo jeho předek je smazaný"
    assert done["decision"]["appliedRevision"] is None and "appliedFragment" not in done
    assert fragment(client, child["id"])["latestRevision"] == before
    assert text_of(client, child["id"]) == "Importuj CSV."


def test_adopt_on_deleted_subject_fails_closed(client):
    subject = root(client)
    duel = open_duel(client, {"kind": "fragment", "id": subject["id"]})["fragment"]
    post(client, headers=HUMAN, op="delete", fragmentId=subject["id"], expectedRevision=1, note="pryč")
    done = adopt(client, duel)
    assert done["applied"] is False and done["decision"]["reason"] == "předmět nebo jeho předek je smazaný"
    assert fragment(client, subject["id"])["latestRevision"] == 2


def test_identical_text_is_explicit_no_op(client):
    subject = walk(client, root(client), "weighed")
    done = adopt(client, open_against(client, subject["id"], "Importuj CSV.", "Importuj CSV."))
    assert done["applied"] is False and done["decision"]["applied"] is False
    assert done["decision"]["reason"] == SAME and done["decision"]["appliedRevision"] is None
    after = fragment(client, subject["id"])
    assert after["latestRevision"] == subject["revision"] and after["gateStep"] == 2  # brány beze změny


def test_project_identical_text_is_explicit_no_op(client):
    created = post(client, headers=HUMAN, op="vision-set", scopeNodeId="s1", text="Importuj JSON místo CSV.",
                   note="Založení")["fragment"]
    done = adopt(client, open_duel(client, PROJECT)["fragment"])
    assert done["applied"] is False and done["decision"]["reason"] == SAME
    assert done["decision"]["appliedRevision"] is None
    assert vision(client)["vision"]["revision"] == created["revision"]
