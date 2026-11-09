"""Research map client: lossless facts, scoped reads, and durable idempotent retries."""
import json
from types import SimpleNamespace

import pytest

from backend.brain_opora.heart import command, opora_heart, opora_research, opora_research_map as mapping

AT = "2026-11-08T12:00:00Z"
SCOPE = {"project": "draft", "workspace": "draft"}


def args(*extra):
    return opora_heart.parser().parse_args(["research", "--title", "Login", "--question", "How?", *extra])


def test_original_fragment_show_falls_back_without_masquerading_as_research_card(monkeypatch):
    calls = []
    def call(method, path, query=None):
        calls.append((method, path, query))
        if '/cards/' in path:
            raise opora_heart.Failure({"status": 404, "code": "research_not_found"})
        return {"origin": "brief-vault", "type": "original-research", "sourceId": "fragment", "sourceRevision": 3}
    monkeypatch.setattr(opora_heart, 'call', call)
    monkeypatch.setattr(opora_heart, 'scope', lambda: SCOPE)
    parsed = opora_heart.parser().parse_args(['research-map', 'show', 'fragment', '--revision', '3'])
    result = mapping.run(parsed, opora_heart)
    assert result['type'] == 'original-research' and 'card' not in result
    assert calls[-1] == ('GET', '/api/research/originals/fragment', {**SCOPE, 'revision': 3})


def result():
    return {"digest": {"verdict": "unverified", "confidence": "low", "next": "ask", "nextWhy": "Check identity",
                       "layers": {}, "hypotheses": [], "slices": []},
            "facts": [{"id": f"f{i}", "source": "https://example.org/login", "claim": f"Finding {i}",
                       "quote": "quote " * 1000, "verified": state, "layer": "logic"}
                      for i, state in enumerate(["verified", "observed", "false", "unreachable"] * 3)],
            "options": [{"detail": "full options"}], "stats": {"calls": 1, "costUsd": 0.1, "seconds": 1,
                                                                  "claimed": 12, "verified": 6}}


def test_full_facts_shared_url_states_and_refs_survive_import():
    source = result()
    parsed = args("--topic", "Login", "--topic", "Logic", "--question-id", "pq_1", "--node", "n1",
                  "--ticket", "tk_1", "--session", "office-a", "--attachment", "drawing_1")
    saved = mapping.batch(source, "vf_a", parsed, AT)
    assert saved == mapping.batch(source, "vf_a", parsed, AT)
    cards = [op for op in saved["operations"] if op["op"] == "card"]
    assert len(cards) == 13 and len({c["id"] for c in cards}) == 13
    assert json.loads(cards[0]["content"])["digest"] == source["digest"]
    for card, fact in zip(cards[1:], source["facts"], strict=True):
        assert json.loads(card["content"]) == fact
        assert card["sources"][0]["quote"] == fact["quote"]
        assert card["verification"]["status"] == fact["verified"]
        assert card["refs"] == {"nodeIds": ["n1"], "questionIds": ["pq_1"], "ticketIds": ["tk_1"],
                                 "sessionIds": ["office-a"], "fragmentIds": ["vf_a"], "attachmentIds": ["drawing_1"]}
        assert card["topicPath"] == ["Login", "Logic", "logic"]
    assert all(op["relation"] == "elaborates" for op in saved["operations"] if op["op"] == "edge")


def test_video_range_and_code_revision_location_survive_validated_import():
    from backend.editor.research import model

    source = result()
    source["facts"] = [
        {**source["facts"][0], "source": "https://www.youtube.com/watch?v=demo", "timestamp": "01:12–01:46"},
        {**source["facts"][1], "source": "https://github.com/example/app/blob/abc123/auth.py#L12-L26",
         "revision": "abc123", "location": "auth.py:12–26"},
    ]
    saved = mapping.batch(source, "vf_source_metadata", args(), AT)
    cards = [op for op in saved["operations"] if op["op"] == "card"][1:]
    for item in cards:
        model.card({key: item[key] for key in model.CARD})
    assert cards[0]["sources"][0]["timestamp"] == "01:12–01:46"
    assert cards[1]["sources"][0]["revision"] == "abc123"
    assert cards[1]["sources"][0]["location"] == "auth.py:12–26"
    assert json.loads(cards[1]["content"]) == source["facts"][1]


