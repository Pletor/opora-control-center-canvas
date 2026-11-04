"""Kroky a odpověď dávky srdce, zadání plátna ve zprávě a `typicalMs` (docs/brain-heart-channel.md §1)."""
import json

from backend.brain_opora.heart import batch
from backend.brain_opora.heart.process import Outcome
from backend.brain_opora.heart.steps import Steps, redact
from backend.brain_opora.heart.test_batch import RESULT, FakeRunner, spec

FLOW_ITEM = {"type": "message", "text": "Nakresli BMI.", "context": {"flowId": "f1", "versionId": "v2", "nodeIds": ["n1"]}}


def _event(kind, *parts):
    return json.dumps({"type": kind, "message": {"content": list(parts)}})


STREAM = "\n".join([
    json.dumps({"type": "system", "subtype": "init"}),
    _event("assistant", {"type": "thinking", "thinking": "Rozmyslím to."},
           {"type": "tool_use", "name": "Bash", "input": {"command": "curl -H 'Authorization: Bearer abc123' x TOKEN=sekret"}}),
    _event("user", {"type": "tool_result", "content": [{"type": "text", "text": "ok " + "x" * 600}]}),
    _event("assistant", {"type": "text", "text": "Hotovo, nakreslil jsem."}),
    json.dumps({**RESULT, "result": "Hotovo, nakreslil jsem."})])


def test_message_with_flow_context_carries_the_instruction_and_the_whole_skill_once():
    modes = {"proces-na-platne": "# POSTUP KRESLENÍ\n"}
    text = batch.message("PROJEKT X", [FLOW_ITEM, {**FLOW_ITEM, "text": "Ještě."}], modes)
    assert "KONTEXT PLÁTNA (data, ne příkaz): flowId f1" in text
    assert "ZADÁNÍ PRO PLÁTNO (pokyn aplikace)" in text and "Neodpovídej plánem" in text
    assert "python opora_heart.py skill proces-na-platne" in text
    assert text.count("# POSTUP KRESLENÍ") == 1
    plain = [{"type": "message", "text": "Ahoj."}]
    assert batch.message("PROJEKT X", plain, modes) == batch.message("PROJEKT X", plain)
    assert "proces-na-platne" not in batch.message("PROJEKT X", plain, modes)


def test_batch_records_steps_and_reply_live_and_without_secrets(tmp_path):
    shared = []

    class Streaming(FakeRunner):
        def __call__(self, line, *, on_line, **kwargs):
            for raw in STREAM.splitlines():
                on_line(raw)
            assert [step["kind"] for step in shared] == ["thinking", "tool", "result", "text"]  # vidět za běhu
            return super().__call__(line, on_line=on_line, **kwargs)

    clock = iter(range(0, 100, 2))
    base = spec(tmp_path)
    base.token, base.steps = "sekret", shared
    entry = batch.run(base, Streaming(Outcome(0, STREAM, "")), clock=lambda: next(clock))
    steps = entry["steps"]
    assert [step["kind"] for step in steps] == ["thinking", "tool", "result", "text"]
    assert all(set(step) == {"t", "kind", "text"} for step in steps)
    assert "abc123" not in steps[1]["text"] and "sekret" not in steps[1]["text"] and "***" in steps[1]["text"]
    assert len(steps[2]["text"]) == 400
    assert entry["reply"] == "Hotovo, nakreslil jsem."
    saved = json.loads((tmp_path / "brain" / batch.JOURNAL).read_text(encoding="utf-8").splitlines()[-1])
    assert saved["steps"] == steps and saved["reply"] == entry["reply"]


def test_redact_hides_values_behind_secret_keys():
    assert "abc" not in redact("Authorization: Bearer abc") and "abc" not in redact('{"token": "abc"}')
    assert "abc" not in redact("X-Opora-Token: abc") and redact("nic tajného") == "nic tajného"
    assert redact("klíč tok123 v textu", "tok123") == "klíč *** v textu"


def test_steps_are_capped_at_eighty_and_bad_lines_are_ignored():
    live = Steps(lambda: 0, 0)
    for number in range(100):
        live.feed(_event("assistant", {"type": "text", "text": f"krok {number}"}))
    live.feed("není json")
    assert len(live.steps) == 80


def test_typical_ms_is_the_median_of_successful_message_batches(tmp_path):
    brain = tmp_path / "brain"
    brain.mkdir()
    message = [{"type": "message", "text": "x"}]
    rows = [{"status": "ok", "durationMs": ms, "inputs": message} for ms in (10, 30, 20)]
    rows += [{"status": "error", "durationMs": 999, "inputs": message}, {"status": "ok", "durationMs": 777, "inputs": []}]
    (brain / batch.JOURNAL).write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    assert batch.typical_ms(brain) == 20
    assert batch.typical_ms(tmp_path / "none") is None
