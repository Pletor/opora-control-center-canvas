import { test, expect, type Page } from '@playwright/test';

// Jen UI kontrakt s výslovnými transport doubles; skutečný Hermes běh je samostatná acceptance.
async function openTask(page: Page) {
  const view = await (await page.request.get('/api/view?project=draft&workspace=draft')).json();
  const seeded = await page.request.post('/api/graph', { headers: { Origin: 'http://127.0.0.1:8769' }, data: { project: 'draft', workspace: 'draft', digest: view.digest, graph: { nodes: [
    { id: 'frontend', kind: 'sector', name: 'Frontend', purpose: 'Rozhraní uživatele', parentId: null, x: 0, y: 0 },
    { id: 'login', kind: 'node', name: 'Přihlášení', purpose: 'Ověření identity', parentId: 'frontend', x: 0, y: 0 },
  ], edges: [] } } });
  expect(seeded.ok(), await seeded.text()).toBeTruthy();
  await page.goto('/?screen=canvas&project=draft&workspace=draft&environment=editor');
  await page.getByRole('button', { name: 'AI nástroje', exact: true }).click();
  const dock = page.getByRole('region', { name: 'Nástroje práce s AI' });
  await dock.getByLabel('Uzel paketu', { exact: true }).selectOption('frontend');
  await dock.getByRole('button', { name: 'Sestavit paket', exact: true }).click();
  await expect(dock.getByTestId('context-packet-preview')).toBeVisible();
  await dock.getByRole('button', { name: 'Dokumentační úkol', exact: true }).click();
  return dock;
}

test('explicit preview then confirm, no automatic model start', async ({ page }) => {
  let starts = 0;
  const row = { id: 'task-ui-proof', digest: 'immutable-digest', scope: { project: 'draft', workspace: 'draft', node: 'frontend' }, task: 'Zdokumentuj vazbu Frontend na Přihlášení.', status: 'prepared', allowedFiles: ['result.md'], readableNodeIds: ['frontend','login'], provider: 'test-double', model: 'not-a-real-model', budgetSeconds: 60, contextSummary: 'Zmrazená mapa a dokumentace', events: [], verification: { passed: null }, result: null, error: null };
  await page.route('**/api/task-handoffs**', async route => {
    const url = new URL(route.request().url());
    let body: unknown = row;
    if (url.pathname.endsWith('/capabilities')) body = { available: true, reason: null, mode: 'isolated_documentation', provider: row.provider, model: row.model, budgetSeconds: 60 };
    else if (url.pathname.endsWith('/prepare')) {
      const input = route.request().postDataJSON();
      expect(input.packetId).toBeTruthy(); expect(input.task).toBe(row.task);
    } else if (url.pathname.endsWith('/start')) {
      expect(route.request().postDataJSON()).toEqual({ digest: row.digest, confirmed: true });
      starts++; body = { ...row, status: 'running', events: [{ kind: 'worker_started' }] };
    } else if (url.pathname.endsWith('/export')) body = { id: row.id, digest: row.digest, task: row.task, context: { title: 'Frontend' } };
    else if (url.pathname === '/api/task-handoffs') body = { runs: [] };
    else body = { ...row, status: starts ? 'running' : 'prepared' };
    await route.fulfill({ json: body });
  });
  const dock = await openTask(page);
  expect(starts).toBe(0);
  await dock.getByLabel('Zadání dokumentačního úkolu', { exact: true }).fill(row.task);
  await dock.getByRole('button', { name: 'Připravit zadání', exact: true }).click();
  await expect(dock.getByText('immutable-digest', { exact: true })).toBeVisible();
  await expect(dock.getByTestId('task-exact-context')).toContainText('Frontend');
  await expect(dock.getByText('Potvrzení spustí providerové volání přes Hermes. Časový limit není cenový strop. Běh se sám nerestartuje.', { exact: true })).toBeVisible();
  await expect(dock.getByRole('button', { name: 'Potvrdit a spustit agenta', exact: true })).toBeDisabled();
  expect(starts).toBe(0);
  await dock.getByLabel('Schvaluji tento kontext, rozsah a spuštění modelu', { exact: true }).check();
  await dock.getByRole('button', { name: 'Potvrdit a spustit agenta', exact: true }).click();
  await expect(dock.getByText('Běží', { exact: true })).toBeVisible();
  expect(starts).toBe(1);
});

