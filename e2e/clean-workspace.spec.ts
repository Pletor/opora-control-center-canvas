import { test, expect, type Page } from "@playwright/test";

/**
 * Čistý pracovní prostor (COMMAND / INSPECT): jedna horní lišta s menu Nastavení,
 * rail módů, obsah-first plocha a jeden kontextový inspektor.
 */

async function createOnCanvas(page: Page, name: string, position: { x: number; y: number }) {
  await page.getByTestId("board-surface").dblclick({ position });
  const rename = page.getByLabel("Jméno uzlu na plátně");
  await expect(rename).toBeFocused();
  await rename.fill(name);
  await rename.press("Enter");
  await expect(page.locator(".canvas-card").filter({ hasText: name })).toBeVisible();
}

const inspector = (page: Page) => page.getByRole("complementary", { name: "Inspektor" });
const menuButton = (page: Page) => page.getByRole("button", { name: "Nastavení", exact: true });
const menu = (page: Page) => page.getByRole("group", { name: "Nastavení a operace" });

test("jedna horní lišta: menu Nastavení drží nastavení i operace projektu, strom vrstev zmizel", async ({ page }) => {
  await page.goto("/?screen=canvas");
  await expect(page.getByRole("banner")).toBeVisible();
  // Rail módů je jediná navigace; trvalý levý strom vrstev už neexistuje.
  await expect(page.getByRole("navigation", { name: "Pracovní módy" })).toBeVisible();
  await expect(page.getByText("STRUKTURA PROJEKTU", { exact: true })).toHaveCount(0);
  // Menu je zavřené, dokud ho uživatel neotevře.
  await expect(menu(page)).toHaveCount(0);
  await expect(menuButton(page)).toHaveAttribute("aria-expanded", "false");
  await menuButton(page).click();
  await expect(menuButton(page)).toHaveAttribute("aria-expanded", "true");
  await expect(menu(page).getByRole("button", { name: "Nastavení plochy", exact: true })).toBeVisible();
  await expect(menu(page).getByRole("button", { name: "Nastavení projektu", exact: true })).toBeVisible();
  await expect(menu(page).getByRole("button", { name: "Obnovit pohled", exact: true })).toBeVisible();
  // Lokální návrh nemá repozitář: git operace se nenabízejí jako falešně funkční.
  await expect(menu(page).getByRole("button", { name: "Synchronizovat main", exact: true })).toHaveCount(0);
  await expect(menu(page).getByRole("button", { name: "Odebrat repozitář", exact: true })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(menu(page)).toHaveCount(0);
  await menuButton(page).click();
  await menu(page).getByRole("button", { name: "Nastavení plochy", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Hotovo", exact: true }).click();
  await expect(menu(page)).toHaveCount(0);
  // Bez výběru ukazuje inspektor skutečný kontext pohledu, ne dekoraci.
  const view = await (await page.request.get("/api/view?project=draft&workspace=draft")).json();
  await expect(inspector(page).getByTestId("scope-context")).toContainText(view.source);
  await expect(page.getByText("Celý systém.", { exact: false })).toHaveCount(0);
});

test("git projekt: přepínač main/worktree a git operace jsou v liště a menu", async ({ page }) => {
  await page.goto("/?screen=canvas");
  await page.getByLabel("Projekt", { exact: true }).selectOption("fixture");
  await expect(page.getByRole("group", { name: "Pracovní větev" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Čistý main", exact: true })).toHaveAttribute("aria-pressed", "true");
  await menuButton(page).click();
  await expect(menu(page).getByRole("button", { name: "Synchronizovat main", exact: true })).toBeVisible();
  await expect(menu(page).getByRole("button", { name: "Odebrat repozitář", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  // Pohled mainu musí být načtený (karta fixture sektoru), teprve pak má přepínač seznam worktree.
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await expect(page.getByRole("button", { name: "+ Sektor", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Pracovní prostor", exact: true }).click();
  await expect(page.getByLabel("Pracovní strom")).toBeVisible();
  await expect(page.getByRole("button", { name: "Pracovní prostor", exact: true })).toHaveAttribute("aria-pressed", "true");
});

test("inspektor uzlu: Obsah je výchozí, Zadání a Práce se odkrývají, smazání zůstává dostupné", async ({ page }) => {
  await page.goto("/?screen=canvas");
  await createOnCanvas(page, "Karta inspektoru", { x: 200, y: 120 });
  const panel = inspector(page);
  await expect(panel.getByRole("tab", { name: "Obsah", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(panel.getByTestId("node-blocks")).toBeVisible();
  await expect(panel.getByRole("button", { name: "Otevřít vnitřní plátno", exact: true })).toBeVisible();
  await expect(panel.getByTestId("agent-task-action")).toBeVisible();
  await expect(page.getByLabel("Cíl práce")).toBeHidden();
  await expect(page.getByLabel("Podstata uzlu")).toBeHidden();
  await panel.getByRole("tab", { name: "Zadání", exact: true }).click();
  await expect(page.getByLabel("Cíl práce")).toBeVisible();
  await expect(page.getByLabel("Podstata uzlu")).toBeVisible();
  await expect(panel.getByTestId("node-blocks")).toBeHidden();
  // Rozepsaný text v jiné kartě přepnutím nezmizí (panely zůstávají připojené).
  await page.getByLabel("Podstata uzlu").fill("Rozepsaná podstata");
  await panel.getByRole("tab", { name: "Práce", exact: true }).click();
  await expect(panel.getByText("Pracovní prostory uzlu", { exact: true })).toBeVisible();
  await panel.getByRole("tab", { name: "Zadání", exact: true }).click();
  await expect(page.getByLabel("Podstata uzlu")).toHaveValue("Rozepsaná podstata");
  await expect(panel.getByRole("button", { name: "Smazat uzel", exact: true })).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: "evidence/design-desktop.png" });
});

test("text mód: obsah je dokument, inspektor nese Souvislosti a Deník vrstvy", async ({ page }) => {
  await page.goto("/?screen=canvas");
  await createOnCanvas(page, "Dokumentová vrstva", { x: 200, y: 120 });
  await page.getByRole("button", { name: "Otevřít vnitřní plátno", exact: true }).click();
  await page.getByRole("button", { name: "Mód: Text", exact: true }).click();
  const main = page.getByRole("main");
  await expect(main.getByTestId("node-blocks").first()).toBeVisible();
  await expect(main.getByRole("tab")).toHaveCount(0);
  const panel = inspector(page);
  await expect(panel.getByRole("tab", { name: "Souvislosti", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(panel.getByTestId("node-links")).toBeVisible();
  await panel.getByRole("tab", { name: "Deník", exact: true }).click();
  await expect(panel.getByTestId("journal-blocks")).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: "evidence/design-text.png" });
});

test("běhy bez backendu /api/agents: pravdivá chyba, nic se nespouští", async ({ page }) => {
  const starts: string[] = [];
  page.on("request", (request) => {
    if (/\/api\/(coding|llm)\/start/.test(request.url()) || (request.url().includes("/api/agents") && request.method() !== "GET"))
      starts.push(request.url());
  });
  const probe = await page.request.get("/api/agents/sources");
  await page.goto("/?screen=canvas&mode=agents");
  await expect(page.getByRole("button", { name: "Mód: Běhy", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("region", { name: "Agenti" })).toBeVisible();
  if (probe.status() === 404) {
    await expect(page.getByRole("alert").first()).toContainText("HTTP 404");
  } else {
    expect(probe.ok()).toBe(true);
  }
  expect(starts).toEqual([]);
});

test("běh → detail zdroje: aktivita uzlu otevře běh v módu Běhy (FIXTURE jen v testu)", async ({ page }) => {
  // FIXTURE: /api/agents v této bázi neexistuje; odpovědi níže jsou testovací atrapa označená jako taková.
  const run = { sourceId: "hermes", runId: "run-fixture-1", stateOrigin: "fixture", sourceTimestamp: null, lastEventSeq: 3,
    status: { reported: "stopped", liveness: "reported_stopped" }, preview: [], cost: null, missing: ["cost"] };
  await page.route("**/api/agents/**", async (route) => {
    const url = new URL(route.request().url());
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (route.request().method() !== "GET") return route.fulfill({ status: 405, contentType: "application/json", body: JSON.stringify({ error: "FIXTURE: zápis není povolen" }) });
    if (url.pathname.endsWith("/sources")) return json({ hermes: { available: true, status: "FIXTURE" } });
    if (url.pathname.endsWith("/runs")) return json({ items: [run], nextCursor: null, total: 1 });
    if (url.pathname.includes("/runs/")) return json({ ...run, brain: { promptSpec: "FIXTURE prompt", contextSnapshot: "FIXTURE kontext", toolAction: null, verifierArtifact: "unavailable", iterations: "1", maxIterations: "3", budget: "unavailable", noProgressSignal: "unavailable", doneReason: "fixture" } });
    if (url.pathname.endsWith("/unbound")) return json({ items: [] });
    if (url.pathname.endsWith("/bindings/sector")) return json({ items: [] });
    if (url.pathname.endsWith("/bindings")) return json({ revision: 1, items: [{ bindingId: "b1", sourceId: "hermes", runId: "run-fixture-1", sessionId: null, layer: "", createdAt: "2026-09-10T00:00:00Z" }] });
    if (url.pathname.endsWith("/activity")) return json([]);
    return route.fallback();
  });
  await page.goto("/?screen=canvas");
  await createOnCanvas(page, "Agentní uzel", { x: 200, y: 120 });
  const panel = inspector(page);
  await panel.getByRole("tab", { name: "Práce", exact: true }).click();
  await expect(panel.getByRole("button", { name: "hermes/run-fixture-1", exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "hermes/run-fixture-1", exact: true }).click();
  await expect(page.getByRole("button", { name: "Mód: Běhy", exact: true })).toHaveAttribute("aria-pressed", "true");
  const agents = page.getByRole("region", { name: "Agenti" });
  await expect(agents.getByRole("heading", { name: "hermes / run-fixture-1" })).toBeVisible();
  await expect(agents.getByText("FIXTURE prompt", { exact: true })).toBeVisible();
  await expect(agents.getByText("Harness neposkytuje: cost", { exact: true })).toBeVisible();
});

test("mobil: lišta, rail, obsah i inspektor bez vodorovného přetečení", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?screen=canvas");
  await createOnCanvas(page, "Mobilní uzel", { x: 120, y: 120 });
  for (const mode of ["Text", "Mapa", "Struktura"]) {
    await page.getByRole("button", { name: "Mód: " + mode, exact: true }).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await menuButton(page).click();
  expect(await menu(page).evaluate((el) => { const r = el.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth; })).toBe(true);
  await page.keyboard.press("Escape");
  await page.locator(".canvas-card").filter({ hasText: "Mobilní uzel" }).click();
  await inspector(page).getByRole("tab", { name: "Obsah", exact: true }).scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "evidence/design-mobile.png", fullPage: true });
});
