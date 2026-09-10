import { test, expect, type Page } from "@playwright/test";

/** Otevření vnitřního plátna uzlu přes jeho detail (dvojklik na název karty přejmenovává). */
async function enterNode(page: Page, name: string) {
  await page.locator(".canvas-card").filter({ hasText: name }).click();
  await page.getByRole("button", { name: "Otevřít vnitřní plátno", exact: true }).click();
}

/** Nový uzel vzniká dvojklikem na prázdné plátno a hned se pojmenuje na místě. */
async function createOnCanvas(page: Page, name: string, position: { x: number; y: number }) {
  await page.getByTestId("board-surface").dblclick({ position });
  const rename = page.getByLabel("Jméno uzlu na plátně");
  await expect(rename).toBeFocused();
  await rename.fill(name);
  await rename.press("Enter");
  await expect(page.locator(".canvas-card").filter({ hasText: name })).toBeVisible();
}

test("přirozené plátno: přímá tvorba, bloky, odkazy, deník a scope úkolu", async ({ page, context }) => {
  await page.goto("/?screen=canvas");
  await expect(page.getByTestId("board-hint")).toBeVisible();

  // 1. Přímá tvorba bez dialogu a přejmenování na kartě.
  await createOnCanvas(page, "Alfa", { x: 180, y: 110 });
  await createOnCanvas(page, "Beta", { x: 560, y: 110 });
  const alfa = page.locator(".canvas-card").filter({ hasText: "Alfa" });
  await alfa.getByText("Alfa").dblclick();
  const rename = page.getByLabel("Jméno uzlu na plátně");
  await rename.fill("Alfa sektor");
  await rename.press("Enter");
  await expect(page.locator(".canvas-card").filter({ hasText: "Alfa sektor" })).toBeVisible();

  // 2. Vstup do vrstvy a psaní bloků: Enter, Tab a Shift+Tab.
  await enterNode(page, "Alfa sektor");
  await page.getByRole("button", { name: "Mód: Text", exact: true }).click();
  const outline = page.getByTestId("node-blocks").first();
  const first = outline.getByLabel("Bloky uzlu · blok 1");
  await first.fill("Kořenový blok");
  await first.press("Enter");
  const second = outline.getByLabel("Bloky uzlu · blok 2");
  await expect(second).toBeFocused();
  await second.fill("Dítě");
  await second.press("Tab");
  await expect(outline.getByTestId("block-row").nth(1)).toHaveAttribute("data-depth", "1");
  await expect(second).toBeFocused();
  await second.press("Shift+Tab");
  await expect(outline.getByTestId("block-row").nth(1)).toHaveAttribute("data-depth", "0");
  // Kořen se nevynoří pod nulu a hierarchie zůstane platná.
  await first.focus();
  await first.press("Shift+Tab");
  await expect(outline.getByTestId("block-row").nth(0)).toHaveAttribute("data-depth", "0");

  // 3. Slash paleta s klávesovými nápovědami a Escape.
  await second.press("Enter");
  const third = outline.getByLabel("Bloky uzlu · blok 3");
  await third.fill("");
  await third.pressSequentially("/");
  const menu = page.getByTestId("block-menu");
  await expect(menu).toBeVisible();
  await expect(menu.getByRole("option", { name: /Zanořit blok/ })).toContainText("Tab");
  await third.press("Escape");
  await expect(menu).toHaveCount(0);

  // 4. Odkaz [[ ]] vybírá existující uzel a odkazuje na stejnou identitu.
  await third.fill("");
  await third.pressSequentially("Souvisí s [[Bet");
  await expect(page.getByTestId("block-menu")).toBeVisible();
  await third.press("Enter");
  await expect(third).toHaveValue("Souvisí s [[Beta]]");
  const chip = outline.getByTestId("block-link").filter({ hasText: "Beta" });
  await expect(chip).toBeVisible();

  // 5. Debounced uložení říká pravdu a přežije reload.
  await expect(page.getByTestId("text-status").first()).toContainText("Uloženo · verze", { timeout: 8000 });
  await page.reload();
  await expect(page.getByTestId("node-blocks").first().getByLabel("Bloky uzlu · blok 1")).toHaveValue("Kořenový blok");
  await expect(page.getByTestId("node-blocks").first().getByLabel("Bloky uzlu · blok 3")).toHaveValue("Souvisí s [[Beta]]");

  // 6. Souvislosti ukazují skutečné počty a klik naviguje na týž uzel.
  await expect(page.getByTestId("link-out-count")).toHaveText("1");
  await page.getByTestId("link-out").first().click();
  await expect(page.locator(".canvas-card.selected")).toContainText("Beta");

  // 7. Kontextová akce vydá přesný scope, žádný placený běh nezačne.
  const runs: string[] = [];
  page.on("request", (request) => {
    if (/\/api\/(coding|llm)\/start/.test(request.url())) runs.push(request.url());
  });
  await page.getByTestId("agent-task-action").click();
  const notice = page.getByTestId("agent-task-notice");
  await expect(notice.getByTestId("agent-task-node")).toContainText("Beta");
  await expect(notice.getByTestId("agent-task-layer")).toContainText("kořen projektu");
  expect(runs).toEqual([]);
  await notice.getByRole("button", { name: "Zavřít", exact: true }).click();

  // 8. Deník je datovaný zápis u téhož uzlu.
  await enterNode(page, "Alfa sektor");
  await page.getByRole("button", { name: "Mód: Text", exact: true }).click();
  await page.getByRole("tab", { name: "Deník", exact: true }).click();
  const day = await page.getByLabel("Den zápisu").inputValue();
  const journal = page.getByTestId("journal-blocks").getByLabel("Zápis dne · blok 1");
  await journal.fill("Rozhodnutí dne <script>window.injected=true</script>");
  await expect(page.getByTestId("journal-status")).toContainText("Uloženo · verze 1", { timeout: 8000 });
  await expect(page.getByTestId("journal-day").first()).toContainText(day);
  await page.reload();
  await page.getByRole("tab", { name: "Deník", exact: true }).click();
  await expect(page.getByTestId("journal-blocks").getByLabel("Zápis dne · blok 1")).toHaveValue(
    "Rozhodnutí dne <script>window.injected=true</script>",
  );
  expect(await page.evaluate(() => (window as { injected?: boolean }).injected)).toBeUndefined();

  // 9. Konflikt CAS zachová rozepsaný text a řekne pravdu.
  const second_window = await context.newPage();
  await second_window.goto(page.url());
  const other = second_window.getByTestId("node-blocks").first().getByLabel("Bloky uzlu · blok 1");
  await other.fill("Změna z druhého okna");
  await expect(second_window.getByTestId("text-status").first()).toContainText("Uloženo · verze", { timeout: 8000 });
  const mine = page.getByTestId("node-blocks").first().getByLabel("Bloky uzlu · blok 1");
  await mine.fill("Moje rozepsaná verze");
  await expect(page.getByRole("alert").first()).toContainText("Konflikt", { timeout: 8000 });
  await expect(mine).toHaveValue("Moje rozepsaná verze");
  await expect(page.getByTestId("text-status").first()).toContainText("Neuloženo");
  await second_window.close();
  await page.screenshot({ path: "evidence/natural-canvas.png", fullPage: true });
});
