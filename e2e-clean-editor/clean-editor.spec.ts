import { test, expect, type Page } from '@playwright/test';
import { mkdtempSync, mkdirSync, writeFileSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

async function attach(page: Page) {
  const source = mkdtempSync(path.join(tmpdir(), 'opora-clean-'));
  for (const name of ['src', 'backend', 'node_modules', 'generated']) mkdirSync(path.join(source, name));
  writeFileSync(path.join(source, '.gitignore'), 'generated/\n');
  writeFileSync(path.join(source, 'src', 'App.tsx'), 'export default function App() {}');
  await page.goto('/?screen=home');
  const project = await page.evaluate(async (source) => (await fetch('/api/local-project', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:'Skutečný pracovní projekt',path:source,confirmed:true})})).json(), source);
  return { source, project };
}

test('clean project tree defaults to working files and explicitly reveals ignored files', async ({ page }) => {
  const { source, project } = await attach(page);
  await page.goto(`/?screen=canvas&project=${project.id}&workspace=draft&environment=project`);
  const tree = page.getByRole('tree', { name:'Soubory pracovního prostoru' });
  await expect(tree.getByRole('button', {name:'src',exact:true})).toBeVisible();
  await expect(tree.getByRole('button', {name:'node_modules',exact:true})).toHaveCount(0);
  await expect(tree.getByRole('button', {name:'generated',exact:true})).toHaveCount(0);
  await expect(tree.locator('.source-name').first()).toHaveText('src');
  await page.getByLabel('Zobrazit i ignorované a technické soubory').check();
  await expect(tree.getByRole('button', {name:'node_modules',exact:true})).toBeVisible();
  await page.getByLabel('Zobrazit i ignorované a technické soubory').uncheck();
  await expect(tree.getByRole('button', {name:'node_modules',exact:true})).toHaveCount(0);
  await page.reload();
  await expect(tree.getByRole('button', {name:'src',exact:true})).toBeVisible();
  await expect(tree.getByRole('button', {name:'generated',exact:true})).toHaveCount(0);
  expect(readdirSync(source)).toContain('node_modules');
});

test('greenfield sector and child stay design-only and cannot bind an existing file without a source sector', async ({ page }) => {
  const { source, project } = await attach(page);
  const before = readdirSync(source).sort();
  await page.goto(`/?screen=canvas&project=${project.id}&workspace=draft&environment=editor`);
  await page.getByRole('button',{name:'+ Sektor',exact:true}).click();
  await page.getByLabel('Název uzlu').fill('Moje nová funkční oblast');
  await page.getByRole('button',{name:'Jen funkce / myšlenka, bez souboru',exact:true}).click();
  await page.getByLabel('Co má tato část umět?').fill('Místo pro návrhy bez znalosti struktury kódu.');
  await page.getByRole('button',{name:'Vytvořit',exact:true}).click();
  await page.getByRole('button',{name:'Otevřít vnitřní plátno',exact:true}).click();
  await page.getByRole('button',{name:'+ Uzel',exact:true}).click();
  await expect(page.getByRole('button',{name:'Navázat na existující zdroj',exact:true})).toBeDisabled();
  await page.getByLabel('Název uzlu').fill('Přidat oblíbené');
  await page.getByRole('button',{name:'Jen funkce / myšlenka, bez souboru',exact:true}).click();
  await page.getByLabel('Co má tato část umět?').fill('Uživatel označí oblíbenou položku.');
  await page.getByRole('button',{name:'Vytvořit',exact:true}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.reload();
  await expect(page.locator('.canvas-card').getByText('Přidat oblíbené',{exact:true})).toBeVisible();
  const state = await page.evaluate(async id => (await fetch('/api/view?'+new URLSearchParams({project:id,workspace:'draft'}))).json(),project.id);
  const sector = state.graph.nodes.find((n:{kind:string}) => n.kind === 'sector');
  const child = state.graph.nodes.find((n:{kind:string}) => n.kind === 'node');
  expect(sector.sourceRef).toBeUndefined();
  expect(child.sourceRef).toBeUndefined();
  expect(child.parentId).toBe(sector.id);
  expect(readdirSync(source).sort()).toEqual(before);
});

test('greenfield function persists without choosing sector path or creating source files', async ({ page }) => {
  const { source, project } = await attach(page);
  const before = readdirSync(source).sort();
  await page.goto(`/?screen=canvas&project=${project.id}&workspace=draft&environment=editor`);
  await page.getByRole('button',{name:'+ Uzel',exact:true}).click();
  await page.getByLabel('Název uzlu').fill('Uživatel si uloží oblíbené položky');
  await page.getByRole('button',{name:'Jen funkce / myšlenka, bez souboru',exact:true}).click();
  await page.getByLabel('Co má tato část umět?').fill('Chci si označit položku a později ji rychle najít.');
  await expect(page.getByLabel('Zamýšlená cesta')).toHaveCount(0);
  await expect(page.getByLabel('Cílový sektor')).toHaveCount(0);
  await page.getByRole('button',{name:'Vytvořit',exact:true}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.reload();
  await expect(page.locator('.canvas-card').getByText('Uživatel si uloží oblíbené položky',{exact:true})).toBeVisible();
  const state = await page.evaluate(async id => (await fetch('/api/view?'+new URLSearchParams({project:id,workspace:'draft'}))).json(), project.id);
  expect(state.graph.nodes).toHaveLength(1);
  expect(state.graph.nodes[0].sourceRef).toBeUndefined();
  expect(state.graph.nodes[0].purpose).toContain('označit položku');
  expect(readdirSync(source).sort()).toEqual(before);
  await page.getByRole('navigation',{name:'Pracovní prostředí'}).getByRole('button',{name:'Projekt',exact:true}).click();
  await expect(page.getByRole('tree')).toBeVisible();
  await page.getByRole('button',{name:'Editor',exact:true}).click();
  await expect(page.locator('.canvas-card').getByText('Uživatel si uloží oblíbené položky',{exact:true})).toBeVisible();
});
