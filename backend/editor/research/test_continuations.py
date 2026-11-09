import json
import pytest

from backend.api.editor.test_brief_vault_routes import client_with_sector, post as vault
from backend.api.editor.test_research_routes import card
from backend.editor.node.test_removals import HEADERS, SCOPE
from backend.editor.research import continuations


def imported(client, accepted_context=True, extra_operations=(), finalization=None):
    if accepted_context:
        from backend.canvas.opora_graph_proposals import OporaGraphProposals
        from backend.canvas.test_opora_graph_proposals import accept, proposal
        native = OporaGraphProposals(client.app.state.service)
        accept(native, proposal(native))  # Isolated test fixture, not production approval.
    root = vault(client, op="create", scopeNodeId="s1", discipline="ux", title="Root", text="Original").json()["fragment"]
    response = vault(client, op="research", fragmentId=root["id"], title="V3", text="Original question",
                     question="Versioned vectors?", status="running")
    assert response.status_code == 200, response.text
    source = response.json()["fragment"]
    value = card(kind="question")
    value["refs"]["fragmentIds"] = [source["id"]]
    body = {**SCOPE, "key": "import", "operations": [value, *extra_operations], "continuation": {
        "researchId": value["id"], "sourceFragmentId": source["id"], "sourceRevision": source["revision"]}}
    if finalization is not None:
        body["continuation"]["finalization"] = finalization
    result = client.post("/api/research", headers=HEADERS, json=body)
    assert result.status_code == 200, result.text
    return body, result.json(), source


def test_atomic_import_replay_no_sources_and_restart_backlog(tmp_path):
    from backend.canvas.opora_events import QUIET
    assert "research.planning.requested" in QUIET
    with client_with_sector(tmp_path) as client:
        body, result, source = imported(client)
        assert client.post("/api/research", headers=HEADERS, json=body).json() == result
        service = client.app.state.service
        first = continuations.wakes(service, "draft", 0)
        assert first == continuations.wakes(service, "draft", 1)
        assert len(first) == 1
        assert first[0][1]["researchRevision"] == 1
        events = service.db_for("draft").execute("SELECT kind FROM opora_events WHERE kind='research.planning.requested'").fetchall()
        assert len(events) == 1
        assert result["cards"][0]["verification"]["status"] == "unverified"
        assert result["cards"][0]["status"] == "open"
        changed = {**body, "continuation": {**body["continuation"], "sourceRevision": 999}}
        assert client.post("/api/research", headers=HEADERS, json=changed).status_code == 409
        original = client.get('/api/research/originals/' + source['id'], params=SCOPE).json()
        assert original["origin"] == "brief-vault" and original["type"] == "original-research"
        assert original["original"]["details"]["research"]["status"] == "running"


@pytest.mark.parametrize("accepted_before_poll", [False, True, "stale_source"])
def test_native_proposal_receipt_acknowledges_saved_content(tmp_path, accepted_before_poll):
    with client_with_sector(tmp_path) as client:
        _, result, _ = imported(client)
        service = client.app.state.service
        item = result["continuation"]
        assert continuations.wakes(service, "draft", 0)
        from backend.canvas.opora_graph_proposals import OporaGraphProposals
        proposals = OporaGraphProposals(service)
        context = proposals.context("draft", "draft")
        from backend.editor.research.planning_source import pins
        made = proposals.create({**SCOPE, "operationId": item["operationId"], "parentRevision": context["acceptedHead"],
            "expectedGraphDigest": context["graphDigest"], "subject": "Partial proposal",
            "plan": {"draftVersion": 3, "researchSource": pins(item),
                     "nodes": [{"ref": "task", "kind": "node", "name": "Independent task", "text": "Partial evidence"}]}},
            {"kind": "agent", "name": "heart"})
        if accepted_before_poll == "stale_source":
            from backend.editor.research.model import CARD
            original = result['cards'][0]
            revised = {**{key: original[key] for key in CARD}, 'op': 'card', 'id': original['id'],
                       'expectedRevision': original['revision'], 'content': 'New contradictory evidence'}
            assert client.post('/api/research', headers=HEADERS,
                json={**SCOPE, 'key': 'revised-source', 'operations': [revised]}).status_code == 200
            assert continuations.wakes(service, 'draft', 1) == []
            receipt = continuations.listing(service, 'draft', 'draft')[0]
            assert receipt['status'] == 'conflict' and receipt['proposalId'] is None
            assert proposals.read('draft', 'draft', made['id'])['accepted'] is False
            return
        if accepted_before_poll is True:
            from backend.canvas.opora_graph_changes import OporaGraphChanges
            from backend.canvas.test_opora_graph_changes import approve
            approve(OporaGraphChanges(service), made)  # Explicit isolated test-human action.
        assert continuations.wakes(service, "draft", 1) == []
        stored = continuations.listing(service, "draft", "draft")[0]
        assert stored["status"] == "complete" and stored["proposalId"] == made["id"]
        assert proposals.read("draft", "draft", made["id"])["accepted"] is accepted_before_poll
        assert stored["acceptedAtReadback"] is accepted_before_poll
        assert continuations.wakes(service, "draft", 1000) == []


