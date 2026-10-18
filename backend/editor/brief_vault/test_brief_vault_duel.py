"""Duel a představa přes API (docs/schranka-duel.md §1–§5): open → grill → answer → score → decide → poučení,
pravidla stran, kol a claimů, neslučitelnost soudce a strany, concede, rebuttedBy, doklady, obhájená syntéza,
CAS, rozhodnutý duel, override jen člověk, /next (blokace podle předmětu a hlava fronty), strom, představa
(založení člověkem, změna jen duelem), trajektorie (bod na rozhodnutý duel) a totožný claim strany = 409."""
import itertools
import json
import threading

import pytest

from backend.editor.brief_vault.brief_vault_details import validate_details
from backend.editor.brief_vault.brief_vault_duel_math import MAX_CLAIMS, MAX_ROUNDS
from backend.editor.brief_vault.test_brief_vault_discipline import HEADERS, SCOPE, nodes, post, tree
from backend.editor.brief_vault.test_brief_vault_gates import root, vault_client

DEFENDER = {**HEADERS, "X-Opora-Actor": "agent; name=obhajce"}
CHALLENGER = {**HEADERS, "X-Opora-Actor": "agent; name=vyzyvatel"}
JUDGES = [{**HEADERS, "X-Opora-Actor": f"agent; name=kritik-{index}"} for index in range(3)]
HUMAN = HEADERS
EVIDENCE = [{"source": "backend/editor/brief_vault/brief_vault.py:42", "quote": "CAS přes expectedRevision"}]
PROJECT = {"kind": "project", "id": SCOPE["project"]}


@pytest.fixture
def client(tmp_path):
    with vault_client(tmp_path) as client:
        yield client


def get(client, path, expect=200, **params):
    response = client.get(f"/api/brief-vault/{path}", params={**SCOPE, **params})
    assert response.status_code == expect, response.text
    return response.json()


def open_duel(client, subject=None, headers=CHALLENGER, expect=200, scope="s1", **extra):
    subject = subject or {"kind": "fragment", "id": root(client)["id"]}
    return post(client, expect=expect, headers=headers, op="duel-open", subject=subject, scopeNodeId=scope,
                incumbent={"text": "Importuj CSV."}, challenger={"text": "Importuj JSON místo CSV."}, **extra)


_TEXTS = itertools.count(1)


def turn(client, fragment, side, kind, headers, expect=200, text=None, **extra):
    text = f"argument {next(_TEXTS)}" if text is None else text  # různé texty: totožný claim strany je 409
    return post(client, expect=expect, headers=headers, op="duel-turn", fragmentId=fragment["id"],
                expectedRevision=fragment["revision"], side=side, kind=kind, text=text, **extra)


def score(client, fragment, turn_id, headers, strength=10, supports="B", expect=200, **extra):
    return post(client, expect=expect, headers=headers, op="duel-score", fragmentId=fragment["id"],
                expectedRevision=fragment["revision"], turnId=turn_id, strength=strength, supports=supports, **extra)


def decide(client, fragment, headers=DEFENDER, expect=200, **extra):
    return post(client, expect=expect, headers=headers, op="duel-decide", fragmentId=fragment["id"],
                expectedRevision=fragment["revision"], **extra)


