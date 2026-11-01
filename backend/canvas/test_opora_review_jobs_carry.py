"""PIPE-006: a rebase that leaves the change content unchanged carries the completed review over."""
import pytest

from backend.canvas.opora_review_gate import read_review_gates
from backend.canvas.test_opora_execution_pull_requests import NEXT_SHA, SHA
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_jobs import CONFIG, THIRD_SHA, ChangeReader, push, run_finders
from backend.canvas.test_opora_review_jobs import review_fixture as review  # noqa: F401

SAME, OTHER = "1" * 64, "2" * 64


class PrintReader(ChangeReader):
    """Change reader with a content fingerprint per head and a compare read for older heads."""

    def __init__(self, prints, older=None):
        super().__init__()
        self.prints, self.older, self.compares = prints, older or {}, []

    def change(self, repository, number, head):
        return {**super().change(repository, number, head), "fingerprint": self.prints.get(head)}

    def fingerprint(self, repository, base, head):
        self.compares.append((base, head))
        return self.older.get(head)


def use(review, reader, max_rounds=3):  # noqa: F811
    config = {**CONFIG, "maxRounds": max_rounds}
    review["jobs"]._reader, review["jobs"].config = reader, lambda: config
    return config


def code_jobs(review):  # noqa: F811
    return {job["headSha"]: job for job in review["jobs"].list(**review["scope"])["jobs"] if job["kind"] == "code"}


def gate(review, config):  # noqa: F811
    [item] = read_review_gates(review["service"], **review["scope"], config=config)
    return item


def complete_round(review, head, request):  # noqa: F811
    if head != SHA:
        push(review, head, request)
    review["jobs"].sync(**review["scope"])
    run_finders(review, *[{"findings": []}] * 3)


def test_clean_rebase_carries_the_review_without_a_new_round(review):  # noqa: F811
    use(review, PrintReader({SHA: SAME, NEXT_SHA: SAME, THIRD_SHA: OTHER}))
    complete_round(review, SHA, None)
    source = code_jobs(review)[SHA]
    assert source["risk"]["patchFingerprint"] == SAME and "carriedFrom" not in source["risk"]
    push(review, NEXT_SHA, "rebase")
    [carried_id] = review["jobs"].sync(**review["scope"])
    carried = code_jobs(review)[NEXT_SHA]
    assert carried["reviewJobId"] == carried_id and carried["phase"] == "completed" and carried["tasks"] == []
    assert (carried["round"], carried["riskTier"], carried["requiredHumanApprovals"]) == (
        1, source["riskTier"], source["requiredHumanApprovals"])
    assert carried["risk"]["carriedFrom"] == source["reviewJobId"] and carried["risk"]["patchFingerprint"] == SAME
    assert review["jobs"].sync(**review["scope"]) == []
    push(review, THIRD_SHA, "fix")  # Different content: a real next round, diffed from the rebased head.
    review["jobs"].sync(**review["scope"])
    third = code_jobs(review)[THIRD_SHA]
    assert (third["round"], third["sinceSha"], third["phase"]) == (2, NEXT_SHA, "find")


def test_carry_works_past_the_cap_and_computes_an_old_fingerprint_once(review):  # noqa: F811
    # Live case: the reviewed job predates stored fingerprints; the compare read fills it in once.
    reader = PrintReader({NEXT_SHA: SAME, THIRD_SHA: SAME}, older={SHA: SAME})
    config = use(review, reader, max_rounds=1)
    reader.prints = {}
    complete_round(review, SHA, None)
    assert "patchFingerprint" not in code_jobs(review)[SHA]["risk"]
    reader.prints = {NEXT_SHA: SAME, THIRD_SHA: SAME}
    push(review, NEXT_SHA, "rebase")
    review["jobs"].sync(**review["scope"])
    assert reader.compares == [("b" * 40, SHA)]
    assert code_jobs(review)[SHA]["risk"]["patchFingerprint"] == SAME
    item = gate(review, config)
    assert item["reviewJobId"] == code_jobs(review)[NEXT_SHA]["reviewJobId"] and item["round"] == 1
    assert "review_round_cap_reached" not in item["reviewGate"]["reasons"]
    assert "review_not_enqueued" not in item["reviewGate"]["reasons"]
    push(review, THIRD_SHA, "rebase-2")  # Another clean rebase: still carried from the reviewed round.
    review["jobs"].sync(**review["scope"])
    assert code_jobs(review)[THIRD_SHA]["risk"]["carriedFrom"] == code_jobs(review)[SHA]["reviewJobId"]
    assert len(reader.compares) == 1


@pytest.mark.parametrize("fingerprint", [OTHER, None])
def test_changed_or_unknown_content_keeps_the_round_and_the_cap(review, fingerprint):  # noqa: F811
    third = "3" * 64 if fingerprint else None
    config = use(review, PrintReader({SHA: SAME, NEXT_SHA: fingerprint, THIRD_SHA: third}))
    complete_round(review, SHA, None)
    push(review, NEXT_SHA, "push")
    review["jobs"].sync(**review["scope"])
    assert (code_jobs(review)[NEXT_SHA]["round"], code_jobs(review)[NEXT_SHA]["phase"]) == (2, "find")
    run_finders(review, *[{"findings": []}] * 3)
    config = use(review, review["jobs"]._reader, max_rounds=2)
    push(review, THIRD_SHA, "push-2")
    assert review["jobs"].sync(**review["scope"]) == []
    assert gate(review, config)["reviewGate"]["reasons"][0] == "review_round_cap_reached"
