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
