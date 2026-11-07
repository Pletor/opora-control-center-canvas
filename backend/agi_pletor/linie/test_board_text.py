"""Textový přehled Linie (L8b): týž snímek jako obrazovka, pořadí a věta fronty beze změny, jedna kulička = jeden řádek."""
from backend.agi_pletor.linie import board_text, human_queue
from backend.agi_pletor.linie.test_human_queue import ball


def snapshot(*balls, rows=None, worktrees=()):
    rows = rows or [{"id": "r", "name": "Vlak", "branch": "feat/x", "target": "develop", "depth": 1},
                    {"id": "e", "name": "Prázdný", "branch": "feat/e", "target": "develop", "depth": 2}]
    human = human_queue.order(list(balls), rows)
    return {"rows": rows, "balls": list(balls), "worktrees": list(worktrees), "queues": {
        "humanDecisions": len(human), "human": human, "plansWaiting": None, "ticketsTodo": 0, "officeTasks": 1, "gitQueue": 1},
        "snapshot": {"builtAt": "2026-11-07T10:02:00Z", "sources": {
            "git": {"verifiedAt": "2026-11-07T10:02:00Z", "ok": True}, "prs": {"verifiedAt": None, "ok": False},
            "deploy": {"verifiedAt": "2026-11-07T10:00:00Z", "ok": True}}}}


def two_cars():
    child = ball("B", "feat/x-y", "feat/x", row="r", created="2026-11-07T10:00:00Z", headSha7="bbbbbbb")
    top = ball("A", "feat/x", "develop", row="r", headSha7="aaaaaaa")
    return child, top


def test_human_queue_lines_match_service_order_and_sentence():
    text = board_text.render(snapshot(*two_cars()))
    queue = text.split("Čeká na člověka:\n")[1].split("\n\n")[0].splitlines()
    assert queue[0] == "  1. OP-B B · feat/x-y → feat/x · pending · aaaaaaa · začlení feat/x-y do feat/x, pak bude na řadě OP-A (feat/x)"
    assert queue[1].startswith("  2. OP-A A · feat/x → develop") and queue[1].endswith("pak už nic nečeká")
    assert "  Člověk: 2 rozhodnutí" in text and "  Srdce: — (nedostupné)" in text and "  Git: 1 PR" in text
    assert "PR nedostupné (poslední čtení nevím)" in text and "deploy" not in text and "nasazení před 120 s" not in text


def test_rows_balls_one_line_each_and_row_without_balls():
    child, top = two_cars()
    stray = ball("S", "feat/s", "develop", row="nikde")
    text = board_text.render(snapshot(child, top, stray))
    rows = text.split("Řádky:\n")[1]
    assert "  Vlak [feat/x] → develop\n    OP-B B · pending · aaaaaaa · další: dál" in rows or "    OP-B B · pending" in rows
    assert "    Prázdný [feat/e] → develop\n" in rows and rows.count("OP-") >= 2
    assert text.endswith("Bez řádku:\n  OP-S S · pending · - · další: dál\n")


def test_empty_queue_and_journal():
    text = board_text.render(snapshot(), journal=[
        {"id": i, "kind": "linie.report", "at": f"t{i}", "by": "agent:dev", "refs": {"sha": "a" * 40}, "data": {}} for i in range(25)])
    assert "Nic nečeká na člověka." in text and "Pletor: Na plátně 0 kuliček; nic nečeká na člověka." in text
    tail = text.split("Deník (posledních 20):\n")[1].splitlines()
    assert len(tail) == 20 and tail[0] == "  t5 dev report aaaaaaa" and tail[-1] == "  t24 dev report aaaaaaa"


def test_mine_keeps_only_agents_balls_by_worktree_binding():
    child, top = two_cars()
    bound = [{"binding": {"ticketId": "B", "agent": "dev"}}, {"binding": {"ticketId": "A", "agent": "jiny"}}, {"binding": None}]
    text = board_text.render(snapshot(child, top, worktrees=bound), mine="dev")
    rows = text.split("Řádky (jen dev):\n")[1]
    assert "OP-B B" in rows and "OP-A A" not in rows and "Prázdný" not in rows
    assert "OP-A A" in text.split("Řádky")[0]  # fronta člověka zůstává celá


def test_closed_row_is_one_line_without_balls_unless_all():
    from backend.agi_pletor.linie.board_text import _clock
    child, top = two_cars()
    shut = {"at": "2026-11-07T14:15:43Z", "sha": "0" * 40, "target": "develop", "by": "merge", "balls": 2}
    found = snapshot(child, top)
    found["rows"][0]["closed"] = shut
    rows = board_text.render(found).split("Řádky:\n")[1]
    assert f"  ⊕ Vlak · uzavřeno {_clock(shut['at'])} → develop (2 kuličky)\n    Prázdný" in rows and "OP-A" not in rows
    rows = board_text.render(found, all=True).split("Řádky:\n")[1]
    assert "⊕" not in rows and "  Vlak [feat/x] → develop\n" in rows and "OP-A A" in rows


def test_closed_row_hides_its_subtree_by_parent_unless_all():
    shut = {"at": "2026-11-07T14:15:43Z", "sha": "0" * 40, "target": "develop", "by": "merge", "balls": 1}
    rows = [{"id": "r", "name": "Vlak", "branch": "feat/x", "parent": "develop", "depth": 1, "closed": shut},
            {"id": "c", "name": "Dítě", "branch": "feat/x-y", "parent": "feat/x", "depth": 2, "closed": {**shut, "target": "feat/x"}},
            {"id": "g", "name": "Vnuk", "branch": "feat/x-y-z", "parent": "feat/x-y", "depth": 3, "closed": None},
            {"id": "e", "name": "Soused", "branch": "feat/e", "parent": "develop", "depth": 2}]
    found = snapshot(ball("B", "feat/x-y", "feat/x", row="c"), rows=rows)
    text = board_text.render(found).split("Řádky:\n")[1]
    assert "⊕ Vlak" in text and "Dítě" not in text and "Vnuk" not in text and "OP-B" not in text and "    Soused [feat/e]" in text
    text = board_text.render(found, all=True).split("Řádky:\n")[1]
    assert "    Dítě [feat/x-y]" in text and "      Vnuk" in text and "OP-B" in text and "⊕" not in text


def test_closed_row_without_at_and_sha_prints_question_mark():
    found = snapshot(*two_cars())
    found["rows"][0]["closed"] = {"at": None, "sha": None, "target": "develop", "by": "merge", "balls": 2}
    assert "  ⊕ Vlak · uzavřeno ? → develop (2 kuličky)\n" in board_text.render(found)
