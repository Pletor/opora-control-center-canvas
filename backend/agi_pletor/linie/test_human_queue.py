"""„Čeká na tebe“ (L7g, kontrakt §6 a §7 bod 7): pořadí fronty člověka a jedna akce přijmout a začlenit."""
from backend.agi_pletor.linie import board, human_queue, merge_log, rows, work
from backend.agi_pletor.linie.test_board import NO_PR
from backend.agi_pletor.linie.test_branches import commit, run
from backend.agi_pletor.linie.test_merge import GREEN
from backend.agi_pletor.linie.test_work import (  # noqa: F401 (fixture)
    BODY,
    NOW,
    agent_commit,
    refused,
    setup,
)

OP = "1b4e28ba-2fa1-11d2-883f-0016d3cca427"


def ball(tid, branch, target, key="pending", row="r", created="2026-11-07T10:00:00Z", **extra):
    return {"ticketId": tid, "mark": "OP-" + tid, "title": tid, "branch": branch, "rowId": row, "createdAt": created,
            "queues": ["humanDecisions"], "allowed": ["accept", "block"], "mergeAllowed": None, "acceptance": None,
            "summary": {"key": key, "text": key, "next": "dál"}, "preview": None,
            "axes": {"work": {"sha": "a" * 40}, "checks": {"state": "passed", "sha": "a" * 40},
                     "integration": {"state": "none", "target": target}}, **extra}


def test_order_blocker_first_then_deepest_then_oldest():
    found = human_queue.order([
        ball("A", "feat/x", "develop", row="ra"),
        ball("C", "feat/x-y-z", "feat/x-y", row="rc"),
        ball("B", "feat/x-y", "feat/x", row="rb"),
        ball("D", "feat/q", "develop", row="rd", created="2026-11-07T09:00:00Z"),  # starší, mělký, nikoho neblokuje
        ball("E", "feat/w-v", "feat/w", row="re", queues=[], summary={"key": "todo", "text": "", "next": ""}),
    ], [{"id": "ra", "depth": 2}, {"id": "rb", "depth": 3}, {"id": "rc", "depth": 4}, {"id": "rd", "depth": 2},
        {"id": "re", "depth": 3}])
    assert [row["ticketId"] for row in found] == ["C", "B", "D", "A"]  # vlak zdola nahoru, E není ve frontě
    assert [row["order"] for row in found] == [1, 2, 3, 4]
    assert found[0]["sentence"] == "začlení feat/x-y-z do feat/x-y, pak bude na řadě OP-B (feat/x-y)"
    assert found[-1]["sentence"].endswith("pak už nic nečeká")
    assert found[0]["action"] == {"kind": "accept_merge", "label": "Přijmout a začlenit"}


def test_row_says_why_with_one_action():
    moved = ball("M", "feat/m", "develop", key="accepted", allowed=["allow_merge", "block"],
                 mergeAllowed={"target": "develop", "targetSha": "b" * 40, "sourceSha": "a" * 40})
    blocked = ball("X", "feat/b", "develop", key="blocked", queues=[], allowed=["unblock", "block"])
    waits = ball("W", "feat/c", "develop", key="nocheck", queues=["officeTasks"], allowed=["revoke_accept", "block"],
                 acceptance={"sha": "c" * 40})
    office = ball("O", "feat/d", "develop", key="nocheck", queues=["officeTasks"], allowed=["block"])
    found = {row["ticketId"]: row for row in human_queue.order([moved, blocked, waits, office], [])}
    assert found["M"]["action"] == {"kind": "accept_merge", "label": "Povolit znovu a začlenit"}
    assert "X" not in found  # blokovaná kulička nečeká na rozhodnutí, odblokuje se v detailu
    assert found["W"]["action"] is None and found["W"]["next"] == "dál"  # přijal dřív, teď čeká: proč, bez tlačítka
    assert "O" not in found  # nic od člověka nečeká


