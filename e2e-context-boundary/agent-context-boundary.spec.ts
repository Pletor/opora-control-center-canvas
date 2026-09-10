import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

// Nezávislé orákulum: stejný obraz pro člověka a agenta, bez odeslání modelu.
test("shared diagram exports real peer names without reintroducing redacted credentials", async ({ page, request }) => {
  const fakeSecret = "ghp_" + "A".repeat(40); // Pouze syntetická hodnota testovacího vzoru.
  const viewResponse = await request.get("/api/view?project=draft&workspace=draft");
  expect(viewResponse.ok()).toBeTruthy();
  const view = await viewResponse.json();
  const graph = {
    nodes: [
      { id: "boundary-sector", parentId: null, kind: "sector", name: "Boundary sector", purpose: "A proposed bounded source area", x: 0, y: 0, sourceRef: { origin: "planned", path: "", kind: "directory" } },
      { id: "boundary-focus", parentId: "boundary-sector", kind: "node", name: "Boundary focus " + fakeSecret, purpose: "A visible bounded proposal", x: 0, y: 0 },
      { id: "boundary-peer", parentId: "boundary-sector", kind: "node", name: "Boundary peer", purpose: "An actual graph peer " + fakeSecret, x: 310, y: 0 },
    ],
    edges: [{ id: "boundary-edge", source: "boundary-peer", target: "boundary-focus" }],
  };
  const saved = await request.post("/api/graph", { headers: { Origin: "http://127.0.0.1:8766" }, data: { project: "draft", workspace: "draft", graph, digest: view.digest } });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  const modelCalls: string[] = [];
  page.on("request", (r) => { if (r.method() === "POST" && /\/api\/(llm|coding|agents\/controls)(\/|$)/.test(r.url())) modelCalls.push(r.url()); });
  await page.goto("/?screen=canvas&project=draft&workspace=draft&environment=editor");
  await page.getByRole("button", { name: "Kontextový paket", exact: true }).click();
  const dock = page.getByRole("region", { name: "Nástroje práce s AI" });
  await dock.getByLabel("Uzel paketu", { exact: true }).selectOption("boundary-focus");
  await expect(dock.getByText("Mapa kontextu pro agenta", { exact: true })).toBeVisible({ timeout: 2500 });
  await dock.getByRole("button", { name: "Sestavit paket", exact: true }).click();
  await expect(dock.getByTestId("context-packet-preview")).toContainText("[REDACTED]");
  await expect(dock.getByTestId("agent-context-ancestry")).toContainText("Boundary sector");
  await expect(dock.getByTestId("agent-context-ancestry")).not.toContainText(fakeSecret);
  const downloadWait = page.waitForEvent("download");
  await dock.getByRole("button", { name: "Exportovat paket a reference", exact: true }).click();
  const downloaded = await downloadWait;
  const data = JSON.parse(await readFile((await downloaded.path())!, "utf8"));
  expect(data.canvasPacket.content.focus.nodeId).toBe("boundary-focus");
  expect(data.designContext).toBeTruthy();
  expect(JSON.stringify(data.designContext)).toContain("boundary-edge");
  expect(JSON.stringify(data.designContext)).toContain("Boundary peer");
  expect(JSON.stringify(data)).not.toContain(fakeSecret);
  expect(modelCalls).toEqual([]);
  let release!: () => void;
  let started = false;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/context/packets", async (route) => {
    const response = await route.fetch(); started = true;
    await gate; await route.fulfill({ response });
  });
  const arrived = page.waitForResponse("**/api/context/packets");
  await dock.getByRole("button", { name: "Sestavit paket", exact: true }).click();
  await expect.poll(() => started).toBe(true);
  await dock.getByLabel("Uzel paketu", { exact: true }).selectOption("boundary-sector");
  try { await expect(dock.getByRole("button", { name: "Sestavit paket", exact: true })).toBeEnabled({ timeout: 2000 }); }
  finally { release(); }
  await arrived;
  await expect(dock.getByTestId("context-packet-preview")).toHaveCount(0);
  await page.unroute("**/api/context/packets");
  await dock.getByText("Další uzly a deníky", { exact: true }).click();
  await dock.locator("label.check").filter({ hasText: "Boundary peer" }).getByRole("checkbox").check();
  await dock.getByLabel("Uzel paketu", { exact: true }).selectOption("boundary-peer");
  const nextRequest = page.waitForRequest((r) => r.method() === "POST" && r.url().endsWith("/api/context/packets"));
  await dock.getByRole("button", { name: "Sestavit paket", exact: true }).click();
  expect((await nextRequest).postDataJSON().includeNodeIds).not.toContain("boundary-peer");
  await expect(dock.getByTestId("context-packet-preview")).toBeVisible();
  await dock.getByLabel("Limit obsahu paketu (UTF-8 bajty)").fill("0");
  await expect(dock.getByRole("button", { name: "Sestavit paket", exact: true })).toBeDisabled({ timeout: 2000 });
});
