import { test, expect, type Page } from '@playwright/test';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

// Izolovaný lokální projekt v dočasné složce; žádná produkční data.
async function attach(page: Page) {
  const source = mkdtempSync(path.join(tmpdir(), 'opora-v3-shell-'));
  mkdirSync(path.join(source, 'src'));
  writeFileSync(path.join(source, 'src', 'App.tsx'), 'export default function App() {}');
  await page.goto('/?screen=home');
  const project = await page.evaluate(async (source) => (await fetch('/api/local-project', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'Shell fixture', path: source, confirmed: true }) })).json(), source);
  return project.id as string;
}
async function openEditor(page: Page, id: string) {
  await page.goto(`/?screen=canvas&project=${id}&workspace=draft&environment=editor`);
  await expect(page.getByRole('toolbar', { name: 'Nástroje Editoru' })).toBeVisible();
}
const luminance = (rgb: string) => { const [r, g, b] = rgb.match(/\d+(\.\d+)?/g)!.map(Number); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const bgOf = (page: Page, selector: string) => page.evaluate((s) => getComputedStyle(document.querySelector(s)!).backgroundColor, selector);

test('light/dark theme persists without first flash and themes shell, canvas and drawing', async ({ page }) => {
  const id = await attach(page);
  await openEditor(page, id);
  await page.getByRole('button', { name: 'Vzhled', exact: true }).click();
  await page.getByRole('button', { name: 'Světlý', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  expect(luminance(await bgOf(page, '.canvas-area'))).toBeGreaterThan(200);
  expect(luminance(await bgOf(page, '.topbar'))).toBeGreaterThan(200);
  expect(luminance(await bgOf(page, '.inspector'))).toBeGreaterThan(200);
  // Stav <html> v okamžiku vložení <body>: bez inline bootstrapu by byl nejdřív výchozí (flash).
  await page.addInitScript(() => {
    const w = window as unknown as { __themeAtBody?: string };
    new MutationObserver(() => { if (document.body && !w.__themeAtBody) w.__themeAtBody = document.documentElement.dataset.theme ?? 'none'; })
      .observe(document, { childList: true, subtree: true });
  });
  await page.reload();
  expect(await page.evaluate(() => (window as unknown as { __themeAtBody?: string }).__themeAtBody)).toBe('light');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.getByRole('button', { name: 'Mód: Kreslení' }).click();
  const drawing = page.locator('.excalidraw').first();
  await expect(drawing).toBeVisible({ timeout: 20000 });
  await expect(drawing).not.toHaveClass(/theme--dark/);
  await page.getByRole('button', { name: 'Vzhled', exact: true }).click();
  await page.getByRole('button', { name: 'Tmavý', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('.excalidraw').first()).toHaveClass(/theme--dark/);
  expect(luminance(await bgOf(page, '.topbar'))).toBeLessThan(80);
});

test('density is an optional persisted tweak', async ({ page }) => {
  const id = await attach(page);
  await openEditor(page, id);
  await expect(page.locator('html')).toHaveAttribute('data-density', 'normal');
  await page.getByRole('button', { name: 'Vzhled', exact: true }).click();
  await page.getByRole('button', { name: 'Kompaktní', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-density', 'compact');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-density', 'compact');
  await page.getByRole('button', { name: 'Vzhled', exact: true }).click();
  await page.getByRole('button', { name: 'Vzdušná', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-density', 'airy');
});

for (const width of [1280, 1440, 1920]) {
  test(`canvas dominates at ${width}px and the inspector is hideable and persistent`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const id = await attach(page);
    await openEditor(page, id);
    const toolbar = page.getByRole('toolbar', { name: 'Nástroje Editoru' });
    await toolbar.getByRole('button', { name: 'Kontext', exact: true }).click();
    await expect(page.getByRole('complementary', { name: 'Kontext Editoru' })).toBeVisible();
    const canvasShare = async () => (await page.locator('.canvas-area').boundingBox())!.width / width;
    expect(await canvasShare()).toBeGreaterThanOrEqual(0.5);
    const inspectorToggle = toolbar.getByRole('button', { name: 'Inspektor', exact: true });
    await expect(inspectorToggle).toHaveAttribute('aria-pressed', 'true');
    await inspectorToggle.click();
    await expect(page.locator('aside.inspector')).toHaveCount(0);
    expect(await canvasShare()).toBeGreaterThanOrEqual(0.75);
    await page.reload();
    await expect(page.locator('aside.inspector')).toHaveCount(0);
    await toolbar.getByRole('button', { name: 'Inspektor', exact: true }).click();
    await expect(page.locator('aside.inspector')).toBeVisible();
    // Každé hlavní tlačítko musí být na šířce viditelné (nic nezmizí za okraj).
    for (const name of ['Podklady pro agenta', 'AI nástroje', '+ Uzel', '+ Sektor', 'Dokumentace']) {
      const box = (await toolbar.getByRole('button', { name, exact: true }).boundingBox())!;
      expect(box.x + box.width).toBeLessThanOrEqual(width);
    }
  });
}

test('one primary agent-materials entry; advanced Plan/Coding/Task stay reachable', async ({ page }) => {
  const id = await attach(page);
  await openEditor(page, id);
  const toolbar = page.getByRole('toolbar', { name: 'Nástroje Editoru' });
  await expect(toolbar.getByRole('button', { name: 'Podklady pro agenta', exact: true })).toHaveCount(1);
  await expect(toolbar.getByRole('button', { name: 'Podklady pro agenta', exact: true })).toHaveClass(/primary/);
  await expect(toolbar.getByRole('button', { name: 'Kontextový paket', exact: true })).toHaveCount(0);
  await toolbar.getByRole('button', { name: 'Podklady pro agenta', exact: true }).click();
  const bench = page.getByRole('region', { name: 'Nástroje práce s AI' });
  await expect(bench.getByRole('heading', { name: 'Podklady pro agenta' })).toBeVisible();
  // Bez napojeného v3 panelu zůstává skutečný existující builder, nikoli prázdný stub.
  await expect(bench.getByRole('button', { name: 'Sestavit paket', exact: true })).toBeVisible();
  const advanced = bench.getByRole('navigation', { name: 'Pokročilé nástroje' });
  for (const name of ['LLM návrh', 'Coding', 'Dokumentační úkol']) await expect(advanced.getByRole('button', { name, exact: true })).toBeVisible();
  await advanced.getByRole('button', { name: 'LLM návrh', exact: true }).click();
  await expect(advanced.getByRole('button', { name: 'LLM návrh', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await bench.getByRole('button', { name: 'Skrýt nástroje', exact: true }).click();
  await expect(bench).toBeHidden();
  await toolbar.getByRole('button', { name: 'AI nástroje', exact: true }).click();
  await expect(bench).toBeVisible();
});

test('three workspaces keep their own selection and mode', async ({ page }) => {
  const id = await attach(page);
  await page.goto(`/?screen=canvas&project=${id}&workspace=draft&environment=project`);
  const tree = page.getByRole('tree', { name: 'Soubory pracovního prostoru' });
  await tree.getByRole('button', { name: 'src', exact: true }).click();
  await expect(page.locator('.source-row.selected')).toContainText('src');
  const envs = page.getByRole('navigation', { name: 'Pracovní prostředí' });
  await envs.getByRole('button', { name: /^Editor/ }).click();
  await page.getByRole('button', { name: 'Mód: Text' }).click();
  await envs.getByRole('button', { name: /^Live Run/ }).click();
  await expect(page.getByRole('button', { name: 'Mód: Text' })).toHaveCount(0);
  await envs.getByRole('button', { name: /^Editor/ }).click();
  await expect(page.getByRole('button', { name: 'Mód: Text' })).toHaveAttribute('aria-pressed', 'true');
  await envs.getByRole('button', { name: /^Projekt/ }).click();
  await expect(page.locator('.source-row.selected')).toContainText('src');
  await expect(envs.getByRole('button', { name: /^Projekt/ })).toHaveAttribute('aria-pressed', 'true');
});
