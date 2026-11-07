"""Žádost srdci: přijata ihned, kroky jen s ověřeným důkazem, větvení na dva tickety, selhání viditelné."""
from backend.agi_pletor.linie import attempt, journal, requests, rows, work
from backend.agi_pletor.linie.test_branches import run
from backend.agi_pletor.linie.test_work import BODY, NOW, refused, setup  # noqa: F401 (fixture)


def ticket_for(service, repo, request_id, branch):
    row = rows.add(service.root, "draft", branch, "work")
    return work.create(service, "draft", "main", BODY, {"rowId": row["id"], "title": branch, "branch": branch,
                                                        "baseBranch": "develop", "requestId": request_id},
                       NOW, root=repo)["ticketId"]


def test_request_is_accepted_at_once_and_idempotent(setup):
    service, _repo, _tid = setup
    made = requests.create(service, "draft", "  Přidej datový uzel ", "k1", "human", NOW)
    assert made["id"].startswith("rq_") and made["text"] == "Přidej datový uzel"
    assert made["steps"] == [{"k": "accepted", "at": NOW, "by": "human"}]
    assert requests.create(service, "draft", "Přidej datový uzel", "k1", "human", NOW)["id"] == made["id"]
    assert refused(lambda: requests.create(service, "draft", "Jiný text", "k1", "human", NOW)).code == \
        "idempotency_conflict"
    assert len(requests.listing(service, "draft")) == 1
    kinds = [e["kind"] for e in journal.read(service, "draft")["events"]]
    assert kinds.count("linie.request.accepted") == 1


def test_steps_need_evidence_and_request_branches(setup):
    service, repo, tid = setup
    rid = requests.create(service, "draft", "Dva kusy práce", "k2", "human", NOW)["id"]
    assert refused(lambda: requests.confirm(service, "draft", rid, "ticket", "agent:srdce", NOW)).code == \
        "evidence_required"
    assert refused(lambda: requests.confirm(service, "draft", rid, "ticket", "agent:srdce", NOW,
                                            {"ticket": tid})).code == "evidence_invalid"  # ticket bez žádosti
    first, second = ticket_for(service, repo, rid, "feat/jedna"), ticket_for(service, repo, rid, "feat/dva")
    for ticket_id in (first, second, first):  # opakování téhož důkazu krok nezdvojí
        found = requests.confirm(service, "draft", rid, "ticket", "agent:srdce", NOW, {"ticket": ticket_id})
    assert [s["evidence"]["ticket"] for s in found["steps"] if s["k"] == "ticket"] == [first, second]
    failed = requests.confirm(service, "draft", rid, "plan", "agent:srdce", NOW, failed=True, why="karta chybí")
    assert failed["steps"][-1] == {"k": "plan", "failed": True, "why": "karta chybí", "at": NOW, "by": "agent:srdce"}
    assert refused(lambda: requests.confirm(service, "draft", rid, "plan", "agent:srdce", NOW,
                                            {"cardId": "nic"})).code == "evidence_invalid"


def test_attempt_and_commit_steps_follow_the_work(setup):
    service, repo, _tid = setup
    rid = requests.create(service, "draft", "Uzel", "k3", "human", NOW)["id"]
    tid = ticket_for(service, repo, rid, "feat/zadost")
    shown = attempt.attempt(service, "draft", tid, {"branch": "feat/zadost", "requestId": rid}, "agent:dev", NOW)
    made = shown["work"]["attempts"][0]
    assert made["requestId"] == rid
    requests.follow(service, "draft", shown, "attempt", "agent:dev", NOW, attemptId=made["attemptId"])
    mark = shown["work"]["mark"]
    run(repo, "checkout", "-q", "-b", "feat/zadost", "develop")
    (repo / "z.txt").write_text("z", encoding="utf-8")
    run(repo, "add", "z.txt")
    run(repo, "commit", "-q", "-m", "bez značky")
    plain = run(repo, "rev-parse", "HEAD")
    run(repo, "commit", "-q", "--allow-empty", "-m", f"uzel\n\nOpora-Mark: {mark}")
    marked = run(repo, "rev-parse", "HEAD")
    run(repo, "checkout", "-q", "main")
    assert refused(lambda: requests.confirm(service, "draft", rid, "commit", "agent:dev", NOW,
                                            {"ticket": tid, "sha": plain})).code == "evidence_invalid"
    assert requests.is_open(requests.get(service, "draft", rid))
    reported = work.report(service, "draft", tid, marked, [], None, NOW, "agent:dev")
    done = requests.follow(service, "draft", reported, "commit", "agent:dev", NOW, sha=marked)
    assert [s["k"] for s in done["steps"]] == ["accepted", "attempt", "commit"]
    assert done["steps"][-1]["evidence"] == {"ticket": tid, "sha": marked}
    assert requests.listing(service, "draft", open_only=True) == []