def test_original_materialization_preserves_history_and_is_idempotent(tmp_path):
    with client_with_sector(tmp_path) as client:
        _, _, source = imported(client)
        route = '/api/research/originals/' + source['id']
        original = client.get(route, params=SCOPE).json()
        body = {**SCOPE, "revision": original["sourceRevision"], "detailsRevision": original["detailsRevision"]}
        response = client.post(route + '/materialize', json=body, headers=HEADERS)
        assert response.status_code == 200, response.text
        assert client.post(route + '/materialize', json=body, headers=HEADERS).json() == response.json()
        after = client.get(route, params=SCOPE).json()
        assert after["sourceHistory"] == original["sourceHistory"]
        projected = response.json()["cards"][0]
        assert projected["id"] == "rc_login"  # Reuse the existing canonical mapped question.
        assert len([c for c in after["mappedCards"] if c["kind"] == "question"]) == 1
        assert projected["status"] == "open" and projected["verification"]["status"] == "unverified"
        assert json.loads(projected["content"])["sourceRevision"] == source["revision"]


def recorded_run(service, item, number, status="running"):
    from backend.flow.catalogs.heart.seed import ensure_active
    with service.registry_lock, service.db:
        workflow, _ = ensure_active(service.db)
        version = service.db.execute("SELECT id FROM flow_workflow_versions WHERE workflow_id=? AND status='active'",
                                     (workflow,)).fetchone()[0]
        service.db.execute("INSERT INTO flow_runs(id,workflow_version_id,trigger,status,created_at,updated_at) "
                           "VALUES(?,?,?,?,?,?)", (str(number), version, json.dumps({"source": "heart", "payload": {
            **SCOPE, "items": [item]}}), status, "now", "now"))


def test_native_run_recovery_and_bounded_retry_even_when_llm_succeeds(tmp_path):
    with client_with_sector(tmp_path) as client:
        imported(client)
        service = client.app.state.service
        item = continuations.wakes(service, "draft", 0)[0][1]
        # Crash after flow start but before receipt update: native flow input is the durable fence.
        recorded_run(service, item, 1)
        assert continuations.wakes(service, "draft", 0) == []
        assert continuations.listing(service, "draft", "draft")[0]["status"] == "running"
        for number in range(1, 4):
            with service.db:
                service.db.execute("UPDATE flow_runs SET status='succeeded' WHERE id=?", (str(number),))
            assert continuations.wakes(service, "draft", number * 1000) == []
            found = continuations.wakes(service, "draft", number * 1000 + 300)
            if number < 3:
                assert len(found) == 1
                assert found[0][1]["operationId"] == item["operationId"]
                recorded_run(service, item, number + 1)
            else:
                assert found == []
        receipt = continuations.listing(service, "draft", "draft")[0]
        assert receipt["status"] == "exhausted" and receipt["attempts"] == 3 and receipt["proposalId"] is None


def test_changed_research_revision_conflicts_and_foreign_token_cannot_read(tmp_path):
    from backend.brain_opora.determinism import tokens
    with client_with_sector(tmp_path) as client:
        body, _, source = imported(client)
        changed = {**body["operations"][0], "expectedRevision": 1, "content": "New evidence"}
        assert client.post('/api/research', headers=HEADERS, json={**SCOPE, "key": "change", "operations": [changed]}).status_code == 200
        service = client.app.state.service
        assert continuations.wakes(service, "draft", 0) == []
        assert continuations.listing(service, "draft", "draft")[0]["status"] == "conflict"
        session = tokens.issue_worker(service, "draft", "draft", {"name": "reader"})
        headers = {**HEADERS, "X-Opora-Actor": "agent; name=reader", tokens.HEADER: session["token"]}
        for route in ('/api/research/continuations', '/api/research/originals/' + source['id']):
            for scope in ({**SCOPE, "workspace": "foreign"}, {**SCOPE, "project": "foreign"}):
                assert client.get(route, headers=headers, params=scope).status_code == 403


def test_import_rollback_cannot_leave_cards_without_continuation(tmp_path, monkeypatch):
    from backend.canvas import opora_events
    with client_with_sector(tmp_path) as client:
        emit = opora_events.emit_event
        def fail(*args, **kwargs):
            if kwargs.get('kind') == 'research.planning.requested':
                raise RuntimeError('outbox interrupted')
            return emit(*args, **kwargs)
        monkeypatch.setattr(opora_events, 'emit_event', fail)
        with pytest.raises(RuntimeError, match='outbox interrupted'):
            imported(client)
        db = client.app.state.service.db_for('draft')
        assert db.execute('SELECT count(*) FROM research_card_revisions').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM research_continuations').fetchone()[0] == 0


