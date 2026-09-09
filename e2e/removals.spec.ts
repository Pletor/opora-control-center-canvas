import { test, expect, type Page } from "@playwright/test";
const n = (id: string, parentId: string | null = null, kind = "node", x = 0) => ({ id, parentId, kind, name: id, purpose: "", x, y: 0 });
async function seed(page: Page, graph: object) {
  await page.goto("/?screen=canvas");
  const origin = new URL(page.url()).origin;
  expect(new URL(origin).port).toBe("8741");
  const prior = await (await page.request.get(origin + "/api/view")).json();
  for (const item of prior.graph.nodes.filter((n: { parentId: string | null }) => n.parentId === null)) {
    const scope = { project: "draft", workspace: "draft", kind: "node", target: item.id };
    const preview = await (await page.request.get(origin + "/api/removal-preview?" + new URLSearchParams(scope))).json();
    expect((await page.request.post(origin + "/api/remove", { headers: { origin }, data: { ...scope, digest: preview.digest, confirmed: true } })).ok()).toBe(true);
  }
  const old = await (await page.request.get(origin + "/api/view")).json();
  const result = await page.request.post(origin + "/api/graph", { headers: { origin }, data: { project: "draft", workspace: "draft", graph, digest: old.digest } });
  expect(result.ok()).toBe(true);
  await page.reload();
}

test("node deletion can be cancelled and confirmed deletion survives reload", async ({ page }) => {
  await seed(page, { nodes: [n("remove"), n("keep", null, "node", 360)], edges: [] });
  await page.locator(".react-flow__node").filter({ hasText: "remove" }).click();
  await page.getByRole("button", { name: "Smazat uzel", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByTestId("removal-node-count")).toHaveText("1");
  await dialog.getByRole("button", { name: "Zrušit", exact: true }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(2);
  await page.getByRole("button", { name: "Smazat uzel", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Potvrdit smazání", exact: true }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await page.reload();
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await expect(page.locator(".react-flow__node")).toContainText("keep");
});

test("sector confirmation counts nested children and removes incident edges", async ({ page }) => {
  await seed(page, { nodes: [n("sector", null, "sector"), n("child", "sector"), n("deep", "child"), n("keep", null, "node", 360)], edges: [{ id: "connection", source: "sector", target: "keep" }] });
  await page.locator(".react-flow__node").filter({ hasText: "sector" }).click();
  await page.getByRole("button", { name: "Smazat sektor", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByTestId("removal-node-count")).toHaveText("3");
  await expect(dialog.getByTestId("removal-edge-count")).toHaveText("1");
  await page.screenshot({ path: "evidence/delete-confirmation.png" });
  await dialog.getByRole("button", { name: "Potvrdit smazání", exact: true }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  const graph = (await (await page.request.get("/api/view")).json()).graph;
  expect(graph.nodes.map((item: { id: string }) => item.id)).toEqual(["keep"]);
  expect(graph.edges).toEqual([]);
});

test("selected edge can be removed without deleting its nodes", async ({ page }) => {
  await seed(page, { nodes: [n("left"), { ...n("right", null, "node", 420), y: 120 }], edges: [{ id: "link", source: "left", target: "right" }] });
  await page.locator(".react-flow__edge").click();
  await page.getByRole("button", { name: "Smazat vazbu", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Potvrdit smazání", exact: true }).click();
  await expect(page.locator(".react-flow__edge")).toHaveCount(0);
  await expect(page.locator(".react-flow__node")).toHaveCount(2);
});

test("repository can be removed from application with explicit preservation notice", async ({ page }) => {
  await page.goto("/?project=removal-fixture&workspace=main");
  await page.getByRole("button", { name: "Odebrat repozitář", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("GitHub ani lokální soubory se nesmažou");
  await expect(dialog.getByTestId("removal-workspace-count")).toHaveText("1");
  await dialog.getByRole("button", { name: "Zrušit", exact: true }).click();
  await expect(page.getByLabel("Projekt")).toHaveValue("removal-fixture");
  await page.getByRole("button", { name: "Odebrat repozitář", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Potvrdit odebrání", exact: true }).click();
  await expect(page.getByLabel("Projekt")).toHaveValue("draft");
  await page.reload();
  await expect(page.locator('option[value="removal-fixture"]')).toHaveCount(0);
  await expect(page.locator('option[value="fixture"]')).toHaveCount(1);
});

test("stale removal preview stays open and cannot remove changed graph", async ({ page }) => {
  await seed(page, { nodes: [n("stale"), n("survivor", null, "node", 360)], edges: [] });
  await page.locator(".react-flow__node").filter({ hasText: "stale" }).click();
  await page.getByRole("button", { name: "Smazat uzel", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByTestId("removal-node-count")).toHaveText("1");
  const origin = new URL(page.url()).origin;
  const view = await (await page.request.get("/api/view")).json();
  view.graph.nodes[0].purpose = "Nová revize v jiném okně";
  expect((await page.request.post("/api/graph", { headers: { origin }, data: { project: "draft", workspace: "draft", graph: view.graph, digest: view.digest } })).ok()).toBe(true);
  await dialog.getByRole("button", { name: "Potvrdit smazání", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("Plátno se změnilo");
  await expect(page.locator(".react-flow__node")).toHaveCount(2);
  await dialog.getByRole("button", { name: "Zrušit", exact: true }).click();
  await page.reload();
  await expect(page.locator(".react-flow__node")).toHaveCount(2);
});

test("removal dialog is contained on mobile and Escape cancels", async ({ page }) => {
  await seed(page, { nodes: [n("mobile")], edges: [] });
  await page.locator(".react-flow__node").click();
  await page.getByRole("button", { name: "Smazat uzel", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("button", { name: "Zrušit", exact: true })).toBeFocused();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await dialog.evaluate((el) => { const r = el.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth; })).toBe(true);
  await page.screenshot({ path: "evidence/delete-mobile.png" });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  expect((await (await page.request.get("/api/view")).json()).graph.nodes).toHaveLength(1);
});