def test_open_grill_answer_score_decide_writes_lesson(client):
    subject = root(client)
    opened = open_duel(client, {"kind": "fragment", "id": subject["id"]})
    duel = opened["fragment"]
    assert duel["kind"] == "duel" and duel["title"] == "Duel: Importuj JSON místo CSV." and duel["discipline"] == "be"
    assert opened["duel"]["status"] == "open" and opened["duel"]["challenger"]["by"] == "vyzyvatel"
    head = get(client, "next")
    assert head["needs"] == "duel" and head["gate"] is None and head["fragment"]["id"] == duel["id"]
    assert head["blockedBy"]["duel"] == 1 and head["hint"].startswith("Duel:")
    grill = turn(client, duel, "B", "grill", CHALLENGER, text="Proč CSV, když zdroj dává JSON?")
    assert grill["duel"]["status"] == "grill" and grill["onTurn"] == [{"side": "A", "grillId": grill["turn"]["id"]}]
    duel = grill["fragment"]
    assert "na tahu strana A" in get(client, "next")["hint"]
    decide(client, duel, expect=409)  # otevřená grill a kola nevyčerpaná
    answer = turn(client, duel, "A", "answer", DEFENDER, refs=[grill["turn"]["id"]], text="CSV čte účetní.")
    duel = answer["fragment"]
    turn(client, duel, "A", "answer", DEFENDER, refs=[grill["turn"]["id"]], expect=409)  # jedna answer na grill
    claims = []
    for index in range(3):
        claim = turn(client, duel, "B", "claim", CHALLENGER, text=f"důvod {index}", evidence=EVIDENCE)
        duel, claims = claim["fragment"], [*claims, claim["turn"]["id"]]
    for claim_id in claims:
        duel = score(client, duel, claim_id, JUDGES[0])["fragment"]
    view = get(client, "duel", id=duel["id"])
    assert view["probability"]["n"] == 3 and view["probability"]["p"] > 0.75 and view["canDecide"]
    assert all(item["weight"] == 1.0 for item in view["probability"]["contributions"])  # doklad soudce neověřil
    assert view["rounds"] == {"A": 0, "B": 1} and view["onTurn"] == [] and view["trajectory"]["state"] == "insufficient"
    assert view["duel"]["fragment"]["text"] == "Importuj JSON místo CSV." and len(view["duel"]["turns"]) == 5
    decided = decide(client, duel)
    assert decided["decision"]["outcome"] == "adopt" and decided["decision"]["text"] == "Importuj JSON místo CSV."
    assert decided["duel"]["status"] == "decided" and decided["lesson"]["kind"] == "pattern"
    assert decided["lesson"]["discipline"] == "be" and "obstála" in decided["lesson"]["text"]
    assert [item["id"] for item in get(client, "lessons", discipline="be")["lessons"]] == [decided["lesson"]["id"]]
    duel = decided["fragment"]
    turn(client, duel, "A", "claim", DEFENDER, expect=409)
    score(client, duel, claims[0], JUDGES[1], expect=409)
    decide(client, duel, expect=409)
    after = get(client, "next")
    assert after["needs"] != "duel" and after["fragment"]["id"] == subject["id"] and after["blockedBy"]["duel"] == 0


def test_sides_need_different_actors_and_rules_of_turns(client):
    duel = open_duel(client)["fragment"]
    turn(client, duel, "A", "claim", CHALLENGER, expect=400)  # autor challengeru nehájí A
    duel = turn(client, duel, "A", "claim", DEFENDER)["fragment"]
    turn(client, duel, "B", "claim", DEFENDER, expect=400)
    turn(client, duel, "judge", "claim", JUDGES[0], expect=400)
    turn(client, duel, "human", "note", DEFENDER, expect=400)
    claim = turn(client, duel, "A", "claim", DEFENDER)
    turn(client, claim["fragment"], "B", "answer", CHALLENGER, refs=[claim["turn"]["id"]], expect=400)  # ne grill
    turn(client, claim["fragment"], "B", "claim", CHALLENGER, refs=["neni"], expect=400)
    turn(client, duel, "B", "claim", CHALLENGER, expect=409)  # CAS
    duel = turn(client, claim["fragment"], "judge", "note", JUDGES[0])["fragment"]
    duel = turn(client, duel, "B", "claim", HUMAN)["fragment"]  # člověk se přidá k B
    turn(client, duel, "A", "claim", HUMAN, expect=400)  # ale jen k jedné straně
    duel = turn(client, duel, "human", "note", HUMAN)["fragment"]
    for _ in range(MAX_ROUNDS):
        duel = turn(client, duel, "B", "grill", CHALLENGER)["fragment"]
    turn(client, duel, "B", "grill", CHALLENGER, expect=400)
    turn(client, duel, "B", "claim", CHALLENGER, expect=400)
    synthesis = turn(client, duel, "B", "synthesis", CHALLENGER, text="JSON i CSV.")
    assert synthesis["duel"]["status"] == "synthesis" and synthesis["rounds"]["B"] == MAX_ROUNDS
    open_duel(client, {"kind": "node", "id": "c1"})
    open_duel(client, {"kind": "node", "id": "c1"}, expect=409)  # jeden otevřený duel na předmět
    open_duel(client, {"kind": "node", "id": "neni"}, expect=409)
    open_duel(client, {"kind": "planet", "id": "x"}, expect=400)


