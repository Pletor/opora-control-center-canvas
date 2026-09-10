const { chromium, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
(async () => {
  const out = path.resolve('.opora/workunits/WU-DOCUMENT-TASK');
  const input = JSON.parse(fs.readFileSync(path.join(out, 'live-acceptance-input.json'), 'utf8'));
  const result = JSON.parse(fs.readFileSync(path.join(out, 'live-acceptance-result.json'), 'utf8')).state;
  const writes = [], errors = [];
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1080 } });
  page.setDefaultTimeout(8000);
  page.on('pageerror', error => errors.push(String(error)));
  await page.route('**/api/**', route => {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(route.request().method())) { writes.push(route.request().url()); return route.abort(); }
    return route.continue();
  });
  try {
    await page.goto('http://127.0.0.1:8768/?screen=canvas&environment=editor&project=' + input.prepared.scope.project + '&workspace=draft');
    await page.getByRole('button', { name: 'AI nástroje', exact: true }).click();
    const dock = page.getByRole('region', { name: 'Nástroje práce s AI' });
    await dock.getByRole('button', { name: 'Kontext', exact: true }).click();
    await dock.getByLabel('Uzel paketu', { exact: true }).selectOption(input.prepared.scope.node);
    await dock.getByRole('button', { name: 'Dokumentační úkol', exact: true }).click();
    await expect(dock.getByText('Dokončeno', { exact: true })).toBeVisible();
    await expect(dock.locator('pre').filter({ hasText: input.marker })).toBeVisible();
    const downloadPromise = page.waitForEvent('download');
    await dock.getByRole('button', { name: 'Stáhnout dokument', exact: true }).click();
    const document = await downloadPromise;
    const bytes = fs.readFileSync(await document.path());
    const sha = crypto.createHash('sha256').update(bytes).digest('hex');
    if (sha !== result.result.sha256) throw new Error('Downloaded bytes differ from verified file');
    const exportPromise = page.waitForEvent('download');
    await dock.getByRole('button', { name: 'Exportovat přesné zadání', exact: true }).click();
    const exported = JSON.parse(fs.readFileSync(await (await exportPromise).path(), 'utf8'));
    if (exported.id !== result.id || exported.digest !== result.digest || !JSON.stringify(exported).includes(input.marker)) throw new Error('Export mismatch');
    await page.screenshot({ path: path.join(out, 'live-document-ui.png'), fullPage: true });
    if (writes.length || errors.length) throw new Error(JSON.stringify({ writes, errors }));
    fs.writeFileSync(path.join(out, 'live-ui-verification.json'), JSON.stringify({ runId: result.id, restoredFromServer: true, downloadedSha256: sha, exactContextExport: true, modelStarts: writes.length, pageErrors: errors }, null, 2));
    console.log(JSON.stringify({ runId: result.id, restoredFromServer: true, downloadedSha256: sha, exactContextExport: true, modelStarts: writes.length, pageErrors: errors }));
  } catch (error) {
    await page.screenshot({ path: path.join(out, 'live-ui-diagnostic.png'), fullPage: true });
    console.error(JSON.stringify({ url: page.url(), body: (await page.locator('body').innerText()).slice(-5500), writes, errors }));
    throw error;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
