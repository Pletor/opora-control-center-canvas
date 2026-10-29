"""Dávka srdce s falešným procesem: zpráva, řádka, deník `batches.jsonl`, rotace, limit a vypršení času."""
import json

from backend.brain_opora.heart import batch, session
from backend.brain_opora.heart.process import Outcome

RESULT = {"type": "result", "subtype": "success", "is_error": False, "session_id": "11111111-1111-1111-1111-111111111111",
          "total_cost_usd": 0.0421, "num_turns": 7, "result": "Hotovo.",
          "usage": {"input_tokens": 900, "cache_read_input_tokens": 20_000},
          "modelUsage": {"claude-haiku-4-5": {"costUSD": 0.0121}, "claude-opus-4-5": {"costUSD": 0.03}}}


class FakeRunner:
    def __init__(self, outcome, done=None):
        self.outcome, self.done, self.calls = outcome, done, []

    def __call__(self, line, *, cwd, env, stdin_text, timeout):
        self.calls.append({"line": line, "cwd": cwd, "env": env, "stdin": stdin_text, "timeout": timeout})
        if self.done:
            (batch.Path(cwd) / batch.LAST_DONE).write_text(json.dumps({"summary": self.done}), encoding="utf-8")
        return self.outcome


def spec(tmp_path, inputs=None):
    return batch.BatchSpec(brain=tmp_path / "brain", claude="claude", base_url="http://127.0.0.1:9", token="tok",
                           project="p1", workspace="main", snapshot="PROJEKT p1", inputs=inputs or [])



def test_message_renders_merge_and_new_commits_in_czech():
    text = batch.message("S", [{"type": "merged", "nodeId": "n1", "executionId": "ex1", "mergeSha": "abcdef1234567890",
                                "pr": 7},
                               {"type": "merged", "nodeId": "n2", "executionId": "ex2", "mergeSha": "fff", "pr": None},
                               {"type": "commits", "from": "1111111aaaa", "to": "2222222bbbb",
                                "log": ["2222222 Druhý", "1a1a1a1 První"]}])
    assert "- SLOUČENO: karta n1, PR #7, sha abcdef123456 (běh ex1)" in text
    assert "- SLOUČENO: karta n2, lokální sloučení, sha fff" in text
    assert "- NOVÉ COMMITY 1111111..2222222: 2222222 Druhý; 1a1a1a1 První" in text

def clock(*values):
    items = iter(values)
    return lambda: next(items)


def test_message_contains_snapshot_inputs_and_the_finish_instruction():
    text = batch.message("PROJEKT X", [{"type": "message", "text": "Dvě stránky."},
                                       {"type": "ticket", "ticketId": "gt_1", "kind": "ask", "body": {"q": "?"}},
                                       {"type": "taskFailed", "taskId": "ht_1", "title": "Hero", "body": {"do": "Sekce hero"},
                                        "report": {"sha": "a"}}])
    assert text.index("PROJEKT X") < text.index("ZPRÁVA ČLOVĚKA: Dvě stránky.") < text.index("LÍSTEK gt_1 (ask)")
    assert "ÚKOL SELHAL ht_1" in text and "Sekce hero" in text and text.rstrip().endswith(batch.FINISH)


def test_ok_batch_is_journaled_with_costs_and_summary(tmp_path):
    inputs = [{"type": "message", "text": "Dvě stránky."}]
    runner = FakeRunner(Outcome(0, "noise\n" + json.dumps(RESULT), ""), done="Dva úkoly ve frontě.")
    entry = batch.run(spec(tmp_path, inputs), runner, clock(100.0, 160.5))
    call = runner.calls[0]
    assert call["timeout"] == batch.TIMEOUT and call["cwd"].endswith("brain") and "--session-id" in call["line"]
    assert call["env"]["OPORA_HEART_TOKEN"] == "tok" and "Dvě stránky." in call["stdin"]
    assert entry["status"] == "ok" and entry["summary"] == "Dva úkoly ve frontě." and entry["numTurns"] == 7
    assert entry["costByModel"] == {"claude-haiku-4-5": 0.0121, "claude-opus-4-5": 0.03}
    assert entry["costUsd"] == 0.0421 and entry["durationMs"] == 60_500 and entry["inputs"] == inputs
    assert batch.read_journal(tmp_path / "brain") == [entry]
    assert session.load(tmp_path / "brain") == {"sessionId": RESULT["session_id"], "batches": 1,
                                                "lastInputTokens": 20_900}
    assert (tmp_path / "brain" / batch.SNAPSHOT).read_text(encoding="utf-8") == "PROJEKT p1"
    second = FakeRunner(Outcome(0, json.dumps(RESULT), ""))
    batch.run(spec(tmp_path), second, clock(200.0, 201.0))
    assert second.calls[0]["line"][second.calls[0]["line"].index("--resume") + 1] == RESULT["session_id"]
    assert session.load(tmp_path / "brain")["batches"] == 2