def test_claims_per_side_are_capped(client):
    duel = open_duel(client)["fragment"]
    for _ in range(MAX_CLAIMS):
        duel = turn(client, duel, "B", "claim", CHALLENGER)["fragment"]
    turn(client, duel, "B", "claim", CHALLENGER, expect=400)
    turn(client, duel, "B", "claim", HUMAN, expect=400)  # mez platí pro stranu, ne pro aktéra
    assert turn(client, duel, "A", "claim", DEFENDER)["fragment"]["revision"] == duel["revision"] + 1


def test_concede_only_from_opposite_side(client):
    duel = open_duel(client)["fragment"]
    own = turn(client, duel, "A", "claim", DEFENDER)
    other = turn(client, own["fragment"], "B", "claim", CHALLENGER)
    duel = other["fragment"]
    turn(client, duel, "A", "concede", DEFENDER, refs=[own["turn"]["id"]], expect=400)
    turn(client, duel, "A", "concede", DEFENDER, expect=400)
    assert turn(client, duel, "A", "concede", DEFENDER, refs=[other["turn"]["id"]])["turn"]["kind"] == "concede"


def test_judges_and_sides_exclude_each_other(client):
    duel = open_duel(client)["fragment"]
    claim = turn(client, duel, "A", "claim", DEFENDER)
    duel, claim_id = claim["fragment"], claim["turn"]["id"]
    score(client, duel, claim_id, DEFENDER, expect=400)
    score(client, duel, claim_id, CHALLENGER, expect=400)
    score(client, duel, claim_id, JUDGES[0], strength=11, expect=400)
    score(client, duel, claim_id, JUDGES[0], supports="C", expect=400)
    score(client, duel, claim_id, JUDGES[0], evidenceOk="ano", expect=400)
    duel = score(client, duel, claim_id, JUDGES[0], supports="A")["fragment"]
    score(client, duel, claim_id, JUDGES[0], supports="A", expect=409)
    turn(client, duel, "B", "claim", JUDGES[0], expect=400)  # kdo soudil, nehájí stranu
    turn(client, duel, "A", "grill", JUDGES[0], expect=400)
    duel = turn(client, duel, "A", "note", JUDGES[0])["fragment"]  # note smí
    found = score(client, duel, claim_id, JUDGES[1], supports="A", strength=6)
    assert [item["judge"] for item in found["duel"]["scores"]] == ["kritik-0", "kritik-1"]
    assert found["probability"]["contributions"][0]["delta"] < 0


def test_rebutted_by_must_answer_the_scored_turn_from_other_side(client):
    duel = open_duel(client)["fragment"]
    claim = turn(client, duel, "A", "claim", DEFENDER)
    same_side = turn(client, claim["fragment"], "A", "claim", DEFENDER, refs=[claim["turn"]["id"]])
    unrelated = turn(client, same_side["fragment"], "B", "claim", CHALLENGER)
    rebuttal = turn(client, unrelated["fragment"], "B", "grill", CHALLENGER, refs=[claim["turn"]["id"]])
    duel, claim_id = rebuttal["fragment"], claim["turn"]["id"]
    for bad in (claim_id, same_side["turn"]["id"], unrelated["turn"]["id"], "neni"):
        score(client, duel, claim_id, JUDGES[0], supports="A", rebuttedBy=bad, expect=400)
    found = score(client, duel, claim_id, JUDGES[0], supports="A", rebuttedBy=rebuttal["turn"]["id"])
    assert found["score"]["rebuttedBy"] == rebuttal["turn"]["id"]


