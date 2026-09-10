import { test, expect } from "@playwright/test";

test("agent context map explains selected ancestry and exports only the built packet", async ({ page }) => {
  const paid: string[] = [];
  page.on("request", (request) => {
    if (/\/api\/(llm|coding)\//.test(request.url())) paid.push(request.url());
  });

  await page.goto("/?screen=canvas");
  const mainView = await page.request.get("/api/view?project=fixture&workspace=main");
  const fixture = await mainView.json() as { workspaces: { id: string }[] };
  await page.goto(`/?screen=canvas&project=fixture&workspace=${fixture.workspaces[0].id}&mode=structure`);
  await page.locator(".react-flow__node").filter({ hasText: "Fixture sector" }).click();
  await page.getByRole("tab", { name: "Zadání", exact: true }).click();
  await page.getByLabel("Cíl práce", { exact: true }).fill("Real map goal");
  await page.getByLabel("Co není součástí", { exact: true }).fill("No automatic disk read");
  await page.getByLabel("Podmínky dokončení", { exact: true }).fill("Evidence is explicit");
  await page.getByRole("button", { name: "Uložit zadání", exact: true }).click();

  await page.getByRole("button", { name: "Kontextový paket", exact: true }).click();
  const dock = page.getByRole("region", { name: "Nástroje práce s AI" });
  await expect(dock.getByRole("heading", { name: "Mapa kontextu pro agenta" })).toBeVisible();
  await expect(dock.getByTestId("agent-context-ancestry")).toContainText("Fixture sector");
  await expect(dock.getByText("Zadání → Vybraný kontext → Návrh modelu → Nástroj / akce → Důkaz výsledku")).toBeVisible();
  await expect(dock.getByText("Diagramové spojení není důkaz skutečného runtime volání ani závislosti.")).toBeVisible();

  await dock.getByRole("button", { name: "Sestavit paket", exact: true }).click();
  await expect(dock.getByTestId("context-packet-summary")).toContainText("Real map goal");
  await expect(dock.getByTestId("context-packet-preview")).toContainText("No automatic disk read");

  const download = page.waitForEvent("download");
  await dock.getByRole("button", { name: "Exportovat paket jako Markdown", exact: true }).click();
  const markdown = await (await download).createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of markdown!) chunks.push(chunk as Buffer);
  const text = Buffer.concat(chunks).toString("utf8");
  expect(text).toContain("Real map goal");
  expect(text).toContain("ID paketu:");
  expect(text).not.toContain("sourceReferences");
  expect(paid).toEqual([]);
  await dock.getByRole("heading", { name: "Mapa kontextu pro agenta" }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: ".opora/workunits/WU-AGENT-CONTEXT-MAP/context-map-fixture.png", fullPage: true });
});
