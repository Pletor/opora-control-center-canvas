"""Real factory HTTP validates human policy, strict v2 admission and cancellation."""
import pytest

from backend.api.editor.test_opora_changeset_routes import AGENT
from backend.api.editor.test_opora_execution_routes import BASE, payload
from backend.api.editor.test_opora_execution_routes import (
    client as client,  # noqa: PLC0414 - shared pytest fixture.
)
from backend.canvas.test_canvas_plan import HEADERS, SCOPE

BUDGETS='/api/oporahub/execution-budgets'
LIMITS={'maxRunSeconds':60,'maxAttempts':3,'maxRepairRounds':1}


def policy_payload(client):
    expected=payload(client)
    return {**SCOPE,'nodeId':'n0','expectedPolicyHead':None,'expectedAcceptedHead':expected['expectedAcceptedHead'],
            'requestId':'policy','limits':LIMITS}


def test_actual_factory_policy_identity_cas_v2_receipt_cancel_and_replay(client):
    data=policy_payload(client)
    assert client.post(BUDGETS,headers=AGENT,json=data).status_code==403
    client.cookies.clear()
    assert client.post(BUDGETS,headers=HEADERS,json=data).status_code==428
    client.get('/api/access/ui-session',headers={'sec-fetch-site':'same-origin','sec-fetch-mode':'cors'})
    first=client.post(BUDGETS,headers=HEADERS,json=data)
    assert first.status_code==200,first.text
    assert client.post(BUDGETS,headers=HEADERS,json=data).json()==first.json()
    assert client.post(BUDGETS,headers=HEADERS,json={**data,'limits':{**LIMITS,'maxAttempts':4}}).status_code==409
    legacy=payload(client)
    assert client.post(BASE+'/claim',headers=AGENT,json=legacy).status_code==409
    context=client.get(BASE+'/context',params={**SCOPE,'nodeId':'n0'}).json()
    assert context['executionProtocolVersion']==2 and context['budget']['enrolled']
    claimed=client.post(BASE+'/claim',headers=AGENT,json={**legacy,'requestId':'budget-run',
        'expectedBudgetPolicyHead':first.json()['policyHead'],'previousExecutionId':None})
    assert claimed.status_code==200,claimed.text
    run=claimed.json()
    assignment=client.get(BASE+f"/{run['executionId']}/assignment",params=SCOPE,
        headers={**AGENT,'X-Opora-Execution-Token':run['token']})
    assert assignment.json()['budget']==run['budget'] and 'token' not in assignment.json()
    history=client.get(BASE,params=SCOPE,headers=AGENT)
    assert history.json()['executions'][0]['owner'].startswith('agent:') and run['token'] not in history.text
    cancellation={**SCOPE,'epoch':run['epoch'],'requestId':'cancel'}
    assert client.post(BUDGETS+f"/{run['executionId']}/cancel",headers=AGENT,json=cancellation).status_code==403
    cancelled=client.post(BUDGETS+f"/{run['executionId']}/cancel",headers=HEADERS,json=cancellation)
    assert cancelled.status_code==200 and cancelled.json()['state']=='cancelled'
    assert client.post(BUDGETS+f"/{run['executionId']}/cancel",headers=HEADERS,json=cancellation).json()==cancelled.json()
    assert client.post(BASE+f"/{run['executionId']}/heartbeat",headers=AGENT,
        json={**SCOPE,'token':run['token'],'epoch':run['epoch'],'ttlSeconds':60}).status_code==409
    stored=client.get(BUDGETS+'/history',params={**SCOPE,'nodeId':'n0'})
    assert stored.status_code==200 and len(stored.json()['allocations'])==1
    assert run['token'] not in stored.text


@pytest.mark.parametrize('extra',[{'by':{'kind':'human'}},{'maxAttempts':100},{'limits':[]},{'nodeId':[]},
    {'limits':{'maxRunSeconds':True,'maxAttempts':1,'maxRepairRounds':0}}])
def test_policy_malformed_and_spoof_payload_are_safe_conflicts(client,extra):
    response=client.post(BUDGETS,headers=HEADERS,json={**policy_payload(client),**extra})
    assert response.status_code==409,response.text


def test_readonly_card_cannot_configure_but_history_remains(client,monkeypatch):
    data=policy_payload(client)
    assert client.post(BUDGETS,headers=HEADERS,json=data).status_code==200
    service=client.app.state.service
    original=service.view
    monkeypatch.setattr(service,'view',lambda *args:{**original(*args),'readOnly':True})
    context=client.get(BUDGETS,params={**SCOPE,'nodeId':'n0'}).json()
    assert not context['canConfigure'] and context['canCancel']
    assert client.post(BUDGETS,headers=HEADERS,json={**data,'requestId':'readonly','expectedPolicyHead':context['policyHead']}).status_code==409
    assert client.get(BUDGETS+'/history',params={**SCOPE,'nodeId':'n0'}).status_code==200