def test_evidence_source_and_bonus_need_judges(client):
    duel = open_duel(client)["fragment"]
    for source in ("", "../tajne.py:1", "/etc/passwd:1", "C:/x.py:1", "soubor bez radku", "ftp://x"):
        turn(client, duel, "B", "claim", CHALLENGER, evidence=[{"source": source, "quote": "q"}], expect=400)
    turn(client, duel, "B", "claim", CHALLENGER, evidence=[{"source": "https://example.org", "quote": ""}], expect=400)
    claim = turn(client, duel, "B", "claim", CHALLENGER, evidence=[{"source": "https://example.org/a", "quote": "q"}])
    duel, claim_id = claim["fragment"], claim["turn"]["id"]
    duel = score(client, duel, claim_id, JUDGES[0], evidenceOk=True)["fragment"]
    found = score(client, duel, claim_id, JUDGES[1], evidenceOk=False)
    assert found["probability"]["contributions"][0]["weight"] == 1.0  # 1 z 2 není většina
    found = score(client, found["fragment"], claim_id, JUDGES[2], evidenceOk=True)
    assert found["probability"]["contributions"][0]["weight"] == 1.5


def test_keep_and_defended_synthesis(client):
    keep = open_duel(client)["fragment"]
    kept = decide(client, keep)  # bez skóre P = p0 = 0.35 ≤ 0.40
    assert kept["decision"]["outcome"] == "keep" and kept["decision"]["text"] == "Importuj CSV."
    assert kept["lesson"]["kind"] == "antipattern" and "neobstála" in kept["lesson"]["text"]
    duel = open_duel(client, {"kind": "node", "id": "c1"}, discipline="ux")["fragment"]
    claim = turn(client, duel, "B", "claim", CHALLENGER)
    duel = score(client, claim["fragment"], claim["turn"]["id"], JUDGES[0], strength=5)["fragment"]
    decide(client, duel, expect=409)  # syntéza zatím nebyla obhájena
    synthesis = turn(client, duel, "A", "synthesis", DEFENDER, text="JSON pro import, CSV pro export.")
    duel, synthesis_id = synthesis["fragment"], synthesis["turn"]["id"]
    duel = score(client, duel, synthesis_id, JUDGES[1], strength=5)["fragment"]
    decide(client, duel, synthesisTurnId=synthesis_id, expect=409)  # průměr 5 < 6
    duel = score(client, duel, synthesis_id, JUDGES[2], strength=9)["fragment"]
    decide(client, duel, synthesis="volný text", synthesisTurnId=synthesis_id, expect=400)
    decide(client, duel, expect=400)  # bez synthesisTurnId
    decide(client, duel, synthesisTurnId=claim["turn"]["id"], expect=409)
    done = decide(client, duel, synthesisTurnId=synthesis_id)
    assert done["decision"]["outcome"] == "synthesis" and done["decision"]["text"] == "JSON pro import, CSV pro export."
    assert done["decision"]["synthesisTurnId"] == synthesis_id
    assert done["lesson"]["kind"] == "pattern" and done["lesson"]["discipline"] == "ux"


def test_override_only_human_and_lesson_skipped_without_discipline(client):
    duel = open_duel(client, PROJECT)["fragment"]
    assert duel["discipline"] is None
    duel = turn(client, duel, "B", "grill", CHALLENGER)["fragment"]
    override = {"outcome": "adopt", "reason": "Rozhodl člověk po schůzce."}
    decide(client, duel, override=override, expect=403)
    decide(client, duel, headers=HUMAN, override={"outcome": "maybe", "reason": "x"}, expect=400)
    decide(client, duel, headers=HUMAN, override={"outcome": "adopt", "reason": ""}, expect=400)
    done = decide(client, duel, headers=HUMAN, override=override)
    assert done["decision"]["override"] == {"reason": "Rozhodl člověk po schůzce.", "ruleOutcome": None}
    assert done["decision"]["outcome"] == "adopt" and "lesson" not in done and done["lessonSkipped"]
    open_duel(client, {"kind": "project", "id": "jiny"}, expect=400)


def test_tree_carries_duel_and_vision(client):
    duel = open_duel(client)["fragment"]
    post(client, headers=HUMAN, op="vision-set", scopeNodeId="s1", text="Import bez ruční práce.", note="Představa.")
    found = nodes(tree(client))
    assert found[duel["id"]]["kind"] == "duel" and found[duel["id"]]["duel"]["status"] == "open"
    assert found[duel["id"]]["duel"]["p"] == pytest.approx(0.35)
    vision = next(item for item in found.values() if item["kind"] == "vision")
    assert vision["vision"] == {"points": 0, "last": None} and vision["coverage"]["leaves"] == 0


