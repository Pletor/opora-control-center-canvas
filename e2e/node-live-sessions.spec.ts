import {test,expect} from '@playwright/test';
const live='/?screen=canvas&project=draft&workspace=draft&node=n1&mode=agents&environment=live';
// Pouze izolované UI fixtures: nejsou důkazem skutečné práce modelu.
const fixture=()=>({project:'draft',workspace:'draft',nodeId:'n1',limit:100,truncated:false,sessions:[{
  id:'fixture-binding',source:'claude',sessionId:'fixture-session',parentSessionId:null,role:'worker',
  title:'Testovací worker',project:'draft',workspace:'draft',nodeId:'n1',nodeName:'Testovací uzel',model:'fixture-model',
  status:'running',statusReason:'Ověřený testovací zdroj',sourceAvailable:true,lastActivityAt:'2026-09-11T12:00:00Z',
  boundAt:'2026-09-11T12:00:00Z',closedAt:null,events:[],metrics:{inputTokens:null,outputTokens:null,costUsd:null},sourceLabel:'Izolovaná fixture',
}]});
test.beforeAll(async({request})=>{
  const view=await(await request.get('/api/view?project=draft&workspace=draft')).json();
  const response=await request.post('/api/graph',{headers:{Origin:'http://127.0.0.1:8782'},data:{project:'draft',workspace:'draft',digest:view.digest,
    graph:{nodes:[{id:'n1',parentId:null,kind:'node',name:'Testovací uzel',purpose:'',x:100,y:100}],edges:[]}}});
  expect(response.ok()).toBeTruthy();
});
test('Node action opens dedicated Live layout, keeps deep link and never starts a run',async({page})=>{
  const writes:string[]=[];
  page.on('request',r=>{if(r.method()==='POST')writes.push(r.url())});
  await page.goto('/?screen=canvas&project=draft&workspace=draft&node=n1&mode=structure&environment=editor');
  await expect(page.getByTestId('node-live-run-action')).toBeVisible();
  await page.getByTestId('node-live-run-action').click();
  await expect(page.getByRole('region',{name:'Práce na uzlu — živé sessions'})).toBeVisible();
  expect(new URL(page.url()).searchParams.get('node')).toBe('n1');
  await page.reload();
  await expect(page.getByRole('region',{name:'Práce na uzlu — živé sessions'})).toBeVisible();
  await page.getByRole('button',{name:'Dokumentační běhy',exact:true}).click();
  await expect(page.locator('.live-desktop')).toBeVisible();
  await page.getByRole('button',{name:'Práce na uzlu',exact:true}).click();
  await expect(page.locator('.node-sessions')).toBeVisible();
  expect(writes).toEqual([]);
});
test('API failure cannot keep showing an unverified running badge',async({page})=>{
  let failed=false;
  await page.route('**/api/node-sessions?*',route=>route.fulfill({status:failed?503:200,contentType:'application/json',body:JSON.stringify(failed?{error:'Testovací výpadek'}:fixture())}));
  await page.goto(live);
  await expect(page.locator('.ns-card .ns-status')).toHaveText('Běží');
  failed=true;
  await page.getByRole('button',{name:'Obnovit (jen čtení)'}).click();
  await expect(page.locator('.ns-source-error')).toBeVisible();
  await expect(page.locator('.ns-status-running')).toHaveCount(0);
  await expect(page.locator('.ns-card .ns-status')).toHaveText('Neznámý stav');
});
test('Malformed or foreign-scope records fail safely without page errors',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/node-sessions?*',route=>{
    const data=fixture();(data.sessions[0] as any).metrics=null;
    return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.goto(live);
  await expect(page.locator('.ns-source-error')).toBeVisible();
  expect(errors).toEqual([]);
});
