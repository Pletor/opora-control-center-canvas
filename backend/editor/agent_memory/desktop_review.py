"""Immutable preparation receipts; native human routes remain the sole applied authority."""
import copy
import json
from urllib.parse import urlencode

from backend.canvas.graph import digest
from backend.canvas.operation_receipts import Receipt
from backend.canvas.payload_errors import NextStep
from backend.editor.agent_memory.confirm_proposals import prepare_confirmation
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_memory.memory_items import (
    MAX_BATCH,
    MemoryItems,
    _review_change,
    _validated,
)

KIND = 'desktop-human-preparation'
APPLY_KIND = 'desktop-human-application'
PATHS = {'grant_autonomy': '/api/desktop-v3/autonomy', 'confirm_sector_proposals': '/api/desktop-v3/confirm-proposals',
         'review_rule': '/api/desktop-v3/rule-review', 'review_rules': '/api/desktop-v3/rule-review-batch'}
FIELDS = {'grant_autonomy': {'sectorId', 'until', 'note', 'expectedRevision'},
          'confirm_sector_proposals': {'sectorId', 'nodeIds', 'expectedRevision'},
          'review_rule': {'id', 'decision', 'expected'}, 'review_rules': {'items', 'decision'}}


def observed(service, project, workspace):
    view = service.view(project, workspace)
    stored = DesktopV3State(service).read(project, workspace)
    return {'graphDigest': view['digest'], 'stateRevision': stored['revision'], 'stateDigest': digest(stored['state'])}


def validate(service, project, workspace, operation, data):
    if operation not in PATHS or not isinstance(data, dict) or set(data) != FIELDS[operation]:
        raise ValueError('Invalid native Desktop review fields.')
    state = DesktopV3State(service)
    stored = state.read(project, workspace)
    if stored['readOnly']:
        raise ValueError('Desktop review requires a writable workspace.')
    payload = {'project': project, 'workspace': workspace, **data}
    if operation == 'grant_autonomy':
        state.prepare_autonomy(payload)
    elif operation == 'confirm_sector_proposals':
        prepare_confirmation(state, payload, actor='agent')
    else:
        entries = [{'id': data['id'], 'expected': data['expected']}] if operation == 'review_rule' else data['items']
        if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_BATCH:
            raise ValueError('Invalid native rule review batch.')
        if any(not isinstance(item, dict) or set(item) != {'id', 'expected'} for item in entries):
            raise ValueError('Rule review requires id and exact expected preimage.')
        if len({item['id'] for item in entries if isinstance(item['id'], str)}) != len(entries):
            raise ValueError('Rule review requires distinct string identifiers.')
        native = MemoryItems(state)
        items = copy.deepcopy(stored['state']['rules'])
        nodes = None
        for entry in entries:
            change = _validated(_review_change({'project': project, 'workspace': workspace,
                                                **entry, 'decision': data['decision']}))
            nodes = native._change('rules', items, change, nodes, project, workspace)
    return payload


def prepare(service, project, workspace, operation, data, request_id, author):
    receipt = Receipt({'project': project, 'workspace': workspace, 'operation': operation,
                       'input': data, 'operationId': request_id}, KIND, author)
    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        prior = receipt.replay(db)
        if prior is not None:
            return prior
        payload = validate(service, project, workspace, operation, data)
        value = {'id': request_id, 'project': project, 'workspace': workspace, 'operation': operation,
                 'payload': payload, 'observed': observed(service, project, workspace), 'author': author}
        target_ids = {data.get('sectorId')} | set(data.get('nodeIds', []))
        value['targets'] = [{'id': node['id'], 'name': node['name'], 'kind': node['kind']}
                            for node in service.view(project, workspace)['graph']['nodes'] if node['id'] in target_ids]
        value['digest'] = digest(value)
        result = {'state': 'awaiting_human', 'applied': False, 'review': value,
                  'url': '/?' + urlencode({'project': project, 'workspace': workspace, 'screen': 'canvas',
                                          'environment': 'project', 'desktopReview': request_id})}
        with db:
            receipt.begin(db)
            receipt.complete(db, result)
        return result