def decided_project_duel(client, scope="s1", **decision):
    duel = open_duel(client, PROJECT, scope=scope)["fragment"]
    return decide(client, duel, **decision)["fragment"]


def test_vision_created_by_human_and_changed_only_by_duel(client):
    post(client, expect=403, op="vision-set", scopeNodeId="s1", text="x", note="n")
    post(client, expect=409, headers=HUMAN, op="vision-set", scopeNodeId="s1", fromDuel="0" * 32, note="n")
    assert get(client, "vision", scopeNodeId="s1")["vision"] is None
    created = post(client, headers=HUMAN, op="vision-set", scopeNodeId="s1", text="Import bez ruční práce.", note="n")
    post(client, expect=409, headers=HUMAN, op="vision-set", scopeNodeId="s1", text="Jiná představa.", note="n")
    kept = decided_project_duel(client)  # keep představu nemění
    post(client, expect=409, op="vision-set", scopeNodeId="s1", fromDuel=kept["id"], note="n")
    post(client, expect=400, op="vision-set", scopeNodeId="s1", fromDuel=kept["id"], text="x", note="n")
    adopted = decided_project_duel(client, headers=HUMAN, override={"outcome": "adopt", "reason": "Schůzka."})
    other_scope = decided_project_duel(client, scope="", headers=HUMAN, override={"outcome": "adopt", "reason": "S."})
    post(client, expect=409, op="vision-set", scopeNodeId="s1", fromDuel=other_scope["id"], note="n")
    revised = get(client, "vision", scopeNodeId="s1")["vision"]  # adopt představu změnil sám (§3.2)
    assert revised["id"] == created["fragment"]["id"] and revised["revision"] == 2
    assert revised["text"] == "Importuj JSON místo CSV."
    post(client, expect=409, op="vision-set", scopeNodeId="s1", fromDuel=adopted["id"], note="znovu")


def test_vision_align_needs_decided_duel_and_one_point_each(client):
    post(client, headers=HUMAN, op="vision-set", scopeNodeId="s1", text="Import bez ruční práce.", note="n")
    open_one = open_duel(client, PROJECT)["fragment"]
    align = {"op": "vision-align", "scopeNodeId": "s1", "note": "shoda"}
    post(client, expect=409, headers=JUDGES[2], score=5, **align)  # duelId je povinné
    post(client, expect=409, headers=JUDGES[2], score=5, duelId=open_one["id"], **align)  # nerozhodnutý
    duel = turn(client, open_one, "A", "claim", DEFENDER)["fragment"]
    decided = decide(client, duel)["fragment"]
    post(client, expect=400, headers=CHALLENGER, score=5, duelId=decided["id"], **align)
    post(client, expect=400, headers=DEFENDER, score=5, duelId=decided["id"], **align)
    post(client, expect=400, headers=JUDGES[2], score=11, duelId=decided["id"], **align)
    first = post(client, headers=JUDGES[2], score=3, duelId=decided["id"], **align)
    post(client, expect=409, headers=JUDGES[1], score=4, duelId=decided["id"], **align)  # jeden bod na duel
    duels = [decided_project_duel(client) for _ in range(2)]
    for value, item in zip((5, 8), duels, strict=True):
        found = post(client, headers=JUDGES[2], score=value, duelId=item["id"], **align)
    assert first["point"]["duelId"] == decided["id"] and found["trajectory"]["n"] == 3
    view = get(client, "vision", scopeNodeId="s1")
    assert view["vision"]["text"] == "Import bez ruční práce." and len(view["vision"]["points"]) == 3
    assert view["trajectory"]["state"] == "approaching" and view["trajectory"]["last"] == 8
    assert get(client, "duel", id=decided["id"])["trajectory"]["n"] == 3
    get(client, "duel", id="neni", expect=409)


