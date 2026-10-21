"""Durable consumption survives legacy migration, owner changes, races and restarts."""
import copy
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_execution_budget_cancel import cancel
from backend.canvas.opora_execution_budgets import ExecutionBudgets
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_changesets import HUMAN, SCOPE, accept, propose
from backend.canvas.test_opora_execution_budgets import (  # noqa: F401
    LIMITS,
    configure,
    v2,
)
from backend.canvas.test_opora_execution_budgets import (
    authority as authority,  # noqa: PLC0414 - shared pytest fixture.
)
from backend.canvas.test_opora_execution_budgets import (
    service as service,  # noqa: PLC0414 - shared pytest fixture.
)
from backend.canvas.test_opora_executions import claim, credentials
from database.repositories.opora_execution_budgets import Budgets
from database.repositories.opora_executions import Executions


def test_all_legacy_rows_beyond_ui_history_limit_seed_once_and_never_reset(authority):
    first=claim(authority)
    authority.release(first['executionId'],credentials(first))
    db=authority.canvas.db_for('draft')
    original=Executions(db,**SCOPE).read(first['executionId'])
    with db:
        db.execute('BEGIN IMMEDIATE')
        for sequence in range(102):
            row=copy.deepcopy(original)
            row['executionId']=uuid.uuid4().hex
            row['epoch']=sequence+2
            Executions(db,**SCOPE).insert(row,'agent:legacy-other',f'legacy-{sequence}','a'*64)
    assert len(authority.history(**SCOPE)['executions'])==100
    result=configure(authority,limits={'maxRunSeconds':60,'maxAttempts':100,'maxRepairRounds':0})
    assert result['family']['attempts']==103
    assert result['family']['repairRounds']==0
    updated=configure(authority,'policy2',{'maxRunSeconds':120,'maxAttempts':99,'maxRepairRounds':0})
    assert updated['family']['attempts']==103
    with pytest.raises(ValueError,match='exhausted'):
        v2(authority,'over-budget','agent:new-owner')


def test_repair_classification_imports_reported_boundary_and_counts_legacy_successors(authority):
    first=claim(authority)
    authority.submit(first['executionId'],{**credentials(first),'requestId':'legacy-result','result':{'summary':'reported'}})
    later=claim(authority,'legacy-repair')
    authority.release(later['executionId'],credentials(later))
    result=configure(authority)
    assert result['family']['attempts']==2 and result['family']['repairRounds']==1
    with pytest.raises(ValueError,match='repair'):
        v2(authority)


def test_last_slot_two_independent_connections_only_one_allocation(authority):
    configure(authority,limits={'maxRunSeconds':60,'maxAttempts':1,'maxRepairRounds':0})
    context=authority.context(**SCOPE,node='a')
    payload={**SCOPE,'nodeId':'a','expectedAcceptedHead':context['acceptedHead'],'expectedContextVersion':context['contextVersion'],
        'requestId':'race','ttlSeconds':60,'expectedBudgetPolicyHead':context['budget']['policyHead'],'previousExecutionId':None}
    other=CanvasService(authority.canvas.root)
    barrier=Barrier(2)
    def run(domain,owner):
        barrier.wait()
        try:
            return domain.claim(payload,owner)
        except ValueError:
            return None
    try:
        with ThreadPoolExecutor(2) as pool:
            left=pool.submit(run,authority,'agent:one')
            right=pool.submit(run,ExecutionResults(other),'agent:two')
            assert sum(value is not None for value in (left.result(),right.result()))==1
        family=ExecutionBudgets(authority.canvas).context(**SCOPE,nodeId='a')['family']
        assert family['attempts']==1
    finally:
        other.close()


def test_deleted_result_cannot_return_reported_family_to_retry_phase(authority):
    configure(authority, limits={'maxRunSeconds':60,'maxAttempts':3,'maxRepairRounds':0})
    first=v2(authority)
    authority.submit(first['executionId'],{**credentials(first),'requestId':'result','result':{'summary':'reported'}})
    db=authority.canvas.db_for('draft')
    with db:
        db.execute('DELETE FROM opora_execution_results WHERE execution_id=?',(first['executionId'],))
    context=authority.context(**SCOPE,node='a')
    assert not context['available']
    assert context['budget']['family']['hasReported']
    assert context['budget']['attemptsUsed']==1
    assert context['budget']['remainingAttempts']==2
    with pytest.raises(ValueError,match='repair'):
        authority.claim({**SCOPE,'nodeId':'a','expectedAcceptedHead':first['acceptedRevision'],
            'expectedContextVersion':first['assignment']['contextVersion'],'requestId':'after-result-delete','ttlSeconds':60,
            'expectedBudgetPolicyHead':first['budget']['policyHead'],
            'previousExecutionId':first['executionId']},'agent:another')
    assert Budgets(db,**SCOPE,node='a').family(first['acceptedRevision'])['attempts']==1