def test_same_operation_id_without_pinned_research_does_not_ack(tmp_path):
    with client_with_sector(tmp_path) as client:
        _, result, _ = imported(client)
        service = client.app.state.service
        from backend.canvas.opora_graph_proposals import OporaGraphProposals
        native = OporaGraphProposals(service)
        context = native.context(**SCOPE)
        native.create({**SCOPE, "operationId": result["continuation"]["operationId"],
            "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
            "subject": "Unrelated", "plan": {"nodes": [{"ref": "wrong", "kind": "node", "name": "Unrelated"}]}},
            {"kind": "agent", "name": "heart"})
        assert continuations.wakes(service, "draft", 0) == []
        receipt = continuations.listing(service, "draft", "draft")[0]
        assert receipt["status"] == "conflict" and receipt["proposalId"] is None


def test_proposal_source_must_match_exact_scope_and_original_revision(tmp_path):
    from backend.editor.research.planning_source import pins, validate_source
    from backend.editor.research.model import GateError
    with client_with_sector(tmp_path) as client:
        _, result, _ = imported(client)
        source = pins(result["continuation"])
        service = client.app.state.service
        assert validate_source(service, "draft", "draft", source) == source
        for changed in ({**source, "sourceRevision": 999}, {**source, "researchId": "another"}):
            with pytest.raises(GateError):
                validate_source(service, "draft", "draft", changed)
        with pytest.raises(GateError):
            validate_source(service, "draft", "other", source)