def test_runtime_guidance_and_standalone_helper_are_installed(tmp_path):
    command.write_config(tmp_path, command.HeartSkills("active custom skill", {}, {}))
    prompt = (tmp_path / command.PROMPT_NAME).read_text(encoding="utf-8")
    assert prompt.startswith("active custom skill") and "research-map show ID" in prompt
    assert "ticket-answer --ticket ID" in prompt and "continues_to" in prompt
    assert (tmp_path / "opora_research_map.py").is_file()


def test_scoped_cli_headers_detail_revision_and_batch(monkeypatch, tmp_path):
    monkeypatch.setenv("OPORA_PROJECT", "draft")
    monkeypatch.setenv("OPORA_WORKSPACE", "main")
    monkeypatch.setattr(opora_heart, "active_workspace", lambda: "w1")
    seen = []
    monkeypatch.setattr(opora_heart, "call", lambda *a, **kw: seen.append((a, kw)) or {})
    opora_heart.run(opora_heart.parser().parse_args(["research-map", "ls", "--archived"]))
    assert seen[-1] == (("GET", mapping.API), {"query": {"project": "draft", "workspace": "w1", "archived": 1}})
    opora_heart.run(opora_heart.parser().parse_args(["research-map", "show", "rc_1", "--revision", "2"]))
    assert seen[-1][1]["query"]["revision"] == 2
    opora_heart.run(opora_heart.parser().parse_args(["research-map", "show", "re_1", "--entity", "edge",
                                                   "--revision", "1"]))
    assert seen[-1] == (("GET", "/api/research/edges/re_1"),
                        {"query": {"project": "draft", "workspace": "w1", "revision": 1}})
    file = tmp_path / "batch.json"
    data = {"key": "save-one", "operations": []}
    file.write_text(json.dumps(data), encoding="utf-8")
    opora_heart.run(opora_heart.parser().parse_args(["research-map", "save", "--file", str(file)]))
    assert seen[-1][0][2] == {**data, "project": "draft", "workspace": "w1"}


def test_raw_saved_before_network_failure_and_retry_uses_same_payload(monkeypatch, tmp_path):
    calls = []
    costs = []
    tool = SimpleNamespace(scope=lambda: SCOPE, DILNA=tmp_path, now=lambda: AT, _execute=None,
                           Failure=opora_heart.Failure, log_run=lambda *a: costs.append(a))
    data = result()
    monkeypatch.setattr(opora_research, "find_browser", lambda: None)
    monkeypatch.setattr(opora_research.research_desk, "need_claude", lambda _: "claude")
    monkeypatch.setattr(opora_research.research_desk, "run_desk", lambda *a, **kw: data)
    monkeypatch.setattr(opora_research, "heart_root", lambda *a: "vf_root")

    def call(method, path, body=None, **kw):
        calls.append((method, path, body))
        if path == "/api/brief-vault":
            return {"fragment": {"id": "vf_run", "revision": 1}}
        assert (tmp_path / "out/research/vf_run.json").is_file()
        raise tool.Failure({"code": "offline", "error": "offline"})

    tool.call = call
    with pytest.raises(tool.Failure):
        opora_research.research(args(), tool)
    raw = tmp_path / "out/research/vf_run.json"
    saved = json.loads(raw.read_text(encoding="utf-8"))
    assert saved["facts"] == data["facts"] and saved["digest"] == data["digest"]
    assert len(costs) == 1 and costs[0][-1] == data["stats"]["costUsd"]
    failed_payload = calls[-1][2]
    def retry(method, path, body=None, **kwargs):
        calls.append((method, path, body))
        if method == 'GET':
            return {'sourceRevision': 2, 'original': {'details': {'research': saved['researchBatch']['continuation']['finalization']}}}
        return {'cards': []}
    tool.call = retry
    parsed = opora_heart.parser().parse_args(["research-map", "import", "--file", str(raw)])
    mapping.run(parsed, tool)
    mapping.run(parsed, tool)
    imported_payloads = [body for method, path, body in calls if method == 'POST' and path == mapping.API]
    assert imported_payloads[-1] == imported_payloads[-2] == failed_payload
    tool.scope = lambda: {**SCOPE, "workspace": "foreign"}
    with pytest.raises(tool.Failure) as caught:
        mapping.run(parsed, tool)
    assert caught.value.payload["code"] == "research_scope"


@pytest.mark.parametrize("url,expected", [("https://www.youtube.com/watch?v=x", "youtube"),
                                         ("https://medium.com/a", "medium"), ("src/login.py:3", "code"),
                                         ("https://notyoutube.com", "web")])
def test_source_platform_is_original_not_discovery_engine(url, expected):
    assert mapping.platform(url) == expected


