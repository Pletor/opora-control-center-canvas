"""Budget policy and v2 allocations preserve existing execution authority fences."""
import time

import pytest

from backend.canvas.opora_execution_budget_cancel import cancel
from backend.canvas.opora_execution_budgets import ExecutionBudgets
from backend.canvas.test_opora_changesets import HUMAN, SCOPE
from backend.canvas.test_opora_executions import (
    authority as authority,  # noqa: PLC0414 - shared pytest fixture.
)
from backend.canvas.test_opora_executions import (
    claim,
    credentials,
)
from backend.canvas.test_opora_executions import (
    service as service,  # noqa: PLC0414 - shared pytest fixture.
)

LIMITS={'maxRunSeconds':60,'maxAttempts':3,'maxRepairRounds':1}


def configure(authority,request='policy',limits=None):
    context=authority.context(**SCOPE,node='a')
    budgets=ExecutionBudgets(authority.canvas)
    previous=budgets.context(**SCOPE,nodeId='a',actor='human')
    return budgets.configure({**SCOPE,'nodeId':'a','expectedPolicyHead':previous['policyHead'],
        'expectedAcceptedHead':context['acceptedHead'],'requestId':request,'limits':limits or LIMITS},HUMAN)


def v2(authority,request='run',owner='agent:worker',previous=None):
    context=authority.context(**SCOPE,node='a')
    return authority.claim({**SCOPE,'nodeId':'a','expectedAcceptedHead':context['acceptedHead'],
        'expectedContextVersion':context['contextVersion'],'requestId':request,'ttlSeconds':300,
        'expectedBudgetPolicyHead':context['budget']['policyHead'],
        'previousExecutionId':context['budget']['latestExecutionId'] if previous is None else previous},owner)


def test_policy_v2_retry_repair_and_fixed_deadline(authority):
    first_policy=configure(authority)
    with pytest.raises(ValueError,match='protocol v2'):
        claim(authority)
    first=v2(authority)
    assert first['budget']['kind']=='initial' and first['budget']['attempt']==1
    assert first['expiresAt']==first['budget']['runDeadlineAt']
    renewed=authority.heartbeat(first['executionId'],{**credentials(first),'ttlSeconds':3600})
    assert renewed['budget']==first['budget'] and renewed['expiresAt']==first['budget']['runDeadlineAt']
    authority.release(first['executionId'],credentials(first))
    second=v2(authority,'retry','agent:other')
    assert second['budget']['kind']=='retry' and second['budget']['attempt']==2
    receipt=authority.submit(second['executionId'],{**credentials(second),'requestId':'result','result':{'summary':'reported'}})
    assert receipt['budget']==second['budget'] and receipt['executionProtocolVersion']==2
    third=v2(authority,'repair')
    assert third['budget']['kind']=='repair' and third['budget']['repairRound']==1
    authority.release(third['executionId'],credentials(third))
    with pytest.raises(ValueError,match='exhausted'):
        v2(authority,'fourth')
    changed=configure(authority,'raise',{'maxRunSeconds':120,'maxAttempts':5,'maxRepairRounds':2})
    assert changed['family']['attempts']==3 and changed['policyHead']!=first_policy['policyHead']
    assert third['budget']['maxRunSeconds']==60


def test_policy_replay_cas_and_legacy_running_guard(authority):
    running=claim(authority)
    with pytest.raises(ValueError,match='Release'):
        configure(authority)
    authority.release(running['executionId'],credentials(running))
    result=configure(authority)
    assert result['family']['attempts']==1
    assert result['family']['lastExecutionId']==running['executionId']
    assert v2(authority)['budget']['kind']=='retry'
    domain=ExecutionBudgets(authority.canvas)
    old=result['policy']
    payload={**SCOPE,'nodeId':'a','expectedPolicyHead':None,'expectedAcceptedHead':old['acceptedRevision'],'requestId':'policy','limits':LIMITS}
    assert domain.configure(payload,HUMAN)==result
    with pytest.raises(ValueError,match='different'):
        domain.configure({**payload,'limits':{**LIMITS,'maxAttempts':4}},HUMAN)


def test_clock_regression_persists_freeze_without_partial_write_and_cancel_works(authority,monkeypatch):
    clock=[time.time()]
    monkeypatch.setattr('backend.canvas.opora_executions.time.time',lambda:clock[0])
    configure(authority)
    running=v2(authority)
    clock[0]-=10
    with pytest.raises(ValueError,match='clock'):
        authority.heartbeat(running['executionId'],{**credentials(running),'ttlSeconds':60})
    db=authority.canvas.db_for('draft')
    assert db.execute('SELECT frozen FROM opora_execution_budget_clock').fetchone()[0]==1
    clock[0]+=100
    with pytest.raises(ValueError,match='clock'):
        v2(authority,'after-regression')
    history=authority.history(**SCOPE)
    assert history['executions'][0]['state']=='revoked'
    result=cancel(authority.canvas,running['executionId'],{**SCOPE,'epoch':running['epoch'],'requestId':'cancel'},HUMAN)
    assert result['state']=='cancelled'
    assert cancel(authority.canvas,running['executionId'],{**SCOPE,'epoch':running['epoch'],'requestId':'cancel'},HUMAN)==result


