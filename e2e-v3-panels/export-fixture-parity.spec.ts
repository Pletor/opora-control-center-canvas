import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

// Fixture/backend export parity: exercises fixture-plugin.ts GET /api/task-handoffs/{id}/export
// completely UNMOCKED (no page.route fulfillment for /export) through the real UI vertical —
// preview -> snapshot -> readback -> prepare -> export download — so the fixture itself, not a
// stand-in route handler, is what's under test. Confirms the fixture's export shape matches
// backend/task_handoffs.py TaskHandoffService.export() (id, digest, scope, task, allowedFiles,
// readableNodeIds, context, provider, model, budgetSeconds) instead of the old
// { id, digest, task, context: { fixture: true } }, and that the hardened client's
// assertHandoffExport (src/desktop-v3/api.ts) accepts it — proving nothing here reached a real
// model: provider/model come back as the obviously-synthetic "fixture"/"fixture-model" and zero
// /start requests are ever made.

function url(params: Record<string, string>) {
  const q = new URLSearchParams(params).toString();
  return `/?panel=packet&${q}`;
}

test("prepared run export matches the real backend shape and the saved snapshot, with zero /start requests", async ({
  page,
}) => {
  const project = "proj-efp-vertical";
  const workspace = "draft-efp";
  const nodeId = "n1";

  const startRequests: string[] = [];
  page.on("request", (req) => {
    if (/\/api\/task-handoffs\/[^/]+\/start$/.test(new URL(req.url()).pathname)) startRequests.push(req.url());
  });

  await page.goto(url({ project, workspace, nodeId, path: "", references: "[]" }));
  await page.getByRole("button", { name: "Sestavit náhled balíčku" }).click();
  await expect(page.getByText("Zdrojový manifest")).toBeVisible();

  await page.getByRole("button", { name: "Vytvořit neměnný snímek" }).click();
  await expect(page.getByText(/Snímek:/)).toBeVisible();
  const snapshotId = await page
    .locator('section[aria-label="Neměnný snímek"]')
    .locator("code")
    .first()
    .innerText();

  // Readback verification (fetchSnapshot / assertSnapshotReadback) against the real, unmocked
  // fixture endpoint before preparing a run over it.
  await page.getByRole("button", { name: "Ověřit uložený snímek" }).click();
  await expect(page.getByText(/Snímek načten neměnný/)).toBeVisible();

  await page.getByLabel("Zadání dokumentačního běhu").fill("Připravit shrnutí kontextu pro uzel n1.");
  const prepared = page.waitForResponse(
    (r) => /\/prepare$/.test(new URL(r.url()).pathname) && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Připravit dokumentační běh" }).click();
  const preparedRun = (await (await prepared).json()) as {
    id: string;
    digest: string;
    scope: { project: string; workspace: string; node: string };
  };
  await expect(page.getByText("Připraveno — model neběží")).toBeVisible();

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportovat přesné zadání" }).click();
  const exported = JSON.parse(readFileSync((await (await download).path())!, "utf8"));

  // Fail-closed client assertion (assertHandoffExport) must have accepted this payload — no
  // error surfaced instead of the download.
  await expect(page.locator("p.v3-error")).toHaveCount(0);

  expect(exported.id).toBe(preparedRun.id);
  expect(exported.digest).toBe(preparedRun.digest);
  expect(exported.scope).toEqual({ project, workspace, node: nodeId });
  expect(exported.task).toBe("Připravit shrnutí kontextu pro uzel n1.");
  expect(exported.allowedFiles).toEqual(["result.md"]);
  expect(exported.readableNodeIds).toEqual([nodeId]);
  // Obviously synthetic — this must never be mistaken for a real provider/model that ran.
  expect(exported.provider).toBe("fixture");
  expect(exported.model).toBe("fixture-model");
  expect(typeof exported.budgetSeconds).toBe("number");
  expect(exported.context).toBeTruthy();
  expect(exported.context.snapshotId).toBe(snapshotId);
  expect(exported.context.digest).toBe(preparedRun.digest);

  expect(startRequests).toEqual([]);
});

test("export context stays the original prepared snapshot after a later preview mutates the same scope", async ({
  page,
}) => {
  const project = "proj-efp-immutable";
  const workspace = "draft-efp";
  const nodeId = "n1";

  await page.goto(url({ project, workspace, nodeId, path: "", references: "[]", note: "original note" }));
  await page.getByRole("button", { name: "Sestavit náhled balíčku" }).click();
  await expect(page.getByText("Zdrojový manifest")).toBeVisible();
  await page.getByRole("button", { name: "Vytvořit neměnný snímek" }).click();
  await expect(page.getByText(/Snímek:/)).toBeVisible();
  await page.getByLabel("Zadání dokumentačního běhu").fill("Připravit shrnutí kontextu pro uzel n1, verze jedna.");
  const prepared = page.waitForResponse(
    (r) => /\/prepare$/.test(new URL(r.url()).pathname) && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Připravit dokumentační běh" }).click();
  const preparedRun = (await (await prepared).json()) as { id: string };
  await expect(page.getByText("Připraveno — model neběží")).toBeVisible();

  // Simulate a later mutation in the SAME scope directly against the real fixture (bypasses the
  // React component entirely, so it can never be blocked by generation/ticket guards) — this must
  // not leak into the context of the run that was already prepared above.
  await page.evaluate(
    async ({ project, workspace, nodeId }) => {
      await fetch("/api/desktop-v3/packet/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, workspace, nodeId, path: "", sessionId: "", references: [], note: "mutated note" }),
      });
    },
    { project, workspace, nodeId },
  );

  const first = await page.evaluate(
    (id) => fetch(`/api/task-handoffs/${id}/export`).then((r) => r.json()),
    preparedRun.id,
  );
  const second = await page.evaluate(
    (id) => fetch(`/api/task-handoffs/${id}/export`).then((r) => r.json()),
    preparedRun.id,
  );

  expect(second).toEqual(first);
  expect(JSON.stringify(first.context)).not.toContain("mutated note");
  expect(JSON.stringify(first.context)).toContain("original note");
});