def test_next_filters_duel_by_discipline(client):
    open_duel(client)
    assert get(client, "next", discipline="be")["needs"] == "duel"
    other = get(client, "next", discipline="ux")
    assert other["fragment"] is None and other["blockedBy"]["duel"] == 0


def test_project_duel_blocks_its_scope_and_heads_every_discipline(client):
    inside = root(client, "be")
    outside = post(client, op="create", scopeNodeId="c1", discipline="ux", title="Jinde", text="t")["fragment"]
    duel = open_duel(client, PROJECT)["fragment"]
    for discipline in ("be", "ux", None):
        head = get(client, "next", **({"discipline": discipline} if discipline else {}))
        assert head["needs"] == "duel" and head["fragment"]["id"] == duel["id"]
    assert get(client, "next", discipline="be")["blockedBy"]["duel"] == 1
    assert get(client, "next", discipline="ux")["blockedBy"]["duel"] == 0  # jiný rozsah (c1)
    decide(client, duel)
    whole = open_duel(client, PROJECT, scope="")["fragment"]
    assert get(client, "next")["blockedBy"]["duel"] == 2  # prázdný rozsah = celý projekt
    decide(client, whole)
    assert {get(client, "next", discipline=d)["fragment"]["id"] for d in ("be", "ux")} == {inside["id"], outside["id"]}


def test_node_duel_blocks_fragments_referenced_by_card(client):
    linked = root(client, "be")
    free = post(client, op="create", scopeNodeId="s1", discipline="be", title="Volný", text="t")["fragment"]
    current = client.get("/api/desktop-v3/state", params=SCOPE).json()
    card = {"phase": "discover", "criteria": [], "steps": [], "fragmentRefs": [{"fragmentId": linked["id"], "revision": 1}]}
    saved = client.post("/api/desktop-v3/state", headers=HEADERS, json={
        **SCOPE, "expectedRevision": current["revision"], "state": {**current["state"], "nodes": {"c1": card}}})
    assert saved.status_code == 200, saved.text
    duel = open_duel(client, {"kind": "node", "id": "c1"})["fragment"]
    head = get(client, "next")
    assert head["fragment"]["id"] == duel["id"] and head["blockedBy"]["duel"] == 1
    decide(client, duel)
    assert get(client, "next")["fragment"]["id"] in (linked["id"], free["id"])
    assert get(client, "next")["blockedBy"]["duel"] == 0


def test_stored_shape_is_validated():
    with pytest.raises(ValueError):
        validate_details({"duel": {"subject": {"kind": "fragment", "id": "x"}}})
    with pytest.raises(ValueError):
        validate_details({"vision": {"points": [{"score": 12, "note": "n", "by": "a", "actor": "agent", "at": "t"}]}})
    assert validate_details({"vision": {"points": []}}) == {"vision": {"points": []}}


def latest_revision(client, fragment):
    found = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": fragment["id"]})
    assert found.status_code == 200, found.text
    return found.json()["latestRevision"]


def test_identical_claim_of_same_side_is_409_and_writes_nothing(client):
    proof = [*EVIDENCE, {"source": "https://example.org/a", "quote": "JSON"}]
    duel = open_duel(client)["fragment"]
    first = turn(client, duel, "B", "claim", CHALLENGER, text="Zdroj dává JSON.", evidence=proof)
    duel, original = first["fragment"], first["turn"]["id"]
    before = (latest_revision(client, duel), get(client, "duel", id=duel["id"])["duel"])
    for text, evidence in (("Zdroj dává JSON.", proof), ("  Zdroj   dává\nJSON. ", proof[::-1])):
        refused = turn(client, duel, "B", "claim", HUMAN, text=text, evidence=evidence, expect=409)
        assert original in str(refused)
        assert (latest_revision(client, duel), get(client, "duel", id=duel["id"])["duel"]) == before
    duel = turn(client, duel, "B", "claim", CHALLENGER, text="zdroj dává JSON.", evidence=proof)["fragment"]
    duel = turn(client, duel, "A", "claim", DEFENDER, text="Zdroj dává JSON.", evidence=proof)["fragment"]
    duel = turn(client, duel, "B", "grill", CHALLENGER, text="Proč?")["fragment"]
    duel = turn(client, duel, "B", "grill", CHALLENGER, text="Proč?")["fragment"]  # ostatní kinds beze změny
    view = get(client, "duel", id=duel["id"])
    assert latest_revision(client, duel) == before[0] + 4 and len(view["duel"]["turns"]) == 5


