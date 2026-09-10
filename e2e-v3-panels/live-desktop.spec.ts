import {test, expect} from '@playwright/test';

const project = 'live-desktop-test';
const workspace = 'draft';
const proposal = (id: string, output: string, status = 'completed') => ({id, project_id: project, workspace, layer: '', digest: 'digest', status, message: `Úkol ${id}`, output, provider_billing: 'unknown', created_at: '2026-09-10T10:00:00Z', updated_at: '2026-09-10T10:01:00Z'});

test('desktop Live Run selects real proposal outputs in three columns and seven functional tabs without starting models', async ({page, request}) => {
  await request.post('/api/test/seed-planning-runs', {data: {project, runs:[proposal('proposal-a','Přesný uložený výstup A'), proposal('proposal-b','Přesný uložený výstup B')]}});
  const writes: string[] = [];
  page.on('request', r => {if(r.method()==='POST') writes.push(r.url());});
  await page.goto(`/?panel=live&project=${project}&workspace=${workspace}`);
  const shelf=page.getByRole('complementary',{name:'Sessions projektu'});
  const detail=page.getByRole('region',{name:'Detail session'});
  await expect(shelf).toBeVisible();
  await shelf.getByRole('button',{name:/proposal-b/}).click();
  await expect(detail.getByTestId('live-run-output')).toHaveText('Přesný uložený výstup B');
  await expect(detail).toContainText('Návrh není implementace');
  await expect(page.getByRole('tab')).toHaveCount(7);
  await page.getByRole('tab',{name:'3 Náklady a výkon'}).click();
  await expect(detail).toContainText('nedostupné');
  await expect(detail).not.toContainText('unknown USD');
  await page.getByRole('tab',{name:'7 Kontext a osa'}).click();
  await expect(detail).toContainText('2026-09-10T10:01:00Z');
  await expect(page.getByRole('button',{name:'Odeslat boční dotaz'})).toBeDisabled();
  const a=await shelf.boundingBox(),b=await detail.boundingBox(),c=await page.getByRole('complementary',{name:'Boční vlákno a ovládání'}).boundingBox();
  expect(a!.x+a!.width).toBeLessThanOrEqual(b!.x+1);
  expect(b!.x+b!.width).toBeLessThanOrEqual(c!.x+1);
  expect(writes).toEqual([]);
});

test('a stalled optional handoff source does not delay planning results',async({page})=>{
  let release!:()=>void;const gate=new Promise<void>(r=>{release=r;});
  await page.route('**/api/task-handoffs?*',async route=>{await gate;await route.fulfill({json:{runs:[]}});});
  await page.route('**/api/llm/runs?*',route=>route.fulfill({json:{runs:[proposal('available','Skutečný dostupný výstup')],active:null}}));
  await page.goto(`/?panel=live&project=${project}&workspace=${workspace}`);
  try{await expect(page.getByTestId('live-run-output')).toHaveText('Skutečný dostupný výstup',{timeout:1500});}finally{release();}
});

test('manual refresh preserves the selected run and detail tab', async ({page})=>{
  let reads=0;let release!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  await page.route('**/api/llm/runs?*',async route=>{reads++;if(reads===2)await gate;await route.fulfill({json:{runs:[proposal('first','A'),proposal('second','B')],active:null}});});
  await page.goto(`/?panel=live&project=${project}&workspace=${workspace}`);
  await page.getByRole('complementary',{name:'Sessions projektu'}).getByRole('button',{name:/second/}).click();
  await page.getByRole('tab',{name:'3 Náklady a výkon'}).click();
  await page.getByRole('button',{name:'Obnovit (jen čtení)'}).click();
  await expect.poll(()=>reads).toBe(2);
  try{await expect(page.getByRole('region',{name:'Detail session'})).toContainText('second');}finally{release();}
  await expect(page.getByRole('button',{name:'Obnovit (jen čtení)'})).toBeEnabled();
  await expect(page.getByRole('region',{name:'Detail session'})).toContainText('second');
  await expect(page.getByRole('tab',{name:'3 Náklady a výkon'})).toHaveAttribute('aria-selected','true');
});

