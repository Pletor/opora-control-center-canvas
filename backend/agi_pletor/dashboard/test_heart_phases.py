"""Rozpad dávky srdce na fáze: čas otevřeného nástroje patří jemu, jinak modelu; selhání a souběžné nástroje."""
from backend.agi_pletor.dashboard.heart_phases import analyze, category, headline


def step(t, kind, text):
    return {"t": t, "kind": kind, "text": text}


def test_categories():
    assert category("Bash: python opora_heart.py steps --node x") == "opora_write"
    assert category("Bash: python opora_heart.py ctx plan-of") == "opora_read"
    assert category("Read: {}") == "files" and category("Write: {}") == "write_files"
    assert category("Bash: git status") == "commands"


def test_write_wait_dominates_and_failure_is_named():
    batch = {"durationMs": 200_000, "steps": [
        step(10_000, "text", "Začínám."),
        step(12_000, "tool", "Bash: python opora_heart.py steps --node a"),
        step(13_000, "tool", "Bash: python opora_heart.py intake --entry b"),
        step(132_000, "result", 'Exit code 1 {"error": "OPORA neodpověděla", "code": "server_unreachable"}'),
        step(150_000, "result", '{"ok": true}'),
        step(190_000, "text", "Hotovo."),
    ]}
    analysis = analyze(batch)
    phases = {phase["id"]: phase["ms"] for phase in analysis["phases"]}
    assert phases == {"model": 10_000 + 2_000 + 40_000 + 10_000, "opora_write": 138_000}
    assert analysis["failures"] == [{"tool": "opora_heart.py steps", "error": "server_unreachable", "ms": 120_000}]
    assert analysis["slowest"][0]["ms"] == 137_000 and analysis["slowest"][0]["tool"] == "opora_heart.py intake"
    assert analysis["slowest"][0]["parallel"] is True  # odesláno spolu se steps, sdílí čas
    assert "zápis do OPORY" in headline(analysis) and "server_unreachable" in headline(analysis)


def test_empty_and_unanswered():
    assert analyze({})["phases"] == [] and headline(analyze({})) == "Dávka bez kroků."
    open_call = analyze({"durationMs": 5000, "steps": [step(1000, "tool", "Read: {}")]})
    assert open_call["unanswered"] == ["Read: {}"] and open_call["phases"][0]["id"] == "files"


def test_truncated_tail_is_not_blamed_on_the_open_tool():
    steps = [step(i * 1000, "tool" if i % 2 == 0 else "result", "Read: {}") for i in range(80)]
    analysis = analyze({"durationMs": 500_000, "steps": steps})
    phases = {phase["id"]: phase["ms"] for phase in analysis["phases"]}
    assert analysis["truncated"] is True and phases["untraced"] == 500_000 - 79_000