def test_attachment_uses_drawing_store_with_content_id_and_no_scene_mutation(tmp_path):
    image = tmp_path / "login.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nexample")
    calls = []
    tool = SimpleNamespace(scope=lambda: SCOPE, Failure=opora_heart.Failure,
                           call=lambda *a: calls.append(a) or {})
    parsed = opora_heart.parser().parse_args(["research-map", "attach", "--file", str(image)])
    first = mapping.run(parsed, tool)
    assert mapping.run(parsed, tool) == first
    assert calls[0] == calls[1]
    assert calls[0][:2] == ("POST", "/api/drawing-file")
    assert calls[0][2]["file"]["id"] == first["attachmentId"]
    assert calls[0][2]["file"]["dataURL"].startswith("data:image/png;base64,")
    invalid = tmp_path / "login.svg"
    invalid.write_text("<svg/>")
    with pytest.raises(opora_heart.Failure):
        mapping.attach(str(invalid), tool)


@pytest.mark.parametrize('mode', ['new', 'already', 'lost-response', 'advanced-conflict'])
def test_finalization_keeps_original_cas_and_replays_only_exact_native_output(mode):
    fields = {'status': 'done', 'verdict': 'unverified', 'confidence': '', 'approach': 'Result', 'evidence': []}
    intent = {'sourceFragmentId': 'original', 'sourceRevision': 1, 'finalization': fields}
    state = {'revision': 2 if mode in ('already', 'advanced-conflict') else 1}
    writes, reads = [], []
    tool = SimpleNamespace(Failure=opora_heart.Failure)

    def call(method, route, body=None, query=None):
        if method == 'GET':
            reads.append(query)
            actual = fields if state['revision'] == 2 and mode != 'advanced-conflict' else {**fields, 'approach': 'Other'}
            return {'sourceRevision': state['revision'], 'original': {'details': {'research': actual}}}
        writes.append(body)
        assert body['expectedRevision'] == 1
        state['revision'] = 2
        if mode == 'lost-response':
            raise tool.Failure({'error': 'Response lost'})
        return {'fragment': {'revision': 2}}

    tool.call = call
    if mode == 'advanced-conflict':
        with pytest.raises(tool.Failure) as caught:
            mapping.finalize(intent, tool, SCOPE)
        assert caught.value.payload['code'] == 'research_finalization_conflict' and writes == []
    else:
        mapping.finalize(intent, tool, SCOPE)
        assert len(writes) == (0 if mode == 'already' else 1)
        assert mapping.finalize(intent, tool, SCOPE)['alreadyFinalized'] is True
        assert len(writes) == (0 if mode == 'already' else 1)
    assert all(query == SCOPE for query in reads)


def test_research_saves_finalization_intent_before_import_and_completes_native_original(monkeypatch, tmp_path):
    calls = []
    tool = SimpleNamespace(scope=lambda: SCOPE, DILNA=tmp_path, now=lambda: AT, _execute=None,
                           Failure=opora_heart.Failure, log_run=lambda *args: None)
    data = result()
    monkeypatch.setattr(opora_research, 'find_browser', lambda: None)
    monkeypatch.setattr(opora_research.research_desk, 'need_claude', lambda _: 'claude')
    monkeypatch.setattr(opora_research.research_desk, 'run_desk', lambda *a, **kw: data)
    monkeypatch.setattr(opora_research, 'heart_root', lambda *a: 'root')

    def call(method, path, body=None, query=None):
        calls.append((method, path, body))
        if body and body.get('op') == 'research':
            return {'fragment': {'id': 'original', 'revision': 1}}
        saved = json.loads((tmp_path / 'out/research/original.json').read_text('utf-8'))
        if path == mapping.API:
            assert body['continuation']['finalization'] == saved['researchBatch']['continuation']['finalization']
            return {'cards': [{'id': 'question'}]}
        if method == 'GET':
            return {'sourceRevision': 1}
        assert body['op'] == 'research-update' and body['expectedRevision'] == 1
        assert all(body[key] == value for key, value in saved['researchBatch']['continuation']['finalization'].items())
        return {'fragment': {'id': 'original', 'revision': 2}}

    tool.call = call
    completed = opora_research.research(args(), tool)
    assert completed['researchIds'] == ['question']
    assert [(method, path) for method, path, _ in calls] == [
        ('POST', '/api/brief-vault'), ('POST', mapping.API),
        ('GET', mapping.API + '/originals/original'), ('POST', '/api/brief-vault')]