def test_rate_limit_keeps_session_and_is_marked(tmp_path):
    limited = {**RESULT, "is_error": True, "result": "Claude AI usage limit reached; you've hit your session limit"}
    entry = batch.run(spec(tmp_path), FakeRunner(Outcome(1, json.dumps(limited), "")), clock(0.0, 1.0))
    assert entry["status"] == "rate_limited" and "limit" in entry["error"]
    assert session.load(tmp_path / "brain") == session.EMPTY
    assert batch.rate_limited(None, "Error: rate_limit_error") is True
    assert batch.rate_limited(RESULT, "") is False


def test_timeout_and_error_force_rotation(tmp_path):
    entry = batch.run(spec(tmp_path), FakeRunner(Outcome(None, "", "", True)), clock(0.0, 900.0))
    assert entry["status"] == "timeout" and entry["isError"] is True and entry["summary"] is None
    failed = {**RESULT, "is_error": True, "subtype": "error_during_execution", "result": "No conversation found"}
    assert batch.run(spec(tmp_path), FakeRunner(Outcome(1, json.dumps(failed), "")), clock(0.0, 1.0))["status"] == "error"
    assert session.choose(tmp_path / "brain", lambda: "new")[1] is False
    assert [item["status"] for item in batch.read_journal(tmp_path / "brain")] == ["timeout", "error"]


def test_advisor_is_dropped_after_the_daily_cap(tmp_path):
    brain = tmp_path / "brain"
    brain.mkdir()
    day = 1_800_000_000.0  # 2027-01-15 UTC
    old = {"at": "2027-01-14T23:00:00Z", "costByModel": {"claude-opus-4-5": 9.0}}
    today = {"at": "2027-01-15T08:00:00Z", "costByModel": {"claude-opus-4-5": 1.5, "claude-haiku-4-5": 3.0}}
    (brain / batch.JOURNAL).write_text("\n".join(json.dumps(item) for item in (old, today)) + "\n", encoding="utf-8")
    assert batch.advisor_spent(brain, day) == 1.5
    first = FakeRunner(Outcome(0, json.dumps(RESULT), ""))
    assert batch.run(spec(tmp_path), first, clock(day, day + 1))["advisor"] is True
    assert "--advisor" in first.calls[0]["line"]
    with (brain / batch.JOURNAL).open("a", encoding="utf-8") as journal:
        journal.write(json.dumps({**today, "costByModel": {"claude-opus-4-5": 0.6}}) + "\n")
    second = FakeRunner(Outcome(0, json.dumps(RESULT), ""))
    assert batch.run(spec(tmp_path), second, clock(day + 2, day + 3))["advisor"] is False
    assert "--advisor" not in second.calls[0]["line"]


def test_sub_cost_sums_workshop_runs_since_the_batch_started(tmp_path):
    runs = tmp_path / "brain" / batch.RUNS
    runs.parent.mkdir(parents=True)
    runs.write_text(json.dumps({"at": "1970-01-01T00:00:10Z", "subCostUsd": 5.0}) + "\n", encoding="utf-8")

    class Runs(FakeRunner):
        def __call__(self, line, **kwargs):
            with runs.open("a", encoding="utf-8") as file:
                for cost in (0.01, 0.0025):
                    file.write(json.dumps({"at": "1970-01-01T00:01:41Z", "script": "x", "subCostUsd": cost}) + "\n")
                file.write("rozbitý řádek\n")
            return super().__call__(line, **kwargs)

    runner = Runs(Outcome(0, json.dumps(RESULT), ""))
    entry = batch.run(batch.BatchSpec(**{**vars(spec(tmp_path)), "source_root": tmp_path}), runner, clock(100.0, 101.0))
    assert entry["subCostUsd"] == 0.0125
    assert runner.calls[0]["env"]["OPORA_SOURCE_ROOT"] == str(tmp_path)
    assert (tmp_path / "brain" / "dilna" / "rlm.py").is_file() and (tmp_path / "brain" / "dilna" / "scripts").is_dir()
    assert batch.sub_cost(tmp_path / "nic", "1970") == 0.0
