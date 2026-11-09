"""Project-owned workflow and immutable draft creation reuse native schemas and stores."""
from fastapi import HTTPException
from pydantic import ValidationError
from backend.api.flow.flow_routes import WorkflowIn, DraftIn
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.flow_reads import owner
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.flow import workflows
from backend.flow.graph_check import FlowInvalid
from backend.canvas.payload_errors import NextStep

CONTRACTS = {
    'flow_routes.workflow_create': contract(('kind', 'name'), ('owner_ref',), effect='draft', replay=True,
        output='Native workflow bound to authenticated project'),
    'flow_routes.version_draft': contract(('workflow_id', 'graph'), ('parent_version_id', 'note', 'learnedFrom'),
        effect='draft', replay=True, cas='native immutable parent version', output='Native immutable draft; not activated'),
}
for _contract in CONTRACTS.values():
    _contract['test'] = 'backend/api/brain_opora/test_canvas_capability_flow_drafts.py'


def invoke(service, project, workspace, session, capability, data, request_id):
    creating = capability == 'flow_routes.workflow_create'
    try:
        body = WorkflowIn.model_validate({**data, 'project_id': project}) if creating else DraftIn.model_validate(
            {key: value for key, value in data.items() if key != 'workflow_id'})
        if not creating and body.learnedFrom and body.learnedFrom.project != project:
            raise GateError(403, 'gate_scope', 'Draft provenance belongs to another project.', 'Use evidence in the authenticated project.')

        def snapshot():
            with service.registry_lock:
                if creating:
                    return [item for item in workflows.list_workflows(service.db, project) if item['project_id'] == project]
                owner(service.db, project, workflow_id=data['workflow_id'])
                if body.parent_version_id:
                    owner(service.db, project, version_id=body.parent_version_id)
                return workflows.list_versions(service.db, data['workflow_id'])

        def action():
            with service.registry_lock:
                if creating:
                    return workflows.create_workflow(service.db, body.kind, body.name, project, body.owner_ref)
                owner(service.db, project, workflow_id=data['workflow_id'])
                meta = {key: value for key, value in (
                    ('note', (body.note or '').strip() or None),
                    ('learnedFrom', body.learnedFrom.model_dump(exclude_none=True) if body.learnedFrom else None)) if value}
                return workflows.create_draft(service.db, data['workflow_id'], body.graph, body.parent_version_id, meta=meta or None)

        def verify(before, after, result):
            found = next((item for item in after if item['id'] == result['id']), None)
            # Native workflow list adds active-version projections; compare the full created record.
            if found is None or any(found.get(key) != value for key, value in result.items()) or (not creating and result['status'] != 'draft'):
                raise NextStep('Native flow draft readback failed.', code='operation_incomplete', hint='Inspect the stored workflow/version before retrying.')

        return run(service, project, workspace, session, capability, data, request_id,
                   snapshot=snapshot, action=action, verify=verify)
    except ValidationError as error:
        raise HTTPException(422, error.errors(include_url=False, include_context=False)) from error
    except workflows.FlowNotFound as error:
        raise HTTPException(404, str(error)) from error
    except workflows.FlowConflict as error:
        raise HTTPException(409, str(error)) from error
    except FlowInvalid as error:
        raise HTTPException(422, str(error)) from error