def test_deadline_boundary_result_replay_and_cancel_keeps_reported_receipt(authority,monkeypatch):
    clock=[time.time()]
    monkeypatch.setattr('backend.canvas.opora_executions.time.time',lambda:clock[0])
    configure(authority)
    running=v2(authority)
    payload={**credentials(running),'requestId':'result','result':{'summary':'done'}}
    receipt=authority.submit(running['executionId'],payload)
    cancel(authority.canvas,running['executionId'],{**SCOPE,'epoch':running['epoch'],'requestId':'cancel-reported'},HUMAN)
    clock[0]=running['budget']['runDeadlineAt']+100
    assert authority.submit(running['executionId'],payload)==receipt
    with pytest.raises(ValueError):
        authority.submit(running['executionId'],{**payload,'requestId':'late'})


def test_allocation_failure_rolls_back_family_and_lease(authority,monkeypatch):
    configure(authority)
    from database.repositories.opora_executions import Executions
    def fail(*args):
        raise RuntimeError('injected execution write')
    monkeypatch.setattr(Executions,'insert',fail)
    with pytest.raises(RuntimeError):
        v2(authority)
    context=ExecutionBudgets(authority.canvas).context(**SCOPE,nodeId='a',actor='human')
    assert context['attemptsUsed']==0
    assert authority.canvas.db_for('draft').execute('SELECT COUNT(*) FROM card_leases').fetchone()[0]==0


@pytest.mark.parametrize('limits',[{'maxRunSeconds':True,'maxAttempts':3,'maxRepairRounds':1},
    {'maxRunSeconds':10**200,'maxAttempts':3,'maxRepairRounds':1},{'maxRunSeconds':60,'maxAttempts':1,'maxRepairRounds':1}])
def test_malformed_limits_rejected(authority,limits):
    with pytest.raises(ValueError):
        configure(authority,limits=limits)


def test_deadline_denial_keeps_highwater_and_cannot_resurrect_after_clock_regression(authority,monkeypatch):
    clock=[time.time()]
    monkeypatch.setattr('backend.canvas.opora_executions.time.time',lambda:clock[0])
    configure(authority)
    running=v2(authority)
    clock[0]=running['budget']['runDeadlineAt']
    with pytest.raises(ValueError,match='deadline'):
        authority.heartbeat(running['executionId'],{**credentials(running),'ttlSeconds':60})
    assert authority.canvas.db_for('draft').execute('SELECT high_water FROM opora_execution_budget_clock').fetchone()[0]==clock[0]
    clock[0]-=1
    with pytest.raises(ValueError,match='clock'):
        authority.heartbeat(running['executionId'],{**credentials(running),'ttlSeconds':60})
    assert authority.canvas.db_for('draft').execute('SELECT frozen FROM opora_execution_budget_clock').fetchone()[0]==1


def test_public_history_owner_is_sql_authority_and_never_token(authority):
    running=claim(authority)
    db=authority.canvas.db_for('draft')
    import json
    row=db.execute('SELECT record FROM opora_executions WHERE id=?',(running['executionId'],)).fetchone()
    stored=json.loads(row[0])
    stored['owner']='spoofed JSON owner'
    with db:
        db.execute('UPDATE opora_executions SET record=? WHERE id=?',(json.dumps(stored),running['executionId']))
    public=authority.history(**SCOPE)['executions'][0]
    assert public['owner']=='agent:worker'
    assert running['token'] not in json.dumps(public)


def test_expiry_during_context_capture_never_renews_or_accepts_budgeted_result(authority,monkeypatch):
    import backend.canvas.opora_executions as module
    clock=[time.time()]
    monkeypatch.setattr(module.time,'time',lambda:clock[0])
    configure(authority)
    first=v2(authority)
    original=module.assignment
    def slow(*args,**kwargs):
        result=original(*args,**kwargs)
        clock[0]=first['budget']['runDeadlineAt']
        return result
    monkeypatch.setattr(module,'assignment',slow)
    for action in ('heartbeat','result'):
        clock[0]=first['budget']['admittedAt']+1
        with pytest.raises(ValueError,match='authoritative|deadline|clock'):
            if action=='heartbeat':
                authority.heartbeat(first['executionId'],{**credentials(first),'ttlSeconds':60})
            else:
                authority.submit(first['executionId'],{**credentials(first),'requestId':'late','result':{'summary':'late'}})
    assert authority.canvas.db_for('draft').execute('SELECT COUNT(*) FROM opora_execution_results').fetchone()[0]==0
