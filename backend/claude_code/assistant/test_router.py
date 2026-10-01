from backend.claude_code.assistant.router import MAX_STATE_TEXT, QUESTIONS, SOURCES, hint_from, route


def answers(probabilities, noul=0.8):
    return {"source": {"type": "choice", "choice": max(probabilities, key=probabilities.get),
                       "probabilities": probabilities},
            "needs_lookup": {"type": "noul", "noul": noul}}


def test_route_sends_state_and_contract_questions():
    seen = []

    def evaluate(state, questions):
        seen.append((state, questions))
        return answers({"code": 0.6, "find": 0.3, "web": 0.1})

    hint = route("x" * 5000, {"environment": "editor", "selectedNodeIds": ["a", "b"]}, evaluate=evaluate)
    state, questions = seen[0]
    assert state == {"request": "x" * MAX_STATE_TEXT, "environment": "editor", "selectedCount": 2}
    assert questions is QUESTIONS and questions["source"]["criteria"] is SOURCES
    assert hint == {"sources": ["code", "find"], "needsLookup": 0.8}


def test_slash_commands_and_failures_have_no_hint():
    called = []
    assert route("  /grill-me plán", {}, evaluate=lambda *a: called.append(a)) is None
    assert called == []
    assert route("ahoj", None, evaluate=lambda *a: None) is None


def test_hint_keeps_only_known_sources_above_threshold():
    hint = hint_from(answers({"canvas": 0.5, "hack": 0.4, "web": 0.1, "graphify": 0.25, "find": 0.2}))
    assert hint == {"sources": ["canvas", "graphify"], "needsLookup": 0.8}
    assert hint_from({"source": {"probabilities": {"canvas": 2}}, "needs_lookup": {"noul": "x"}}) is None
    assert hint_from([]) is None