def test_assigned_original_and_older_output_remain_separate_from_imported_question(tmp_path):
    from backend.brain_opora.determinism.brain_files import brain_dir
    with client_with_sector(tmp_path) as client:
        root = vault(client, op="create", scopeNodeId="s1", discipline="ux", title="Root", text="Original").json()["fragment"]
        source = vault(client, op="research", fragmentId=root["id"], title="V1 round two", text="New question",
                       question="Isolation?", status="assigned").json()["fragment"]
        path = brain_dir(client.app.state.service, 'draft') / 'dilna/out/research' / (source['id'] + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {"fragmentId": source['id'], "digest": {"verdict": "feasible"}, "facts": []}
        path.write_text(json.dumps(artifact), encoding='utf-8')
        route = '/api/research/originals/' + source['id']
        original = client.get(route, params=SCOPE).json()
        assert original['original']['details']['research']['status'] == 'assigned'
        assert original['originalOutput']['content'] == artifact
        assert original['originalOutput']['scopeRecorded'] is False
        response = client.post(route + '/materialize', headers=HEADERS, json={**SCOPE,
            'revision': original['sourceRevision'], 'detailsRevision': original['detailsRevision']})
        assert response.status_code == 200, response.text
        assert response.json()['cards'][0]['verification']['status'] == 'unverified'
        assert continuations.listing(client.app.state.service, 'draft', 'draft') == []
        assert client.get(route, params=SCOPE).json()['sourceHistory'] == original['sourceHistory']


@pytest.mark.parametrize('tamper', [False, True])
def test_no_accepted_context_saves_verified_initial_draft_without_acceptance(tmp_path, tamper):
    from backend.canvas.canvas_plan import apply_plan
    from backend.editor.research.planning_source import pins
    from database.repositories.opora_changesets import ChangesetRepository
    with client_with_sector(tmp_path) as client:
        _, initial, _ = imported(client, accepted_context=False)
        service = client.app.state.service
        item = initial['continuation']
        found = continuations.wakes(service, 'draft', 0)
        assert len(found) == 1 and found[0][1]['operationId'] == item['operationId']
        body = {**SCOPE, 'digest': service.view('draft', 'draft')['digest'],
                'operationId': item['operationId'], 'researchSource': pins(item),
                'plan': {'nodes': [{'ref': 'first', 'kind': 'node', 'name': 'First research task',
                                    'text': 'Pinned evidence and explicit uncertainty',
                                    'spec': {'goal': 'Verify evidence', 'acceptance': 'Review succeeds'}}]}}
        made = apply_plan(service, body, actor='agent', operation_actor={'kind': 'agent', 'name': 'heart'})
        assert apply_plan(service, body, actor='agent', operation_actor={'kind': 'agent', 'name': 'heart'}) == made
        assert ChangesetRepository(service.db_for('draft'), 'draft', 'draft').head() is None
        if tamper:
            document = next(doc for doc in made['canvasDraft']['documents'] if doc['kind'] == 'text')
            with service.db_for('draft'):
                service.texts.save_in_transaction(('draft', document['ownerWorkspace'], document['nodeId']),
                                                  document['revision'], 'Changed after write')
        assert continuations.wakes(service, 'draft', 100) == []
        stored = continuations.listing(service, 'draft', 'draft')[0]
        assert stored['proposalId'] is None
        if tamper:
            assert stored['status'] == 'conflict'
        else:
            assert stored['status'] == 'complete' and stored['resultKind'] == 'canvasDraft'
            assert stored['canvasDraft'] == made['canvasDraft']
            assert stored['acceptedHeadAtReadback'] is None


def test_content_only_proposal_is_a_real_planning_result(tmp_path):
    from backend.canvas.opora_graph_proposals import OporaGraphProposals
    from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
    from backend.editor.research.planning_source import pins
    with client_with_sector(tmp_path) as client:
        _, result, _ = imported(client)
        service = client.app.state.service
        native = OporaGraphProposals(service)
        context = native.context(**SCOPE)
        state = DesktopV3State(service).current('draft', 'draft')
        target = next(n['id'] for n in service.view('draft', 'draft')['graph']['nodes'] if n['kind'] == 'node')
        spec = service.specs.read(('draft', 'draft', target))
        made = native.create({**SCOPE, 'operationId': result['continuation']['operationId'],
            'parentRevision': context['acceptedHead'], 'expectedGraphDigest': context['graphDigest'],
            'subject': 'Research clarification', 'plan': {'draftVersion': 3, 'researchSource': pins(result['continuation']),
                'extend': [{'node': '@' + target, 'expectedRevision': state['revision'],
                            'spec': {'expectedRevision': spec['revision'], 'fields': {'goal': 'Clarified with partial evidence'}}}]}},
            {'kind': 'agent', 'name': 'heart'})
        assert made['resultGraph'] == made['baseGraph']
        assert continuations.wakes(service, 'draft', 0) == []
        assert continuations.listing(service, 'draft', 'draft')[0]['proposalId'] == made['id']


def test_materialize_new_round_updates_same_card_without_losing_manual_refs(tmp_path):
    from backend.editor.research.model import CARD
    with client_with_sector(tmp_path) as client:
        _, _, source = imported(client)
        route = '/api/research/originals/' + source['id']
        original = client.get(route, params=SCOPE).json()
        first_body = {**SCOPE, 'revision': original['sourceRevision'], 'detailsRevision': original['detailsRevision']}
        first = client.post(route + '/materialize', headers=HEADERS, json=first_body).json()['cards'][0]
        changed = {key: first[key] for key in CARD}
        changed['refs']['nodeIds'] = ['s1']
        assert client.post('/api/research', headers=HEADERS, json={**SCOPE, 'key': 'manual-link', 'operations': [
            {**changed, 'op': 'card', 'id': first['id'], 'expectedRevision': first['revision']}]}).status_code == 200
        details = original['original']['details']['research']
        update = vault(client, headers=HEADERS, op='research-update', fragmentId=source['id'],
            expectedRevision=source['revision'], note='Second research round', **{**details, 'round': 2, 'status': 'assigned'})
        assert update.status_code == 200, update.text
        latest = client.get(route, params=SCOPE).json()
        body = {**SCOPE, 'revision': latest['sourceRevision'], 'detailsRevision': latest['detailsRevision']}
        response = client.post(route + '/materialize', headers=HEADERS, json=body)
        assert response.status_code == 200, response.text
        second = response.json()['cards'][0]
        assert second['id'] == first['id'] and second['revision'] == first['revision'] + 2
        assert second['refs']['nodeIds'] == ['s1']
        assert json.loads(second['content'])['originalRunStatus'] == 'assigned'
        assert len(second['content']) < 2000
        assert client.post(route + '/materialize', headers=HEADERS, json=body).json() == response.json()
        assert client.post(route + '/materialize', headers=HEADERS, json=first_body).status_code == 409


def test_original_multiple_mapped_questions_requires_explicit_reconciliation(tmp_path):
    with client_with_sector(tmp_path) as client:
        _, _, source = imported(client)
        extra = card('other-map', kind='question')
        extra['refs']['fragmentIds'] = [source['id']]
        assert client.post('/api/research', headers=HEADERS, json={**SCOPE, 'key': 'other-map',
                          'operations': [extra]}).status_code == 200
        route = '/api/research/originals/' + source['id']
        original = client.get(route, params=SCOPE).json()
        response = client.post(route + '/materialize', headers=HEADERS, json={**SCOPE,
            'revision': original['sourceRevision'], 'detailsRevision': original['detailsRevision']})
        assert response.status_code == 409 and response.json()['code'] == 'research_mapping_conflict'