def test_identical_claim_at_claim_limit_is_409_not_400(client):
    duel = open_duel(client)["fragment"]
    first = turn(client, duel, "B", "claim", CHALLENGER, text="První důvod.")
    duel = first["fragment"]
    for index in range(MAX_CLAIMS - 1):
        duel = turn(client, duel, "B", "claim", CHALLENGER, text=f"Další důvod {index}.")["fragment"]
    before = latest_revision(client, duel)
    refused = turn(client, duel, "B", "claim", CHALLENGER, text="První důvod.", expect=409)
    assert first["turn"]["id"] in str(refused) and latest_revision(client, duel) == before
    turn(client, duel, "B", "claim", CHALLENGER, text="Čtvrtý jiný důvod.", expect=400)


def test_two_concurrent_identical_claims_write_once(client):
    duel = open_duel(client)["fragment"]
    results = []

    def run():
        results.append(client.post("/api/brief-vault", headers=CHALLENGER, json={
            **SCOPE, "op": "duel-turn", "fragmentId": duel["id"], "expectedRevision": duel["revision"], "side": "B",
            "kind": "claim", "text": "Souběžný důvod.", "evidence": EVIDENCE}).status_code)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [200, 409] and latest_revision(client, duel) == duel["revision"] + 1
    assert len(get(client, "duel", id=duel["id"])["duel"]["turns"]) == 1


def test_identical_claim_after_exhausted_rounds_is_409_not_400(client):
    duel = open_duel(client)["fragment"]
    first = turn(client, duel, "B", "claim", CHALLENGER, text="První důvod.")
    duel = first["fragment"]
    for _ in range(MAX_ROUNDS):
        duel = turn(client, duel, "B", "grill", CHALLENGER)["fragment"]
    before = latest_revision(client, duel)
    refused = turn(client, duel, "B", "claim", CHALLENGER, text="První důvod.", expect=409)
    assert first["turn"]["id"] in str(refused) and latest_revision(client, duel) == before
    turn(client, duel, "B", "claim", CHALLENGER, text="Jiný důvod.", expect=400)  # kola vyčerpaná


def test_claim_limit_counts_unique_claims_in_legacy_history(client):
    duel = open_duel(client)["fragment"]
    duel = turn(client, duel, "B", "claim", CHALLENGER, text="X")["fragment"]
    db = client.app_state.service.db_for(SCOPE["project"])
    row = db.execute("SELECT revision, fields FROM brief_fragment_details WHERE project_id=? AND workspace_id=? AND "
                     "fragment_id=? ORDER BY revision DESC LIMIT 1",
                     (SCOPE["project"], SCOPE["workspace"], duel["id"])).fetchone()
    fields = json.loads(row["fields"] if not isinstance(row, tuple) else row[1])
    original = fields["duel"]["turns"][0]
    fields["duel"]["turns"] += [{**original, "id": f"kopie{index}"} for index in range(MAX_CLAIMS - 1)]
    db.execute("UPDATE brief_fragment_details SET fields=? WHERE project_id=? AND workspace_id=? AND fragment_id=? "
               "AND revision=?", (json.dumps(fields, ensure_ascii=False), SCOPE["project"], SCOPE["workspace"],
                                  duel["id"], row["revision"] if not isinstance(row, tuple) else row[0]))
    db.commit()
    assert len(get(client, "duel", id=duel["id"])["duel"]["turns"]) == MAX_CLAIMS  # legacy X, X, X
    duel = turn(client, duel, "B", "claim", CHALLENGER, text="Y")["fragment"]  # 1 unikátní claim → Y projde
    duel = turn(client, duel, "B", "claim", CHALLENGER, text="Z")["fragment"]
    turn(client, duel, "B", "claim", CHALLENGER, text="W", expect=400)  # X, Y, Z = 3 unikátní