test('restores verified document and exports its exact task without starting an agent', async ({ page }) => {
  let starts = 0;
  const row = { id: 'restored-proof', digest: 'digest', scope: { project: 'draft', workspace: 'draft', node: 'frontend' }, task: 'Úkol z předchozí návštěvy', status: 'completed', events: [{ kind: 'context_read' }, { kind: 'file_written' }], verification: { passed: true }, result: { content: '# Testovací dokument\nVýslovný transport double pro UI test.', sha256: 'fixture-hash' } };
  await page.route('**/api/task-handoffs**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/start')) starts++;
    return route.fulfill({ json: path.endsWith('/capabilities') ? { available: true } : path === '/api/task-handoffs' ? { runs: [row] } : path.endsWith('/export') ? { id: row.id, digest: row.digest, task: row.task, context: { immutable: 'approved-context' } } : row });
  });
  const dock = await openTask(page);
  await expect(dock.getByText('Soubor byl nezávisle ověřen.', { exact: true })).toBeVisible();
  await expect(dock.getByTestId('task-result-content')).toHaveText(row.result.content);
  const downloading = page.waitForEvent('download');
  await dock.getByRole('button', { name: 'Stáhnout dokument', exact: true }).click();
  expect((await downloading).suggestedFilename()).toBe('result.md');
  const exporting = page.waitForEvent('download');
  await dock.getByRole('button', { name: 'Exportovat přesné zadání', exact: true }).click();
  expect((await exporting).suggestedFilename()).toBe('opora-task-restored-proof.json');
  expect(starts).toBe(0);
});

test('stop is separately confirmed and not shown stopped before server evidence', async ({ page }) => {
  let stops = 0;
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  const row = { id: 'running-proof', digest: 'digest', scope: { project: 'draft', workspace: 'draft', node: 'frontend' }, task: 'Běžící testovací úkol', status: 'running', events: [], result: null };
  let stopped = false;
  await page.route('**/api/task-handoffs**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/stop')) {
      expect(route.request().postDataJSON()).toEqual({ confirmed: true }); stops++;
      await pending; stopped = true;
    }
    await route.fulfill({ json: path.endsWith('/capabilities') ? { available: true } : path === '/api/task-handoffs' ? { runs: [row] } : { ...row, status: stopped ? 'cancelled' : 'running' } });
  });
  const dock = await openTask(page);
  await expect(dock.getByText('Běží', { exact: true })).toBeVisible();
  await dock.getByRole('button', { name: 'Zastavit tento běh', exact: true }).click();
  expect(stops).toBe(0);
  const request = page.waitForRequest('**/api/task-handoffs/running-proof/stop');
  await dock.getByRole('button', { name: 'Potvrdit zastavení', exact: true }).click();
  await request;
  await expect(dock.getByText('Zastaveno', { exact: true })).toBeHidden();
  release();
  await expect(dock.getByText('Zastaveno', { exact: true })).toBeVisible();
  expect(stops).toBe(1);
});

for (const broken of ['unavailable', 'foreign-digest']) {
  test(`blocks approval when exact context is ${broken}`, async ({ page }) => {
    let starts = 0;
    const row = { id: 'untrusted-preview', digest: 'approved', scope: { project: 'draft', workspace: 'draft', node: 'frontend' }, task: 'Připrav dokument bezpečně', status: 'prepared', allowedFiles: ['result.md'], readableNodeIds: ['frontend'] };
    await page.route('**/api/task-handoffs**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/start')) starts++;
      if (path.endsWith('/export')) return route.fulfill(broken === 'unavailable' ? { status: 503, json: { error: 'Unavailable fixture' } } : { json: { id: row.id, digest: 'wrong', context: { outside: 'not-approved' } } });
      return route.fulfill({ json: path.endsWith('/capabilities') ? { available: true } : path === '/api/task-handoffs' ? { runs: [] } : row });
    });
    const dock = await openTask(page);
    await dock.getByLabel('Zadání dokumentačního úkolu', { exact: true }).fill(row.task);
    await dock.getByRole('button', { name: 'Připravit zadání', exact: true }).click();
    await expect(dock.getByText('Přesný kontext nebyl ověřen; spuštění je zablokované.', { exact: true })).toBeVisible();
    await expect(dock.getByLabel('Schvaluji tento kontext, rozsah a spuštění modelu', { exact: true })).toBeDisabled();
    await expect(dock.getByRole('button', { name: 'Potvrdit a spustit agenta', exact: true })).toBeDisabled();
    if (broken === 'foreign-digest') {
      const downloads: string[] = [];
      page.on('download', download => downloads.push(download.suggestedFilename()));
      await dock.getByRole('button', { name: 'Exportovat přesné zadání', exact: true }).click();
      await expect(dock.getByRole('alert')).toContainText('Export neodpovídá běhu');
      expect(downloads).toEqual([]);
    }
    expect(starts).toBe(0);
  });
}