def test_accept_merge_one_step_and_same_op_merges_once(setup):
    service, repo, tid = setup
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    done = human_queue.accept_merge(service, "draft", tid, head[:7], OP, "", NOW, True)
    tip = run(repo, "rev-parse", "origin/develop")
    assert done["summary"]["key"] == "merged" and done["work"]["merged"]["sha"] == tip
    assert done["work"]["acceptance"]["sha"] == head and done["work"]["mergeAllowed"]["sourceSha"] == head
    again = human_queue.accept_merge(service, "draft", tid, head, OP, "", NOW, True)
    assert again["work"]["merged"] == done["work"]["merged"] and run(repo, "rev-parse", "origin/develop") == tip
    assert len(merge_log.read(service.root, "draft")) == 1


def test_accept_merge_stops_on_first_409_with_sentence(setup):
    service, repo, tid = setup
    old = agent_commit(repo)
    work.report(service, "draft", tid, old, GREEN, None, NOW, "agent:t")
    agent_commit(repo, name="v.txt")  # cizí revize: člověk viděl old, na větvi už je nová
    error = refused(lambda: human_queue.accept_merge(service, "draft", tid, old, OP, "", NOW, True))
    assert error.status == 409 and error.code == "head_moved"
    assert str(error).startswith("Přijetí se zastavilo: na větvi je jiná revize") and "špičku" in error.hint
    shown = work.get(service, "draft", tid)["work"]
    assert shown["acceptance"] is None and shown["mergeAllowed"] is None and not merge_log.read(service.root, "draft")


def test_accept_merge_reallows_moved_target(setup):
    service, repo, tid = setup
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    work.accept(service, "draft", tid, head, "", NOW, untested=True)
    work.allow_merge(service, "draft", tid, "develop", NOW)
    run(repo, "checkout", "-q", "develop")
    commit(repo, "jiny.txt")  # zaseklé povolení z posunutého cíle (§6 důvod L7g)
    run(repo, "push", "-q", "origin", "develop")
    run(repo, "checkout", "-q", "main")
    shown = board.board(service, "draft", "main", repo, pr_lookup=NO_PR)["queues"]["human"]
    assert shown[0]["action"]["label"] == "Povolit znovu a začlenit"
    assert human_queue.accept_merge(service, "draft", tid, head, None, "", NOW, True)["summary"]["key"] == "merged"


def test_train_of_three_bottom_up(setup):
    service, repo, tid = setup  # feat/uzel z develop
    tids, heads = [], {}
    for branch, base in (("feat/uzel", "develop"), ("feat/uzel-b", "feat/uzel"), ("feat/uzel-b-c", "feat/uzel-b")):
        if branch != "feat/uzel":  # báze dítěte = špička rodiče, takže ticket až po commitu rodiče
            row = rows.add(service.root, "draft", branch, "work")
            tid = work.create(service, "draft", "main", BODY, {"rowId": row["id"], "title": branch, "branch": branch,
                                                               "baseBranch": base, "target": base}, NOW,
                              root=repo)["ticketId"]
        tids.append(tid)
        heads[tid] = agent_commit(repo, branch=branch, base=base, name=branch.replace("/", "_") + ".txt")
        work.report(service, "draft", tid, heads[tid], GREEN, None, NOW, "agent:t")
    queue = board.board(service, "draft", "main", repo, pr_lookup=NO_PR)["queues"]["human"]
    assert [row["ticketId"] for row in queue] == list(reversed(tids))  # nejhlubší dítě první
    assert queue[0]["sentence"].startswith("začlení feat/uzel-b-c do feat/uzel-b, pak bude na řadě")
    for t, branch in zip(reversed(tids), ("feat/uzel-b-c", "feat/uzel-b", "feat/uzel")):
        tip = run(repo, "rev-parse", branch)  # rodič má po začlenění dítěte novou špičku; agent ji nahlásí
        if tip != heads[t]:
            work.report(service, "draft", t, tip, GREEN, None, NOW, "agent:t")
        assert human_queue.accept_merge(service, "draft", t, tip, None, "", NOW, True)["summary"]["key"] == "merged"
    assert board.board(service, "draft", "main", repo, pr_lookup=NO_PR)["queues"]["human"] == []


def test_blocked_is_not_in_human_queue_key_and_count_equals_list():
    from backend.agi_pletor.linie import plan_view
    blocked = {"summary": {"key": "blocked"}, "pr": None}
    assert "humanDecisions" not in plan_view.ball_queues(blocked)
