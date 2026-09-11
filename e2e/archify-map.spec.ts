import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import {createHash} from 'node:crypto';

// UI fixture čte skutečný doručený soubor; není důkazem nasazení ani běhu agenta.
const folder='docs/architecture/archify/';
const html=fs.readFileSync(folder+'opora-canvas.architecture.html','utf8');
const specificationJson=fs.readFileSync(folder+'opora-canvas.architecture.json','utf8');
const receipt=JSON.parse(fs.readFileSync(folder+'deliver-receipt.json','utf8'));
const artifact={project:'draft',html,specificationJson,artifact:receipt.artifact,specification:receipt.specification,
  sourcePath:folder+'opora-canvas.architecture.html',fileName:'opora-canvas.architecture.html',specificationName:'opora-canvas.architecture.json',
  sourceRoot:'Fixture hlavního projektu',sourceRevision:null,freshness:'unknown',validation:receipt.validation,
  browserEvidence:{status:'unavailable',coverage:[]},counts:{components:14,connections:14,boundaries:4},specificationDocument:'Fixture'};

test('hlavní Projekt má jediný layout se stromem a mapou bez starých bloků',async({page})=>{
  await page.route('**/api/archify/artifact?project=draft',route=>route.fulfill({json:artifact}));
  await page.route('**/api/workspace/tree?**',route=>route.fulfill({json:{root:'Fixture',available:true,total:2,hasMore:false,nextOffset:null,observedAt:null,entries:[
    {name:'backend',path:'backend',kind:'directory',blocked:false},{name:'src',path:'src',kind:'directory',blocked:false}]}}));
  await page.goto('/?screen=canvas&project=draft&workspace=draft&environment=project');
  const layout=page.getByRole('region',{name:'Hlavní projekt',exact:true});
  await expect(layout.locator('iframe')).toBeVisible();
  const removed=['Obnovit strom','Rozbalit src, backend, tests','Sbalit vše','Dokumentace','Přidat do kontextu','Cesta','Paměť projektu','Připojení a nastavení projektu','Kontext Editoru','Poznámka ke kontextu'];
  for(const text of removed)await expect(layout.getByText(text,{exact:true})).toHaveCount(0);
  await expect(layout.getByText(/společný pracovní kontext|zatím bez cest|0\/100 referencí/i)).toHaveCount(0);
  await expect(layout.getByRole('tree')).toBeVisible();
  await layout.getByRole('button',{name:'Backend',exact:true}).click();
  await expect(layout.getByRole('button',{name:'backend',exact:true})).toBeVisible();
  await expect(layout.getByRole('button',{name:'src',exact:true})).toHaveCount(0);
  await layout.getByRole('button',{name:'Štítky',exact:true}).click();
  await expect(layout.getByRole('button',{name:'src',exact:true})).toBeVisible();
  const bounds=await layout.boundingBox();const tree=await layout.getByRole('tree').boundingBox();const map=await layout.locator('iframe').boundingBox();
  expect(tree!.x).toBeLessThan(map!.x);expect(map!.width).toBeGreaterThan(bounds!.width*.7);
});

test('Graphify-out načte projekt, vytvoří chybějící graf a zobrazí původní HTML',async({page})=>{
  let generated=0;
  await page.route('**/api/archify/artifact?project=draft',route=>route.fulfill({json:artifact}));
  await page.route('**/api/graphify/artifact?project=draft',route=>route.fulfill({status:404,json:{error:'Chybí graf'}}));
  await page.route('**/api/graphify/generate?project=draft',route=>{generated++;return route.fulfill({json:{project:'draft',html:'<!doctype html><html><head></head><body><p>Original Graphify fixture</p></body></html>',graphJson:'{}',counts:{nodes:2,edges:1},hashes:{},sourceRoot:'Fixture',sourcePath:'graphify-out/graph.html',version:'0.9.24',scope:'code-only',generatedAt:null}})});
  await page.goto('/?screen=canvas&project=draft&workspace=draft&environment=project');
  await page.getByRole('button',{name:'Graphify-out',exact:true}).click();
  const frame=page.frameLocator('iframe[title="Graphify — graf projektu"]');
  await expect(frame.getByText('Original Graphify fixture')).toBeVisible();
  await expect(page.getByText('2 uzlů · 1 vztahů')).toBeVisible();
  expect(generated).toBe(1);
  await page.getByRole('button',{name:'Aktualizovat graf',exact:true}).click();
  await expect.poll(()=>generated).toBe(2);
  await page.getByRole('button',{name:'Archify',exact:true}).click();
  await expect(page.locator('iframe[title="Archify — mapa projektu"]')).toBeVisible();
});

test('Mapa přímo zobrazí hotové HTML, nikoli vlastní renderer nebo graf',async({page})=>{
  const posts:string[]=[];page.on('request',r=>{if(r.method()==='POST')posts.push(r.url())});
  await page.route('**/api/archify/artifact?project=draft',route=>route.fulfill({json:artifact}));
  await page.goto('/?screen=canvas&project=draft&workspace=draft&mode=map&environment=editor');
  const iframe=page.locator('iframe[title="Archify — mapa projektu"]');
  await expect(iframe).toBeVisible();
  await expect(page.getByRole('complementary',{name:'Inspektor',exact:true})).toHaveCount(0);
  await expect(page.locator('.statusline')).toHaveCount(0);
  await expect(iframe).toHaveAttribute('sandbox','allow-scripts allow-downloads');
  await expect(page.getByRole('button',{name:'Vykreslit JSON',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Editovat mapu',exact:true})).toHaveCount(0);
  const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'Stáhnout HTML',exact:true}).click()]);
  expect(createHash('sha256').update(fs.readFileSync((await download.path())!)).digest('hex')).toBe(receipt.artifact.sha256);
  expect(posts).toEqual([]);
  await page.route('**/api/archify/artifact?project=draft',route=>route.fulfill({status:404,json:{error:'Mapa zatím chybí.'}}));
  await page.getByRole('button',{name:'Načíst ze souboru',exact:true}).click();
  await expect(iframe).toHaveCount(0);
  await expect(page.getByRole('alert')).toContainText('Mapa zatím chybí');
});
