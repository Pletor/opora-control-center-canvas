"""Provider-independent read loop: intermediate actions/text never escape, no invented answer after budget."""
from backend.agi_pletor import research_context, research_turn


def setup(monkeypatch):
    monkeypatch.setattr(research_context, "overview", lambda *a: "\nREŠERŠE rc_1")
    monkeypatch.setattr(research_context, "read", lambda *a: {"data": "DOKLAD ZDROJE", "nextOffset": None})


def test_intermediate_read_reply_and_mutation_are_discarded(monkeypatch):
    setup(monkeypatch)
    seen = []
    output = []

    def run(context, text, history, on_delta=None):
        seen.append(context)
        if len(seen) == 1:
            on_delta("TOTO NEČÍST")
            return "TOTO NEČÍST", [{"type": "research_read", "cardId": "rc_1"},
                                  {"type": "heart_message", "text": "TOTO NEPROVÉST"}]
        assert "DOKLAD ZDROJE" in context
        on_delta("Doložená ")
        on_delta("odpověď.")
        return "Doložená odpověď.", []

    reply, actions = research_turn.turn(run, None, "p", "w", "PODKLADY", "Co víme?", on_delta=output.append)
    assert reply == "Doložená odpověď." and actions == []
    assert output == ["Doložená ", "odpověď."]
    assert len(seen) == 2


def test_limit_does_not_execute_actions_or_present_unsupported_answer(monkeypatch):
    setup(monkeypatch)
    calls = []
    def run(*args, **kwargs):
        calls.append(1)
        return "Všechno vím.", [{"type": "research_read", "cardId": "rc_1"},
                               {"type": "vault_note", "text": "Nedoložený závěr"}]
    reply, actions = research_turn.turn(run, None, "p", "w", "", "?")
    assert "nedočetl" in reply and actions == []
    assert len(calls) == research_turn.MAX_READS + 1
    assert "automaticky nenavazuje" in reply


def test_continuation_instruction_includes_snapshot_and_supports_more_than_three_reads(monkeypatch):
    setup(monkeypatch)
    calls = []

    def run(context, text, history, on_delta=None):
        calls.append(context)
        if len(calls) <= 4:
            return "", [{"type": "research_read", "cardId": "rc_1"}]
        assert "snapshot" in context and "offset=nextOffset" in context
        return "Ověřeno ze čtyř čtení.", []

    reply, actions = research_turn.turn(run, None, "p", "w", "", "?")
    assert reply == "Ověřeno ze čtyř čtení." and actions == [] and len(calls) == 5


def test_plain_provider_reply_and_final_actions_survive(monkeypatch):
    setup(monkeypatch)
    output = []
    action = {"type": "vault_note", "text": "Dohodnuto"}
    result = research_turn.turn(lambda *a, **kw: ("Odpověď bez streamu.", [action]),
                                None, "p", "w", "", "?", on_delta=output.append)
    assert result == ("Odpověď bez streamu.", [action]) and output == ["Odpověď bez streamu."]
