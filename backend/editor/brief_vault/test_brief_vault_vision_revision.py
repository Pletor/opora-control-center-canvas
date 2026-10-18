"""Rozhodnutí a trend musí patřit ke stejné obsahové verzi představy (docs/schranka-duel.md §3.3).

Scénáře převzaty z opravy nezávislého revieweru (Codex) a převedeny na tok, kde adopt představu změní sám
(`duel-decide`, §3.2); ruční `vision-set fromDuel` už použité nebo zastaralé rozhodnutí odmítne (409)."""
from backend.editor.brief_vault.test_brief_vault_duel import (  # noqa: F401 (fixture client)
    CHALLENGER, HUMAN, JUDGES, PROJECT, client, decide, get, post,
)


def vision(client):
    return get(client, "vision", scopeNodeId="s1")


def change(client, old, new):
    opened = post(client, headers=CHALLENGER, op="duel-open", subject=PROJECT, scopeNodeId="s1",
                  incumbent={"text": old}, challenger={"text": new})
    decided = decide(client, opened["fragment"], headers=HUMAN,
                     override={"outcome": "adopt", "reason": "Test změny cíle."})
    return decided["fragment"]["id"], decided


def replay(client, duel, expect=409):
    return post(client, op="vision-set", scopeNodeId="s1", fromDuel=duel, note="Změna", expect=expect)


def start(client):
    post(client, headers=HUMAN, op="vision-set", scopeNodeId="s1", text="V0", note="Založení")


def test_old_decision_cannot_restore_previous_vision(client):
    start(client)
    first, done = change(client, "V0", "V1")
    assert done["applied"] is True and vision(client)["vision"]["text"] == "V1"
    second, _ = change(client, "V1", "V2")
    before = vision(client)
    assert before["vision"]["text"] == "V2"
    replay(client, first)
    replay(client, second)  # už uplatněné rozhodnutí podruhé nic nezmění
    assert vision(client) == before


def test_unused_decision_against_old_vision_is_also_rejected(client):
    start(client)
    stale = post(client, headers=CHALLENGER, op="duel-open", subject=PROJECT, scopeNodeId="s1",
                 incumbent={"text": "V0"}, challenger={"text": "Stará alternativa"})["fragment"]
    decided = decide(client, stale)  # keep: P = p0, představa se nemění
    assert decided["applied"] is False and vision(client)["vision"]["text"] == "V0"
    change(client, "V0", "V1")
    before = vision(client)
    replay(client, decided["fragment"]["id"])
    assert vision(client) == before


def test_alignment_does_not_invalidate_open_duel_but_new_goal_resets_trend(client):
    start(client)
    kept = decide(client, post(client, headers=CHALLENGER, op="duel-open", subject=PROJECT, scopeNodeId="s1",
                               incumbent={"text": "V0"}, challenger={"text": "Nic"})["fragment"])["fragment"]["id"]
    opened = post(client, headers=CHALLENGER, op="duel-open", subject=PROJECT, scopeNodeId="s1",
                  incumbent={"text": "V0"}, challenger={"text": "V1"})["fragment"]
    aligned = post(client, headers=JUDGES[2], op="vision-align", scopeNodeId="s1", duelId=kept,
                   score=8, note="Shoda se starým cílem")
    assert aligned["trajectory"]["n"] == 1
    done = decide(client, opened, headers=HUMAN, override={"outcome": "adopt", "reason": "Test změny cíle."})
    assert done["applied"] is True  # bod trajektorie mezitím duel nezneplatnil
    assert vision(client)["trajectory"]["n"] == 0
    assert get(client, "duel", id=kept)["trajectory"]["n"] == 0
    next_duel, _ = change(client, "V1", "V2")
    aligned = post(client, headers=JUDGES[2], op="vision-align", scopeNodeId="s1", duelId=next_duel,
                   score=3, note="Shoda s novým cílem")
    assert aligned["trajectory"]["n"] == 1
    assert aligned["trajectory"]["last"] == 3


def test_duel_opened_before_vision_cannot_change_it(client):
    old, done = change(client, "Bez představy", "V1")
    assert done["applied"] is False
    start(client)
    before = vision(client)
    replay(client, old)
    assert vision(client) == before


def test_return_to_same_text_does_not_revalidate_old_decision(client):
    start(client)
    old, _ = change(client, "V0", "V1")
    change(client, "V1", "V0")
    before = vision(client)
    assert before["vision"]["text"] == "V0"
    replay(client, old)
    assert vision(client) == before