def test_policy_change_during_run_does_not_extend_or_replace_allocation(authority):
    configure(authority)
    first=v2(authority)
    configure(authority,'new-policy',{'maxRunSeconds':3600,'maxAttempts':4,'maxRepairRounds':2})
    renewed=authority.heartbeat(first['executionId'],{**credentials(first),'ttlSeconds':3600})
    assert renewed['budget']==first['budget'] and renewed['expiresAt']<=first['budget']['runDeadlineAt']


def test_predecessor_cas_request_replay_and_v2_never_downgrades(authority):
    with pytest.raises(ValueError,match='enrolled'):
        v2(authority)
    configure(authority)
    first=v2(authority)
    replay=authority.claim({**SCOPE,'nodeId':'a','expectedAcceptedHead':first['acceptedRevision'],
        'expectedContextVersion':first['assignment']['contextVersion'],'requestId':'run','ttlSeconds':300,
        'expectedBudgetPolicyHead':first['budget']['policyHead'],'previousExecutionId':None},'agent:worker')
    assert replay['executionId']==first['executionId'] and replay['budget']==first['budget']
    authority.release(first['executionId'],credentials(first))
    with pytest.raises(ValueError,match='predecessor'):
        v2(authority,'wrong',previous='f'*32)
    second=v2(authority,'second')
    assert second['budget']['attempt']==2
    late=cancel(authority.canvas,first['executionId'],{**SCOPE,'epoch':first['epoch'],'requestId':'cancel-old'},HUMAN)
    assert late['state']=='released'
    assert authority.heartbeat(second['executionId'],{**credentials(second),'ttlSeconds':60})['state']=='running'


def test_new_accepted_revision_needs_explicit_human_policy_and_old_family_stays(authority):
    initial=configure(authority)
    first=v2(authority)
    authority.release(first['executionId'],credentials(first))
    change=propose(authority.canvas,('b',))
    new=accept(authority.canvas,change,first['acceptedRevision'])
    context=authority.context(**SCOPE,node='a')
    assert context['executionProtocolVersion']==2 and not context['available']
    with pytest.raises(ValueError,match='policy'):
        v2(authority,'new-head')
    published=configure(authority,'new-family')
    assert published['family']['attempts']==0 and published['family']['id']!=initial['family']['id']
    second=v2(authority,'new-head')
    assert second['budget']['attempt']==1 and second['acceptedRevision']==new['id']
    old=Budgets(authority.canvas.db_for('draft'),**SCOPE,node='a').family(first['acceptedRevision'])
    assert old['attempts']==1


def test_missing_enrollment_and_tampered_allocation_fail_closed(authority):
    configure(authority)
    first=v2(authority)
    db=authority.canvas.db_for('draft')
    with db:
        db.execute('DELETE FROM opora_execution_budget_enrollment')
    with pytest.raises(ValueError,match='enrollment'):
        claim(authority,'downgrade')
    with db:
        db.execute('UPDATE opora_execution_budget_ledger SET content=?',('{}',))
    with pytest.raises(ValueError):
        authority.heartbeat(first['executionId'],{**credentials(first),'ttlSeconds':60})


def test_deleted_ledger_tail_blocks_future_admission_after_lease_release(authority):
    configure(authority)
    first=v2(authority)
    authority.release(first['executionId'],credentials(first))
    db=authority.canvas.db_for('draft')
    with db:
        db.execute('DELETE FROM opora_execution_budget_ledger WHERE id=?',(first['budget']['allocationId'],))
    context=authority.context(**SCOPE,node='a')
    assert not context['available']
    with pytest.raises(ValueError,match='incomplete'):
        authority.claim({**SCOPE,'nodeId':'a','expectedAcceptedHead':first['acceptedRevision'],
            'expectedContextVersion':first['assignment']['contextVersion'],'requestId':'after-tail-delete','ttlSeconds':60,
            'expectedBudgetPolicyHead':first['budget']['policyHead'],'previousExecutionId':None},'agent:another')


@pytest.mark.parametrize('mutation',[{'executionProtocolVersion':None},{'executionProtocolVersion':3},{'executionProtocolVersion':True}])
def test_corrupt_protocol_cannot_bypass_immutable_budget_deadline(authority,mutation):
    configure(authority)
    first=v2(authority)
    db=authority.canvas.db_for('draft')
    with db:
        row=Executions(db,**SCOPE).read(first['executionId'])
        row.update(mutation)
        Executions(db,**SCOPE).save(row)
    with pytest.raises(ValueError,match='protocol'):
        authority.heartbeat(first['executionId'],{**credentials(first),'ttlSeconds':60})


def test_deleted_clock_authority_after_allocation_cannot_silently_reinitialize(authority):
    configure(authority)
    first=v2(authority)
    db=authority.canvas.db_for('draft')
    with db:
        db.execute('DELETE FROM opora_execution_budget_clock')
    context=authority.context(**SCOPE,node='a')
    assert context['executionProtocolVersion']==2 and not context['available']
    with pytest.raises(ValueError,match='clock'):
        authority.heartbeat(first['executionId'],{**credentials(first),'ttlSeconds':60})
    assert db.execute('SELECT frozen FROM opora_execution_budget_clock').fetchone()[0]==1
