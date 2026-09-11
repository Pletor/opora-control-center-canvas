import { test, expect, type Page, type Route } from "@playwright/test";
import { readFileSync } from "node:fs";

// Export / readback scope hardening: a handoff export or snapshot readback that belongs to a
// different project/workspace/node/run (or lacks a well-formed scope) must never be displayed
// or downloaded. A valid payload must be passed through byte-for-byte unchanged.

type Json = Record<string, unknown>;
const isExport = (u: URL) => /^\/api\/task-handoffs\/[^/]+\/export$/.test(u.pathname);

function exportPayload(run: { id: string; digest: string; project: string; workspace: string; node: string }, marker: string): Json {
  // Exact shape returned by backend/task_handoffs.py TaskHandoffService.export().
  return {
    id: run.id,
    digest: run.digest,
    scope: { project: run.project, workspace: run.workspace, node: run.node },
    task: "Připravit shrnutí kontextu pro uzel.",
    allowedFiles: ["result.md"],
    readableNodeIds: [run.node],
    context: { marker, ancestors: [] },
    provider: "fixture",
    model: "fixture-model",
    budgetSeconds: 60,
  };
}

// Každá varianta vychází z platného payloadu a porušuje přesně jednu vlastnost.
const INVALID: [string, (valid: Json) => Json][] = [
  ["wrong project", (v) => ({ ...v, scope: { ...(v.scope as Json), project: "proj-foreign" } })],
  ["wrong workspace", (v) => ({ ...v, scope: { ...(v.scope as Json), workspace: "draft-foreign" } })],
  ["wrong node", (v) => ({ ...v, scope: { ...(v.scope as Json), node: "n-foreign" } })],
  ["wrong id", (v) => ({ ...v, id: "run-foreign" })],
  ["wrong digest", (v) => ({ ...v, digest: "digest-foreign" })],
  ["missing scope", (v) => { const { scope: _scope, ...rest } = v; return rest; }],
  ["null scope", (v) => ({ ...v, scope: null })],
  ["malformed scope project", (v) => ({ ...v, scope: { ...(v.scope as Json), project: 42 } })],
  ["missing context", (v) => { const { context: _context, ...rest } = v; return rest; }],
  ["non-object body", () => ["not", "an", "export"] as unknown as Json],
];

// ---------------------------------------------------------------- LiveWorkspacePanel

const LIVE = { project: "proj-es-live", workspace: "draft-es" };
const runA = { id: "run-a", digest: "digest-a", ...LIVE, node: "n1" };
const runB = { id: "run-b", digest: "digest-b", ...LIVE, node: "n2" };
const handoffRow = (r: typeof runA, at: string) => ({
  id: r.id, digest: r.digest, scope: { project: r.project, workspace: r.workspace, node: r.node },
  task: `Úkol ${r.id}`, status: "completed", provider: "fixture", model: "fixture-model",
  events: [], error: null, verification: { passed: true }, result: null, createdAt: at, updatedAt: at,
});

async function mountLive(page: Page, exportHandler: (route: Route) => Promise<void> | void) {
  await page.route((u) => u.pathname === "/api/llm/runs", (route) => route.fulfill({ json: { runs: [], active: null } }));
  await page.route((u) => u.pathname === "/api/task-handoffs", (route) =>
    route.fulfill({ json: { runs: [handoffRow(runA, "2026-09-11T10:00:02Z"), handoffRow(runB, "2026-09-11T10:00:01Z")] } }),
  );
  await page.route(isExport, exportHandler);
  await page.goto(`/?panel=live&${new URLSearchParams({ ...LIVE, nodeId: "" })}`);
  await page.locator(".live-session-card", { hasText: "run-a" }).click();
  await page.getByRole("tab", { name: "4 Paměť" }).click();
}

test("live: valid export is displayed and downloaded byte-for-byte unchanged", async ({ page }) => {
  const payload = exportPayload(runA, "CTX-VALID-A");
  await mountLive(page, (route) => route.fulfill({ json: payload }));
  await page.getByRole("button", { name: "Načíst přesné předané zadání" }).click();
  const expected = JSON.stringify(payload, null, 2);
  await expect(page.locator("pre.live-output")).toHaveText(expected);
  await expect(page.getByRole("alert")).toHaveCount(0);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Stáhnout přesný kontext" }).click();
  expect(readFileSync((await (await download).path())!, "utf8")).toBe(expected);
});

