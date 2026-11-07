"""Uzavření řádku po začlenění (§10.2): šest případů bez gitu; git otázka je mapa „větev je v cíli“."""
from backend.agi_pletor.linie.closed import closed_rows


def row(branch, rid=None, **extra):
    return {"id": rid or branch, "name": branch, "branch": branch, "planned": False, **extra}


def ball(tid, rid, state="merged", at="2026-11-07T11:00:00Z", sha=None, mode="merge"):
    return {"ticketId": tid, "rowId": rid, "state": state,
            "axes": {"integration": {"state": state if state == "merged" else "none", "at": at,
                                     "sha": sha or tid.lower() * 7, "mode": mode}}}


ROWS = [row("main", fixed=True), row("develop", fixed=True), row("feat/a"), row("feat/a-b"), row("feat/a-b-c"),
        {"id": "plan", "name": "plán", "branch": None, "planned": True}]


def in_target(*branches):
    return lambda branch, sha, target: branch in branches


def test_two_merged_balls_close_row_with_last_merge():
    balls = [ball("X", "feat/a-b-c", at="2026-11-07T10:00:00Z"), ball("Y", "feat/a-b-c", at="2026-11-07T12:00:00Z")]
    found = closed_rows(ROWS, balls, [], in_target("feat/a-b-c"))
    assert found["feat/a-b-c"] == {"at": "2026-11-07T12:00:00Z", "sha": "yyyyyyy", "target": "feat/a-b", "by": "merge",
                                   "balls": 2}
    assert found["main"] is found["develop"] is found["plan"] is None
    assert found["feat/a-b"] is None  # bez vlastní kuličky se neuzavře


def test_wip_ball_or_live_worktree_keeps_row_open():
    balls = [ball("X", "feat/a-b-c"), ball("W", "feat/a-b-c", state="wip")]
    assert closed_rows(ROWS, balls, [], in_target("feat/a-b-c"))["feat/a-b-c"] is None
    live = [{"branch": "feat/a-b-c", "binding": {"ticketId": "X", "live": True}}]
    assert closed_rows(ROWS, balls[:1], live, in_target("feat/a-b-c"))["feat/a-b-c"] is None


def test_open_child_keeps_parent_open():
    balls = [ball("P", "feat/a-b"), ball("C", "feat/a-b-c", state="pending")]
    assert closed_rows(ROWS, balls, [], in_target("feat/a-b", "feat/a-b-c"))["feat/a-b"] is None


def test_commit_after_merge_reopens():
    balls = [ball("X", "feat/a-b-c")]
    assert closed_rows(ROWS, balls, [], in_target())["feat/a-b-c"] is None  # špička už není předkem cíle


def test_squash_closes_without_ancestor():
    balls = [ball("X", "feat/a-b-c", mode="squash")]
    assert closed_rows(ROWS, balls, [], in_target())["feat/a-b-c"]["target"] == "feat/a-b"


def test_cascade_three_levels_bottom_up():
    balls = [ball("A", "feat/a"), ball("B", "feat/a-b"), ball("C", "feat/a-b-c")]
    every = in_target("feat/a", "feat/a-b", "feat/a-b-c")
    found = closed_rows(ROWS, balls, [], every)
    assert [found[b]["target"] for b in ("feat/a", "feat/a-b", "feat/a-b-c")] == ["develop", "feat/a", "feat/a-b"]
    balls.append(ball("N", "feat/a-b-c", state="todo"))  # nová kulička na nejnižší větvi otevře celou kaskádu
    assert all(closed_rows(ROWS, balls, [], every)[b] is None for b in ("feat/a", "feat/a-b", "feat/a-b-c"))


def test_blocked_ball_does_not_keep_row_open():
    balls = [ball("X", "feat/a-b-c"), ball("B", "feat/a-b-c", state="blocked")]
    found = closed_rows(ROWS, balls, [], in_target("feat/a-b-c"))
    assert found["feat/a-b-c"]["balls"] == 1
    assert closed_rows(ROWS, balls[1:], [], in_target("feat/a-b-c"))["feat/a-b-c"] is None  # jen blokovaná = nic