test('stale polling cannot restore running after a verified stop',async({page})=>{
  await page.clock.install();
  let reads=0,status='running';let release!:()=>void;
  const gate=new Promise<void>(r=>{release=r;});
  await page.route('**/api/llm/runs?*',async route=>{reads++;const observed=status;if(reads===2)await gate;await route.fulfill({json:{runs:[proposal('race-run','',observed)],active:null}});});
  await page.route('**/api/llm/stop',route=>{status='stopped_local';return route.fulfill({json:proposal('race-run','',status)});});
  await page.goto(`/?panel=live&project=${project}&workspace=${workspace}`);
  await expect(page.getByRole('button',{name:'Zastavit tento běh'})).toBeEnabled();
  await page.clock.runFor(4100);await expect.poll(()=>reads).toBe(2);
  await page.getByRole('button',{name:'Zastavit tento běh'}).click();
  await page.getByRole('button',{name:'Potvrdit zastavení',exact:true}).click();
  await expect(page.getByRole('region',{name:'Detail session'})).toContainText('Lokální proces zastaven');
  const response=page.waitForResponse('**/api/llm/runs?*');release();await response;
  await page.clock.runFor(100);
  await expect(page.getByRole('region',{name:'Detail session'})).toContainText('Lokální proces zastaven');
  await expect(page.getByRole('button',{name:'Zastavit tento běh'})).toBeDisabled();
});

test('manual refresh during stop does not strand the confirmation state',async({page})=>{
  let release!:()=>void;const gate=new Promise<void>(r=>{release=r;});let status='running',stopping=false;
  await page.route('**/api/llm/runs?*',route=>route.fulfill({json:{runs:[proposal('refresh-stop','',status)],active:null}}));
  await page.route('**/api/llm/stop',async route=>{stopping=true;await gate;status='stopped_local';await route.fulfill({json:proposal('refresh-stop','',status)});});
  await page.goto(`/?panel=live&project=${project}&workspace=${workspace}`);
  await page.getByRole('button',{name:'Zastavit tento běh'}).click();await page.getByRole('button',{name:'Potvrdit zastavení',exact:true}).click();
  await expect.poll(()=>stopping).toBe(true);
  await page.getByRole('button',{name:'Obnovit (jen čtení)'}).click();
  await expect(page.getByRole('button',{name:'Obnovit (jen čtení)'})).toBeEnabled();
  release();await expect(page.getByRole('group',{name:'Potvrzení zastavení'})).toHaveCount(0);
});

test('stopping uses the real planning endpoint only after confirmation and reads back the same scoped run', async ({page}) => {
  let status='running';let payload:unknown=null;let reads=0;
  await page.route('**/api/llm/runs?*',route=>{reads++;return route.fulfill({json:{runs:[proposal('active-run','',status)],active:null}});});
  await page.route('**/api/llm/stop',route=>{payload=route.request().postDataJSON();status='stopped_local';return route.fulfill({json:proposal('active-run','',status)});});
  await page.goto(`/?panel=live&project=${project}&workspace=${workspace}`);
  await expect(page.getByRole('button',{name:'Zastavit tento běh'})).toBeEnabled();
  await page.getByRole('button',{name:'Zastavit tento běh'}).click();
  expect(payload).toBe(null);const before=reads;
  await page.getByRole('button',{name:'Potvrdit zastavení',exact:true}).click();
  await expect.poll(()=>payload).toEqual({project,runId:'active-run',confirmed:true});
  await expect.poll(()=>reads).toBeGreaterThan(before);
  await expect(page.getByRole('region',{name:'Detail session'})).toContainText('Lokální proces zastaven');
  await expect(page.getByRole('button',{name:'Zastavit tento běh'})).toBeDisabled();
});
