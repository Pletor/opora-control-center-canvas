"""Archived workspace budget history and human cancellation need no live graph."""
from backend.canvas.opora_execution_budget_cancel import cancel
from backend.canvas.opora_execution_budgets import ExecutionBudgets
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_reconciliation import (
    reconciliation_project as reconciliation_project,  # noqa: PLC0414 - shared pytest fixture.
)
from backend.canvas.test_opora_review_fixtures import (
    HUMAN,
)
from backend.canvas.test_opora_review_fixtures import (
    evidence_project as evidence_project,  # noqa: PLC0414 - shared pytest fixture.
)
from backend.project.worktrees.test_workspace_archive import Hooks, Sessions
from backend.project.worktrees.workspace_archive import WorkspaceArchive


def test_real_archive_preserves_budget_history_and_cancellation(reconciliation_project):
    service,scope,pin=reconciliation_project
    budgets=ExecutionBudgets(service)
    policy=budgets.configure({**scope,'nodeId':'card','expectedPolicyHead':None,
        'expectedAcceptedHead':pin['expectedAcceptedHead'],'requestId':'budget',
        'limits':{'maxRunSeconds':60,'maxAttempts':2,'maxRepairRounds':0}},HUMAN)
    authority=ExecutionResults(service)
    context=authority.context(**scope,node='card')
    execution=authority.claim({**scope,'nodeId':'card','expectedAcceptedHead':context['acceptedHead'],
        'expectedContextVersion':context['contextVersion'],'expectedBudgetPolicyHead':policy['policyHead'],
        'previousExecutionId':None,'requestId':'claim','ttlSeconds':60},'agent:archived')
    authority.release(execution['executionId'],{**scope,'token':execution['token'],'epoch':execution['epoch']})
    result=WorkspaceArchive(service,Sessions(),Hooks()).archive(scope['workspace'],
        {'project':scope['project'],'reason':'Budget archive proof','confirmed':True})
    assert result['archived']==scope['workspace']
    current=budgets.context(**scope,nodeId='card',actor='human')
    assert not current['canConfigure'] and current['canCancel'] and current['attemptsUsed']==1
    assert len(budgets.history(**scope,nodeId='card')['allocations'])==1
    cancelled=cancel(service,execution['executionId'],{**scope,'epoch':execution['epoch'],'requestId':'cancel-archive'},HUMAN)
    assert cancelled['state']=='released'