test('a pending old-node preparation cannot appear after focus changes', async ({ page }) => {
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  const row = { id: 'old-node-only', digest: 'old-context', scope: { project: 'draft', workspace: 'draft', node: 'frontend' }, task: 'Starý kontext', status: 'prepared' };
  await page.route('**/api/task-handoffs**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/prepare')) await pending;
    await route.fulfill({ json: path.endsWith('/capabilities') ? { available: true } : path === '/api/task-handoffs' ? { runs: [] } : row });
  });
  const dock = await openTask(page);
  await dock.getByLabel('Zadání dokumentačního úkolu', { exact: true }).fill('Starý čekající úkol');
  const request = page.waitForRequest('**/api/task-handoffs/prepare');
  await dock.getByRole('button', { name: 'Připravit zadání', exact: true }).click(); await request;
  await dock.getByRole('button', { name: 'Kontext', exact: true }).click();
  await dock.getByLabel('Uzel paketu', { exact: true }).selectOption('login');
  await dock.getByRole('button', { name: 'Dokumentační úkol', exact: true }).click();
  const response = page.waitForResponse('**/api/task-handoffs/prepare'); release(); await (await response).finished();
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(dock.getByText('old-node-only', { exact: true })).toBeHidden();
  await expect(dock.getByLabel('Zadání dokumentačního úkolu', { exact: true })).toHaveValue('');
  await expect(dock.getByRole('button', { name: 'Připravit zadání', exact: true })).toBeDisabled();
});

for (const [state, label] of [['stopping', 'Zastavuje se'], ['verifying', 'Ověřuje se výsledek']]) {
  test(`keeps monitoring transitional ${state} until verified terminal state`, async ({ page }) => {
    let reads = 0;
    const row = { id: 'transition', digest: 'digest', scope: { project: 'draft', workspace: 'draft', node: 'frontend' }, task: 'Přechodový stav', status: state };
    await page.route('**/api/task-handoffs**', route => {
      const path = new URL(route.request().url()).pathname;
      return route.fulfill({ json: path.endsWith('/capabilities') ? { available: true } : path === '/api/task-handoffs' ? { runs: [row] } : { ...row, status: ++reads > 1 ? 'cancelled' : state } });
    });
    const dock = await openTask(page);
    await expect(dock.getByText(label, { exact: true })).toBeVisible();
    await expect(dock.getByText('Zastaveno', { exact: true })).toBeVisible();
  });
}

test('rejects a foreign polling snapshot without displaying its result', async ({ page }) => {
  let reads = 0;
  const row = { id: 'poll-owner', digest: 'digest', scope: { project: 'draft', workspace: 'draft', node: 'frontend' }, task: 'Vlastní běh', status: 'running' };
  await page.route('**/api/task-handoffs**', route => {
    const path = new URL(route.request().url()).pathname;
    const detail = ++reads > 3 ? { ...row, id: 'foreign-run', scope: { ...row.scope, node: 'login' }, status: 'completed', verification: { passed: true }, result: { content: 'FOREIGN_RESULT_MUST_NOT_APPEAR', sha256: 'wrong' } } : row;
    return route.fulfill({ json: path.endsWith('/capabilities') ? { available: true } : path === '/api/task-handoffs' ? { runs: [row] } : detail });
  });
  const dock = await openTask(page);
  await expect(dock.getByRole('alert')).toContainText('Stav běhu se nepodařilo ověřit');
  await expect(dock.getByText('FOREIGN_RESULT_MUST_NOT_APPEAR', { exact: true })).toBeHidden();
  await expect(dock.getByText('poll-owner', { exact: true })).toBeVisible();
});

test('accepted stopping response disables duplicate confirmation while awaiting evidence', async ({ page }) => {
  let stops = 0;
  const row = { id: 'stop-pending', digest: 'digest', scope: { project: 'draft', workspace: 'draft', node: 'frontend' }, task: 'Vlastní běh', status: 'running' };
  await page.route('**/api/task-handoffs**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/stop')) stops++;
    return route.fulfill({ json: path.endsWith('/capabilities') ? { available: true } : path === '/api/task-handoffs' ? { runs: [row] } : { ...row, status: stops ? 'stopping' : 'running' } });
  });
  const dock = await openTask(page);
  await dock.getByRole('button', { name: 'Zastavit tento běh', exact: true }).click();
  await dock.getByRole('button', { name: 'Potvrdit zastavení', exact: true }).click();
  await expect(dock.getByText('Zastavuje se', { exact: true })).toBeVisible();
  await expect(dock.getByRole('button', { name: 'Potvrdit zastavení', exact: true })).toBeHidden();
  await expect(dock.getByRole('button', { name: 'Zastavit tento běh', exact: true })).toBeDisabled();
  expect(stops).toBe(1);
});

test('explains the read-only main restriction', async ({ page }) => {
  await page.route('**/api/task-handoffs**', route => route.fulfill({ json: { available: true, runs: [] } }));
  await page.goto('/?screen=canvas&project=fixture&workspace=main&environment=editor');
  await page.getByRole('button', { name: 'AI nástroje', exact: true }).click();
  const dock = page.getByRole('region', { name: 'Nástroje práce s AI' });
  await dock.getByRole('button', { name: 'Dokumentační úkol', exact: true }).click();
  await expect(dock.getByText('V main se úkol nespouští. Zvolte pracovní větev nebo návrh.', { exact: true })).toBeVisible();
  await expect(dock.getByRole('button', { name: 'Připravit zadání', exact: true })).toBeDisabled();
});
