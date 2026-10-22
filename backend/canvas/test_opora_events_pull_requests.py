"""Events of the PR chain: link, merge write-back and card stage are emitted exactly once per change."""
from backend.canvas.opora_execution_pull_requests import ExecutionPullRequestLinks
from backend.canvas.test_opora_execution_pull_requests import Reader, body, claim, close, observe
from backend.canvas.test_opora_execution_pull_requests import (
    world_fixture as world_fixture,  # noqa: PLC0414
)
from database.repositories import opora_events as store


def found(service, scope, since=0):
    return store.page(service.db_for(scope["project"]), scope["project"], None, since, 1000)[0]


def last(service, scope):
    items = found(service, scope)
    return items[-1]["id"] if items else 0


def test_link_and_merge_emit_once_and_move_the_card_stage(world):
    service, scope, executions = world
    record = claim(executions, scope)
    links = ExecutionPullRequestLinks(service, Reader())
    mark = last(service, scope)
    linked = links.link(record["executionId"], body(record), "agent")
    links.link(record["executionId"], body(record), "agent")  # Exact replay: no new event.
    after_link = found(service, scope, mark)
    assert [item["kind"] for item in after_link] == ["pr.linked", "stage.changed"]
    assert after_link[0]["prNumber"] == 7 and after_link[0]["nodeId"] == "card"
    assert after_link[1]["stage"] in {"pull_request", "review"}
    mark = last(service, scope)
    observe(service, scope, linked["bindingId"], "merged")
    close(service, links, scope)
    close(service, links, scope)  # Second pass: nothing changed, nothing emitted.
    merged = found(service, scope, mark)
    assert [item["kind"] for item in merged] == ["merge.done", "stage.changed", "writeback.done", "decision.created"]
    stage = merged[1]
    assert (stage["stage"], stage["health"], stage["data"]["reason"]) == ("merge", "waiting", "awaiting_human_close")
    assert merged[3]["data"]["decision"] == "close_card"
