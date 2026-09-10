import { test, expect } from "@playwright/test";

// Fixture pro Live Run/Agenti: bez skutečných zdrojů, jen deterministické odpovědi.
async function mockAgentSources(page: import("@playwright/test").Page) {
  await page.route("**/api/agents/sources", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) }),
  );
}

test.describe("Issue 1: environment a mode se čtou z URL nezávisle", () => {
  test("environment=live&mode=structure otevře Live Run, ne editovatelný Board pod ním", async ({ page }) => {
    await mockAgentSources(page);
    await page.route("**/api/agents/runs", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], total: 0, nextCursor: null }) }),
    );
    await page.route("**/api/agents/unbound**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [] }) }),
    );
    await page.goto("/?screen=canvas&project=draft&workspace=draft&environment=live&mode=structure");
    const environments = page.getByRole("navigation", { name: "Pracovní prostředí" });
    await expect(environments.getByRole("button", { name: "Live Run", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("region", { name: "Agenti", exact: true })).toBeVisible();
    await expect(page.getByRole("toolbar", { name: "Nástroje Editoru" })).toHaveCount(0);
    await expect(page.getByTestId("board-surface")).toHaveCount(0);
  });

  test("environment=editor&mode=agents otevře Editor se Strukturou, ne Agenty", async ({ page }) => {
    await page.goto("/?screen=canvas&project=draft&workspace=draft&environment=editor&mode=agents");
    const environments = page.getByRole("navigation", { name: "Pracovní prostředí" });
    await expect(environments.getByRole("button", { name: "Editor", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("toolbar", { name: "Nástroje Editoru" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Mód: Struktura", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("board-surface")).toBeVisible();
    await expect(page.getByRole("region", { name: "Agenti", exact: true })).toHaveCount(0);
  });

  test("obyčejná záložka bez environment parametru zůstává zachovaná", async ({ page }) => {
    await page.goto("/?screen=canvas&project=draft&workspace=draft&mode=text");
    const environments = page.getByRole("navigation", { name: "Pracovní prostředí" });
    await expect(environments.getByRole("button", { name: "Editor", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("button", { name: "Mód: Text", exact: true })).toHaveAttribute("aria-pressed", "true");
  });
});

test.describe("Issue 2: přiřazení běhu k uzlu posílá pravdivý scope", () => {
  test("bere revizi konkrétního uzlu a vrstvu ze skutečného rodiče v grafu", async ({ page }) => {
    await mockAgentSources(page);
    await page.route("**/api/agents/runs", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], total: 0, nextCursor: null }) }),
    );
    await page.route("**/api/agents/unbound**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [{ sourceId: "fixture", runId: "run-2" }] }),
      }),
    );
    // Uzel "child-1" už má jednu vazbu z dřívějška -> revize uzlu je 3, ne 0.
    await page.route("**/api/agents/bindings?**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ revision: 3, items: [] }) }),
    );
    await page.route("**/api/view**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          graph: {
            nodes: [
              { id: "sector-1", parentId: null, kind: "sector", name: "Sektor", purpose: "", x: 0, y: 0 },
              { id: "child-1", parentId: "sector-1", kind: "node", name: "Vnořený uzel", purpose: "", x: 0, y: 0 },
            ],
            edges: [],
          },
          digest: "fixture-digest",
          readOnly: false,
          source: "fixture",
          sha: null,
          branch: null,
          dirty: false,
          graphStatus: "clean",
          workspaces: [],
          observedAt: new Date().toISOString(),
        }),
      }),
    );
    let captured: Record<string, unknown> | null = null;
    await page.route("**/api/agents/bindings", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      captured = route.request().postDataJSON();
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ revision: 4, items: [] }) });
    });
    await page.goto("/?screen=canvas&project=draft&workspace=draft&mode=agents");
    await page.getByRole("button", { name: "Přiřadit k uzlu", exact: true }).click();
    await page.getByLabel("ID uzlu", { exact: true }).fill("child-1");
    await page.getByRole("checkbox", { name: "Potvrzuji přiřazení k tomuto uzlu", exact: true }).check();
    await page.getByRole("button", { name: "Potvrdit vazbu", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Přiřazení běhu k uzlu" })).toHaveCount(0);
    expect(captured).not.toBeNull();
    expect(captured).toMatchObject({
      project: "draft",
      workspace: "draft",
      layer: "sector-1",
      nodeId: "child-1",
      expectedRevision: 3,
      confirmed: true,
    });
  });
});

test.describe("Issue 3: stránkování Live Run přežije zpožděnou starou odpověď", () => {
  test("stará odpověď na cursor=0 dorazí po přepnutí na novější stránku a nepřepíše ji", async ({ page }) => {
    await mockAgentSources(page);
    await page.route("**/api/agents/unbound**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [] }) }),
    );
    const row = (id: string) => ({
      sourceId: "fixture", runId: id, sessionId: null, stateOrigin: "fixture", sourceTimestamp: null,
      lastEventSeq: null, status: { reported: "stopped", liveness: "reported_stopped" }, preview: [], cost: null, missing: [],
    });
    let runsCalls = 0;
    await page.route("**/api/agents/runs**", async (route) => {
      runsCalls += 1;
      const url = new URL(route.request().url());
      const cursor = Number(url.searchParams.get("cursor") ?? 0);
      // Druhé volání je ruční "Obnovit zdroje" na starém cursoru=0: zpozdíme ho tak,
      // aby dorazilo až po přepnutí na cursor=30, což z něj dělá zastaralou odpověď.
      if (runsCalls === 2) await new Promise((resolve) => setTimeout(resolve, 900));
      const body = cursor === 0
        ? { items: Array.from({ length: 30 }, (_, i) => row(`fixture-${i}`)), total: 31, nextCursor: 30 }
        : { items: [row("fixture-30")], total: 31, nextCursor: null };
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto("/?screen=canvas&project=draft&workspace=draft&mode=agents");
    await expect(page.locator(".agent-run-item")).toHaveCount(30);
    await page.getByRole("button", { name: "Obnovit zdroje", exact: true }).click();
    await page.getByRole("button", { name: "Další relace", exact: true }).click();
    await expect(page.locator(".agent-run-item")).toHaveCount(1);
    await expect(page.locator(".agent-run-item").first()).toContainText("fixture-30");
    // Počkat, až zpožděná odpověď z cursoru=0 dorazí, a ověřit, že stránku nepřepsala.
    await page.waitForTimeout(1100);
    await expect(page.locator(".agent-run-item")).toHaveCount(1);
    await expect(page.locator(".agent-run-item").first()).toContainText("fixture-30");
  });
});