for (const [name, mutate] of INVALID) {
  test(`live: ${name} export is rejected, not displayed and not downloadable`, async ({ page }) => {
    const payload = mutate(exportPayload(runA, "CTX-FOREIGN"));
    await mountLive(page, (route) => route.fulfill({ json: payload }));
    await page.getByRole("button", { name: "Načíst přesné předané zadání" }).click();
    await expect(page.getByRole("alert")).toContainText(/Export/);
    await expect(page.getByText("CTX-FOREIGN")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Stáhnout přesný kontext" })).toHaveCount(0);
  });
}

test("live: export resolved after switching to another run is dropped silently", async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  await mountLive(page, async (route) => {
    await gate;
    await route.fulfill({ json: exportPayload(runA, "CTX-STALE-A") });
  });
  await page.getByRole("button", { name: "Načíst přesné předané zadání" }).click();
  await page.locator(".live-session-card", { hasText: "run-b" }).click();
  await page.getByRole("tab", { name: "4 Paměť" }).click();
  await expect(page.locator(".live-run-id")).toHaveText("run-b");
  release();
  await page.waitForTimeout(300);
  await expect(page.getByText("CTX-STALE-A")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

// ---------------------------------------------------------------- AgentPacketPanel

async function prepareRun(page: Page, project: string, workspace: string) {
  await page.goto(`/?panel=packet&${new URLSearchParams({ project, workspace, nodeId: "n1", path: "", references: "[]" })}`);
  await page.getByRole("button", { name: "Sestavit náhled balíčku" }).click();
  await expect(page.getByText("Zdrojový manifest")).toBeVisible();
  await page.getByRole("button", { name: "Vytvořit neměnný snímek" }).click();
  await expect(page.getByText(/Snímek:/)).toBeVisible();
  await page.getByLabel("Zadání dokumentačního běhu").fill("Připravit shrnutí kontextu pro uzel n1.");
  const prepared = page.waitForResponse((r) => r.url().includes("/prepare") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Připravit dokumentační běh" }).click();
  const run = (await (await prepared).json()) as { id: string; digest: string };
  await expect(page.getByText("Připraveno — model neběží")).toBeVisible();
  return { id: run.id, digest: run.digest, project, workspace, node: "n1" };
}

test("packet: valid export downloads the exact server payload unchanged", async ({ page }) => {
  const run = await prepareRun(page, "proj-es-pkt-ok", "draft-es");
  const payload = exportPayload(run, "CTX-PKT-VALID");
  await page.route(isExport, (route) => route.fulfill({ json: payload }));
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportovat přesné zadání" }).click();
  expect(readFileSync((await (await download).path())!, "utf8")).toBe(JSON.stringify(payload, null, 2));
  await expect(page.locator("p.v3-error")).toHaveCount(0);
});

for (const [name, mutate] of INVALID) {
  test(`packet: ${name} export is rejected and never downloaded`, async ({ page }) => {
    const run = await prepareRun(page, "proj-es-pkt-bad", "draft-es");
    const payload = mutate(exportPayload(run, "CTX-PKT-FOREIGN"));
    await page.route(isExport, (route) => route.fulfill({ json: payload }));
    let downloaded = false;
    page.on("download", () => (downloaded = true));
    await page.getByRole("button", { name: "Exportovat přesné zadání" }).click();
    await expect(page.locator("p.v3-error")).toContainText(/Export/);
    await page.waitForTimeout(200);
    expect(downloaded).toBe(false);
  });
}

test("packet: export still in flight during page reload never downloads", async ({ page }) => {
  await prepareRun(page, "proj-es-pkt-reload", "draft-es");
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  await page.route(isExport, async (route) => {
    await gate;
    await route.fulfill({ json: { error: "stale" }, status: 404 }).catch(() => undefined);
  });
  let downloaded = false;
  page.on("download", () => (downloaded = true));
  await page.getByRole("button", { name: "Exportovat přesné zadání" }).click();
  await page.reload();
  release();
  await page.waitForTimeout(300);
  expect(downloaded).toBe(false);
  await expect(page.getByText("Připraveno — model neběží")).toHaveCount(0);
});

const SNAPSHOT_INVALID: [string, (valid: Json) => Json][] = [
  ["wrong id", (v) => ({ ...v, id: "snap-foreign" })],
  ["wrong project", (v) => ({ ...v, packet: { ...(v.packet as Json), scope: { ...((v.packet as Json).scope as Json), project: "proj-foreign" } } })],
  ["wrong workspace", (v) => ({ ...v, packet: { ...(v.packet as Json), scope: { ...((v.packet as Json).scope as Json), workspace: "draft-foreign" } } })],
  ["missing packet scope", (v) => { const { scope: _s, ...packet } = v.packet as Json; return { ...v, packet }; }],
];

for (const [name, mutate] of SNAPSHOT_INVALID) {
  test(`packet: snapshot readback with ${name} is not reported as verified`, async ({ page }) => {
    const project = "proj-es-snap";
    await page.goto(`/?panel=packet&${new URLSearchParams({ project, workspace: "draft-es", nodeId: "n1", path: "", references: "[]" })}`);
    await page.getByRole("button", { name: "Sestavit náhled balíčku" }).click();
    await expect(page.getByText("Zdrojový manifest")).toBeVisible();
    await page.getByRole("button", { name: "Vytvořit neměnný snímek" }).click();
    await expect(page.getByText(/Snímek:/)).toBeVisible();
    await page.route((u) => /^\/api\/desktop-v3\/packet\/snapshots\/[^/]+$/.test(u.pathname), async (route) => {
      const real = (await (await route.fetch()).json()) as Json;
      await route.fulfill({ json: mutate(real) });
    });
    await page.getByRole("button", { name: "Ověřit uložený snímek" }).click();
    await expect(page.locator("p.v3-error")).toContainText(/Snímek|snímek/);
    await expect(page.getByText(/Snímek načten neměnný/)).toHaveCount(0);
  });
}

test("packet: valid snapshot readback is still reported as verified", async ({ page }) => {
  await page.goto(`/?panel=packet&${new URLSearchParams({ project: "proj-es-snap-ok", workspace: "draft-es", nodeId: "n1", path: "", references: "[]" })}`);
  await page.getByRole("button", { name: "Sestavit náhled balíčku" }).click();
  await page.getByRole("button", { name: "Vytvořit neměnný snímek" }).click();
  await page.getByRole("button", { name: "Ověřit uložený snímek" }).click();
  await expect(page.getByText(/Snímek načten neměnný/)).toBeVisible();
  await expect(page.locator("p.v3-error")).toHaveCount(0);
});