def read(service, project, workspace, identifier):
    with service.reading(project):
        service.view(project, workspace)
        row = service.db_for(project).execute('SELECT status,response FROM canvas_operation_receipts WHERE '
            'project_id=? AND workspace_id=? AND operation_kind=? AND operation_id=?',
            (project, workspace, KIND, identifier)).fetchone()
        if row is None or row['status'] != 'complete':
            raise ValueError('Desktop review preparation does not exist in this scope.')
        value = json.loads(row['response'])['review']
        if digest({key: item for key, item in value.items() if key != 'digest'}) != value['digest']:
            raise NextStep('Desktop review integrity check failed.', code='review_integrity', hint='Do not apply this preparation.')
        current = observed(service, project, workspace)
        application = service.db_for(project).execute('SELECT status,response FROM canvas_operation_receipts WHERE '
            'project_id=? AND workspace_id=? AND operation_kind=? AND operation_id=?',
            (project, workspace, APPLY_KIND, identifier)).fetchone()
        if application is not None:
            complete = application['status'] == 'complete'
            return {'review': value, 'current': current, 'state': 'applied' if complete else 'incomplete',
                    'applied': complete, 'application': json.loads(application['response']),
                    'nativeState': DesktopV3State(service).read(project, workspace),
                    'nativePath': PATHS[value['operation']]}
        fresh = current == value['observed']
        if fresh:
            try:
                validate(service, project, workspace, value['operation'], {key: item for key, item in value['payload'].items() if key not in ('project', 'workspace')})
            except ValueError:
                fresh = False
        return {'review': value, 'current': current, 'state': 'ready' if fresh else 'stale',
                'applied': False, 'nativePath': PATHS[value['operation']]}


def apply(service, project, workspace, identifier, expected_digest, actor):
    if actor != 'human':
        from backend.brain_opora.determinism.gate_payloads import GateError
        raise GateError(403, 'human_required', 'Desktop review requires an authenticated human.', 'Open the exact review in the UI.')
    with service.graph_lock_for(project), service.lock_for(project):
        prepared = read(service, project, workspace, identifier)
        review = prepared['review']
        if review['digest'] != expected_digest:
            raise NextStep('Desktop review digest does not match.', code='review_conflict', hint='Open the exact stored review.')
        receipt = Receipt({'project': project, 'workspace': workspace, 'operationId': identifier,
                           'reviewDigest': expected_digest}, APPLY_KIND, {'kind': actor})
        db = service.db_for(project)
        replay = receipt.replay(db)
        if replay is not None:
            return replay
        if prepared['state'] != 'ready':
            raise NextStep('Desktop review is stale or does not match.', code='review_conflict', hint='Inspect current native state; do not silently refresh this preparation.')
        with db:
            receipt.begin(db, {'reviewDigest': expected_digest, 'observed': review['observed']})
        try:
            state = DesktopV3State(service)
            operation, payload = review['operation'], review['payload']
            if operation == 'grant_autonomy':
                result = state.set_autonomy(payload)
            elif operation == 'confirm_sector_proposals':
                from backend.editor.agent_memory.confirm_proposals import confirm_proposals
                result = confirm_proposals(state, payload, actor=actor)
            elif operation == 'review_rule':
                result = MemoryItems(state).review_rule(payload, actor=actor)
            else:
                result = MemoryItems(state).review_rules(payload, actor=actor)
            after = state.read(project, workspace)
            if result.get('revision') != after['revision']:
                raise NextStep('Native Desktop result does not match saved revision.', code='operation_incomplete', hint='Inspect native state before reconciliation.')
            if 'state' in result and result['state'] != after['state']:
                raise NextStep('Native Desktop result does not match saved content.', code='operation_incomplete', hint='Inspect native state before reconciliation.')
            if operation == 'review_rule':
                actual = next((item for item in after['state']['rules'] if item['id'] == payload['id']), None)
                if result['item'] != actual:
                    raise NextStep('Native rule readback differs.', code='operation_incomplete', hint='Inspect native state.')
            elif operation == 'review_rules':
                actual = {item['id']: item for item in after['state']['rules']}
                if any(item['item'] != actual.get(item['id']) for item in result['items']):
                    raise NextStep('Native rules readback differs.', code='operation_incomplete', hint='Inspect native state.')
            response = {'state': 'applied', 'applied': True, 'reviewDigest': review['digest'], 'result': result,
                        'nativeState': after}
            with db:
                receipt.complete(db, response)
            return response
        except Exception as error:
            try:
                unchanged = observed(service, project, workspace) == review['observed']
            except Exception:
                unchanged = False
            if unchanged:
                with db:
                    db.execute("DELETE FROM canvas_operation_receipts WHERE project_id=? AND workspace_id=? AND operation_kind=? AND operation_id=? AND status='pending'", receipt.scope)
                raise
            raise NextStep(f"Desktop operation {identifier} has an uncertain native result.",
                code='operation_incomplete', hint=f"Read the exact Desktop review and reconcile pending operation {identifier}; do not repeat it blindly.") from error
